"""Redis integration tests for session, cache, and blackboard flows.

端到端测试，验证会话存储、语义缓存和公共黑板的集成流程。
使用 fakeredis 模拟 Redis 行为。
"""

from __future__ import annotations

import asyncio

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
    metrics: EventMetricsCollector | None = None,
) -> RedisSemanticCache:
    """创建使用 fake Redis 的 SemanticCache。"""
    config = RedisConfig()
    cache = RedisSemanticCache(config, metrics_collector=metrics)
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

    def test_full_session_lifecycle(self) -> None:
        """完整的会话生命周期：创建、读取、删除。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        storage = _create_session_storage(fake_redis)

        async def run() -> None:
            # 创建会话
            session_data = {
                "conversation": [{"role": "user", "content": "Hello"}],
                "context": {"user_id": "u1"},
            }
            await storage.save("sess-1", "agent-1", session_data)

            # 读取会话
            loaded = await storage.load("sess-1")
            assert loaded is not None
            assert loaded["session_id"] == "sess-1"
            assert loaded["agent_id"] == "agent-1"
            assert loaded["state"] == session_data

            # 删除会话
            await storage.delete("sess-1")
            assert await storage.exists("sess-1") is False

        asyncio.run(run())


class TestSemanticCacheIntegration:
    """语义缓存集成测试。"""

    def test_cache_miss_then_hit(self) -> None:
        """先未命中，再存储后命中。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        metrics = EventMetricsCollector()
        cache = _create_semantic_cache(fake_redis, metrics)

        async def run() -> None:
            embedding = [0.5, 0.3, 0.2]

            # 第一次查询未命中
            result = await cache.get(embedding, threshold=0.9)
            assert result is None
            assert metrics.metrics.cache_misses_total == 1

            # 存储结果
            await cache.set(embedding, {"answer": "Cached answer"})

            # 第二次查询命中
            result = await cache.get(embedding, threshold=0.99)
            assert result is not None
            assert result["answer"] == "Cached answer"
            assert metrics.metrics.cache_hits_total == 1

        asyncio.run(run())

    def test_cache_hit_rate(self) -> None:
        """验证缓存命中率计算。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        metrics = EventMetricsCollector()
        cache = _create_semantic_cache(fake_redis, metrics)

        async def run() -> None:
            # 3 次未命中
            for _ in range(3):
                await cache.get([0.1, 0.2], threshold=0.9)

            # 存储
            await cache.set([0.1, 0.2], {"data": "value"})

            # 2 次命中
            for _ in range(2):
                await cache.get([0.1, 0.2], threshold=0.99)

            # 命中率 = 2 / (2 + 3) = 0.4
            assert metrics.hit_rate == pytest.approx(0.4)

        asyncio.run(run())


class TestPublicBlackboardIntegration:
    """公共黑板集成测试。"""

    def test_multi_agent_collaboration(self) -> None:
        """多 Agent 协作场景。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_public_blackboard(fake_redis)

        async def run() -> None:
            # Agent 1 发布分析结果
            v1 = await board.post(
                "conv-1",
                "agent-analyst",
                {"finding": "Pattern detected"},
                confidence=0.9,
                citations=["data-source-1"],
            )
            assert v1 == 1

            # Agent 2 发布决策
            v2 = await board.post(
                "conv-1",
                "agent-decider",
                {"decision": "Take action A"},
                confidence=0.85,
            )
            assert v2 == 2

            # Agent 1 更新分析
            v3 = await board.post(
                "conv-1",
                "agent-analyst",
                {"finding": "Pattern confirmed"},
                confidence=0.95,
            )
            assert v3 == 3

            # 获取所有条目
            all_entries = await board.get("conv-1")
            assert len(all_entries) == 3

            # Agent 1 查看自己的最新条目
            analyst_latest = await board.get_by_agent("conv-1", "agent-analyst")
            assert analyst_latest is not None
            assert analyst_latest["content"]["finding"] == "Pattern confirmed"
            assert analyst_latest["version"] == 3

            # 查看全局最新条目
            global_latest = await board.get_latest("conv-1")
            assert global_latest is not None
            assert global_latest["version"] == 3

        asyncio.run(run())


class TestCombinedFlow:
    """组合流程测试：会话 + 缓存 + 黑板。"""

    def test_full_agent_workflow(self) -> None:
        """完整的 Agent 工作流：会话管理、缓存查询、黑板协作。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        storage = _create_session_storage(fake_redis)
        metrics = EventMetricsCollector()
        cache = _create_semantic_cache(fake_redis, metrics)
        board = _create_public_blackboard(fake_redis)

        async def run() -> None:
            # 1. 加载会话状态
            session_data = {"step": "analysis", "query": "What is AI?"}
            await storage.save("sess-1", "agent-1", session_data)

            loaded = await storage.load("sess-1")
            assert loaded is not None
            assert loaded["state"]["step"] == "analysis"

            # 2. 查询语义缓存
            embedding = [0.1] * 10  # 模拟查询向量
            cached_result = await cache.get(embedding, threshold=0.9)

            if cached_result is None:
                # 缓存未命中，生成新结果并存储
                new_result = {"answer": "AI is artificial intelligence"}
                await cache.set(embedding, new_result)
                assert metrics.metrics.cache_misses_total == 1
            else:
                # 缓存命中
                assert metrics.metrics.cache_hits_total >= 1

            # 3. 发布到黑板
            version = await board.post(
                "conv-1",
                "agent-1",
                {"finding": "Analysis complete"},
                confidence=0.95,
            )
            assert version >= 1

            # 4. 从黑板读取
            entries = await board.get("conv-1")
            assert len(entries) >= 1

            # 验证指标
            assert metrics.hit_rate >= 0.0

        asyncio.run(run())
