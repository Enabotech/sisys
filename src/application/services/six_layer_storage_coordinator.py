"""SixLayerStorageCoordinator — 六层存储协同服务。

协调 L0-L5 各层存储的读写，作为 MemoryService 与各层存储之间的协调层。
- L0: FileMemoryAdapter（Story 1.15a 已实现，由 MemoryService 直接调用）
- L1: RedisMemoryCache（由 Coordinator 管理）
- L2: MemoryMetadataRepository + MemoryChangeHistoryRepository（Story 1.15a 已实现）
- L3: QdrantVectorStorage（Story 1.6 已实现）
- L4: MinIORepository（Story 1.7 已实现）
- L5: Neo4jGraphStorage（Story 1.8 已实现）

架构来源: architecture.md §11.2.9
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.repositories.memory_change_history_repository import MemoryChangeHistoryRepository
    from src.infrastructure.repositories.memory_metadata_repository import MemoryMetadataRepository
    from src.infrastructure.storage.minio.minio_repository import MinIORepository
    from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage
    from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
    from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache


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

    def save(
        self,
        memory_id: str,
        content: str,
        layer: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> None:
        """保存记忆到指定层。

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            layer: 目标层 (L0-L5)
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称
        """
        if layer == "L1":
            self._save_to_l1(memory_id, content, memory_type, owner_id, name)
        elif layer == "L2":
            self._save_to_l2(memory_id, content, memory_type, owner_id, name)
        elif layer == "L3":
            self._save_to_l3(memory_id, content, memory_type, owner_id, name)
        elif layer == "L4":
            self._save_to_l4(memory_id, content, memory_type, owner_id, name)
        elif layer == "L5":
            self._save_to_l5(memory_id, content, memory_type, owner_id, name)
        else:
            raise LayerNotFoundError(layer)

    def read(
        self,
        memory_id: str,
        layer: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> str | None:
        """从指定层读取记忆。

        Args:
            memory_id: 记忆 ID
            layer: 源层 (L0-L5)
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称

        Returns:
            记忆内容，不存在则返回 None
        """
        if layer == "L1":
            return self._read_from_l1(memory_id, memory_type, owner_id, name)
        elif layer == "L2":
            return self._read_from_l2(memory_id)
        else:
            raise LayerNotFoundError(layer)

    def invalidate(
        self,
        memory_id: str,
        layer: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> None:
        """失效指定层缓存。

        Args:
            memory_id: 记忆 ID
            layer: 目标层 (L1)
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称
        """
        if layer == "L1":
            self._invalidate_l1(memory_id, memory_type, owner_id, name)
        else:
            raise LayerNotFoundError(layer)

    def get_layer_status(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, bool]:
        """获取各层存储状态。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)，用于 L1 检查
            name: 记忆名称，用于 L1 检查

        Returns:
            各层是否存在 {layer: exists}
        """
        status = {"L0": True}  # L0 始终存在（文件系统）
        status["L1"] = self._check_l1_exists(memory_id, memory_type, owner_id, name)
        status["L2"] = self._check_l2_exists(memory_id)
        status["L3"] = self._check_l3_exists(memory_id) if self._l3_vector_store else False
        status["L4"] = self._check_l4_exists(memory_id) if self._l4_object_store else False
        status["L5"] = self._check_l5_exists(memory_id) if self._l5_graph_store else False
        return status

    def _save_to_l1(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> None:
        """保存到 L1 Redis 缓存。

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称
        """
        if self._redis_cache is None:
            return
        self._redis_cache.set(memory_type, owner_id, name, content)

    def _save_to_l2(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> None:
        """保存到 L2 PostgreSQL (通过事件驱动，由调用方确保事务一致性)。

        注意: L2 的实际持久化由 MemoryService 在同一事务中调用 MemoryMetadataRepository 完成。
        此处仅用于触发可能的副作用（如通知、触发器等）。

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称
        """
        # L2 写入已在 MemoryService.save() 中通过 metadata_repository.save() 完成
        # 此处不需要重复写入，避免事务冲突
        pass

    def _save_to_l3(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> None:
        """保存到 L3 Qdrant 向量存储（压缩后内容 >500 tokens 时触发）。

        触发条件由 Story 6.3 (Checkpoint 快照创建) 实现。

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称
        """
        if self._l3_vector_store is None:
            return
        # TODO: L3 向量存储由 Story 6.3 实现
        # 需要嵌入 content 并存储到 Qdrant

    def _save_to_l4(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> None:
        """保存到 L4 MinIO 对象存储（Checkpoint 创建时触发）。

        触发条件由 Story 6.3 (Checkpoint 快照创建) 实现。

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称
        """
        if self._l4_object_store is None:
            return
        # TODO: L4 对象存储由 Story 6.3 实现
        # 需要归档 content 到 MinIO

    def _save_to_l5(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> None:
        """保存到 L5 Neo4j 知识图谱（实体关系提取后触发）。

        通过 EntityExtractorService 协议接口调用 LLM 分析（协议定义在本 Story，
        实现由后续 LLM 集成 Story 提供）。

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称
        """
        if self._l5_graph_store is None:
            return
        # TODO: L5 知识图谱由后续 LLM 集成 Story 实现
        # 需要通过 EntityExtractorService 提取实体关系

    def _read_from_l1(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> str | None:
        """从 L1 Redis 缓存读取。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称

        Returns:
            记忆内容，不存在则返回 None
        """
        if self._redis_cache is None:
            return None
        return self._redis_cache.get(memory_type, owner_id, name)

    def _read_from_l2(self, memory_id: str) -> str | None:
        """从 L2 PostgreSQL 读取。"""
        if self._l2_repository is None:
            return None
        return None

    def _invalidate_l1(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> None:
        """失效 L1 Redis 缓存。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称
        """
        if self._redis_cache is None:
            return
        self._redis_cache.delete(memory_type, owner_id, name)

    def _check_l1_exists(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str | None = None,
        name: str | None = None,
    ) -> bool:
        """检查 L1 是否存在。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称

        Returns:
            L1 缓存是否存在
        """
        if self._redis_cache is None:
            return False
        if owner_id is None or name is None:
            return False  # 无法检查，没有足够信息构建 key
        return self._redis_cache.get(memory_type, owner_id, name) is not None

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
