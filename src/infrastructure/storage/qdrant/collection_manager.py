"""基础设施层 Qdrant Collection 管理模块

负责 Qdrant Collection 的创建、删除、查询和列表操作
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, SparseVectorParams, VectorParams


class QdrantCollectionManager:
    """Qdrant Collection 管理器

    实现 CollectionManager 接口，提供 Collection 生命周期管理
    """

    def __init__(self, client: AsyncQdrantClient):
        """初始化 Collection 管理器

        Args:
            client: Qdrant 异步客户端实例
        """
        self._client = client

    async def create_collection(
        self,
        name: str,
        vector_size: int = 1024,
        distance: str = "Cosine",
        sparse_vectors_config: dict | None = None,
        **kwargs,
    ) -> bool:
        """创建 Collection

        Args:
            name: Collection 名称
            vector_size: 向量维度
            distance: 相似度度量方式
            sparse_vectors_config: 稀疏向量配置，默认 {"sparse": SparseVectorParams()}
            **kwargs: 其他配置参数

        Returns:
            创建成功返回 True，已存在返回 False
        """
        if await self.collection_exists(name):
            return False

        # 默认自动配置稀疏向量索引（Story 3-1b: AC-4 要求）
        if sparse_vectors_config is None:
            sparse_vectors_config = {"sparse": SparseVectorParams()}

        distance_map = {
            "Cosine": Distance.COSINE,
            "Euclidean": Distance.EUCLID,
            "Dot": Distance.DOT,
        }
        distance_enum = distance_map.get(distance, Distance.COSINE)

        hnsw_config = kwargs.get(
            "hnsw_config",
            {
                "m": 16,
                "ef_construct": 128,
                "full_scan_threshold": 10000,
            },
        )

        await self._client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=distance_enum,
            ),
            hnsw_config=hnsw_config,
            shard_number=kwargs.get("shard_number", 1),
            replication_factor=kwargs.get("replication_factor", 1),
            on_disk_payload=kwargs.get("on_disk", False),
            sparse_vectors_config=sparse_vectors_config,
        )
        return True

    async def delete_collection(self, name: str) -> bool:
        """删除 Collection

        Args:
            name: Collection 名称

        Returns:
            删除成功返回 True，不存在返回 False
        """
        if not await self.collection_exists(name):
            return False

        await self._client.delete_collection(collection_name=name)
        return True

    async def collection_exists(self, name: str) -> bool:
        """检查 Collection 是否存在

        Args:
            name: Collection 名称

        Returns:
            存在返回 True，否则返回 False
        """
        try:
            collections = await self._client.get_collections()
            return name in [c.name for c in collections.collections]
        except Exception:
            return False

    async def list_collections(self) -> list[str]:
        """列出所有 Collection

        Returns:
            Collection 名称列表
        """
        try:
            collections = await self._client.get_collections()
            return [c.name for c in collections.collections]
        except Exception:
            return []
