"""应用层混合检索编排服务

编排 Dense 语义检索和 Sparse 稀疏检索两个通道，
通过 asyncio.gather 并行执行，RRF 融合后返回统一排序结果。

降级策略：
- 单路失败 → WARNING 日志 + 降级为单路结果
- 两路均失败 → RuntimeError
- Sparse 空结果（非异常）→ 正常参与 RRF 融合（空列表）

依赖注入：
- DenseSemanticSearchService（外部构造）
- Bm25SparseSearchService（外部构造）
- fuse 可调用对象（from src.domain.services.rrf_fusion import fuse）
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from src.application.services.dense_search_service import DenseSemanticSearchService
from src.application.services.sparse_search_service import Bm25SparseSearchService
from src.domain.exceptions import ValidationError
from src.domain.ports.l3_vector import SearchResult

logger = logging.getLogger(__name__)


class HybridSearchService:
    """混合检索编排服务

    注入 DenseSemanticSearchService、Bm25SparseSearchService 和 RRF fuse 可调用对象。
    search(collection, query_text, limit, tenant_id, filter_payload) 签名与两路服务一致。
    """

    def __init__(
        self,
        dense_search: DenseSemanticSearchService,
        sparse_search: Bm25SparseSearchService,
        fuse: Callable[..., list[SearchResult]],
    ) -> None:
        """初始化混合检索服务

        Args:
            dense_search: Dense 语义检索服务
            sparse_search: BM25 稀疏检索服务
            fuse: RRF 融合函数（可调用对象，from src.domain.services.rrf_fusion import fuse）
        """
        self._dense = dense_search
        self._sparse = sparse_search
        self._fuse = fuse

    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """执行混合检索（Dense + Sparse → RRF 融合）

        使用 asyncio.gather 并行执行两路检索，RRF 融合后返回统一排序结果。

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID（自动注入到 filter）
            filter_payload: Payload 过滤条件

        Returns:
            RRF 融合后的统一排序结果列表

        Raises:
            ValidationError: 查询文本为空、Collection 名称为空或 limit 无效时
            RuntimeError: Dense 和 Sparse 检索通道均失败时
        """
        # 输入验证（与 Dense/Sparse 服务一致）
        if not query_text or not query_text.strip():
            raise ValidationError(message="查询文本不能为空")
        if not collection or not collection.strip():
            raise ValidationError(message="Collection 名称不能为空")
        if limit < 1:
            raise ValidationError(message=f"limit 必须为正整数，当前值: {limit}")

        # 并行执行两路检索
        dense_task = asyncio.create_task(self._safe_dense_search(collection, query_text, limit, tenant_id, filter_payload))
        sparse_task = asyncio.create_task(self._safe_sparse_search(collection, query_text, limit, tenant_id, filter_payload))

        dense_raw, sparse_raw = await asyncio.gather(dense_task, sparse_task)

        # 降级判断：两路均失败
        dense_failed = isinstance(dense_raw, Exception)
        sparse_failed = isinstance(sparse_raw, Exception)
        if dense_failed and sparse_failed:
            raise RuntimeError("Dense 和 Sparse 检索通道均失败")

        # 降级：单路失败 → 返回另一路结果
        if dense_failed:
            logger.warning("Dense 检索通道失败，降级为 Sparse-only 结果: %s", dense_raw)
            assert not isinstance(sparse_raw, Exception)  # 已验证 sparse_failed is False
            return sparse_raw

        if sparse_failed:
            logger.warning("Sparse 检索通道失败，降级为 Dense-only 结果: %s", sparse_raw)
            assert not isinstance(dense_raw, Exception)  # dense_failed is False
            return dense_raw

        # 两路均成功 → RRF 融合
        fused = self._fuse(dense_raw, sparse_raw)

        # 按 limit 截断结果
        return fused[:limit]

    async def _safe_dense_search(
        self,
        collection: str,
        query_text: str,
        limit: int,
        tenant_id: str | None,
        filter_payload: dict | None,
    ) -> list[SearchResult] | Exception:
        """安全执行 Dense 检索（异常不中断并行流程）

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表或异常对象
        """
        try:
            return await self._dense.search(collection, query_text, limit, tenant_id, filter_payload)
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
        """安全执行 Sparse 检索（异常不中断并行流程）

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表或异常对象
        """
        try:
            return await self._sparse.search(collection, query_text, limit, tenant_id, filter_payload)
        except Exception as e:
            return e
