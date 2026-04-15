"""Qdrant 向量存储实现。

提供向量点的增删查和 Dense/Sparse 检索功能。
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    Range,
)
from qdrant_client.models import (
    SparseVector as QdrantSparseVector,
)

from src.infrastructure.storage.qdrant.client import QdrantClientWrapper
from src.infrastructure.storage.qdrant.models import SparseVector, VectorPoint


class QdrantVectorStorage:
    """Qdrant 向量存储实现。

    实现 VectorStorage 接口，提供向量点 CRUD 和检索功能。
    """

    def __init__(self, client_wrapper: QdrantClientWrapper):
        """初始化向量存储。

        Args:
            client_wrapper: Qdrant 客户端封装
        """
        self._client_wrapper = client_wrapper

    def _get_client(self) -> AsyncQdrantClient:
        """获取异步客户端。

        Returns:
            AsyncQdrantClient 实例
        """
        return self._client_wrapper.get_async_client()

    async def upsert_points(self, collection: str, points: list[VectorPoint]) -> bool:
        """批量插入或更新向量点。

        Args:
            collection: Collection 名称
            points: 向量点列表

        Returns:
            操作成功返回 True
        """
        client = self._get_client()
        point_structs = [
            PointStruct(
                id=point.id,
                vector=point.vector,
                payload={**point.payload, "created_at": point.created_at.isoformat()},
            )
            for point in points
        ]
        await client.upsert(collection_name=collection, points=point_structs)
        return True

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """Dense 语义检索。

        Args:
            collection: Collection 名称
            query_vector: 查询向量
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表
        """
        client = self._get_client()
        query_filter: Filter | None = None
        if filter_payload:
            conditions: list[FieldCondition] = []
            for key, value in filter_payload.items():
                if isinstance(value, str | bool):
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
                elif isinstance(value, int | float) and not isinstance(value, bool):
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=int(value))))
                elif isinstance(value, dict) and "gte" in value and "lte" in value:
                    conditions.append(
                        FieldCondition(
                            key=key,
                            range=Range(gte=value["gte"], lte=value["lte"]),
                        )
                    )
                else:
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=str(value))))
            if conditions:
                query_filter = Filter(
                    must=conditions  # type: ignore[arg-type]
                )

        response = await client.query_points(
            collection_name=collection,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return [
            {
                "id": point.id,
                "score": point.score,
                "payload": point.payload or {},
            }
            for point in response.points
        ]

    async def search_sparse(
        self,
        collection: str,
        sparse_vector: SparseVector,
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """BM25 稀疏检索。

        Args:
            collection: Collection 名称
            sparse_vector: 稀疏向量
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表
        """
        client = self._get_client()
        query_filter: Filter | None = None
        if filter_payload:
            conditions: list[FieldCondition] = []
            for key, value in filter_payload.items():
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            if conditions:
                query_filter = Filter(
                    must=conditions  # type: ignore[arg-type]
                )

        try:
            qdrant_sparse = QdrantSparseVector(
                indices=sparse_vector.indices,
                values=sparse_vector.values,
            )
            response = await client.query_points(
                collection_name=collection,
                query=qdrant_sparse,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            return [
                {
                    "id": point.id,
                    "score": point.score,
                    "payload": point.payload or {},
                }
                for point in response.points
            ]
        except Exception:
            return []

    async def delete_points(self, collection: str, point_ids: list[str]) -> bool:
        """删除向量点。

        Args:
            collection: Collection 名称
            point_ids: 要删除的向量点 ID 列表

        Returns:
            操作成功返回 True
        """
        client = self._get_client()
        await client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=list(point_ids)),  # type: ignore[arg-type]
        )
        return True

    async def get_point(self, collection: str, point_id: str) -> dict | None:
        """获取单个向量点。

        Args:
            collection: Collection 名称
            point_id: 向量点 ID

        Returns:
            向量点数据，不存在返回 None
        """
        client = self._get_client()
        points = await client.retrieve(
            collection_name=collection,
            ids=[point_id],
            with_payload=True,
        )
        if not points:
            return None
        point = points[0]
        return {
            "id": point.id,
            "vector": point.vector,
            "payload": point.payload,
        }
