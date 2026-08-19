"""HybridSearchService 单元测试

验证混合检索编排：三路并行检索 + 加权 RRF 融合 + 降级策略 + 重排序集成。
使用 mock 隔离 DenseSemanticSearchService、Bm25SparseSearchService、GraphSearchService 和 RRF fuse。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.hybrid_search_service import HybridSearchService
from src.domain.exceptions import HybridSearchError, ValidationError
from src.domain.ports.l3_vector import SearchResult


def _make_mock_dense_service(
    results: list[SearchResult] | None = None,
    side_effect: Exception | None = None,
) -> AsyncMock:
    """构造 mock DenseSemanticSearchService"""
    from src.application.services.dense_search_service import DenseSemanticSearchService

    mock = AsyncMock(spec=DenseSemanticSearchService)
    if side_effect:
        mock.search.side_effect = side_effect
    else:
        mock.search.return_value = results or []
    return mock


def _make_mock_sparse_service(
    results: list[SearchResult] | None = None,
    side_effect: Exception | None = None,
) -> AsyncMock:
    """构造 mock Bm25SparseSearchService"""
    from src.application.services.sparse_search_service import Bm25SparseSearchService

    mock = AsyncMock(spec=Bm25SparseSearchService)
    if side_effect:
        mock.search.side_effect = side_effect
    else:
        mock.search.return_value = results or []
    return mock


def _make_mock_graph_service(
    results: list[SearchResult] | None = None,
    side_effect: Exception | None = None,
) -> AsyncMock:
    """构造 mock GraphSearchService"""
    from src.application.services.graph_search_service import GraphSearchService

    mock = AsyncMock(spec=GraphSearchService)
    if side_effect:
        mock.search.side_effect = side_effect
    else:
        mock.search.return_value = results or []
    return mock


def _make_hybrid_service(
    dense_service: AsyncMock | None = None,
    sparse_service: AsyncMock | None = None,
    graph_service: AsyncMock | None = None,
    fuse_fn: MagicMock | None = None,
    weights: list[float] | None = None,
    reranker: Any | None = None,
) -> HybridSearchService:
    """构造测试用 HybridSearchService"""
    from src.domain.services.rrf_fusion import fuse as real_fuse

    return HybridSearchService(
        dense_search=dense_service or _make_mock_dense_service(),
        sparse_search=sparse_service or _make_mock_sparse_service(),
        fuse=fuse_fn or MagicMock(wraps=real_fuse),
        graph_search=graph_service,
        weights=weights or [1.0, 1.0, 0.5],
        reranker=reranker,
    )


class TestHybridSearchServiceBasic:
    """基本混合检索流程"""

    @pytest.mark.asyncio
    async def test_search_calls_all_services(self) -> None:
        """search() 应同时调用 dense、sparse 和 graph 服务"""
        dense_mock = _make_mock_dense_service([SearchResult(id="doc1", score=0.95, payload={})])
        sparse_mock = _make_mock_sparse_service([SearchResult(id="doc2", score=8.0, payload={})])
        graph_mock = _make_mock_graph_service([SearchResult(id="doc3", score=0.5, payload={})])
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
        )

        await service.search("test_collection", "查询文本")

        dense_mock.search.assert_called_once()
        sparse_mock.search.assert_called_once()
        graph_mock.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_three_way_fusion_default_weights(self) -> None:
        """三路均成功，默认权重 [1.0, 1.0, 0.5] 融合正确"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={"title": "d1"})]
        sparse_results = [SearchResult(id="doc2", score=8.0, payload={"title": "d2"})]
        graph_results = [SearchResult(id="doc3", score=0.5, payload={"title": "d3"})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(sparse_results)
        graph_mock = _make_mock_graph_service(graph_results)
        fuse_mock = MagicMock(return_value=dense_results + sparse_results + graph_results)
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
            fuse_fn=fuse_mock,
        )

        result = await service.search("test_collection", "查询文本")

        fuse_mock.assert_called_once()
        call_args = fuse_mock.call_args[0]
        assert len(call_args) == 3  # 三路结果
        assert result is not None

    @pytest.mark.asyncio
    async def test_custom_weights_via_search(self) -> None:
        """search() 方法参数权重覆盖构造参数权重"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        sparse_results = [SearchResult(id="doc2", score=8.0, payload={})]
        graph_results = [SearchResult(id="doc3", score=0.5, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(sparse_results)
        graph_mock = _make_mock_graph_service(graph_results)
        fuse_mock = MagicMock(return_value=dense_results)
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
            fuse_fn=fuse_mock,
        )

        await service.search("test_collection", "查询文本", weights=[0.5, 0.3, 0.2])

        # 验证 fuse 被调用时 weights 参数为 [0.5, 0.3, 0.2]
        call_kwargs = fuse_mock.call_args.kwargs
        assert call_kwargs.get("weights") == [0.5, 0.3, 0.2]

    @pytest.mark.asyncio
    async def test_backward_compatible_two_way(self) -> None:
        """向后兼容：两路注入时保持原有行为"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        sparse_results = [SearchResult(id="doc2", score=8.0, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(sparse_results)
        fuse_mock = MagicMock(return_value=dense_results)
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            fuse_fn=fuse_mock,
        )

        result = await service.search("test_collection", "查询文本")

        fuse_mock.assert_called_once()
        call_args = fuse_mock.call_args[0]
        assert len(call_args) == 2  # 两路结果
        assert result is not None


