"""应用层混合检索编排服务

编排 Dense 语义检索、Sparse 稀疏检索和 Graph 图检索三个通道，
通过 asyncio.gather 并行执行，RRF 融合后返回统一排序结果，可选重排序。

降级策略：
- 三路均成功 → 三路加权 RRF 融合
- Graph 失败 → 两路（Dense + Sparse）RRF 融合，WARNING 日志
- Dense + Sparse 均失败 → 单路 Graph 结果
- 三路均失败 → HybridSearchError（替换 RuntimeError 历史违规）

依赖注入：
- DenseSemanticSearchService（外部构造）
- Bm25SparseSearchService（外部构造）
- GraphSearchService（可选，第三路信号）
- fuse 可调用对象（from src.domain.services.rrf_fusion import fuse）
- RerankerPort（可选，重排序）
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from src.domain.exceptions import HybridSearchError, ValidationError
from src.domain.ports.hybrid_search import HybridSearchPort
from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.reranker import RerankerPort
from src.domain.ports.search_service import DenseSearchPort, GraphSearchPort, SparseSearchPort

logger = logging.getLogger(__name__)

# 默认三路权重 [dense, sparse, graph]（不可变元组，避免模块级列表被误修改）
_DEFAULT_WEIGHTS: tuple[float, ...] = (1.0, 1.0, 0.5)


class HybridSearchService(HybridSearchPort):
    """混合检索编排服务

    注入 DenseSemanticSearchService、Bm25SparseSearchService、GraphSearchService
    和 RRF fuse 可调用对象。search() 签名与两路服务一致。
    """

    def __init__(
        self,
        dense_search: DenseSearchPort,
        sparse_search: SparseSearchPort,
        fuse: Callable[..., list[SearchResult]],
        graph_search: GraphSearchPort | None = None,
        weights: list[float] | None = None,
        reranker: RerankerPort | None = None,
    ) -> None:
        """初始化混合检索服务

        Args:
            dense_search: Dense 语义检索服务
            sparse_search: BM25 稀疏检索服务
            fuse: RRF 融合函数
            graph_search: Graph 检索服务（可选，第三路信号）
            weights: 三路权重 [dense, sparse, graph]，默认 [1.0, 1.0, 0.5]
            reranker: 重排序器（可选，对 RRF 融合结果进行精排）
        """
        self._dense = dense_search
        self._sparse = sparse_search
        self._graph = graph_search
        self._fuse = fuse
        self._weights = list(weights) if weights is not None else list(_DEFAULT_WEIGHTS)
        self._reranker = reranker

    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
        weights: list[float] | None = None,
    ) -> list[SearchResult]:
        """执行混合检索（Dense + Sparse + Graph → RRF 融合 → 可选重排序）

        使用 asyncio.gather 并行执行三路检索，RRF 融合后返回统一排序结果。

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID（自动注入到 filter）
            filter_payload: Payload 过滤条件
            weights: 单次查询权重覆盖（可选，覆盖构造参数）

        Returns:
            RRF 融合后的统一排序结果列表

        Raises:
            ValidationError: 查询文本为空、Collection 名称为空或 limit 无效时
            HybridSearchError: 三路检索通道均失败时
        """
        # 输入验证
        if not query_text or not query_text.strip():
            raise ValidationError(message="查询文本不能为空")
        if not collection or not collection.strip():
            raise ValidationError(message="Collection 名称不能为空")
        if limit < 1:
            raise ValidationError(message=f"limit 必须为正整数，当前值: {limit}")

        # 并行执行三路检索
        tasks = [
            asyncio.create_task(self._safe_dense_search(collection, query_text, limit, tenant_id, filter_payload)),
            asyncio.create_task(self._safe_sparse_search(collection, query_text, limit, tenant_id, filter_payload)),
        ]

        if self._graph is not None:
            tasks.append(asyncio.create_task(self._safe_graph_search(collection, query_text, limit, tenant_id, filter_payload)))

        results = await asyncio.gather(*tasks)

        dense_raw, sparse_raw = results[0], results[1]
        graph_raw = results[2] if len(results) > 2 else None

        # 降级判断：使用 isinstance 类型守卫而非 assert（assert 在 -O 模式下被禁用）
        dense_failed = not isinstance(dense_raw, list)
        sparse_failed = not isinstance(sparse_raw, list)
        graph_failed = graph_raw is not None and not isinstance(graph_raw, list)

        # 三路均失败 → HybridSearchError（替换 RuntimeError 历史违规）
        if dense_failed and sparse_failed and (graph_failed or self._graph is None):
            raise HybridSearchError("三路检索通道均失败")

        # 确定有效结果列表
        result_lists: list[list[SearchResult]] = []

        if not dense_failed and isinstance(dense_raw, list):
            result_lists.append(dense_raw)
        if not sparse_failed and isinstance(sparse_raw, list):
            result_lists.append(sparse_raw)
        if graph_raw is not None and not graph_failed and isinstance(graph_raw, list):
            result_lists.append(graph_raw)

        # 降级：Dense + Sparse 均失败 → 单路 Graph 结果
        if dense_failed and sparse_failed and graph_raw is not None and not graph_failed and isinstance(graph_raw, list):
            logger.warning("Dense 和 Sparse 检索通道均失败，降级为 Graph-only 结果")
            return graph_raw[:limit]

        # 降级：单路失败 → 记录日志（仅记录异常类型与摘要，避免完整异常串带来的日志注入风险）
        if dense_failed:
            logger.warning("Dense 检索通道失败，降级为两路融合: %s: %s", type(dense_raw).__name__, str(dense_raw)[:200])
        if sparse_failed:
            logger.warning("Sparse 检索通道失败，降级为两路融合: %s: %s", type(sparse_raw).__name__, str(sparse_raw)[:200])
        if graph_failed:
            logger.warning("Graph 检索通道失败，降级为两路融合: %s: %s", type(graph_raw).__name__, str(graph_raw)[:200])

        # 应用有效权重（按通道索引映射，而非前缀截断）
        # 显式 is None 判空：weights=[]（空覆盖）不再静默回退默认权重，
        # 由下游 fuse 的权重长度校验显式拒绝不匹配场景
        all_weights = self._weights if weights is None else weights
        channel_active = [
            not dense_failed,  # dense 通道状态
            not sparse_failed,  # sparse 通道状态
            self._graph is not None and not graph_failed,  # graph 通道状态
        ]
        effective_weights = [w for w, active in zip(all_weights, channel_active) if active]

        # RRF 融合（单路时 fuse 内部直接透传，跳过融合）
        fused = self._fuse(*result_lists, weights=effective_weights)

        # 可选重排序
        if self._reranker is not None and fused:
            try:
                top_k = min(limit * 2, 20)
                fused = await self._reranker.rerank(query_text, fused, top_k=top_k)
            except Exception as e:
                logger.warning("重排序失败，降级返回 RRF 融合结果: %s", e)

        # 按 limit 截断
        return fused[:limit]

    async def _safe_dense_search(
        self,
        collection: str,
        query_text: str,
        limit: int,
        tenant_id: str | None,
        filter_payload: dict | None,
    ) -> list[SearchResult] | Exception:
        """安全执行 Dense 检索"""
        try:
            result: list[SearchResult] | Exception
            result = await self._dense.search(
                collection,
                query_text,
                limit,
                tenant_id,
                filter_payload,
            )
            return result
        except Exception as e:
            return e

    async def _safe_sparse_search(
        self,
        collection: str,
        query_text: str,
        limit: int,
        tenant_id: str | None,
        filter_payload: dict | None,
    ) -> list[SearchResult] | Exception:
        """安全执行 Sparse 检索"""
        try:
            result: list[SearchResult] | Exception
            result = await self._sparse.search(
                collection,
                query_text,
                limit,
                tenant_id,
                filter_payload,
            )
            return result
        except Exception as e:
            return e

    async def _safe_graph_search(
        self,
        collection: str,
        query_text: str,
        limit: int,
        tenant_id: str | None,
        filter_payload: dict | None,
    ) -> list[SearchResult] | Exception:
        """安全执行 Graph 检索"""
        if self._graph is None:
            # 防御性检查：该分支仅在 Graph 通道未注入时触发（正常路径在调用前已过滤）
            return HybridSearchError("Graph 检索服务未注入")
        try:
            result: list[SearchResult] | Exception = await self._graph.search(
                collection, query_text, limit, tenant_id, filter_payload
            )
            return result
        except Exception as e:
            return e
