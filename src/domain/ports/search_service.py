"""领域层基础检索端口契约模块（R1 基础端口）

定义统一检索端口 SearchServicePort 及其子类型端口。
遵循 R1：领域层统一抽象各类基础端口。

端口层次：
    SearchServicePort（基础检索端口）
    ├── DenseSearchPort（Dense 语义检索）
    ├── SparseSearchPort（BM25 稀疏检索）
    └── GraphSearchPort（Graph 图检索）

设计决策：
- 所有检索端口统一返回 `SearchResult`（与 Dense/Sparse/Hybrid 现有签名对齐）
- 输入参数签名统一（collection/query_text/limit/tenant_id/filter_payload）
- 领域层零外部依赖（仅使用 Python 标准库 + SearchResult）
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l3_vector import SearchResult


@runtime_checkable
class SearchServicePort(Protocol):
    """R1: 基础检索端口 — 统一检索签名

    所有检索服务（Dense/Sparse/Graph）共享的统一接口契约。
    对应 architecture.md §17.1.5 混合检索架构的领域层抽象。
    """

    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """执行检索

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID（自动注入到 filter）
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表，按相关性降序排列

        Raises:
            ValidationError: 查询文本为空、Collection 名称为空或 limit 无效时
        """
        ...


@runtime_checkable
class DenseSearchPort(SearchServicePort, Protocol):
    """Dense 语义检索端口（继承基础检索端口）

    对应 Story 3.1a：bge-m3 嵌入 + 余弦相似度检索。
    编排 EmbeddingServicePort（文本→向量）和 L3VectorPort（向量→检索）。
    """

    pass


@runtime_checkable
class SparseSearchPort(SearchServicePort, Protocol):
    """BM25 稀疏检索端口（继承基础检索端口）

    对应 Story 3.1b：BM25 关键词检索。
    编排 EmbeddingServicePort（文本→稀疏向量）和 L3VectorPort（稀疏向量→检索）。
    """

    pass


@runtime_checkable
class GraphSearchPort(SearchServicePort, Protocol):
    """Graph 图检索端口（继承基础检索端口）

    对应 Story 3.4：知识图谱实体关联检索。
    通过 L5GraphPort 搜索实体语义，聚合关联文档，作为第三路检索信号。
    """

    pass


__all__ = [
    "SearchServicePort",
    "DenseSearchPort",
    "SparseSearchPort",
    "GraphSearchPort",
]
