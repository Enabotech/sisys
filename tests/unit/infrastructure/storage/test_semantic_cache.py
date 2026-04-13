"""RedisSemanticCache tests using fakeredis."""

from __future__ import annotations

import fakeredis
import pytest

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.semantic_cache import (
    RedisSemanticCache,
    cosine_similarity,
)


def _create_cache(
    fake_redis: fakeredis.FakeRedis,
    metrics_collector: EventMetricsCollector | None = None,
) -> RedisSemanticCache:
    """创建使用 fake Redis 的 SemanticCache。"""
    config = RedisConfig()
    cache = RedisSemanticCache(config, metrics_collector=metrics_collector)
    cache._pool = fake_redis.connection_pool
    return cache


class TestCosineSimilarity:
    """余弦相似度计算测试。"""

    def test_identical_vectors(self) -> None:
        """相同向量相似度应为 1.0。"""
        vec = [1.0, 0.0, 0.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        """正交向量相似度应为 0.0。"""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        """反向向量相似度应为 -1.0。"""
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(-1.0)

    def test_partial_similarity(self) -> None:
        """部分相似向量应在 0 和 1 之间。"""
        vec1 = [1.0, 0.0]
        vec2 = [1.0, 1.0]
        sim = cosine_similarity(vec1, vec2)
        assert 0 < sim < 1
        assert sim == pytest.approx(0.7071067811865475, rel=1e-5)

    def test_dimension_mismatch_raises(self) -> None:
        """维度不匹配应抛出 ValueError。"""
        with pytest.raises(ValueError, match="dimensions must match"):
            cosine_similarity([1.0, 2.0], [1.0])

    def test_empty_vectors(self) -> None:
        """空向量相似度应为 0.0。"""
        assert cosine_similarity([], []) == 0.0

    def test_zero_vector(self) -> None:
        """零向量相似度应为 0.0。"""
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_clamped_result(self) -> None:
        """结果应裁剪到 [-1, 1] 防止浮点误差。"""
        # 构造极端情况确保裁剪逻辑存在
        result = cosine_similarity([1e-200], [1e-200])
        assert -1.0 <= result <= 1.0


class TestRedisSemanticCache:
    """RedisSemanticCache 测试。"""

    @pytest.mark.asyncio
    async def test_set_and_get_hit(self) -> None:
        """存储和查询命中。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        embedding = [0.1, 0.2, 0.3]
        result = {"answer": "test"}
        await cache.set(embedding, result)

        # 相同向量应命中
        found = await cache.get(embedding, threshold=0.99)
        assert found is not None
        assert found["answer"] == "test"

    @pytest.mark.asyncio
    async def test_get_miss(self) -> None:
        """查询未命中。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        # 查询空缓存
        found = await cache.get([0.1, 0.2, 0.3], threshold=0.9)
        assert found is None

    @pytest.mark.asyncio
    async def test_semantic_match(self) -> None:
        """语义相似的向量应命中缓存。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        # 存储一个向量
        original = [1.0, 0.0, 0.0]
        await cache.set(original, {"cached": True})

        # 查询相似向量（余弦相似度很高）
        query = [0.99, 0.01, 0.0]
        found = await cache.get(query, threshold=0.9)
        assert found is not None
        assert found["cached"] is True

    @pytest.mark.asyncio
    async def test_invalidate(self) -> None:
        """使缓存失效。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        embedding = [0.1, 0.2, 0.3]
        await cache.set(embedding, {"data": "value"})

        # 获取缓存键
        cache_key = cache._build_cache_key(embedding)
        await cache.invalidate(cache_key)

        # 查询应未命中
        found = await cache.get(embedding, threshold=0.99)
        assert found is None

    @pytest.mark.asyncio
    async def test_invalidate_with_full_key(self) -> None:
        """使用完整 Redis 键使缓存失效。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        embedding = [0.1, 0.2, 0.3]
        await cache.set(embedding, {"data": "value"})

        # 获取完整键
        from src.infrastructure.storage.redis.key_builder import build_key

        full_key = build_key("cache:semantic", cache._build_cache_key(embedding))

        # 使用完整键失效
        await cache.invalidate(full_key)

        found = await cache.get(embedding, threshold=0.99)
        assert found is None

    @pytest.mark.asyncio
    async def test_metrics_recording(self) -> None:
        """缓存命中/未命中应记录指标。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        metrics = EventMetricsCollector()
        cache = _create_cache(fake_redis, metrics_collector=metrics)

        # 未命中
        await cache.get([0.1, 0.2], threshold=0.9)
        assert metrics.metrics.cache_misses_total == 1

        # 存储
        await cache.set([0.1, 0.2], {"result": "value"})

        # 命中
        await cache.get([0.1, 0.2], threshold=0.99)
        assert metrics.metrics.cache_hits_total == 1

    def test_close(self) -> None:
        """关闭连接池。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        cache.close()
        assert cache._pool is None

    def test_context_manager(self) -> None:
        """上下文管理器应自动关闭连接池。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        config = RedisConfig()
        cache = RedisSemanticCache(config)
        cache._pool = fake_redis.connection_pool

        with cache:
            assert cache._pool is not None

        assert cache._pool is None

    def test_deterministic_cache_key(self) -> None:
        """相同向量应生成相同的缓存键（跨进程一致）。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        embedding = [0.1, 0.2, 0.3]
        key1 = cache._build_cache_key(embedding)
        key2 = cache._build_cache_key(embedding)
        assert key1 == key2
