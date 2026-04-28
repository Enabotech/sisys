"""MemoryChangedListener — 记忆变更事件监听器。

处理 MemoryChanged 事件，下游触发：
1. L1 Redis 缓存失效（同步，立即）：保证"上下文≠缓存"公理
2. L2 PostgreSQL 写入：metadata_repository.upsert() + history_repository.append()
3. L3 Qdrant 向量（按需，内容>500 tokens）：vector_store.embed()
4. L5 Neo4j 图谱（按需）：entity_extractor.extract()

L4 MinIO 不在本流程范围内，由 Checkpoint 持久化流程独立触发（Story 6.3）。

架构来源: architecture.md §11.2.9
Story: 1.15a

调用方式：被 RabbitMQConsumer 通过 await handler(event) 调用，必须是 async def。
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.events.memory_events import MemoryChanged


logger = logging.getLogger(__name__)


class MemoryChangedListener:
    """MemoryChanged 事件监听器。

    事件驱动下游组件更新（§11.2.9 最优架构）：
    - L1 Redis 缓存失效（同步）
    - L2 PostgreSQL 写入（异步）
    - L3 Qdrant 向量（按需）
    - L5 Neo4j 图谱（按需）
    """

    def __init__(
        self,
        storage_coordinator,  # SixLayerStorageCoordinator | None
        metadata_repository,  # MemoryMetadataRepositoryProtocol | None
        history_repository,  # MemoryChangeHistoryRepositoryProtocol | None
    ):
        """初始化监听器。

        Args:
            storage_coordinator: SixLayerStorageCoordinator（L1 缓存失效）
            metadata_repository: L2 元数据仓储（可选）
            history_repository: L2 历史记录仓储（可选）
        """
        self._storage_coordinator = storage_coordinator
        self._metadata_repository = metadata_repository
        self._history_repository = history_repository

    async def handle(self, event: MemoryChanged) -> None:
        """处理 MemoryChanged 事件。

        §11.2.9 最优架构：在 Listener.handle() 中执行 L1/L2/L3/L5 处理。

        Args:
            event: MemoryChanged 事件实例
        """
        logger.info(
            f"MemoryChanged event received: memory_id={event.memory_id}, " f"change_type={event.change_type}, name={event.name}"
        )

        # 1. L1 Redis 缓存失效（同步，立即）
        # 保证"上下文≠缓存"公理
        self._invalidate_l1_cache(event)

        # 2. L2 PostgreSQL 写入（通过 Repository 调用）
        # metadata_repository.upsert() + history_repository.append()
        await self._write_to_l2(event)

        # 3. L3 Qdrant 向量（按需，内容>500 tokens）
        # TODO: Story 6.3 实现

        # 4. L5 Neo4j 图谱（按需，EntityExtractor）
        # TODO: Story 1.17 或 LLM 集成 Story 实现

    def _invalidate_l1_cache(self, event: MemoryChanged) -> None:
        """失效 L1 Redis 缓存（同步，立即）。

        Args:
            event: MemoryChanged 事件
        """
        if self._storage_coordinator is None:
            logger.warning("No storage_coordinator configured, skipping L1 cache invalidation")
            return

        try:
            memory_type = self._get_memory_type(event)
            # owner_id 是 user_id（private 类型）或 group_id
            owner_id = event.user_id
            self._storage_coordinator.invalidate(
                memory_id=event.memory_id,
                layer="L1",
                memory_type=memory_type,
                owner_id=owner_id,
                name=event.name,
            )
            logger.debug(f"L1 cache invalidated: memory_id={event.memory_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate L1 cache: {e}")
            raise

    async def _write_to_l2(self, event: MemoryChanged) -> None:
        """写入 L2 PostgreSQL（通过 Repository 调用）。

        Args:
            event: MemoryChanged 事件
        """
        if self._metadata_repository is None and self._history_repository is None:
            logger.warning("No L2 repositories configured, skipping L2 write")
            return

        from src.domain.entities.memory_change_history import MemoryChangeHistory
        from src.domain.entities.memory_metadata import MemoryMetadata

        memory_type = self._get_memory_type(event)
        metadata = MemoryMetadata(
            memory_id=uuid.UUID(event.memory_id),
            name=event.name,
            type=memory_type,
            path=f"{memory_type}/{event.memory_id}.md",
            user_id=event.user_id,
            description=event.new_value.get("description", "") if event.new_value else "",
            owner=event.new_value.get("owner", "") if event.new_value else "",
            version=1,
            mtime=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        history = MemoryChangeHistory.create(
            memory_id=uuid.UUID(event.memory_id),
            version=1,
            change_type=event.change_type,
            changed_by=event.user_id,
            changed_fields={"is_automatic": event.is_automatic},
        )

        # 顺序执行：metadata 必须先写入（FK 约束）
        if self._metadata_repository is not None:
            await self._metadata_repository.save(metadata)
            logger.debug(f"L2 metadata written: memory_id={event.memory_id}")

        if self._history_repository is not None:
            await self._history_repository.save(history)
            logger.debug(f"L2 history recorded: memory_id={event.memory_id}")

    def _get_memory_type(self, event: MemoryChanged) -> str:
        """从 new_value 中提取 memory_type。

        Args:
            event: MemoryChanged 事件

        Returns:
            memory_type: 'private' | 'group'
        """
        if event.new_value and "type" in event.new_value:
            type_val = event.new_value["type"]
            if isinstance(type_val, str):
                return type_val
        return "private"  # 默认值