class TestHybridSearchServiceValidation:
    """输入验证"""

    @pytest.mark.asyncio
    async def test_raises_on_empty_query(self) -> None:
        """空查询文本应抛出 ValidationError"""
        service = _make_hybrid_service()
        with pytest.raises(ValidationError, match="查询文本不能为空"):
            await service.search("test_collection", "")

    @pytest.mark.asyncio
    async def test_raises_on_whitespace_query(self) -> None:
        """纯空白查询文本应抛出 ValidationError"""
        service = _make_hybrid_service()
        with pytest.raises(ValidationError, match="查询文本不能为空"):
            await service.search("test_collection", "   ")

    @pytest.mark.asyncio
    async def test_raises_on_whitespace_collection(self) -> None:
        """纯空白 collection 名称应抛出 ValidationError"""
        service = _make_hybrid_service()
        with pytest.raises(ValidationError, match="Collection 名称不能为空"):
            await service.search("   ", "查询文本")

    @pytest.mark.asyncio
    async def test_raises_on_empty_collection(self) -> None:
        """空 collection 名称应抛出 ValidationError"""
        service = _make_hybrid_service()
        with pytest.raises(ValidationError, match="Collection 名称不能为空"):
            await service.search("", "查询文本")

    @pytest.mark.asyncio
    async def test_raises_on_zero_limit(self) -> None:
        """limit=0 应抛出 ValidationError"""
        service = _make_hybrid_service()
        with pytest.raises(ValidationError, match="limit 必须为正整数"):
            await service.search("test_collection", "查询文本", limit=0)

    @pytest.mark.asyncio
    async def test_raises_on_negative_limit(self) -> None:
        """负数 limit 应抛出 ValidationError"""
        service = _make_hybrid_service()
        with pytest.raises(ValidationError, match="limit 必须为正整数"):
            await service.search("test_collection", "查询文本", limit=-1)


