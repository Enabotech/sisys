"""基础设施层 Qdrant 适配器模块

包装 QdrantVectorStorage，实现 L3VectorPort 接口。薄适配器层，仅做接口转换，
points 参数使用 list[dict]，内部转换为 VectorPoint
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from src.domain.ports.l3_vector import L3VectorPort

if TYPE_CHECKING:
    pass


class QdrantAdapter(L3VectorPort):
    """Qdrant 向量存储适配器

    包装现有 QdrantVectorStorage + QdrantCollectionManager，
    实现 L3VectorPort 接口
    所有方法委托给内部存储/管理器实例
    """

    def __init__(self, storage: Any, collection_manager: Any | None = None):
        """初始化适配器

        Args:
            storage: QdrantVectorStorage 实例
            collection_manager: QdrantCollectionManager 实例（可选，Phase 3 补全）
        """
        self._storage = storage
        self._collection_manager = collection_manager

    async def upsert_points(
        self,
        collection: str,
        points: list[dict],
    ) -> bool:
        """批量插入或更新向量点

        Args:
            collection: Collection 名称
            points: 向量点列表，每个点是 dict，需包含 id, vector, payload 字段

        Returns:
            操作成功返回 True
        """
        from datetime import datetime

        from src.infrastructure.storage.qdrant.models import VectorPoint

        # 将 dict 转换为 VectorPoint
        vector_points = []
        for point in points:
            vector_points.append(
                VectorPoint(
                    id=point["id"],
                    vector=point["vector"],
                    payload=point.get("payload", {}),
                    created_at=datetime.now(),
                )
            )
        return cast("bool", await self._storage.upsert_points(collection, vector_points))

    async def delete_points(
        self,
        collection: str,
        point_ids: list[str],
    ) -> bool:
        """批量删除向量点

        Args:
            collection: Collection 名称
            point_ids: 要删除的向量点 ID 列表

        Returns:
            删除成功返回 True
        """
        return cast("bool", await self._storage.delete_points(collection, point_ids))

    async def get_point(
        self,
        collection: str,
        point_id: str,
    ) -> dict | None:
        """获取单个向量点

        Args:
            collection: Collection 名称
            point_id: 向量点 ID

        Returns:
            向量点数据 {id, vector, payload}，不存在返回 None
        """
        return cast("dict[Any, Any] | None", await self._storage.get_point(collection, point_id))

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
            检索结果列表 [{id, score, payload}, ...]
        """
        return cast(
            "list[dict[Any, Any]]",
            await self._storage.search(
                collection,
                query_vector,
                limit=limit,
                filter_payload=filter_payload,
            ),
        )

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
            sparse_vector: 稀疏向量 dict，需包含 indices 和 values 字段
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表 [{id, score, payload}, ...]
        """
        from src.infrastructure.storage.qdrant.models import SparseVector

        # 将 dict 转换为 SparseVector
        sv = SparseVector(
            indices=sparse_vector["indices"],
            values=sparse_vector["values"],
        )
        return cast(
            "list[dict[Any, Any]]",
            await self._storage.search_sparse(
                collection,
                sv,
                limit=limit,
                filter_payload=filter_payload,
            ),
        )

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
            vector_params: 可选参数（如 distance、quantization 等）

        Returns:
            创建成功返回 True

        Raises:
            RuntimeError: CollectionManager 未配置时抛出
        """
        if self._collection_manager is None:
            raise RuntimeError("CollectionManager not configured")
        params = vector_params or {}
        distance = params.pop("distance", "Cosine")
        return cast(
            "bool",
            await self._collection_manager.create_collection(
                name=collection,
                vector_size=vector_size,
                distance=distance,
                **params,
            ),
        )

    async def delete_collection(
        self,
        collection: str,
    ) -> bool:
        """删除 Collection

        Args:
            collection: Collection 名称

        Returns:
            删除成功返回 True

        Raises:
            RuntimeError: CollectionManager 未配置时抛出
        """
        if self._collection_manager is None:
            raise RuntimeError("CollectionManager not configured")
        return cast("bool", await self._collection_manager.delete_collection(collection))

    async def collection_exists(
        self,
        collection: str,
    ) -> bool:
        """检查 Collection 是否存在

        Args:
            collection: Collection 名称

        Returns:
            存在返回 True

        Raises:
            RuntimeError: CollectionManager 未配置时抛出
        """
        if self._collection_manager is None:
            raise RuntimeError("CollectionManager not configured")
        return cast("bool", await self._collection_manager.collection_exists(collection))

    async def list_collections(
        self,
    ) -> list[str]:
        """列出所有 Collection

        Returns:
            Collection 名称列表

        Raises:
            RuntimeError: CollectionManager 未配置时抛出
        """
        if self._collection_manager is None:
            raise RuntimeError("CollectionManager not configured")
        return cast("list[str]", await self._collection_manager.list_collections())
