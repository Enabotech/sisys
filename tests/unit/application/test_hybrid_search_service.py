"""HybridSearchService 单元测试

验证混合检索编排：并行检索 + RRF 融合 + 降级策略。
使用 mock 隔离 DenseSemanticSearchService、Bm25SparseSearchService 和 RRF fuse 函数。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.hybrid_search_service import HybridSearchService
from src.domain.exceptions import ValidationError
from src.domain.ports.l3_vector import SearchResult


def _make_mock_dense_service(
    results: list[SearchResult] | None = None,
    side_effect: Exception | None = None,
) -> AsyncMock:
    """构造 mock DenseSemanticSearchService"""
    mock = AsyncMock()
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
    mock = AsyncMock()
    if side_effect:
        mock.search.side_effect = side_effect
    else:
        mock.search.return_value = results or []
    return mock


def _make_hybrid_service(
    dense_service: AsyncMock | None = None,
    sparse_service: AsyncMock | None = None,
    fuse_fn: MagicMock | None = None,
) -> HybridSearchService:
    """构造测试用 HybridSearchService"""
    from src.domain.services.rrf_fusion import fuse as real_fuse

    return HybridSearchService(
        dense_search=dense_service or _make_mock_dense_service(),
        sparse_search=sparse_service or _make_mock_sparse_service(),
        fuse=fuse_fn or MagicMock(wraps=real_fuse),
    )


class TestHybridSearchServiceBasic:
    """基本混合检索流程"""

    @pytest.mark.asyncio
    async def test_search_calls_both_services(self) -> None:
        """search() 应同时调用 dense 和 sparse 服务"""
        dense_mock = _make_mock_dense_service([SearchResult(id="doc1", score=0.95, payload={})])
        sparse_mock = _make_mock_sparse_service([SearchResult(id="doc2", score=8.0, payload={})])
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock)

        await service.search("test_collection", "查询文本")

        dense_mock.search.assert_called_once()
        sparse_mock.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_calls_fuse_with_both_results(self) -> None:
        """search() 应将两路结果传入 fuse"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={"title": "d1"})]
        sparse_results = [SearchResult(id="doc2", score=8.0, payload={"title": "d2"})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(sparse_results)
        fuse_mock = MagicMock(return_value=dense_results)
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock, fuse_fn=fuse_mock)

        result = await service.search("test_collection", "查询文本")

        fuse_mock.assert_called_once()
        call_args = fuse_mock.call_args[0]
        assert len(call_args) == 2  # 两路结果
        assert result == dense_results  # 返回 fuse 结果

    @pytest.mark.asyncio
    async def test_search_passes_parameters_correctly(self) -> None:
        """search() 应将参数正确传递给两路服务"""
        dense_mock = _make_mock_dense_service()
        sparse_mock = _make_mock_sparse_service()
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock)

        await service.search(
            "my_collection",
            "my query",
            limit=20,
            tenant_id="tenant-abc",
            filter_payload={"domain": "finance"},
        )

        # 验证 Dense 调用参数（_safe_dense_search 使用位置参数）
        d_args = dense_mock.search.call_args[0]
        assert d_args[0] == "my_collection"
        assert d_args[1] == "my query"
        assert d_args[2] == 20
        assert d_args[3] == "tenant-abc"
        assert d_args[4] == {"domain": "finance"}

        # 验证 Sparse 调用参数
        s_args = sparse_mock.search.call_args[0]
        assert s_args[0] == "my_collection"
        assert s_args[1] == "my query"
        assert s_args[2] == 20
        assert s_args[3] == "tenant-abc"
        assert s_args[4] == {"domain": "finance"}


class TestHybridSearchServiceValidation:
    """输入验证（与 Dense/Sparse 服务一致）"""

    @pytest.mark.asyncio
    async def test_raises_on_empty_query(self) -> None:
        """空查询文本应抛出 ValidationError"""
        service = _make_hybrid_service()
        with pytest.raises(ValidationError, match="查询文本不能为空"):
            await service.search("test_collection", "")

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


class TestHybridSearchServiceDegradation:
    """降级策略（AC-6）"""

    @pytest.mark.asyncio
    async def test_sparse_failure_degrade_to_dense_only(self) -> None:
        """Sparse 通道失败 → 降级为 Dense-only 结果"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={"title": "d1"})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(side_effect=RuntimeError("Sparse API 不可用"))
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock)

        result = await service.search("test_collection", "查询文本")

        assert result == dense_results

    @pytest.mark.asyncio
    async def test_dense_failure_degrade_to_sparse_only(self) -> None:
        """Dense 通道失败 → 降级为 Sparse-only 结果"""
        sparse_results = [SearchResult(id="doc2", score=8.0, payload={"title": "d2"})]
        dense_mock = _make_mock_dense_service(side_effect=RuntimeError("Dense API 不可用"))
        sparse_mock = _make_mock_sparse_service(sparse_results)
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock)

        result = await service.search("test_collection", "查询文本")

        assert result == sparse_results

    @pytest.mark.asyncio
    async def test_both_failures_raise_runtime_error(self) -> None:
        """两路均失败 → 抛出 RuntimeError"""
        dense_mock = _make_mock_dense_service(side_effect=RuntimeError("Dense 不可用"))
        sparse_mock = _make_mock_sparse_service(side_effect=RuntimeError("Sparse 不可用"))
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock)

        with pytest.raises(RuntimeError, match="Dense 和 Sparse 检索通道均失败"):
            await service.search("test_collection", "查询文本")

    @pytest.mark.asyncio
    async def test_sparse_embed_timeout_degrade_to_dense(self) -> None:
        """Sparse 嵌入超时 → 降级为 Dense-only"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service(side_effect=asyncio.TimeoutError("超时"))
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock)

        result = await service.search("test_collection", "查询文本")

        assert result == dense_results

    @pytest.mark.asyncio
    async def test_empty_search_sparse_results_not_degraded(self) -> None:
        """Sparse 检索空结果（非失败）正常参与 RRF 融合"""
        dense_results = [SearchResult(id="doc1", score=0.95, payload={})]
        dense_mock = _make_mock_dense_service(dense_results)
        sparse_mock = _make_mock_sparse_service([])  # 正常返回空列表
        fuse_mock = MagicMock(return_value=dense_results)
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock, fuse_fn=fuse_mock)

        await service.search("test_collection", "查询文本")

        # fuse 仍然被调用（空列表也是有效输入）
        fuse_mock.assert_called_once()
        call_args = fuse_mock.call_args[0]
        assert call_args[1] == []  # Sparse 结果为空列表


class TestHybridSearchServiceAsyncioGather:
    """并行执行验证"""

    @pytest.mark.asyncio
    async def test_both_services_called_after_completion(self) -> None:
        """两路服务在 search() 返回前均已调用"""
        dense_mock = _make_mock_dense_service([SearchResult(id="d", score=0.9, payload={})])
        sparse_mock = _make_mock_sparse_service([SearchResult(id="s", score=8.0, payload={})])
        service = _make_hybrid_service(dense_service=dense_mock, sparse_service=sparse_mock)

        await service.search("test_collection", "查询文本")

        dense_mock.search.assert_called_once()
        sparse_mock.search.assert_called_once()
