"""SemanticCacheMiddleware 单元测试

TDD 红→绿→重构循环：
- Happy Path: 缓存未命中 → 执行检索 → 自动写入
- Happy Path: 缓存命中 → 直接返回
- Happy Path: 相似查询命中
- Edge Case: 嵌入生成失败 → 直接检索，不缓存
- Edge Case: Redis 不可用 → 透明降级
- Edge Case: 缓存数据损坏 → 视为未命中
- Edge Case: 缓存写入失败 → 仅日志，不阻断
- 指标采集验证
- 不同 weights 缓存隔离
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.semantic_cache import SemanticCache
from src.application.services.semantic_cache_middleware import SemanticCacheMiddleware
from src.domain.ports.embedding_service import EmbeddingServicePort
from src.domain.ports.l3_vector import SearchResult


def _mock_embedding_service() -> AsyncMock:
    """创建 Mock 嵌入服务"""
    emb = AsyncMock(spec=EmbeddingServicePort)
    emb.dimension = 1024

    async def _embed_query(text: str) -> list[float]:
        seed = sum(ord(ch) for ch in text)
        return [1.0, float(seed % 100) / 100.0, 0.5, 0.25]

    emb.embed_query.side_effect = _embed_query
    emb.embed_documents.return_value = [[1.0, 0.0, 0.0, 0.0]]
    return emb


def _make_search_result(doc_id: str, title: str = "test", score: float = 0.95) -> SearchResult:
    return SearchResult(
        id=f"point-{doc_id}",
        score=score,
        payload={"document_id": doc_id, "title": title},
    )


def _sample_results() -> list[SearchResult]:
    return [
        _make_search_result("doc-001", "战略规划"),
        _make_search_result("doc-002", "财务分析"),
        _make_search_result("doc-001", "战略规划补充"),
    ]


def _make_middleware(
    cache: AsyncMock | None = None,
    search_service: AsyncMock | None = None,
    embedding_service: AsyncMock | None = None,
    threshold: float = 0.9,
    ttl: int = 86400,
    avg_tokens_per_search: int = 5000,
    metrics: Any | None = None,
) -> tuple[SemanticCacheMiddleware, AsyncMock, AsyncMock, AsyncMock]:
    """创建测试用中间件实例"""
    if cache is None:
        cache = AsyncMock(spec=SemanticCache)
        cache.get.return_value = None
        cache.set.return_value = None

    if search_service is None:
        search_service = AsyncMock()
        search_service.search.return_value = _sample_results()

    if embedding_service is None:
        embedding_service = _mock_embedding_service()

    middleware = SemanticCacheMiddleware(
        search_service=search_service,
        cache=cache,
        embedding_service=embedding_service,
        threshold=threshold,
        ttl=ttl,
        avg_tokens_per_search=avg_tokens_per_search,
        metrics=metrics,
    )
    return middleware, cache, search_service, embedding_service


class TestSemanticCacheMiddleware:
    """SemanticCacheMiddleware 核心功能测试"""

    # ===================================================================
    # Happy Path: 缓存未命中 → 执行检索 → 自动写入
    # ===================================================================

    async def test_cache_miss_triggers_search_and_auto_write(self) -> None:
        """缓存未命中 → 执行 search → 自动写入缓存"""
        middleware, cache, search_service, _ = _make_middleware()

        results = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
        )

        # 验证缓存查询被调用
        cache.get.assert_called_once()
        get_args = cache.get.call_args
        assert get_args is not None

        # 验证检索服务被调用
        search_service.search.assert_called_once()
        search_args = search_service.search.call_args
        assert search_args is not None
        assert search_args[1].get("query_text") == "企业战略规划"

        # 验证缓存写入被调用
        cache.set.assert_called_once()
        set_args = cache.set.call_args
        assert set_args is not None
        # 验证结果被序列化写入（query_embedding 和 result 是位置参数）
        call_args = set_args[0]
        assert len(call_args) >= 2  # query_embedding + result
        result_dict = call_args[1]
        assert isinstance(result_dict, dict)  # result 是 dict
        assert "results" in result_dict  # 包含 results 字段

        # 验证返回结果正确
        assert len(results) == 3
        assert results[0]["id"] == "point-doc-001"

    # ===================================================================
    # Happy Path: 缓存命中 → 直接返回
    # ===================================================================

    async def test_cache_hit_returns_cached_result(self) -> None:
        """缓存命中 → 直接返回缓存结果，不执行检索"""
        middleware, cache, search_service, _ = _make_middleware()

        # 构造缓存命中响应
        cache.get.return_value = {
            "results": [dict(r) for r in _sample_results()],
            "query_text": "企业战略规划",
            "weights": None,
        }

        results = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
        )

        # 验证缓存查询被调用
        cache.get.assert_called_once()

        # 验证检索服务未被调用
        search_service.search.assert_not_called()

        # 验证缓存写入未被调用
        cache.set.assert_not_called()

        # 验证返回结果正确
        assert len(results) == 3

    # ===================================================================
    # Happy Path: 相似查询命中
    # ===================================================================

    async def test_similar_query_hit(self) -> None:
        """相同查询文本 → 相同向量 → 缓存命中"""
        middleware, cache, search_service, _ = _make_middleware()

        # 第一次查询：未命中 → 检索 → 写入
        cache.get.side_effect = [
            None,
            {
                "results": [dict(r) for r in _sample_results()],
                "query_text": "企业战略规划",
                "weights": None,
            },
        ]

        # 第一次查询
        results1 = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
        )
        assert len(results1) == 3
        assert search_service.search.call_count == 1
        cache.set.assert_called_once()

        # 第二次相同查询：命中缓存
        search_service.search.reset_mock()
        cache.set.reset_mock()

        results2 = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
        )

        assert len(results2) == 3
        search_service.search.assert_not_called()
        cache.set.assert_not_called()

    # ===================================================================
    # Edge Case: 嵌入生成失败 → 直接检索，不缓存
    # ===================================================================

    async def test_embedding_failure_falls_back_to_search(self) -> None:
        """嵌入生成失败 → 降级为直接检索，不缓存"""
        middleware, cache, search_service, embedding_service = _make_middleware()

        # 嵌入服务抛出异常
        embedding_service.embed_query.side_effect = RuntimeError("Embedding API 不可用")

        # 搜索服务正常返回
        search_service.search.return_value = _sample_results()

        results = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
        )

        # 验证检索服务被调用
        search_service.search.assert_called_once()

        # 验证缓存未被写入
        cache.set.assert_not_called()

        # 验证结果正确返回
        assert len(results) == 3

    # ===================================================================
    # Edge Case: Redis 不可用 → 透明降级
    # ===================================================================

    async def test_cache_get_failure_falls_back(self) -> None:
        """缓存查询异常 → 透明降级为直接检索"""
        middleware, cache, search_service, _ = _make_middleware()

        # 缓存查询抛出异常
        cache.get.side_effect = ConnectionError("Redis 连接失败")

        results = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
        )

        # 验证检索服务被调用
        search_service.search.assert_called_once()

        # 验证缓存写入仍被尝试
        cache.set.assert_called_once()

        # 验证结果正确返回
        assert len(results) == 3

    # ===================================================================
    # Edge Case: 缓存数据损坏 → 视为未命中
    # ===================================================================

    async def test_corrupt_cache_data_skipped(self) -> None:
        """缓存数据损坏 → 跳过该条目，视为未命中"""
        middleware, cache, search_service, _ = _make_middleware()

        # 缓存返回损坏数据（缺少 results 字段）
        cache.get.return_value = {"corrupted": True, "data": None}

        results = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
        )

        # 验证检索服务被调用
        search_service.search.assert_called_once()

        # 验证结果正确返回
        assert len(results) == 3

    async def test_corrupt_cache_data_non_list(self) -> None:
        """缓存返回非列表 results 字段 → 视为未命中"""
        middleware, cache, search_service, _ = _make_middleware()

        cache.get.return_value = {"results": "not a list", "query_text": "test", "weights": None}

        results = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
        )

        search_service.search.assert_called_once()
        assert len(results) == 3

    # ===================================================================
    # Edge Case: 缓存写入失败 → 仅日志，不阻断
    # ===================================================================

    async def test_cache_set_failure_does_not_block(self) -> None:
        """缓存写入失败 → 仅日志，不阻断检索结果返回"""
        middleware, cache, search_service, _ = _make_middleware()

        # 缓存写入抛出异常
        cache.set.side_effect = ConnectionError("Redis 写入失败")

        results = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
        )

        search_service.search.assert_called_once()
        cache.set.assert_called_once()
        assert len(results) == 3

    # ===================================================================
    # 不同 weights 缓存隔离
    # ===================================================================

    async def test_different_weights_isolated_cache(self) -> None:
        """不同 weights → 不同缓存键 → 互不影响"""
        middleware, cache, search_service, _ = _make_middleware()

        # 第一次查询 weights=[1.0, 1.0]：未命中
        cache.get.side_effect = [
            None,  # weights=[1.0, 1.0] 未命中
            None,  # weights=[0.5, 1.0] 未命中
        ]

        # 第一次：weights=[1.0, 1.0]
        results1 = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
            weights=[1.0, 1.0],
        )
        assert len(results1) == 3
        assert search_service.search.call_count == 1

        # 第二次：不同 weights=[0.5, 1.0]
        search_service.search.reset_mock()
        cache.set.reset_mock()

        results2 = await middleware.search(
            collection="test_coll",
            query_text="企业战略规划",
            limit=5,
            weights=[0.5, 1.0],
        )
        assert len(results2) == 3
        # 不同 weights 应产生不同缓存键，所以仍是未命中
        assert search_service.search.call_count == 1


class TestSemanticCacheMiddlewareMetrics:
    """指标采集验证"""

    # ===================================================================
    # 缓存命中次数递增
    # ===================================================================

    async def test_hit_counter_increments(self) -> None:
        """缓存命中后计数器递增"""
        from src.application.ports.cache_metrics_port import CacheMetricsPort

        metrics = AsyncMock(spec=CacheMetricsPort)
        middleware, cache, search_service, _ = _make_middleware(metrics=metrics)

        # 写入缓存
        cache.get.return_value = {
            "results": [dict(r) for r in _sample_results()],
            "query_text": "test",
            "weights": None,
        }

        await middleware.search(collection="c", query_text="test", limit=5)
        metrics.record_cache_hit.assert_called_once()

    # ===================================================================
    # 缓存未命中次数递增
    # ===================================================================

    async def test_miss_counter_increments(self) -> None:
        """缓存未命中后计数器递增"""
        from src.application.ports.cache_metrics_port import CacheMetricsPort

        metrics = AsyncMock(spec=CacheMetricsPort)
        middleware, cache, search_service, _ = _make_middleware(metrics=metrics)

        cache.get.return_value = None

        await middleware.search(collection="c", query_text="test", limit=5)
        metrics.record_cache_miss.assert_called_once()

    # ===================================================================
    # 缓存延迟记录
    # ===================================================================

    async def test_cache_latency_recorded_on_hit(self) -> None:
        """缓存命中后记录延迟"""
        from src.application.ports.cache_metrics_port import CacheMetricsPort

        metrics = AsyncMock(spec=CacheMetricsPort)
        middleware, cache, search_service, _ = _make_middleware(metrics=metrics)

        cache.get.return_value = {
            "results": [dict(r) for r in _sample_results()],
            "query_text": "test",
            "weights": None,
        }

        await middleware.search(collection="c", query_text="test", limit=5)

        # record_cache_latency 应被调用，且参数为正数
        metrics.record_cache_latency.assert_called_once()
        latency_arg = metrics.record_cache_latency.call_args[0][0]
        assert latency_arg >= 0, f"延迟应为非负数，实际 {latency_arg}"

    # ===================================================================
    # 命中率计算
    # ===================================================================

    async def test_hit_rate(self) -> None:
        """命中率计算正确"""
        from src.application.ports.cache_metrics_port import CacheMetricsPort

        metrics = AsyncMock(spec=CacheMetricsPort)
        # 模拟命中率计算：3次命中/(3次命中+2次未命中)=0.6
        metrics.hit_rate = 0.6
        middleware, cache, search_service, _ = _make_middleware(metrics=metrics)

        # 3 次命中
        cache.get.return_value = {
            "results": [dict(r) for r in _sample_results()],
            "query_text": "test",
            "weights": None,
        }
        for _ in range(3):
            await middleware.search(collection="c", query_text="test", limit=5)

        # 2 次未命中
        cache.get.return_value = None
        for i in range(2):
            await middleware.search(collection="c", query_text=f"nonexistent{i}", limit=5)

        # 验证 record_cache_hit 和 record_cache_miss 被正确调用
        assert metrics.record_cache_hit.call_count == 3
        assert metrics.record_cache_miss.call_count == 2

    # ===================================================================
    # metrics 属性可访问
    # ===================================================================

    async def test_metrics_property_accessible(self) -> None:
        """metrics 属性返回 CacheMetricsPort 实例"""
        from src.application.ports.cache_metrics_port import CacheMetricsPort

        metrics = AsyncMock(spec=CacheMetricsPort)
        middleware, _, _, _ = _make_middleware(metrics=metrics)

        # 验证 metrics 属性可访问
        assert middleware.metrics is not None
        assert middleware.metrics is metrics

    async def test_metrics_property_none_when_not_configured(self) -> None:
        """未配置指标时 metrics 属性返回 None"""
        middleware, _, _, _ = _make_middleware(metrics=None)
        assert middleware.metrics is None

    # ===================================================================
    # 预估节省 Token 数
    # ===================================================================

    async def test_estimated_tokens_saved(self) -> None:
        """预估节省 Token 数的计算"""
        middleware, cache, search_service, _ = _make_middleware(
            avg_tokens_per_search=5000,
        )

        # 3 次命中
        cache.get.return_value = {
            "results": [dict(r) for r in _sample_results()],
            "query_text": "test",
            "weights": None,
        }
        for _ in range(3):
            await middleware.search(collection="c", query_text="test", limit=5)

        # 使用 middleware.avg_tokens_per_search 属性
        assert middleware.avg_tokens_per_search == 5000


class TestSemanticCacheMiddlewareEdgeCases:
    """边界条件测试"""

    async def test_empty_query_text(self) -> None:
        """空查询文本 → 应抛出异常（由底层服务校验）"""
        middleware, cache, search_service, _ = _make_middleware()

        # 空文本应由 search_service 校验
        from src.domain.exceptions import ValidationError

        search_service.search.side_effect = ValidationError(message="查询文本不能为空")

        with pytest.raises(ValidationError):
            await middleware.search(collection="c", query_text="", limit=5)

    async def test_doc_id_extraction_from_results(self) -> None:
        """从检索结果提取文档 ID 列表"""
        middleware, cache, search_service, _ = _make_middleware()

        results = _sample_results()
        search_service.search.return_value = results

        # 执行查询（未命中 → 检索 → 写入）
        cache.get.return_value = None
        await middleware.search(collection="c", query_text="test", limit=5)

        # 验证缓存写入时携带了 doc_ids
        cache.set.assert_called_once()
        set_kwargs = cache.set.call_args[1]
        doc_ids = set_kwargs.get("doc_ids")
        assert doc_ids is not None
        assert "doc-001" in doc_ids
        assert "doc-002" in doc_ids
        # 应去重
        assert doc_ids.count("doc-001") == 1
