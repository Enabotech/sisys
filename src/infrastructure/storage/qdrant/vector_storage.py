"""基础设施层 Qdrant 向量存储模块

提供向量点的增删查和 Dense/Sparse 检索功能

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Any, cast

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    NamedSparseVector,
    PointIdsList,
    PointStruct,
    Range,
)
from qdrant_client.models import (
    SparseVector as QdrantSparseVector,
)

from src.infrastructure.storage.qdrant.models import SparseVector, VectorPoint


class QdrantVectorStorage:
    """Qdrant 向量存储实现

    实现 VectorStorage 接口，提供向量点 CRUD 和检索功能
    """

    def __init__(self, client: AsyncQdrantClient):
        """初始化向量存储

        Args:
            client: Qdrant 异步客户端实例
        """
        self._client = client

    def _normalize_point_id(self, point_id: str) -> int:
        """规范化向量点 ID，确保 Qdrant 接受

        Qdrant v1.7.x 要求 ID 为无符号整数或 UUID
        对于字符串 ID：
        - 纯数字字符串转换为整数
        - 小整数（<1000）使用 hash 映射到有效范围避免被拒绝

        Args:
            point_id: 原始点 ID（字符串）

        Returns:
            规范化后的整数 ID
        """
        try:
            pid = int(point_id)
            if pid < 1000:
                return abs(hash(point_id)) % (2**31)
            return pid
        except ValueError:
            return abs(hash(point_id)) % (2**31)

    async def upsert_points(self, collection: str, points: list[VectorPoint]) -> bool:
        """批量插入或更新向量点

        Args:
            collection: Collection 名称
            points: 向量点列表

        Returns:
            操作成功返回 True
        """
        point_structs = []
        for point in points:
            pid = self._normalize_point_id(point.id)
            point_structs.append(
                PointStruct(
                    id=pid,
                    vector=point.vector,
                    payload={**point.payload, "created_at": point.created_at.isoformat()},
                )
            )
        await self._client.upsert(collection_name=collection, points=point_structs)
        return True

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
        query_filter: Filter | None = None
        if filter_payload:
            conditions: list[Any] = []
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
                query_filter = Filter(must=conditions)

        response = await self._client.search(
            collection_name=collection,
            query_vector=query_vector,
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
            for point in response
        ]

    async def search_sparse(
        self,
        collection: str,
        sparse_vector: SparseVector,
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """BM25 稀疏检索

        Args:
            collection: Collection 名称
            sparse_vector: 稀疏向量
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表
        """
        query_filter: Filter | None = None
        if filter_payload:
            conditions: list[Any] = []
            for key, value in filter_payload.items():
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            if conditions:
                query_filter = Filter(must=conditions)

        try:
            qdrant_sparse = QdrantSparseVector(
                indices=sparse_vector.indices,
                values=sparse_vector.values,
            )
            named_sparse = NamedSparseVector(name="sparse", vector=qdrant_sparse)
            response = await self._client.search(
                collection_name=collection,
                query_vector=named_sparse,
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
                for point in response
            ]
        except Exception:
            return []

    async def delete_points(self, collection: str, point_ids: list[str]) -> bool:
        """删除向量点

        Args:
            collection: Collection 名称
            point_ids: 要删除的向量点 ID 列表

        Returns:
            操作成功返回 True
        """
        converted_ids = [self._normalize_point_id(pid) for pid in point_ids]
        await self._client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=cast(Any, converted_ids)),
        )
        return True

    async def get_point(self, collection: str, point_id: str) -> dict | None:
        """获取单个向量点

        Args:
            collection: Collection 名称
            point_id: 向量点 ID

        Returns:
            向量点数据，不存在返回 None
        """
        normalized_id = self._normalize_point_id(point_id)
        points = await self._client.retrieve(
            collection_name=collection,
            ids=[normalized_id],
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
