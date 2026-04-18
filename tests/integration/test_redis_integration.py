"""Redis integration tests for session, cache, and blackboard flows.

端到端测试，验证会话存储、语义缓存和公共黑板的集成流程。
使用 fakeredis 模拟 Redis 行为。
"""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache
from src.infrastructure.storage.redis.session_storage import RedisSessionStorage


def _create_session_storage(fake_redis: fakeredis.aioredis.FakeRedis) -> RedisSessionStorage:
    config = RedisConfig()
    storage = RedisSessionStorage(config)
    storage._pool = fake_redis.connection_pool
    return storage


def _create_semantic_cache(
    fake_redis: fakeredis.aioredis.FakeRedis,
    metrics_collector: EventMetricsCollector | None = None,
) -> RedisSemanticCache:
    config = RedisConfig()
    cache = RedisSemanticCache(config, metrics_collector=metrics_collector)
    cache._pool = fake_redis.connection_pool
    return cache


def _create_public_blackboard(fake_redis: fakeredis.aioredis.FakeRedis) -> RedisPublicBlackboard:
    config = RedisConfig()
    board = RedisPublicBlackboard(config)
    board._pool = fake_redis.connection_pool
    return board


class TestSessionStorageIntegration:
    """会话存储集成测试。"""

    @pytest.mark.asyncio
    async def test_full_session_lifecycle(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = _create_session_storage(fake_redis)

        state_data = {"counter": 42, "items": ["a", "b"]}
        await storage.save("sess-1", "agent-1", state_data)
        assert await storage.exists("sess-1") is True

        result = await storage.load("sess-1")
        assert result is not None
        assert result["session_id"] == "sess-1"
        assert result["agent_id"] == "agent-1"
        assert result["state"] == state_data

        await storage.delete("sess-1")
        assert await storage.exists("sess-1") is False
        assert await storage.load("sess-1") is None


class TestSemanticCacheIntegration:
    """语义缓存集成测试。"""

    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache = _create_semantic_cache(fake_redis)

        found = await cache.get([0.1, 0.2, 0.3], threshold=0.9)
        assert found is None

        await cache.set([0.1, 0.2, 0.3], {"answer": "test"})

        found = await cache.get([0.1, 0.2, 0.3], threshold=0.99)
        assert found is not None
        assert found["answer"] == "test"

    @pytest.mark.asyncio
    async def test_cache_hit_rate(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        metrics = EventMetricsCollector()
        cache = _create_semantic_cache(fake_redis, metrics_collector=metrics)

        await cache.get([0.1], threshold=0.9)
        await cache.get([0.2], threshold=0.9)

        await cache.set([0.3], {"result": "value"})
        await cache.get([0.3], threshold=0.99)

        assert metrics.metrics.cache_hits_total == 1
        assert metrics.metrics.cache_misses_total == 2
        assert metrics.hit_rate == pytest.approx(1 / 3)


class TestPublicBlackboardIntegration:
    """公共黑板集成测试。"""

    @pytest.mark.asyncio
    async def test_multi_agent_collaboration(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_public_blackboard(fake_redis)

        v1 = await board.post(
            "conv-1",
            "analyst",
            {"finding": "Market growing 15% YoY"},
            confidence=0.9,
            citations=["report-2024"],
        )
        assert v1 == 1

        v2 = await board.post(
            "conv-1",
            "strategist",
            {"recommendation": "Enter Asian market"},
            confidence=0.8,
            citations=["analysis-1"],
        )
        assert v2 == 2

        entries = await board.get("conv-1")
        assert len(entries) == 2
        assert entries[0]["agent_id"] == "analyst"
        assert entries[1]["agent_id"] == "strategist"

        latest = await board.get_latest("conv-1")
        assert latest is not None
        assert latest["agent_id"] == "strategist"
        assert latest["version"] == 2


class TestCombinedFlow:
    """组合流程测试。"""

    @pytest.mark.asyncio
    async def test_full_agent_workflow(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = _create_session_storage(fake_redis)
        metrics = EventMetricsCollector()
        cache = _create_semantic_cache(fake_redis, metrics_collector=metrics)
        board = _create_public_blackboard(fake_redis)

        session_state = {"step": "analysis", "progress": 0.5}
        await storage.save("sess-1", "analyst", session_state)

        await cache.set([0.1, 0.2], {"result": "cached_analysis"})

        version = await board.post(
            "conv-1",
            "analyst",
            {"status": "analysis_complete"},
            confidence=0.95,
        )
        assert version == 1

        loaded = await storage.load("sess-1")
        assert loaded is not None
        assert loaded["state"]["step"] == "analysis"

        cached = await cache.get([0.1, 0.2], threshold=0.99)
        assert cached is not None
        assert cached["result"] == "cached_analysis"

        blackboard = await board.get_latest("conv-1")
        assert blackboard is not None
        assert blackboard["content"]["status"] == "analysis_complete"
