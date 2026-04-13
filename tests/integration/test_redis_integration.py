"""Redis integration tests for session, cache, and blackboard flows.

端到端测试，验证会话存储、语义缓存和公共黑板的集成流程。
使用 fakeredis 模拟 Redis 行为。
"""

from __future__ import annotations

import fakeredis
import pytest

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache
from src.infrastructure.storage.redis.session_storage import RedisSessionStorage


def _create_session_storage(fake_redis: fakeredis.FakeRedis) -> RedisSessionStorage:
    """创建使用 fake Redis 的 SessionStorage。"""
    config = RedisConfig()
    storage = RedisSessionStorage(config)
    storage._pool = fake_redis.connection_pool
    return storage


def _create_semantic_cache(
    fake_redis: fakeredis.FakeRedis,
    metrics_collector: EventMetricsCollector | None = None,
) -> RedisSemanticCache:
    """创建使用 fake Redis 的 SemanticCache。"""
    config = RedisConfig()
    cache = RedisSemanticCache(config, metrics_collector=metrics_collector)
    cache._pool = fake_redis.connection_pool
    return cache


def _create_public_blackboard(fake_redis: fakeredis.FakeRedis) -> RedisPublicBlackboard:
    """创建使用 fake Redis 的 PublicBlackboard。"""
    config = RedisConfig()
    board = RedisPublicBlackboard(config)
    board._pool = fake_redis.connection_pool
    return board


class TestSessionStorageIntegration:
    """会话存储集成测试。"""

    @pytest.mark.asyncio
    async def test_full_session_lifecycle(self) -> None:
        """会话保存→加载→验证→删除。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        storage = _create_session_storage(fake_redis)

        # 保存
        state_data = {"counter": 42, "items": ["a", "b"]}
        await storage.save("sess-1", "agent-1", state_data)

        # 验证存在
        assert await storage.exists("sess-1") is True

        # 加载
        result = await storage.load("sess-1")
        assert result is not None
        assert result["session_id"] == "sess-1"
        assert result["agent_id"] == "agent-1"
        assert result["state"] == state_data

        # 删除
        await storage.delete("sess-1")

        # 验证不存在
        assert await storage.exists("sess-1") is False
        assert await storage.load("sess-1") is None


class TestSemanticCacheIntegration:
    """语义缓存集成测试。"""

    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self) -> None:
        """缓存未命中→写入→命中。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cache = _create_semantic_cache(fake_redis)

        # 未命中
        found = await cache.get([0.1, 0.2, 0.3], threshold=0.9)
        assert found is None

        # 写入
        await cache.set([0.1, 0.2, 0.3], {"answer": "test"})

        # 命中
        found = await cache.get([0.1, 0.2, 0.3], threshold=0.99)
        assert found is not None
        assert found["answer"] == "test"

    @pytest.mark.asyncio
    async def test_cache_hit_rate(self) -> None:
        """缓存命中率统计。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        metrics = EventMetricsCollector()
        cache = _create_semantic_cache(fake_redis, metrics_collector=metrics)

        # 2 次未命中
        await cache.get([0.1], threshold=0.9)
        await cache.get([0.2], threshold=0.9)

        # 写入并命中
        await cache.set([0.3], {"result": "value"})
        await cache.get([0.3], threshold=0.99)

        assert metrics.metrics.cache_hits_total == 1
        assert metrics.metrics.cache_misses_total == 2
        assert metrics.hit_rate == pytest.approx(1 / 3)


class TestPublicBlackboardIntegration:
    """公共黑板集成测试。"""

    @pytest.mark.asyncio
    async def test_multi_agent_collaboration(self) -> None:
        """多 Agent 协作场景。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_public_blackboard(fake_redis)

        # Agent 1 发布分析结果
        v1 = await board.post(
            "conv-1",
            "analyst",
            {"finding": "Market growing 15% YoY"},
            confidence=0.9,
            citations=["report-2024"],
        )
        assert v1 == 1

        # Agent 2 发布战略建议
        v2 = await board.post(
            "conv-1",
            "strategist",
            {"recommendation": "Enter Asian market"},
            confidence=0.8,
            citations=["analysis-1"],
        )
        assert v2 == 2

        # 读取所有内容
        entries = await board.get("conv-1")
        assert len(entries) == 2
        assert entries[0]["agent_id"] == "analyst"
        assert entries[1]["agent_id"] == "strategist"

        # 获取最新版本
        latest = await board.get_latest("conv-1")
        assert latest is not None
        assert latest["agent_id"] == "strategist"
        assert latest["version"] == 2


class TestCombinedFlow:
    """组合流程测试。"""

    @pytest.mark.asyncio
    async def test_full_agent_workflow(self) -> None:
        """完整 Agent 工作流：会话→缓存→黑板。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        storage = _create_session_storage(fake_redis)
        metrics = EventMetricsCollector()
        cache = _create_semantic_cache(fake_redis, metrics_collector=metrics)
        board = _create_public_blackboard(fake_redis)

        # 1. 保存会话状态
        session_state = {"step": "analysis", "progress": 0.5}
        await storage.save("sess-1", "analyst", session_state)

        # 2. 写入语义缓存
        await cache.set([0.1, 0.2], {"result": "cached_analysis"})

        # 3. 发布到黑板
        version = await board.post(
            "conv-1",
            "analyst",
            {"status": "analysis_complete"},
            confidence=0.95,
        )
        assert version == 1

        # 4. 验证所有数据
        loaded = await storage.load("sess-1")
        assert loaded is not None
        assert loaded["state"]["step"] == "analysis"

        cached = await cache.get([0.1, 0.2], threshold=0.99)
        assert cached is not None
        assert cached["result"] == "cached_analysis"

        blackboard = await board.get_latest("conv-1")
        assert blackboard is not None
        assert blackboard["content"]["status"] == "analysis_complete"
