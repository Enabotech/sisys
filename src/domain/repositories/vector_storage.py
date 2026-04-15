"""VectorStorage Protocol — 领域层定义。

定义向量存储的接口，包括 Collection 管理和向量点 CRUD 操作。
基础设施层负责实现（如 Qdrant 实现）。
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol


class CollectionManager(Protocol):
    """Collection 管理器协议接口。

    所有方法均为异步方法，支持 Collection 的创建、删除、查询和列表操作。
    """

    @abstractmethod
    async def create_collection(self, name: str, vector_size: int = 1024, distance: str = "Cosine", **kwargs) -> bool:
        """创建 Collection。

        Args:
            name: Collection 名称（应遵循 sisys:{type}:{namespace} 规范）
            vector_size: 向量维度（默认 1024）
            distance: 相似度度量方式（默认 Cosine）
            **kwargs: 其他 Collection 配置参数

        Returns:
            创建成功返回 True，如果 Collection 已存在则返回 False
        """

    @abstractmethod
    async def delete_collection(self, name: str) -> bool:
        """删除 Collection。

        Args:
            name: Collection 名称

        Returns:
            删除成功返回 True，如果 Collection 不存在则返回 False
        """

    @abstractmethod
    async def collection_exists(self, name: str) -> bool:
        """检查 Collection 是否存在。

        Args:
            name: Collection 名称

        Returns:
            如果存在返回 True，否则返回 False
        """

    @abstractmethod
    async def list_collections(self) -> list[str]:
        """列出所有 Collection。

        Returns:
            Collection 名称列表
        """


class VectorStorage(Protocol):
    """向量存储协议接口。

    所有方法均为异步方法，支持向量点的增删查和 Dense/Sparse 检索。
    """

    @abstractmethod
    async def upsert_points(self, collection: str, points: list) -> bool:
        """批量插入或更新向量点。

        Args:
            collection: Collection 名称
            points: 向量点列表

        Returns:
            操作成功返回 True
        """

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list:
        """Dense 语义检索。

        Args:
            collection: Collection 名称
            query_vector: 查询向量（1024 维）
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表（按相似度降序排列）
        """

    @abstractmethod
    async def search_sparse(
        self,
        collection: str,
        sparse_vector,
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list:
        """BM25 稀疏检索。

        Args:
            collection: Collection 名称
            sparse_vector: 稀疏向量
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表
        """

    @abstractmethod
    async def delete_points(self, collection: str, point_ids: list[str]) -> bool:
        """删除向量点。

        Args:
            collection: Collection 名称
            point_ids: 要删除的向量点 ID 列表

        Returns:
            操作成功返回 True
        """

    @abstractmethod
    async def get_point(self, collection: str, point_id: str) -> dict | None:
        """获取单个向量点。

        Args:
            collection: Collection 名称
            point_id: 向量点 ID

        Returns:
            向量点数据，如果不存在则返回 None
        """
