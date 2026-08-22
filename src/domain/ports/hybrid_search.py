"""领域层混合检索端口契约模块（R2 组合端口）

定义 HybridSearchPort，组合 Dense+Sparse+Graph 三路检索。
遵循 R2：应用层端口可以组合注入或继承 R1 所述端口。

设计决策：
- 组合 SearchServicePort 三个子类型（DenseSearchPort/SparseSearchPort/GraphSearchPort）
- 执行 RRF 融合排序（fuse 函数），可选重排序（RerankerPort）
- weights 参数支持单次查询权重覆盖（三路 [dense, sparse, graph]）
- 领域层零外部依赖（仅使用 Python 标准库 + SearchResult）
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l3_vector import SearchResult


@runtime_checkable
class HybridSearchPort(Protocol):
    """R2: 混合检索端口 — 组合三路检索

    组合 DenseSearchPort + SparseSearchPort + GraphSearchPort，
    通过 asyncio.gather 并行执行三路检索，RRF 融合后返回统一排序结果，
    可选重排序（RerankerPort）。

    降级策略：
    - 三路均成功 → 三路加权 RRF 融合
    - Graph 失败 → 两路（Dense + Sparse）RRF 融合
    - Dense + Sparse 均失败 → 单路 Graph 结果
    - 三路均失败 → HybridSearchError
    """

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

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID（自动注入到 filter）
            filter_payload: Payload 过滤条件
            weights: 单次查询权重覆盖（[dense, sparse, graph]）

        Returns:
            RRF 融合后的统一排序结果列表

        Raises:
            ValidationError: 查询文本为空、Collection 名称为空或 limit 无效时
            HybridSearchError: 三路检索通道均失败时
        """
        ...


__all__ = [
    "HybridSearchPort",
]
