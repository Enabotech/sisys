"""RedisPublicBlackboard tests using fakeredis."""

from __future__ import annotations

import asyncio

import fakeredis

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard


def _create_blackboard(fake_redis: fakeredis.FakeRedis) -> RedisPublicBlackboard:
    """创建使用 fake Redis 的 PublicBlackboard。"""
    config = RedisConfig()
    board = RedisPublicBlackboard(config)
    board._pool = fake_redis.connection_pool
    return board


class TestRedisPublicBlackboard:
    """RedisPublicBlackboard 测试。"""

    def test_post_and_get(self) -> None:
        """发布和获取内容。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_storage(fake_redis)

        async def run() -> None:
            version = await board.post("conv-1", "agent-1", {"data": "value"})
            assert version == 1

            entries = await board.get("conv-1")
            assert len(entries) == 1
            assert entries[0]["agent_id"] == "agent-1"
            assert entries[0]["content"] == {"data": "value"}

        asyncio.run(run())

    def test_post_increments_version(self) -> None:
        """每次发布应递增版本号。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        async def run() -> None:
            v1 = await board.post("conv-1", "agent-1", {"data": "v1"})
            v2 = await board.post("conv-1", "agent-1", {"data": "v2"})
            v3 = await board.post("conv-1", "agent-2", {"data": "v3"})

            assert v1 == 1
            assert v2 == 2
            assert v3 == 3

        asyncio.run(run())

    def test_get_returns_all_entries(self) -> None:
        """get 应返回所有条目。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        async def run() -> None:
            await board.post("conv-1", "agent-1", {"data": "a"})
            await board.post("conv-1", "agent-2", {"data": "b"})
            await board.post("conv-1", "agent-1", {"data": "c"})

            entries = await board.get("conv-1")
            assert len(entries) == 3

        asyncio.run(run())

    def test_get_by_agent(self) -> None:
        """获取指定 Agent 的最新内容。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        async def run() -> None:
            await board.post("conv-1", "agent-1", {"data": "first"})
            await board.post("conv-1", "agent-2", {"data": "other"})
            await board.post("conv-1", "agent-1", {"data": "second"})

            result = await board.get_by_agent("conv-1", "agent-1")
            assert result is not None
            assert result["content"] == {"data": "second"}
            assert result["version"] == 3

        asyncio.run(run())

    def test_get_by_agent_no_entries(self) -> None:
        """Agent 无条目时返回 None。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        async def run() -> None:
            await board.post("conv-1", "agent-1", {"data": "value"})

            result = await board.get_by_agent("conv-1", "agent-2")
            assert result is None

        asyncio.run(run())

    def test_get_latest(self) -> None:
        """获取最新内容。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        async def run() -> None:
            await board.post("conv-1", "agent-1", {"data": "first"})
            await board.post("conv-1", "agent-2", {"data": "latest"})

            result = await board.get_latest("conv-1")
            assert result is not None
            assert result["content"] == {"data": "latest"}
            assert result["version"] == 2

        asyncio.run(run())

    def test_get_latest_empty(self) -> None:
        """空会话返回 None。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        async def run() -> None:
            result = await board.get_latest("conv-1")
            assert result is None

        asyncio.run(run())

    def test_post_with_confidence_and_citations(self) -> None:
        """发布时包含置信度和引用。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        async def run() -> None:
            await board.post(
                "conv-1",
                "agent-1",
                {"data": "value"},
                confidence=0.85,
                citations=["source1", "source2"],
            )

            entries = await board.get("conv-1")
            assert len(entries) == 1
            assert entries[0]["confidence"] == 0.85
            assert entries[0]["citations"] == ["source1", "source2"]

        asyncio.run(run())

    def test_concurrent_writes(self) -> None:
        """模拟并发写入版本号应唯一。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        async def run() -> None:
            # 顺序执行（模拟并发场景）
            results = []
            for i in range(5):
                v = await board.post("conv-1", f"agent-{i}", {"data": f"value-{i}"})
                results.append(v)

            # 版本号应唯一且递增
            assert len(set(results)) == 5
            assert results == [1, 2, 3, 4, 5]

        asyncio.run(run())

    def test_close(self) -> None:
        """关闭连接池。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        board.close()
        assert board._pool is None


def _create_storage(fake_redis: fakeredis.FakeRedis) -> RedisPublicBlackboard:
    """创建使用 fake Redis 的 PublicBlackboard。"""
    config = RedisConfig()
    board = RedisPublicBlackboard(config)
    board._pool = fake_redis.connection_pool
    return board
