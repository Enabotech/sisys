"""基础设施层内存发件箱仓储模块

MVP 阶段使用内存列表存储 OutboxEntity，公开方法实现领域层接口（同步、无锁），
内部异步方法使用 asyncio.Lock 保护。生产环境应替换为 PostgreSQL 实现
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from src.domain.events.base import DomainEvent
from src.domain.ports.outbox import OutboxRepository
from src.infrastructure.messaging.adapters.event_outbox_adapter import EventOutboxAdapter
from src.infrastructure.messaging.outbox.outbox import OutboxEntity

logger = logging.getLogger(__name__)


class InMemoryOutboxRepository(OutboxRepository):
    """内存发件箱仓储实现（MVP 阶段）

    所有公开方法为 async（实现 OutboxRepository Protocol）
    内部方法（_ 前缀）直接操作 OutboxEntity，使用 asyncio.Lock 保护，仅 Poller 使用

    Attributes:
        _entities: 内存中的 OutboxEntity 列表
    """

    def __init__(self) -> None:
        """初始化空的内存发件箱仓储"""
        self._entities: list[OutboxEntity] = []
        self._lock = asyncio.Lock()

    # ========== 公开方法（实现领域层接口，async） ==========

    async def save(self, event: DomainEvent) -> None:
        """保存事件至发件箱"""
        async with self._lock:
            entity = EventOutboxAdapter.from_domain_event(event)
            self._entities.append(entity)

    async def get_unpublished(self, limit: int) -> list[DomainEvent]:
        """获取未发布的事件列表（FIFO 排序，逐条毒消息隔离）

        单条畸形 payload（反序列化失败）跳过并记日志——对齐 PG 侧 get_unpublished
        的毒隔离语义（单条不阻塞整批）；内存实现无 retry 持久化面，跳过即隔离。
        """
        async with self._lock:
            unpublished = [e for e in self._entities if e.status == "pending"]
            unpublished.sort(key=lambda e: e.created_at)
            events: list[DomainEvent] = []
            for entity in unpublished[:limit]:
                try:
                    events.append(EventOutboxAdapter.to_domain_event(entity))
                except Exception as exc:
                    logger.warning(
                        "InMemory Outbox 事件反序列化失败（毒消息隔离，跳过）: event_id=%s error=%s",
                        entity.event_id,
                        exc,
                    )
            return events

    async def mark_published(self, event_id: UUID) -> None:
        """标记事件已发布"""
        async with self._lock:
            for e in self._entities:
                if e.event_id == event_id:
                    e.mark_published()
                    break

    async def mark_pending(self, event_id: UUID) -> None:
        """将失败事件恢复为待发布状态。"""
        async with self._lock:
            for entity in self._entities:
                if entity.event_id == event_id:
                    entity.mark_pending()
                    return

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        """标记事件发布失败"""
        async with self._lock:
            for e in self._entities:
                if e.event_id == event_id:
                    e.mark_failed(error)
                    break

    async def cleanup_old_published_records(self, older_than_days: int = 30, include_archived: bool = False) -> int:
        """清理超过保留期的已发布记录（可选归档终态行——91-2 AC-3 扩展）

        Args:
            older_than_days: 保留天数（默认 30 天）
            include_archived: 是否同时清理超期 archived 行（以 created_at 计窗口）

        Returns:
            清理的记录数量
        """
        async with self._lock:
            cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
            to_remove = [
                e
                for e in self._entities
                if (e.status == "published" and e.published_at is not None and e.published_at < cutoff)
                or (include_archived and e.status == "archived" and e.created_at < cutoff)
            ]
            for e in to_remove:
                self._entities.remove(e)
            return len(to_remove)

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
                    e.mark_published()
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
                    e.mark_failed(error)
                    break
