"""PostgreSQLOutboxRepository — 基础设施层实现。

实现领域层 OutboxRepository 接口，使用 SQLAlchemy 持久化。
提供公开方法（实现接口）和内部方法（供 AsyncOutboxPoller 使用）。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events.base import DomainEvent
from src.domain.ports.outbox import OutboxRepository
from src.infrastructure.messaging.adapters.sqlalchemy_event_outbox_adapter import (
    SQLAlchemyEventOutboxAdapter,
)
from src.infrastructure.storage.postgresql.models import OutboxModel


class PostgreSQLOutboxRepository(OutboxRepository):
    """PostgreSQL 发件箱仓储实现。

    公开方法实现领域层接口（使用 DomainEvent）。
    内部方法（_ 前缀）直接操作 OutboxModel，仅 Poller 使用。
    """

    def __init__(self, session: AsyncSession):
        """初始化 PostgreSQLOutboxRepository。

        Args:
            session: 异步数据库会话
        """
        self._session = session
        self._lock = asyncio.Lock()

    # ========== 公开方法（实现领域层接口） ==========

    def save(self, event: DomainEvent) -> None:
        """保存事件至发件箱（与业务操作同事务）。

        Args:
            event: 领域事件实例
        """
        model = SQLAlchemyEventOutboxAdapter.from_domain_event(event)
        self._session.add(model)

    def get_unpublished(self, limit: int) -> list[DomainEvent]:
        """获取未发布的事件列表。

        Args:
            limit: 最大返回数量

        Returns:
            未发布的领域事件列表（FIFO 排序）
        """
        raise NotImplementedError("Use async_get_unpublished instead")

    async def async_get_unpublished(self, limit: int) -> list[DomainEvent]:
        """异步获取未发布的事件列表。

        Args:
            limit: 最大返回数量

        Returns:
            未发布的领域事件列表（FIFO 排序）
        """
        result = await self._session.execute(
            select(OutboxModel).where(OutboxModel.status == "pending").order_by(OutboxModel.created_at.asc()).limit(limit)
        )
        models = list(result.scalars().all())
        return [SQLAlchemyEventOutboxAdapter.to_domain_event(m) for m in models]

    def mark_published(self, event_id: UUID) -> None:
        """标记事件已发布。

        Args:
            event_id: 事件唯一标识
        """
        raise NotImplementedError("Use async_mark_published instead")

    async def async_mark_published(self, event_id: UUID) -> None:
        """异步标记事件已发布。

        Args:
            event_id: 事件唯一标识
        """
        result = await self._session.execute(select(OutboxModel).where(OutboxModel.event_id == event_id))
        model = result.scalar_one_or_none()
        if model:
            model.status = "published"
            model.published_at = datetime.now(UTC)

    def mark_failed(self, event_id: UUID, error: str) -> None:
        """标记事件发布失败。

        Args:
            event_id: 事件唯一标识
            error: 错误信息
        """
        raise NotImplementedError("Use async_mark_failed instead")

    async def async_mark_failed(self, event_id: UUID, error: str) -> None:
        """异步标记事件发布失败。

        Args:
            event_id: 事件唯一标识
            error: 错误信息
        """
        result = await self._session.execute(select(OutboxModel).where(OutboxModel.event_id == event_id))
        model = result.scalar_one_or_none()
        if model:
            model.status = "failed"
            model.retry_count += 1
            model.error_message = error

    # ========== 内部方法（仅 Poller 使用） ==========

    async def _get_unpublished_entities(self, limit: int) -> list[OutboxModel]:
        """内部方法: 获取未发布的 OutboxModel 列表（FIFO 排序）。"""
        async with self._lock:
            result = await self._session.execute(
                select(OutboxModel).where(OutboxModel.status == "pending").order_by(OutboxModel.created_at.asc()).limit(limit)
            )
            return list(result.scalars().all())

    async def _mark_published_entity(self, model: OutboxModel) -> None:
        """内部方法: 标记 OutboxModel 为 published。"""
        async with self._lock:
            model.status = "published"
            model.published_at = datetime.now(UTC)

    async def _mark_failed_entity(self, model: OutboxModel, error: str) -> None:
        """内部方法: 标记 OutboxModel 为 failed，递增 retry_count。"""
        async with self._lock:
            model.status = "failed"
            model.retry_count += 1
            model.error_message = error
