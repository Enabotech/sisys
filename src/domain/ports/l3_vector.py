"""领域层 L3 Qdrant 向量存储抽象端口模块

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

from typing import Any, Protocol, TypedDict, runtime_checkable


class SearchResult(TypedDict):
    """统一检索结果 TypedDict

    跨 Dense/Sparse/Hybrid 三通道的标准化检索结果结构。
    与 Qdrant ScoredPoint.id 对齐（str | int），与 DenseSearchResult 接口兼容。

    Attributes:
        id: 向量点标识（Qdrant ScoredPoint 返回 str 或 int）
        score: 相似度/相关性得分
        payload: 元数据字典
    """

    id: str | int
    score: float
    payload: dict[str, Any]


@runtime_checkable
class L3VectorPort(Protocol):
    """L3 Qdrant 向量存储端口接口

    对应 architecture.md §11.1：
    - 内容 >500 tokens 时启用向量检索
    - 支持 Dense+Sparse+Payload 过滤
    """

    async def upsert_points(
        self,
        collection: str,
        points: list[dict],
    ) -> bool:
        """批量插入或更新向量点

        Args:
            collection: Collection 名称
            points: 向量点列表，每个点是 dict，需包含 id, vector, payload 字段
                   示例: [{"id": "mem-123", "vector": [0.1, 0.2], "payload": {...}}, ...]

        Returns:
            操作成功返回 True
        """

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
            query_vector: 查询向量（通常由 embedding service 生成）
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表 [{id, score, payload}, ...]
        """

    async def search_sparse(
        self,
        collection: str,
        sparse_vector: dict[str, Any],
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """BM25 稀疏检索

        对应 architecture.md §11.1 "Dense+Sparse+Payload 过滤"

        Args:
            collection: Collection 名称
            sparse_vector: 稀疏向量，可为 SparseEmbedding TypedDict 或普通 dict
                          需包含 indices 和 values 字段
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表 [{id, score, payload}, ...]
        """

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
        """

    async def delete_collection(
        self,
        collection: str,
    ) -> bool:
        """删除 Collection

        Args:
            collection: Collection 名称

        Returns:
            删除成功返回 True
        """

    async def collection_exists(
        self,
        collection: str,
    ) -> bool:
        """检查 Collection 是否存在

        Args:
            collection: Collection 名称

        Returns:
            存在返回 True
        """

    async def list_collections(
        self,
    ) -> list[str]:
        """列出所有 Collection

        Returns:
            Collection 名称列表
        """
