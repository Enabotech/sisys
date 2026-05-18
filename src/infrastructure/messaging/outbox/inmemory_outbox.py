"""基础设施层内存发件箱仓储模块

MVP 阶段使用内存列表存储 OutboxEntity，公开方法实现领域层接口（同步、无锁），
内部异步方法使用 asyncio.Lock 保护。生产环境应替换为 PostgreSQL 实现

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import asyncio
from datetime import UTC
from uuid import UUID

from src.domain.events.base import DomainEvent
from src.domain.ports.outbox import OutboxRepository
from src.infrastructure.messaging.adapters.event_outbox_adapter import EventOutboxAdapter
from src.infrastructure.messaging.outbox.outbox import OutboxEntity


class InMemoryOutboxRepository(OutboxRepository):
    """内存发件箱仓储实现（MVP 阶段）

    所有公开方法为 async（实现 OutboxRepository Protocol）
    内部方法（_ 前缀）直接操作 OutboxEntity，使用 asyncio.Lock 保护，仅 Poller 使用

    Attributes:
        _entities: 内存中的 OutboxEntity 列表
    """

    def __init__(self) -> None:
        """初始化空的内存发件箱仓储。"""
        self._entities: list[OutboxEntity] = []
        self._lock = asyncio.Lock()

    # ========== 公开方法（实现领域层接口，async） ==========

    async def save(self, event: DomainEvent) -> None:
        """保存事件至发件箱"""
        async with self._lock:
            entity = EventOutboxAdapter.from_domain_event(event)
            self._entities.append(entity)

    async def get_unpublished(self, limit: int) -> list[DomainEvent]:
        """获取未发布的事件列表（FIFO 排序）"""
        async with self._lock:
            unpublished = [e for e in self._entities if e.status == "pending"]
            unpublished.sort(key=lambda e: e.created_at)
            return [EventOutboxAdapter.to_domain_event(e) for e in unpublished[:limit]]

    async def mark_published(self, event_id: UUID) -> None:
        """标记事件已发布"""
        async with self._lock:
            for e in self._entities:
                if e.event_id == event_id:
                    e.status = "published"
                    from datetime import datetime

                    e.published_at = datetime.now(UTC)
                    break

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        """标记事件发布失败"""
        async with self._lock:
            for e in self._entities:
                if e.event_id == event_id:
                    e.status = "failed"
                    e.retry_count += 1
                    e.error_message = error
                    break

    # ========== 内部方法（仅 Poller 使用） ==========

    async def _get_unpublished_entities(self, limit: int) -> list[OutboxEntity]:
        """内部方法: 获取未发布的 OutboxEntity 列表（FIFO 排序）

        Args:
            limit: 最大返回数量

        Returns:
            未发布的 OutboxEntity 列表
        """
        async with self._lock:
            unpublished = [e for e in self._entities if e.status == "pending"]
            unpublished.sort(key=lambda e: e.created_at)
            return unpublished[:limit]

    async def _mark_published_entity(self, entity: OutboxEntity) -> None:
        """内部方法: 标记 OutboxEntity 为 published

        Args:
            entity: 要标记的 OutboxEntity 实例
        """
        async with self._lock:
            for e in self._entities:
                if e.event_id == entity.event_id:
                    e.status = "published"
                    from datetime import datetime

                    e.published_at = datetime.now(UTC)
                    break

    async def _mark_failed_entity(self, entity: OutboxEntity, error: str) -> None:
        """内部方法: 标记 OutboxEntity 为 failed，递增 retry_count

        Args:
            entity: 要标记的 OutboxEntity 实例
            error: 错误信息
        """
        async with self._lock:
            for e in self._entities:
                if e.event_id == entity.event_id:
                    e.status = "failed"
                    e.retry_count += 1
                    e.error_message = error
                    break
