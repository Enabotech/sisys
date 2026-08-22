"""领域层 分层检索端口契约模块（LayeredRetrievalPort）

定义分层检索（L1-L4 检索粒度）的统一抽象端口契约。
支持自顶向下（从高层级向低层级展开）与自底向上（从低层级向高层级回溯）双向遍历检索。
另提供 retrieve() 便捷方法作为统一检索入口（对齐架构 §17.1.5 RAGService 语义）。

设计决策：
- 端口统一返回 `SearchResult`（与现有 Dense/Sparse/Hybrid 检索服务签名对齐）
- `target_level` 为检索目标粒度层级字符串（"L1"/"L2"/"L3"/"L4"），默认 "L4"
- `retrieve()` 默认走 L4 粒度 + HybridSearchService 三路 RRF 融合
- 领域层零外部依赖（仅使用 Python 标准库 + SearchResult）
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l3_vector import SearchResult

# 分层检索粒度层级常量
LAYERED_RETRIEVAL_LEVELS: frozenset[str] = frozenset({"L1", "L2", "L3", "L4"})


@runtime_checkable
class LayeredRetrievalPort(Protocol):
    """分层检索端口契约

    支持不同查询粒度在 L1-L4 层之间双向遍历检索，
    同时提供统一检索入口 retrieve() 对齐架构 RAGService 语义。
    """

    async def retrieve(
        self,
        query: str,
        top_k: int = 20,
        tenant_id: str | None = None,
    ) -> list[SearchResult]:
        """统一检索入口（便捷方法）

        默认走 L4 最小粒度（实体级片段），经 HybridSearchService 三路 RRF 融合。
        相当于 search_top_down(query_text=query, target_level="L4", limit=top_k, tenant_id=tenant_id)。

        对齐架构设计 §17.1.5 RAGService.retrieve() 语义：
        输入 query + top_k → 返回按相关性排序的相关文档列表。
        是分层检索能力的"快路径"，供 RAG 管线/用例直接调用，无需感知 L1-L4 层级语义。

        Args:
            query: 检索查询文本
            top_k: 返回结果数量上限，默认 20
            tenant_id: 租户 ID（用于多租户隔离）

        Returns:
            按相关性降序排列的检索结果列表
        """
        ...

    async def search_top_down(
        self,
        query_text: str,
        target_level: str = "L4",
        collection: str = "documents",
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """自顶向下遍历检索

        从高层级检索结果向低层级展开（如 L3 Parent 命中 → L4 Child 展开）。

        Args:
            query_text: 查询文本
            target_level: 检索目标粒度层级（"L1"/"L2"/"L3"/"L4"），默认 "L4"
            collection: Collection 名称
            limit: 返回结果数量限制
            tenant_id: 租户 ID（自动注入到 filter）
            filter_payload: Payload 过滤条件

        Returns:
            按相关性降序排列的检索结果列表（list[SearchResult]）

        Raises:
            ValidationError: 查询文本为空、Collection 名称为空或 limit 无效时
            LevelTransitionError: 目标层级遍历路径非法时
        """
        ...

    async def search_bottom_up(
        self,
        query_text: str,
        target_level: str = "L4",
        collection: str = "documents",
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """自底向上遍历检索

        从低层级检索结果向高层级回溯（如 L4 Child 命中 → L3 Parent 回溯）。

        Args:
            query_text: 查询文本
            target_level: 检索目标粒度层级（"L1"/"L2"/"L3"/"L4"），默认 "L4"
            collection: Collection 名称
            limit: 返回结果数量限制
            tenant_id: 租户 ID（自动注入到 filter）
            filter_payload: Payload 过滤条件

        Returns:
            按相关性降序排列的检索结果列表（list[SearchResult]）

        Raises:
            ValidationError: 查询文本为空、Collection 名称为空或 limit 无效时
            LevelTransitionError: 目标层级遍历路径非法时
        """
        ...
