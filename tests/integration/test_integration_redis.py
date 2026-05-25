"""Redis integration tests for session, cache, and blackboard flows.

End-to-end tests verifying session storage, semantic cache, and public
blackboard integration flows. Uses fakeredis to simulate Redis behavior.
"""

from __future__ import annotations

from unittest.mock import patch

import fakeredis.aioredis

from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache
from src.infrastructure.storage.redis.session_storage import RedisSessionStorage


def _create_session_storage(fake_redis: fakeredis.aioredis.FakeRedis) -> RedisSessionStorage:
    return RedisSessionStorage(redis_client=fake_redis)


def _create_semantic_cache(
    fake_redis: fakeredis.aioredis.FakeRedis,
    metrics_collector: EventMetricsCollector | None = None,
    embedding_dim: int = 3,
) -> RedisSemanticCache:
    original_execute = fake_redis.execute_command

    async def _mock_execute(*args, **kwargs):
        if args and args[0] in ("FT.CREATE", "FT.SEARCH", "FT.DROPINDEX"):
            if args[0] == "FT.SEARCH":
                return [0]
            return "OK"
        return await original_execute(*args, **kwargs)

    patch.object(fake_redis, "execute_command", _mock_execute).start()
    return RedisSemanticCache(
        redis_client=fake_redis,
        embedding_dim=embedding_dim,
        metrics_collector=metrics_collector,
    )


def _create_public_blackboard(fake_redis: fakeredis.aioredis.FakeRedis) -> RedisPublicBlackboard:
    return RedisPublicBlackboard(redis_client=fake_redis)


class TestSessionStorageIntegration:
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
    async def test_cache_set_and_invalidate(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache = _create_semantic_cache(fake_redis)

        await cache.set([0.1, 0.2, 0.3], {"answer": "test"})

        cache_key = cache._build_cache_key([0.1, 0.2, 0.3])
        await cache.invalidate(cache_key)

        # Verify key deleted in fakeredis
        assert await fake_redis.exists(f"sisys:cache:semantic:{cache_key}") == 0

    async def test_cache_hit_with_mocked_search(self) -> None:
        from src.infrastructure.utils import json_dumps

        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        metrics = EventMetricsCollector()

        # Build a mock FT.SEARCH response
        hit_response = [
            1,
            "sisys:cache:semantic:vec:test",
            ["__embedding_score", "0.05", "result", json_dumps({"answer": "found"})],
        ]

        call_count = 0
        original_execute = fake_redis.execute_command

        async def _mock_execute(*args, **kwargs):
            nonlocal call_count
            if args and args[0] == "FT.CREATE":
                return "OK"
            if args and args[0] == "FT.SEARCH":
                call_count += 1
                if call_count == 1:
                    return [0]  # miss
                return hit_response  # hit
            return await original_execute(*args, **kwargs)

        with patch.object(fake_redis, "execute_command", _mock_execute):
            cache = RedisSemanticCache(
                redis_client=fake_redis,
                embedding_dim=3,
                metrics_collector=metrics,
            )

            # Miss
            found = await cache.get([0.1, 0.2, 0.3], threshold=0.9)
            assert found is None
            assert metrics.metrics.cache_misses_total == 1

            # Hit
            found = await cache.get([0.1, 0.2, 0.3], threshold=0.9)
            assert found is not None
            assert found["answer"] == "found"
            assert metrics.metrics.cache_hits_total == 1


class TestPublicBlackboardIntegration:
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

        blackboard = await board.get_latest("conv-1")
        assert blackboard is not None
        assert blackboard["content"]["status"] == "analysis_complete"
