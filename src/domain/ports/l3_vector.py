"""L3VectorPort — L3 Qdrant 向量存储抽象端口。

对应 architecture.md §11.1：
- 内容 >500 tokens 时启用向量检索
- 支持 Dense+Sparse+Payload 过滤

设计说明：
- 与现有 VectorStorage ABC 语义完全兼容
- embedding 生成职责归于上游服务，不耦合在此层
- collection 参数明确传递（由调用方管理）
- points 参数使用 list[dict]（兼容 duck typing），实际 VectorPoint 由 Adapter 转换

与 VectorStorage ABC 的关系：
- 本质上与 VectorStorage 是同一接口
- L3VectorPort 是分层视角的命名（强调 L3 层级）
- VectorStorage 是职责视角的命名（强调向量存储能力）

设计原则：
- 领域层零外部依赖（仅用 abc + typing）
- 异步优先（async def）
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class L3VectorPort(ABC):
    """L3 Qdrant 向量存储端口接口。

    对应 architecture.md §11.1：
    - 内容 >500 tokens 时启用向量检索
    - 支持 Dense+Sparse+Payload 过滤
    """

    @abstractmethod
    async def upsert_points(
        self,
        collection: str,
        points: list[dict],
    ) -> bool:
        """批量插入或更新向量点。

        Args:
            collection: Collection 名称
            points: 向量点列表，每个点是 dict，需包含 id, vector, payload 字段
                   示例: [{"id": "mem-123", "vector": [0.1, 0.2], "payload": {...}}, ...]

        Returns:
            操作成功返回 True
        """
        pass

    @abstractmethod
    async def delete_points(
        self,
        collection: str,
        point_ids: list[str],
    ) -> bool:
        """批量删除向量点。

        Args:
            collection: Collection 名称
            point_ids: 要删除的向量点 ID 列表

        Returns:
            删除成功返回 True
        """
        pass

    @abstractmethod
    async def get_point(
        self,
        collection: str,
        point_id: str,
    ) -> dict | None:
        """获取单个向量点。

        Args:
            collection: Collection 名称
            point_id: 向量点 ID

        Returns:
            向量点数据 {id, vector, payload}，不存在返回 None
        """
        pass

    @abstractmethod
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
            query_vector: 查询向量（通常由 embedding service 生成）
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表 [{id, score, payload}, ...]
        """
        pass

    @abstractmethod
    async def search_sparse(
        self,
        collection: str,
        sparse_vector: dict,
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """BM25 稀疏检索。

        对应 architecture.md §11.1 "Dense+Sparse+Payload 过滤"。

        Args:
            collection: Collection 名称
            sparse_vector: 稀疏向量 dict，需包含 indices 和 values 字段
                          示例: {"indices": [0, 5, 10], "values": [1.0, 0.5, 0.8]}
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表 [{id, score, payload}, ...]
        """
        pass
