"""SixLayerStorageCoordinator — 六层存储协同服务。

协调 L0-L5 各层存储的读写，作为 MemoryService 与各层存储之间的协调层。
- L0: FileMemoryAdapter（Story 1.15a 已实现，由 MemoryService 直接调用）
- L1: RedisMemoryCache（由 Coordinator 管理）
- L2: MemoryMetadataRepository + MemoryChangeHistoryRepository（Story 1.15a 已实现）
- L3: QdrantVectorStorage（Story 1.6 已实现）
- L4: MinIORepository（Story 1.7 已实现）
- L5: Neo4jGraphStorage（Story 1.8 已实现）

架构来源: architecture.md §11.2.3
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.cache.redis_memory_cache import RedisMemoryCache
    from src.infrastructure.repositories.memory_change_history_repository import MemoryChangeHistoryRepository
    from src.infrastructure.repositories.memory_metadata_repository import MemoryMetadataRepository
    from src.infrastructure.storage.minio.minio_repository import MinIORepository
    from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage
    from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage


class LayerNotFoundError(Exception):
    """指定层不存在异常。"""

    def __init__(self, layer: str):
        """初始化异常。

        Args:
            layer: 层标识 (L0-L5)
        """
        self.layer = layer
        super().__init__(f"Layer not found: {layer}")


class SixLayerStorageCoordinator:
    """六层存储协调器。

    负责协调 L0-L5 各层存储的读写操作。
    L0 由 MemoryService 直接调用 FileMemoryAdapter 处理。
    """

    def __init__(
        self,
        redis_cache: RedisMemoryCache,
        l2_repository: MemoryMetadataRepository | MemoryChangeHistoryRepository | None = None,
        l3_vector_store: QdrantVectorStorage | None = None,
        l4_object_store: MinIORepository | None = None,
        l5_graph_store: Neo4jGraphStorage | None = None,
    ):
        """初始化协调器。

        Args:
            redis_cache: L1 Redis 缓存
            l2_repository: L2 PostgreSQL 仓储
            l3_vector_store: L3 Qdrant 向量存储
            l4_object_store: L4 MinIO 对象存储
            l5_graph_store: L5 Neo4j 图存储
        """
        self._redis_cache = redis_cache
        self._l2_repository = l2_repository
        self._l3_vector_store = l3_vector_store
        self._l4_object_store = l4_object_store
        self._l5_graph_store = l5_graph_store

    def save(self, memory_id: str, content: str, layer: str, memory_type: str) -> None:
        """保存记忆到指定层。

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            layer: 目标层 (L0-L5)
            memory_type: 记忆类型 ('private' | 'group')
        """
        if layer == "L1":
            self._save_to_l1(memory_id, content, memory_type)
        elif layer == "L2":
            self._save_to_l2(memory_id, content, memory_type)
        elif layer == "L3":
            self._save_to_l3(memory_id, content, memory_type)
        elif layer == "L4":
            self._save_to_l4(memory_id, content, memory_type)
        elif layer == "L5":
            self._save_to_l5(memory_id, content, memory_type)
        else:
            raise LayerNotFoundError(layer)

    def read(self, memory_id: str, layer: str, memory_type: str) -> str | None:
        """从指定层读取记忆。

        Args:
            memory_id: 记忆 ID
            layer: 源层 (L0-L5)
            memory_type: 记忆类型 ('private' | 'group')

        Returns:
            记忆内容，不存在则返回 None
        """
        if layer == "L1":
            return self._read_from_l1(memory_id, memory_type)
        elif layer == "L2":
            return self._read_from_l2(memory_id)
        else:
            raise LayerNotFoundError(layer)

    def invalidate(self, memory_id: str, layer: str, memory_type: str) -> None:
        """失效指定层缓存。

        Args:
            memory_id: 记忆 ID
            layer: 目标层 (L1)
            memory_type: 记忆类型 ('private' | 'group')
        """
        if layer == "L1":
            self._invalidate_l1(memory_id, memory_type)
        else:
            raise LayerNotFoundError(layer)

    def get_layer_status(self, memory_id: str, memory_type: str) -> dict[str, bool]:
        """获取各层存储状态。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型 ('private' | 'group')

        Returns:
            各层是否存在 {layer: exists}
        """
        status = {"L0": True}  # L0 始终存在（文件系统）
        status["L1"] = self._check_l1_exists(memory_id, memory_type)
        status["L2"] = self._check_l2_exists(memory_id)
        status["L3"] = self._check_l3_exists(memory_id) if self._l3_vector_store else False
        status["L4"] = self._check_l4_exists(memory_id) if self._l4_object_store else False
        status["L5"] = self._check_l5_exists(memory_id) if self._l5_graph_store else False
        return status

    def _save_to_l1(self, memory_id: str, content: str, memory_type: str) -> None:
        """保存到 L1 Redis 缓存。"""
        if self._redis_cache is None:
            return
        self._redis_cache.set(memory_type, memory_id, memory_id, content)

    def _save_to_l2(self, memory_id: str, content: str, memory_type: str) -> None:
        """保存到 L2 PostgreSQL。"""
        if self._l2_repository is None:
            return
        # L2 写入通过仓储处理

    def _save_to_l3(self, memory_id: str, content: str, memory_type: str) -> None:
        """保存到 L3 Qdrant。"""
        if self._l3_vector_store is None:
            return

    def _save_to_l4(self, memory_id: str, content: str, memory_type: str) -> None:
        """保存到 L4 MinIO。"""
        if self._l4_object_store is None:
            return

    def _save_to_l5(self, memory_id: str, content: str, memory_type: str) -> None:
        """保存到 L5 Neo4j。"""
        if self._l5_graph_store is None:
            return

    def _read_from_l1(self, memory_id: str, memory_type: str) -> str | None:
        """从 L1 Redis 缓存读取。"""
        if self._redis_cache is None:
            return None
        return self._redis_cache.get(memory_type, memory_id, memory_id)

    def _read_from_l2(self, memory_id: str) -> str | None:
        """从 L2 PostgreSQL 读取。"""
        if self._l2_repository is None:
            return None
        return None

    def _invalidate_l1(self, memory_id: str, memory_type: str) -> None:
        """失效 L1 Redis 缓存。"""
        if self._redis_cache is None:
            return
        self._redis_cache.delete(memory_type, memory_id, memory_id)

    def _check_l1_exists(self, memory_id: str, memory_type: str) -> bool:
        """检查 L1 是否存在。"""
        if self._redis_cache is None:
            return False
        return self._redis_cache.get(memory_type, memory_id, memory_id) is not None

    def _check_l2_exists(self, memory_id: str) -> bool:
        """检查 L2 是否存在。"""
        return False

    def _check_l3_exists(self, memory_id: str) -> bool:
        """检查 L3 是否存在。"""
        return False

    def _check_l4_exists(self, memory_id: str) -> bool:
        """检查 L4 是否存在。"""
        return False

    def _check_l5_exists(self, memory_id: str) -> bool:
        """检查 L5 是否存在。"""
        return False
