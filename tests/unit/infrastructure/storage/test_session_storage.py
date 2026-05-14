"""RedisSessionStorage tests using fakeredis."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from src.infrastructure.storage.redis.session_storage import RedisSessionStorage


def _create_storage(fake_redis: fakeredis.aioredis.FakeRedis) -> RedisSessionStorage:
    """Create SessionStorage using fake Redis client."""
    return RedisSessionStorage(redis_client=fake_redis)


class TestRedisSessionStorage:
    """RedisSessionStorage 测试。"""

    @pytest.mark.asyncio
    async def test_save_and_load(self) -> None:
        """保存和加载会话状态。"""
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        state_data = {"counter": 42, "items": ["a", "b"]}
        await storage.save("sess-1", "agent-1", state_data)

        result = await storage.load("sess-1")
        assert result is not None
        assert result["session_id"] == "sess-1"
        assert result["agent_id"] == "agent-1"
        assert result["state"] == state_data

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self) -> None:
        """加载不存在的会话应返回 None。"""
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        result = await storage.load("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        """删除会话。"""
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        await storage.save("sess-1", "agent-1", {"key": "value"})

        # 确认存在
        assert await storage.exists("sess-1") is True

        # 删除
        await storage.delete("sess-1")

        # 确认不存在
        assert await storage.exists("sess-1") is False
        assert await storage.load("sess-1") is None

    @pytest.mark.asyncio
    async def test_exists(self) -> None:
        """检查会话存在性。"""
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        assert await storage.exists("sess-1") is False

        await storage.save("sess-1", "agent-1", {})

        assert await storage.exists("sess-1") is True

    @pytest.mark.asyncio
    async def test_save_with_custom_ttl(self) -> None:
        """保存会话时使用自定义 TTL。"""
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        await storage.save("sess-1", "agent-1", {}, ttl=3600)
        # 会话应存在
        assert await storage.exists("sess-1") is True

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = _create_storage(fake_redis)

        async with storage:
            pass
