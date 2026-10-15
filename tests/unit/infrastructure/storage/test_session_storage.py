"""RedisSessionStorage tests using fakeredis."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from src.infrastructure.storage.redis.session_storage import RedisSessionStorage


def _create_storage(fake_redis: fakeredis.aioredis.FakeRedis) -> RedisSessionStorage:
    """Create SessionStorage using fake Redis client."""
    return RedisSessionStorage(redis_client=fake_redis)


@pytest.fixture
async def fake_redis():
    """场景级 FakeRedis 客户端（同用例生命周期，teardown 关闭——D8 清偿）。"""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


class TestRedisSessionStorage:
    """RedisSessionStorage 测试"""

    async def test_save_and_load(self, fake_redis) -> None:
        """保存和加载会话状态"""
        storage = _create_storage(fake_redis)

        state_data = {"counter": 42, "items": ["a", "b"]}
        await storage.save("sess-1", "agent-1", state_data)

        result = await storage.load("sess-1")
        assert result is not None
        assert result["session_id"] == "sess-1"
        assert result["agent_id"] == "agent-1"
        assert result["state"] == state_data

    async def test_load_nonexistent_returns_none(self, fake_redis) -> None:
        """加载不存在的会话应返回 None"""
        storage = _create_storage(fake_redis)

        result = await storage.load("nonexistent")
        assert result is None

    async def test_delete(self, fake_redis) -> None:
        """删除会话"""
        storage = _create_storage(fake_redis)

        await storage.save("sess-1", "agent-1", {"key": "value"})

        # 确认存在
        assert await storage.exists("sess-1") is True

        # 删除
        await storage.delete("sess-1")

        # 确认不存在
        assert await storage.exists("sess-1") is False
        assert await storage.load("sess-1") is None

    async def test_exists(self, fake_redis) -> None:
        """检查会话存在性"""
        storage = _create_storage(fake_redis)

        assert await storage.exists("sess-1") is False

        await storage.save("sess-1", "agent-1", {})

        assert await storage.exists("sess-1") is True

    async def test_save_with_custom_ttl(self, fake_redis) -> None:
        """保存会话时使用自定义 TTL"""
        storage = _create_storage(fake_redis)

        await storage.save("sess-1", "agent-1", {}, ttl=3600)
        # 会话应存在
        assert await storage.exists("sess-1") is True

    async def test_context_manager(self, fake_redis) -> None:
        storage = _create_storage(fake_redis)

        async with storage:
            pass
