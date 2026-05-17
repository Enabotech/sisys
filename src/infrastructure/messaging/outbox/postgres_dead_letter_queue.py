"""SISYS 基础设施层 PostgreSQL 死信队列模块。

基于 PostgreSQL 实现持久化死信队列，支持事件持久化存储、FIFO 出队、
状态管理（pending/processed）和人工干预。

Session 通过 ContextVar 由 middleware 或 test fixture 提供，
无需构造器注入 session 参数

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.domain.events.base import DomainEvent
from src.infrastructure.storage.postgresql.session_context import get_session

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """PostgreSQL 模型基类。"""

    pass


class DeadLetterQueueModel(Base):
    """死信队列表的 SQLAlchemy 模型。

    Attributes:
        id: 主键（UUID）。
        event_id: 事件唯一标识。
        event_type: 事件类型名称。
        payload: 事件负载（JSONB）。
        error_message: 错误信息。
        retry_count: 重试次数。
        context: 额外上下文信息（JSONB）。
        created_at: 创建时间。
        status: 条目状态（pending/processed）。
        processed_at: 处理时间。
        action_taken: 人工处理动作描述。
    """

    __tablename__ = "dead_letter_queue"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String(200), nullable=True)


class DeadLetterQueueEntry:
    """死信队列条目数据类（由 dequeue 返回）。

    Attributes:
        id: 主键（UUID）。
        event_id: 事件唯一标识。
        event_type: 事件类型名称。
        payload: 事件负载。
        error_message: 错误信息。
        retry_count: 重试次数。
        context: 额外上下文信息。
        created_at: 创建时间。
        status: 条目状态。
        processed_at: 处理时间。
        action_taken: 人工处理动作描述。
    """

    def __init__(
        self,
        event_id: UUID,
        event_type: str,
        payload: dict,
        error_message: str | None = None,
        retry_count: int = 0,
        context: dict | None = None,
        created_at: datetime | None = None,
        status: str = "pending",
        processed_at: datetime | None = None,
        action_taken: str | None = None,
        id: UUID | None = None,
    ):
        from uuid import uuid4

        self.id = id or uuid4()
        self.event_id = event_id
        self.event_type = event_type
        self.payload = payload
        self.error_message = error_message
        self.retry_count = retry_count
        self.context = context
        self.created_at = created_at or datetime.now(UTC)
        self.status = status
        self.processed_at = processed_at
        self.action_taken = action_taken

    def to_domain_event(self) -> DomainEvent:
        """从负载重建领域事件。

        Returns:
            重建的 DomainEvent 实例。
        """
        return DomainEvent.from_dict(self.payload)

    def __repr__(self) -> str:
        return (
            f"DeadLetterQueueEntry(id={self.id}, event_id={self.event_id}, event_type={self.event_type}, status={self.status})"
        )


class PostgresDeadLetterQueue:
    """PostgreSQL 持久化死信队列

    使用 PostgreSQL 存储死信事件，支持：
    - 入队（持久化）
    - 出队（FIFO，支持状态更新）
    - 状态查询
    - 人工干预
    """

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    async def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0, context: dict | None = None) -> None:
        """入队失败事件至 PostgreSQL

        Args:
            event: 领域事件
            error: 错误信息
            retry_count: 重试次数
            context: 额外上下文信息
        """
        from uuid import uuid4

        model = DeadLetterQueueModel(
            id=uuid4(),
            event_id=event.event_id,
            event_type=event.event_type,
            payload=event.to_dict(),
            error_message=error,
            retry_count=retry_count,
            context=context,
            created_at=datetime.now(UTC),
            status="pending",
        )
        self._session.add(model)
        logger.warning(
            "Event %s enqueued to PostgresDLQ: %s (retry_count=%d)",
            event.event_id,
            error,
            retry_count,
        )

    async def dequeue(self) -> tuple[DeadLetterQueueEntry, DomainEvent, str, int] | None:
        """出队最旧的 pending 事件。

        Returns:
            (entry, event, error, retry_count) 元组，队列为空时返回 None。
        """
        result = await self._session.execute(
            select(DeadLetterQueueModel)
            .where(DeadLetterQueueModel.status == "pending")
            .order_by(DeadLetterQueueModel.created_at.asc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None

        # 标记为已处理
        model.status = "processed"
        model.processed_at = datetime.now(UTC)

        # 重建条目和事件
        entry = DeadLetterQueueEntry(
            id=model.id,
            event_id=model.event_id,
            event_type=model.event_type,
            payload=model.payload,
            error_message=model.error_message,
            retry_count=model.retry_count,
            context=model.context,
            created_at=model.created_at,
            status=model.status,
            processed_at=model.processed_at,
        )
        event = entry.to_domain_event()
        return (entry, event, model.error_message or "", model.retry_count)

    async def get_all(self, limit: int = 100) -> list[DeadLetterQueueEntry]:
        """获取所有 DLQ 条目（最近优先）

        Args:
            limit: 最大返回数量

        Returns:
            DLQ 条目列表
        """
        result = await self._session.execute(
            select(DeadLetterQueueModel).order_by(DeadLetterQueueModel.created_at.desc()).limit(limit)
        )
        models = result.scalars().all()
        return [self._model_to_entry(m) for m in models]

    async def get_by_status(self, status: str, limit: int = 100) -> list[DeadLetterQueueEntry]:
        """按状态筛选 DLQ 条目

        Args:
            status: 状态筛选（pending/processed）
            limit: 最大返回数量

        Returns:
            符合条件的 DLQ 条目列表
        """
        result = await self._session.execute(
            select(DeadLetterQueueModel)
            .where(DeadLetterQueueModel.status == status)
            .order_by(DeadLetterQueueModel.created_at.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._model_to_entry(m) for m in models]

    async def mark_action_taken(self, entry_id: UUID, action: str) -> None:
        """标记人工处理动作

        Args:
            entry_id: 条目 ID
            action: 采取的动作
        """
        result = await self._session.execute(select(DeadLetterQueueModel).where(DeadLetterQueueModel.id == entry_id))
        model = result.scalar_one_or_none()
        if model:
            model.action_taken = action
            model.status = "processed"

    async def count_pending(self) -> int:
        """统计 pending 条目数量

        Returns:
            pending 状态条目数量
        """
        result = await self._session.execute(
            select(func.count()).select_from(DeadLetterQueueModel).where(DeadLetterQueueModel.status == "pending")
        )
        return result.scalar() or 0

    def __len__(self) -> int:
        """返回 pending 条目数量（同步接口，供外部调用）。

        Raises:
            NotImplementedError: 始终抛出，应使用 count_pending() 异步方法。
        """
        raise NotImplementedError("Use count_pending() for async count")

    def _model_to_entry(self, model: DeadLetterQueueModel) -> DeadLetterQueueEntry:
        """将 SQLAlchemy 模型转换为 DeadLetterQueueEntry 数据类。

        Args:
            model: SQLAlchemy 模型实例。

        Returns:
            转换后的 DeadLetterQueueEntry 实例。
        """
        return DeadLetterQueueEntry(
            id=model.id,
            event_id=model.event_id,
            event_type=model.event_type,
            payload=model.payload,
            error_message=model.error_message,
            retry_count=model.retry_count,
            context=model.context,
            created_at=model.created_at,
            status=model.status,
            processed_at=model.processed_at,
            action_taken=model.action_taken,
        )
