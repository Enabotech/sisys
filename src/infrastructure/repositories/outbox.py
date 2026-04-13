"""InMemoryOutboxRepository — 基础设施层实现。

MVP 阶段使用内存列表存储 OutboxEntity。
使用 asyncio.Lock 保护所有 _entities 操作。
领域层零 OutboxEntity 污染（方案 A 彻底隔离）。
"""

from __future__ import annotations

import asyncio
from datetime import UTC
from uuid import UUID

from src.domain.events.base import DomainEvent
from src.domain.repositories.outbox import OutboxRepository
from src.infrastructure.adapters.event_outbox_adapter import EventOutboxAdapter
from src.infrastructure.entities.outbox import OutboxEntity


class InMemoryOutboxRepository(OutboxRepository):
    """内存发件箱仓储实现（MVP 占位）。

    公开方法实现领域层接口（使用 DomainEvent）。
    内部方法（_ 前缀）直接操作 OutboxEntity，仅 Poller 使用。
    """

    def __init__(self):
        self._entities: list[OutboxEntity] = []
        self._lock = asyncio.Lock()  # 一把锁，保护所有 _entities 操作

    # ========== 公开方法（实现领域层接口） ==========

    def save(self, event: DomainEvent) -> None:
        """保存事件至发件箱。

        内部将 DomainEvent 转为 OutboxEntity 存储。
        """
        entity = EventOutboxAdapter.from_domain_event(event)
        self._entities.append(entity)

    def get_unpublished(self, limit: int) -> list[DomainEvent]:
        """获取未发布的事件列表。

        内部获取 OutboxEntity 列表，转换为 DomainEvent 返回。
        """
        unpublished = [e for e in self._entities if e.status == "pending"]
        unpublished.sort(key=lambda e: e.created_at)  # FIFO
        return [EventOutboxAdapter.to_domain_event(e) for e in unpublished[:limit]]

    def mark_published(self, event_id: UUID) -> None:
        """标记事件已发布。"""
        for e in self._entities:
            if e.event_id == event_id:
                e.status = "published"
                from datetime import datetime

                e.published_at = datetime.now(UTC)
                break

    def mark_failed(self, event_id: UUID, error: str) -> None:
        """标记事件发布失败。"""
        for e in self._entities:
            if e.event_id == event_id:
                e.status = "failed"
                e.retry_count += 1
                e.error_message = error
                break

    # ========== 内部方法（仅 Poller 使用） ==========

    async def _get_unpublished_entities(self, limit: int) -> list[OutboxEntity]:
        """内部方法: 获取未发布的 OutboxEntity 列表（FIFO 排序）。"""
        async with self._lock:
            unpublished = [e for e in self._entities if e.status == "pending"]
            unpublished.sort(key=lambda e: e.created_at)
            return unpublished[:limit]

    async def _mark_published_entity(self, entity: OutboxEntity) -> None:
        """内部方法: 标记 OutboxEntity 为 published。"""
        async with self._lock:
            for e in self._entities:
                if e.event_id == entity.event_id:
                    e.status = "published"
                    from datetime import datetime

                    e.published_at = datetime.now(UTC)
                    break

    async def _mark_failed_entity(self, entity: OutboxEntity, error: str) -> None:
        """内部方法: 标记 OutboxEntity 为 failed，递增 retry_count。"""
        async with self._lock:
            for e in self._entities:
                if e.event_id == entity.event_id:
                    e.status = "failed"
                    e.retry_count += 1
                    e.error_message = error
                    break
