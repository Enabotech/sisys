"""基础设施层 Qdrant 向量存储模块

提供向量点的增删查和 Dense/Sparse 检索功能
"""

from __future__ import annotations

import hashlib
import logging
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

from src.domain.ports.l3_vector import L3VectorPort
from src.infrastructure.storage.qdrant.models import SparseVector, VectorPoint

logger = logging.getLogger(__name__)


class QdrantVectorStorage(L3VectorPort):
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
        - 其他字符串使用确定性 MD5 哈希映射（避免 Python hash() 随机化导致
          PYTHONHASHSEED 变化后同一字符串映射到不同 ID，破坏幂等 upsert）

        Args:
            point_id: 原始点 ID（字符串）

        Returns:
            规范化后的整数 ID
        """
        try:
            pid = int(point_id)
            if pid < 1000:
                # 小整数用确定哈希避免冲突
                return int(hashlib.md5(point_id.encode("utf-8")).hexdigest(), 16) % (2**31)
            return pid
        except ValueError:
            # 非纯数字字符串：确定性哈希，保证跨进程稳定（幂等 upsert 依赖）
            return int(hashlib.md5(point_id.encode("utf-8")).hexdigest(), 16) % (2**63)

    async def upsert_points(self, collection: str, points: list[VectorPoint] | list[dict]) -> bool:
        """批量插入或更新向量点

        Args:
            collection: Collection 名称
            points: 向量点列表（接受 VectorPoint dataclass 或 dict）

        Returns:
            操作成功返回 True
        """
        point_structs = []
        for point in points:
            if isinstance(point, VectorPoint):
                pid = self._normalize_point_id(point.id)
                payload = {**point.payload, "created_at": point.created_at.isoformat()}
                vec: Any = point.vector
                if point.sparse_vector is not None:
                    vec = {
                        "": point.vector,
                        "sparse": QdrantSparseVector(
                            indices=point.sparse_vector["indices"],
                            values=point.sparse_vector["values"],
                        ),
                    }
            else:
                pid = self._normalize_point_id(point["id"])
                payload = dict(point.get("payload", {}))
                top_created = point.get("created_at")
                if top_created is not None and hasattr(top_created, "isoformat"):
                    payload["created_at"] = top_created.isoformat()
                vec = point["vector"]
                sparse_data = point.get("sparse_vector")
                if sparse_data is not None:
                    vec = {
                        "": point["vector"],
                        "sparse": QdrantSparseVector(
                            indices=sparse_data["indices"],
                            values=sparse_data["values"],
                        ),
                    }
            point_structs.append(
                PointStruct(
                    id=pid,
                    vector=vec,
                    payload=payload,
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
        sparse_vector: SparseVector | dict,
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """BM25 稀疏检索

        Args:
            collection: Collection 名称
            sparse_vector: 稀疏向量（接受 SparseVector dataclass 或 dict）
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
            if isinstance(sparse_vector, SparseVector):
                indices = sparse_vector.indices
                values = sparse_vector.values
            else:
                indices = sparse_vector["indices"]
                values = sparse_vector["values"]

            qdrant_sparse = QdrantSparseVector(
                indices=indices,
                values=values,
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
        except Exception as e:
            logger.error("稀疏检索失败: collection=%s, error=%s", collection, e)
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

    async def create_collection(
        self,
        collection: str,
        vector_size: int,
        vector_params: dict | None = None,
    ) -> bool:
        """创建 Collection（委托给 QdrantCollectionManager）

        注: 此方法在此类中为空实现，Collection 管理由 QdrantCollectionManager 负责

        Args:
            collection: Collection 名称
            vector_size: 向量维度
            vector_params: 可选参数

        Returns:
            始终返回 True
        """
        return True

    async def delete_collection(self, collection: str) -> bool:
        """删除 Collection（委托给 QdrantCollectionManager）

        注: 此方法在此类中为空实现，Collection 管理由 QdrantCollectionManager 负责

        Args:
            collection: Collection 名称

        Returns:
            始终返回 True
        """
        return True

    async def collection_exists(self, collection: str) -> bool:
        """检查 Collection 是否存在（委托给 QdrantCollectionManager）

        注: 此方法在此类中为空实现，Collection 管理由 QdrantCollectionManager 负责

        Args:
            collection: Collection 名称

        Returns:
            始终返回 False
        """
        return False

    async def list_collections(self) -> list[str]:
        """列出所有 Collection（委托给 QdrantCollectionManager）

        注: 此方法在此类中为空实现，Collection 管理由 QdrantCollectionManager 负责

        Returns:
            空列表
        """
        return []
