"""基础设施层 PostgreSQL 发件箱仓储模块

实现领域层 OutboxRepository 接口，使用 SQLAlchemy 持久化发件箱实体
提供公开方法（实现接口）和内部方法（供 AsyncOutboxPoller 使用）

Session 通过 ContextVar 由 middleware 或 test fixture 提供，
无需构造器注入 session 参数

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events.base import DomainEvent
from src.domain.exceptions import InvalidStateTransitionError
from src.domain.ports.outbox import OutboxRepository
from src.infrastructure.messaging.adapters.sqlalchemy_event_outbox_adapter import (
    SQLAlchemyEventOutboxAdapter,
)
from src.infrastructure.storage.postgresql.models import OutboxModel
from src.infrastructure.storage.postgresql.session_context import get_session


class PostgreSQLOutboxRepository(OutboxRepository):
    """PostgreSQL 发件箱仓储实现

    所有公开方法为 async（实现 OutboxRepository Protocol）
    内部方法（_ 前缀）直接操作 OutboxModel，仅 Poller 使用
    """

    def __init__(self) -> None:
        """初始化实例级别 Lock（避免类级别共享导致测试间污染）"""
        self._lock = asyncio.Lock()

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    # ========== 公开方法（实现领域层接口，async） ==========

    async def save(self, event: DomainEvent) -> None:
        """保存事件至发件箱（与业务操作同事务）"""
        model = SQLAlchemyEventOutboxAdapter.from_domain_event(event)
        self._session.add(model)
        await self._session.flush()

    async def get_unpublished(self, limit: int) -> list[DomainEvent]:
        """获取未发布的事件列表（FIFO 排序）"""
        result = await self._session.execute(
            select(OutboxModel).where(OutboxModel.status == "pending").order_by(OutboxModel.created_at.asc()).limit(limit)
        )
        models = list(result.scalars().all())
        return [SQLAlchemyEventOutboxAdapter.to_domain_event(m) for m in models]

    async def mark_published(self, event_id: UUID) -> None:
        """标记事件已发布

        Raises:
            InvalidStateTransitionError: 当当前状态不是 pending 时
        """
        result = await self._session.execute(select(OutboxModel).where(OutboxModel.event_id == event_id))
        model = result.scalar_one_or_none()
        if model:
            if model.status != "pending":
                raise InvalidStateTransitionError(model.status, "published")
            model.status = "published"
            model.published_at = datetime.now(UTC)

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        """标记事件发布失败

        Raises:
            InvalidStateTransitionError: 当当前状态不是 pending 或 failed 时
        """
        result = await self._session.execute(select(OutboxModel).where(OutboxModel.event_id == event_id))
        model = result.scalar_one_or_none()
        if model:
            if model.status not in ("pending", "failed"):
                raise InvalidStateTransitionError(model.status, "failed")
            model.status = "failed"
            model.retry_count += 1
            model.error_message = error

    # ========== 内部方法（仅 Poller 使用） ==========

    async def _get_unpublished_entities(self, limit: int) -> list[OutboxModel]:
        """内部方法: 获取未发布的 OutboxModel 列表（FIFO 排序）

        Args:
            limit: 最大返回数量

        Returns:
            未发布的 OutboxModel 列表
        """
        async with self._lock:
            result = await self._session.execute(
                select(OutboxModel).where(OutboxModel.status == "pending").order_by(OutboxModel.created_at.asc()).limit(limit)
            )
            return list(result.scalars().all())

    async def _mark_published_entity(self, model: OutboxModel) -> None:
        """内部方法: 标记 OutboxModel 为 published

        Args:
            model: 要标记的 OutboxModel 实例

        Raises:
            InvalidStateTransitionError: 当当前状态不是 pending 时
        """
        async with self._lock:
            if model.status != "pending":
                raise InvalidStateTransitionError(model.status, "published")
            model.status = "published"
            model.published_at = datetime.now(UTC)

    async def _mark_failed_entity(self, model: OutboxModel, error: str) -> None:
        """内部方法: 标记 OutboxModel 为 failed，递增 retry_count

        Args:
            model: 要标记的 OutboxModel 实例
            error: 错误信息

        Raises:
            InvalidStateTransitionError: 当当前状态不是 pending 或 failed 时
        """
        async with self._lock:
            if model.status not in ("pending", "failed"):
                raise InvalidStateTransitionError(model.status, "failed")
            model.status = "failed"
            model.retry_count += 1
            model.error_message = error
