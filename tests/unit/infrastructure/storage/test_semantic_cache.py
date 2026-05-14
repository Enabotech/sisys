"""RedisSemanticCache tests using fakeredis."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.semantic_cache import (
    RedisSemanticCache,
    cosine_similarity,
)


def _create_cache(
    fake_redis: fakeredis.aioredis.FakeRedis,
    metrics_collector: EventMetricsCollector | None = None,
) -> RedisSemanticCache:
    """Create SemanticCache using fake Redis client."""
    return RedisSemanticCache(redis_client=fake_redis, metrics_collector=metrics_collector)


class TestCosineSimilarity:
    """Cosine similarity calculation tests."""

    def test_identical_vectors(self) -> None:
        vec = [1.0, 0.0, 0.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(-1.0)

    def test_partial_similarity(self) -> None:
        vec1 = [1.0, 0.0]
        vec2 = [1.0, 1.0]
        sim = cosine_similarity(vec1, vec2)
        assert 0 < sim < 1
        assert sim == pytest.approx(0.7071067811865475, rel=1e-5)

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="dimensions must match"):
            cosine_similarity([1.0, 2.0], [1.0])

    def test_empty_vectors(self) -> None:
        assert cosine_similarity([], []) == 0.0

    def test_zero_vector(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_clamped_result(self) -> None:
        result = cosine_similarity([1e-200], [1e-200])
        assert -1.0 <= result <= 1.0


class TestRedisSemanticCache:
    """RedisSemanticCache tests."""

    @pytest.mark.asyncio
    async def test_set_and_get_hit(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        embedding = [0.1, 0.2, 0.3]
        result = {"answer": "test"}
        await cache.set(embedding, result)

        found = await cache.get(embedding, threshold=0.99)
        assert found is not None
        assert found["answer"] == "test"

    @pytest.mark.asyncio
    async def test_get_miss(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        found = await cache.get([0.1, 0.2, 0.3], threshold=0.9)
        assert found is None

    @pytest.mark.asyncio
    async def test_get_miss_then_set_hit(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        # 先 miss
        assert await cache.get([0.1, 0.2, 0.3], threshold=0.9) is None

        # 写入
        await cache.set([0.1, 0.2, 0.3], {"answer": "test"})

        # 再 hit
        found = await cache.get([0.1, 0.2, 0.3], threshold=0.99)
        assert found is not None
        assert found["answer"] == "test"

    @pytest.mark.asyncio
    async def test_invalidate(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        embedding = [0.1, 0.2, 0.3]
        await cache.set(embedding, {"answer": "test"})

        # 确认命中
        assert await cache.get(embedding, threshold=0.99) is not None

        # 失效
        cache_key = cache._build_cache_key(embedding)
        await cache.invalidate(cache_key)

        # 确认 miss
        assert await cache.get(embedding, threshold=0.99) is None

    @pytest.mark.asyncio
    async def test_metrics_recording(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        metrics = EventMetricsCollector()
        cache = _create_cache(fake_redis, metrics_collector=metrics)

        # miss
        await cache.get([0.1], threshold=0.9)
        assert metrics.metrics.cache_misses_total == 1
        assert metrics.metrics.cache_hits_total == 0

        # hit
        await cache.set([0.1], {"result": "value"})
        await cache.get([0.1], threshold=0.99)
        assert metrics.metrics.cache_hits_total == 1
        assert metrics.metrics.cache_misses_total == 1

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)
        async with cache:
            pass

    @pytest.mark.asyncio
    async def test_deterministic_cache_key(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)
        key1 = cache._build_cache_key([0.1, 0.2, 0.3])
        key2 = cache._build_cache_key([0.1, 0.2, 0.3])
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_dimension_mismatch_raises_in_get(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache = _create_cache(fake_redis)

        # 写入 3 维向量
        await cache.set([0.1, 0.2, 0.3], {"answer": "test"})

        # 用 2 维向量查询应抛出维度不匹配
        with pytest.raises(ValueError, match="dimensions must match"):
            await cache.get([0.1, 0.2], threshold=0.9)
