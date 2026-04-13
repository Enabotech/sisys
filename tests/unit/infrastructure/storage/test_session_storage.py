"""RedisSessionStorage tests using fakeredis."""

from __future__ import annotations

import asyncio

import fakeredis

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.storage.redis.session_storage import RedisSessionStorage


def _create_storage(fake_redis: fakeredis.FakeRedis) -> RedisSessionStorage:
    """创建使用 fake Redis 的 SessionStorage。"""
    config = RedisConfig()
    storage = RedisSessionStorage(config)
    # 直接注入 fake pool
    storage._pool = fake_redis.connection_pool
    return storage


class TestRedisSessionStorage:
    """RedisSessionStorage 测试。"""

    def test_save_and_load(self) -> None:
        """保存和加载会话状态。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        async def run() -> None:
            state_data = {"counter": 42, "items": ["a", "b"]}
            await storage.save("sess-1", "agent-1", state_data)

            result = await storage.load("sess-1")
            assert result is not None
            assert result["session_id"] == "sess-1"
            assert result["agent_id"] == "agent-1"
            assert result["state"] == state_data

        asyncio.run(run())

    def test_load_nonexistent_returns_none(self) -> None:
        """加载不存在的会话应返回 None。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        async def run() -> None:
            result = await storage.load("nonexistent")
            assert result is None

        asyncio.run(run())

    def test_delete(self) -> None:
        """删除会话。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        async def run() -> None:
            await storage.save("sess-1", "agent-1", {"key": "value"})

            # 确认存在
            assert await storage.exists("sess-1") is True

            # 删除
            await storage.delete("sess-1")

            # 确认不存在
            assert await storage.exists("sess-1") is False
            assert await storage.load("sess-1") is None

        asyncio.run(run())

    def test_exists(self) -> None:
        """检查会话存在性。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        async def run() -> None:
            assert await storage.exists("sess-1") is False

            await storage.save("sess-1", "agent-1", {})

            assert await storage.exists("sess-1") is True

        asyncio.run(run())

    def test_save_with_custom_ttl(self) -> None:
        """保存会话时使用自定义 TTL。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        async def run() -> None:
            await storage.save("sess-1", "agent-1", {}, ttl=3600)
            # 会话应存在
            assert await storage.exists("sess-1") is True

        asyncio.run(run())

    def test_close(self) -> None:
        """关闭连接池。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        storage.close()
        assert storage._pool is None
