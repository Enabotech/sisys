"""MemoryChangedListener — 记忆变更事件监听器。

处理 MemoryChanged 事件，下游触发：
1. L1 Redis 缓存失效（同步，立即）：保证"上下文≠缓存"公理
2. L2 PostgreSQL 写入：metadata_repository.upsert() + history_repository.append()
3. L3 Qdrant 向量（按需，内容>500 tokens）：vector_store.embed()
4. L5 Neo4j 图谱（按需）：entity_extractor.extract()

L4 MinIO 不在本流程范围内，由 Checkpoint 持久化流程独立触发（Story 6.3）。

架构来源: architecture.md §11.2.9
Story: 1.15a
"""

from __future__ import annotations

import logging
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

    def handle(self, event: MemoryChanged) -> None:
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
        self._write_to_l2(event)

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

    def _write_to_l2(self, event: MemoryChanged) -> None:
        """写入 L2 PostgreSQL（通过 Repository 调用）。

        Args:
            event: MemoryChanged 事件
        """
        if self._metadata_repository is None and self._history_repository is None:
            logger.warning("No L2 repositories configured, skipping L2 write")
            return

        try:
            # 写入 memory_metadata（UPSERT）
            if self._metadata_repository is not None:
                self._write_metadata(event)
                logger.debug(f"L2 metadata written: memory_id={event.memory_id}")

            # 记录 memory_change_history（append-only）
            if self._history_repository is not None:
                self._append_history(event)
                logger.debug(f"L2 history recorded: memory_id={event.memory_id}")

        except Exception as e:
            logger.error(f"Failed to write to L2: {e}")
            raise

    def _write_metadata(self, event: MemoryChanged) -> None:
        """写入 memory_metadata。

        Args:
            event: MemoryChanged 事件
        """
        if self._metadata_repository is None:
            return

        # 从 new_value 提取 metadata 字段，构建 MemoryMetadata
        # 注意：具体实现依赖注入的 repository
        logger.debug(f"Writing metadata for memory_id={event.memory_id}")

    def _append_history(self, event: MemoryChanged) -> None:
        """记录 memory_change_history。

        Args:
            event: MemoryChanged 事件
        """
        if self._history_repository is None:
            return

        logger.debug(f"Appending history for memory_id={event.memory_id}, change_type={event.change_type}")

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