class TestHybridSearchServiceDegradation:
    """降级策略"""

    @pytest.mark.asyncio
    async def test_dense_failure_two_way_weights_correct(self) -> None:
        """Dense 失败 → 降级两路（Sparse + Graph），权重应为 [1.0, 0.5] 而非前缀截断 [1.0, 1.0]"""
        sparse_results = [SearchResult(id="doc2", score=8.0, payload={})]
        graph_results = [SearchResult(id="doc3", score=0.5, payload={})]
        dense_mock = _make_mock_dense_service(side_effect=RuntimeError("Dense 不可用"))
        sparse_mock = _make_mock_sparse_service(sparse_results)
        graph_mock = _make_mock_graph_service(graph_results)
        fuse_mock = MagicMock(return_value=sparse_results + graph_results)
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
            fuse_fn=fuse_mock,
        )

        await service.search("test_collection", "查询文本")

        fuse_mock.assert_called_once()
        call_args = fuse_mock.call_args[0]
        assert len(call_args) == 2  # Sparse + Graph 两路
        # 权重必须按通道映射：[sparse=1.0, graph=0.5]，而非截断 [1.0, 1.0]
        assert fuse_mock.call_args.kwargs.get("weights") == [1.0, 0.5]

    @pytest.mark.asyncio
    async def test_sparse_failure_two_way_weights_correct(self) -> None:
        """Sparse 失败 → 降级两路（Dense + Graph），权重应为 [1.0, 0.5] 而非前缀截断 [1.0, 1.0]"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        graph_results = [SearchResult(id="doc3", score=0.5, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(side_effect=RuntimeError("Sparse 不可用"))
        graph_mock = _make_mock_graph_service(graph_results)
        fuse_mock = MagicMock(return_value=dense_results + graph_results)
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
            fuse_fn=fuse_mock,
        )

        await service.search("test_collection", "查询文本")

        fuse_mock.assert_called_once()
        call_args = fuse_mock.call_args[0]
        assert len(call_args) == 2  # Dense + Graph 两路
        # 权重必须按通道映射：[dense=1.0, graph=0.5]，而非截断 [1.0, 1.0]
        assert fuse_mock.call_args.kwargs.get("weights") == [1.0, 0.5]

    @pytest.mark.asyncio
    async def test_graph_failure_two_way_weights_correct(self) -> None:
        """Graph 失败 → 降级两路（Dense + Sparse），权重应为 [1.0, 1.0]（回归验证）"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        sparse_results = [SearchResult(id="doc2", score=8.0, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(sparse_results)
        graph_mock = _make_mock_graph_service(side_effect=RuntimeError("Graph 不可用"))
        fuse_mock = MagicMock(return_value=dense_results + sparse_results)
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
            fuse_fn=fuse_mock,
        )

        await service.search("test_collection", "查询文本")

        fuse_mock.assert_called_once()
        assert fuse_mock.call_args.kwargs.get("weights") == [1.0, 1.0]

    @pytest.mark.asyncio
    async def test_graph_failure_degrade_to_two_way(self) -> None:
        """Graph 通道失败 → 降级为两路（Dense + Sparse）融合"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        sparse_results = [SearchResult(id="doc2", score=8.0, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(sparse_results)
        graph_mock = _make_mock_graph_service(side_effect=RuntimeError("Graph 不可用"))
        fuse_mock = MagicMock(return_value=dense_results + sparse_results)
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
            fuse_fn=fuse_mock,
        )

        result = await service.search("test_collection", "查询文本")

        # 验证 fuse 只收到两路结果
        call_args = fuse_mock.call_args[0]
        assert len(call_args) == 2
        assert result is not None

    @pytest.mark.asyncio
    async def test_dense_and_sparse_fail_degrade_to_graph(self) -> None:
        """Dense + Sparse 均失败 → 降级为单路 Graph 结果"""
        graph_results = [SearchResult(id="doc3", score=0.5, payload={})]
        dense_mock = _make_mock_dense_service(side_effect=RuntimeError("Dense 不可用"))
        sparse_mock = _make_mock_sparse_service(side_effect=RuntimeError("Sparse 不可用"))
        graph_mock = _make_mock_graph_service(graph_results)
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
        )

        result = await service.search("test_collection", "查询文本")

        assert result == graph_results

    @pytest.mark.asyncio
    async def test_three_way_all_fail_raises_hybrid_search_error(self) -> None:
        """三路均失败 → 抛出 HybridSearchError（替换 RuntimeError）"""
        dense_mock = _make_mock_dense_service(side_effect=RuntimeError("Dense 不可用"))
        sparse_mock = _make_mock_sparse_service(side_effect=RuntimeError("Sparse 不可用"))
        graph_mock = _make_mock_graph_service(side_effect=RuntimeError("Graph 不可用"))
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
        )

        with pytest.raises(HybridSearchError, match="三路检索通道均失败"):
            await service.search("test_collection", "查询文本")

    @pytest.mark.asyncio
    async def test_graph_empty_results_not_degraded(self) -> None:
        """Graph 空结果（非失败）正常参与 RRF 融合"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service([])
        graph_mock = _make_mock_graph_service([])
        fuse_mock = MagicMock(return_value=dense_results)
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
            fuse_fn=fuse_mock,
        )

        await service.search("test_collection", "查询文本")

        fuse_mock.assert_called_once()
        call_args = fuse_mock.call_args[0]
        assert len(call_args) == 3  # 三路空列表也传入 fuse

    @pytest.mark.asyncio
    async def test_sparse_failure_degrade_to_dense_only(self) -> None:
        """Sparse 通道失败 → 降级为 Dense-only 结果"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(side_effect=RuntimeError("Sparse API 不可用"))
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock)

        result = await service.search("test_collection", "查询文本")

        assert result == dense_results[:10]

    @pytest.mark.asyncio
    async def test_dense_failure_degrade_to_sparse_only(self) -> None:
        """Dense 通道失败 → 降级为 Sparse-only 结果"""
        sparse_results = [SearchResult(id="doc2", score=8.0, payload={})]
        dense_mock = _make_mock_dense_service(side_effect=RuntimeError("Dense API 不可用"))
        sparse_mock = _make_mock_sparse_service(sparse_results)
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock)

        result = await service.search("test_collection", "查询文本")

        assert result == sparse_results[:10]

    @pytest.mark.asyncio
    async def test_both_failures_two_way_raise_hybrid_search_error(self) -> None:
        """两路（无 Graph）均失败 → 抛出 HybridSearchError"""
        dense_mock = _make_mock_dense_service(side_effect=RuntimeError("Dense 不可用"))
        sparse_mock = _make_mock_sparse_service(side_effect=RuntimeError("Sparse 不可用"))
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock)

        with pytest.raises(HybridSearchError, match="三路检索通道均失败"):
            await service.search("test_collection", "查询文本")


class TestHybridSearchServiceReranker:
    """重排序集成"""

    @pytest.mark.asyncio
    async def test_reranker_called_on_fused_results(self) -> None:
        """重排序器在 RRF 融合后被调用"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        sparse_results = [SearchResult(id="doc2", score=8.0, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(sparse_results)
        reranker_mock = AsyncMock()
        reranker_mock.rerank.return_value = dense_results + sparse_results
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            reranker=reranker_mock,
        )

        await service.search("test_collection", "查询文本")

        reranker_mock.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_reranker_failure_fallback_to_rrf(self) -> None:
        """重排序失败时降级返回原始 RRF 融合结果"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service([])
        reranker_mock = AsyncMock()
        reranker_mock.rerank.side_effect = RuntimeError("重排序不可用")
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            reranker=reranker_mock,
        )

        result = await service.search("test_collection", "查询文本")

        assert result is not None


class TestHybridSearchServiceAsyncioGather:
    """并行执行验证"""

    @pytest.mark.asyncio
    async def test_all_services_called_after_completion(self) -> None:
        """三路服务在 search() 返回前均已调用"""
        dense_mock = _make_mock_dense_service([SearchResult(id="d", score=0.9, payload={})])
        sparse_mock = _make_mock_sparse_service([SearchResult(id="s", score=8.0, payload={})])
        graph_mock = _make_mock_graph_service([SearchResult(id="g", score=0.5, payload={})])
        service = _make_hybrid_service(
            dense_service=dense_mock,
            sparse_service=sparse_mock,
            graph_service=graph_mock,
        )

        await service.search("test_collection", "查询文本")

        dense_mock.search.assert_called_once()
        sparse_mock.search.assert_called_once()
        graph_mock.search.assert_called_once()
