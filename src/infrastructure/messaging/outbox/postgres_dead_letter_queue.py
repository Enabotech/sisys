"""PostgreSQL Dead Letter Queue — 基础设施层实现。

基于 PostgreSQL 的持久化死信队列，支持：
- 事件持久化存储
- FIFO 出队
- 状态管理（pending/processed）
- 人工干预支持

表结构：dead_letter_queue (id, event_id, event_type, payload JSONB, error_message,
                        retry_count, context JSONB, created_at, status, processed_at, action_taken)
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

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all PostgreSQL models."""

    pass


class DeadLetterQueueModel(Base):
    """SQLAlchemy model for the dead_letter_queue table."""

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
    """Data class representing a DLQ entry (returned by dequeue)."""

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
        """Reconstruct DomainEvent from payload."""
        return DomainEvent.from_dict(self.payload)

    def __repr__(self) -> str:
        return (
            f"DeadLetterQueueEntry(id={self.id}, event_id={self.event_id}, event_type={self.event_type}, status={self.status})"
        )


class PostgresDeadLetterQueue:
    """PostgreSQL 持久化死信队列。

    使用 PostgreSQL 存储死信事件，支持：
    - 入队（持久化）
    - 出队（FIFO，支持状态更新）
    - 状态查询
    - 人工干预
    """

    def __init__(self, session: AsyncSession):
        """初始化 PostgresDeadLetterQueue。

        Args:
            session: 异步数据库会话
        """
        self._session = session

    async def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0, context: dict | None = None) -> None:
        """入队失败事件至 PostgreSQL。

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
            (entry, event, error, retry_count) 或 None（队列为空）
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

        # Mark as processed
        model.status = "processed"
        model.processed_at = datetime.now(UTC)

        # Reconstruct entry and event
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
        """获取所有 DLQ 条目（最近优先）。

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
        """按状态筛选 DLQ 条目。

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
        """标记人工处理动作。

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
        """统计 pending 条目数量。

        Returns:
            pending 状态条目数量
        """
        result = await self._session.execute(
            select(func.count()).select_from(DeadLetterQueueModel).where(DeadLetterQueueModel.status == "pending")
        )
        return result.scalar() or 0

    def __len__(self) -> int:
        """返回 pending 条目数量（同步接口，供外部调用）。

        Note: 这是一个同步代理，实际统计需要异步调用 count_pending()。
        """
        raise NotImplementedError("Use count_pending() for async count")

    def _model_to_entry(self, model: DeadLetterQueueModel) -> DeadLetterQueueEntry:
        """将模型转换为 DeadLetterQueueEntry。"""
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
