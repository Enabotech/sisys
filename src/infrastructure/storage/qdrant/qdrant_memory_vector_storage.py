"""基础设施层 Qdrant 记忆向量存储模块

实现 MemoryVectorPort 接口，组合 QdrantAdapter 并添加记忆向量索引和语义检索语义
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any, Callable

from src.application.ports.memory_vector_port import MemoryVectorPort

if TYPE_CHECKING:
    from src.infrastructure.storage.qdrant.qdrant_adapter import QdrantAdapter

logger = logging.getLogger(__name__)

# Default collection for memory vectors
MEMORY_COLLECTION = "sisys_memories"


class QdrantMemoryVectorStorage(MemoryVectorPort):
    """Qdrant 记忆向量存储 — 实现 MemoryVectorPort

    组合 QdrantAdapter（Rule 3，L3VectorPort 实现），
    添加记忆语义：自动 embedding 生成 + payload 过滤
    """

    def __init__(
        self,
        adapter: QdrantAdapter,
        embed_fn: Callable[[str], list[float]] | None = None,
        collection: str = MEMORY_COLLECTION,
    ):
        """初始化 QdrantMemoryVectorStorage

        Args:
            adapter: QdrantAdapter 实例（Rule 3）
            embed_fn: 文本→向量转换函数，None 则使用确定性 hash embedding
            collection: 默认 Collection 名称
        """
        self._adapter = adapter
        self._embed_fn = embed_fn or self._deterministic_embed
        self._collection = collection

    # -- L3VectorPort methods (delegate to adapter) --

    async def upsert_points(self, collection: str, points: list[dict]) -> bool:
        """批量插入或更新向量点

        Args:
            collection: Collection 名称
            points: 向量点列表

        Returns:
            操作成功返回 True
        """
        return await self._adapter.upsert_points(collection, points)

    async def delete_points(self, collection: str, point_ids: list[str]) -> bool:
        """批量删除向量点

        Args:
            collection: Collection 名称
            point_ids: 要删除的向量点 ID 列表

        Returns:
            删除成功返回 True
        """
        return await self._adapter.delete_points(collection, point_ids)

    async def get_point(self, collection: str, point_id: str) -> dict | None:
        """获取单个向量点

        Args:
            collection: Collection 名称
            point_id: 向量点 ID

        Returns:
            向量点数据，不存在返回 None
        """
        return await self._adapter.get_point(collection, point_id)

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """Dense 语义检索

        Args:
            collection: Collection 名称
            query_vector: 查询向量
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表
        """
        return await self._adapter.search(collection, query_vector, limit, filter_payload)

    async def search_sparse(
        self,
        collection: str,
        sparse_vector: dict,
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """BM25 稀疏检索

        Args:
            collection: Collection 名称
            sparse_vector: 稀疏向量字典
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表
        """
        return await self._adapter.search_sparse(collection, sparse_vector, limit, filter_payload)

    async def create_collection(
        self,
        collection: str,
        vector_size: int,
        vector_params: dict | None = None,
    ) -> bool:
        """创建 Collection

        Args:
            collection: Collection 名称
            vector_size: 向量维度
            vector_params: 可选参数

        Returns:
            创建成功返回 True
        """
        return await self._adapter.create_collection(collection, vector_size, vector_params)

    async def delete_collection(self, collection: str) -> bool:
        """删除 Collection

        Args:
            collection: Collection 名称

        Returns:
            删除成功返回 True
        """
        return await self._adapter.delete_collection(collection)

    async def collection_exists(self, collection: str) -> bool:
        """检查 Collection 是否存在

        Args:
            collection: Collection 名称

        Returns:
            存在返回 True
        """
        return await self._adapter.collection_exists(collection)

    async def list_collections(self) -> list[str]:
        """列出所有 Collection

        Returns:
            Collection 名称列表
        """
        return await self._adapter.list_collections()

    # -- MemoryVectorPort specific methods --

    async def index_memory(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
    ) -> bool:
        """索引记忆内容，自动生成 embedding 并存储

        Args:
            memory_id: 记忆 ID
            content: 记忆文本内容
            memory_type: 记忆类型
            owner_id: 所有者 ID

        Returns:
            操作成功返回 True
        """
        vector = self._embed_fn(content)
        points = [
            {
                "id": memory_id,
                "vector": vector,
                "payload": {"memory_type": memory_type, "owner_id": owner_id},
            }
        ]
        return await self._adapter.upsert_points(self._collection, points)

    async def search_similar_memories(
        self,
        query: str,
        owner_id: str | None = None,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """语义相似记忆检索

        Args:
            query: 查询文本
            owner_id: 所有者 ID 过滤
            memory_type: 记忆类型过滤
            limit: 返回结果数量限制

        Returns:
            检索结果列表
        """
        query_vector = self._embed_fn(query)
        filter_payload: dict[str, Any] = {}
        if owner_id is not None:
            filter_payload["owner_id"] = owner_id
        if memory_type is not None:
            filter_payload["memory_type"] = memory_type
        return await self._adapter.search(
            self._collection,
            query_vector,
            limit=limit,
            filter_payload=filter_payload or None,
        )

    @staticmethod
    def _deterministic_embed(text: str) -> list[float]:
        """确定性 hash embedding（仅用于测试/开发，非生产质量）

        将文本 hash 映射到固定维度伪向量，生产环境应注入真正的 embedding 函数

        Args:
            text: 输入文本

        Returns:
            128 维伪向量
        """
        dim = 128
        h = hashlib.sha256(text.encode()).digest()
        vector = []
        for i in range(dim):
            byte_idx = i % len(h)
            vector.append(float(h[byte_idx]) / 255.0 - 0.5)
        return vector
