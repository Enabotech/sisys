"""RedisCleanup tests using fakeredis."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from src.domain.exceptions import ValidationError
from src.infrastructure.storage.redis.cleanup import RedisCleanup


def _create_cleanup(fake_redis: fakeredis.aioredis.FakeRedis) -> RedisCleanup:
    """Create Cleanup using fake Redis client."""
    return RedisCleanup(redis_client=fake_redis)


class TestRedisCleanup:
    """RedisCleanup 测试"""

    async def test_cleanup_namespace(self) -> None:
        """清理命名空间应删除匹配的键"""
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        # 创建一些键
        await fake_redis.set("sisys:session:1", "data")
        await fake_redis.set("sisys:session:2", "data")
        await fake_redis.set("sisys:cache:semantic:1", "data")

        deleted = await cleanup.cleanup_namespace("session")
        assert deleted == 2

        # 会话键应被删除
        assert await fake_redis.exists("sisys:session:1") == 0
        assert await fake_redis.exists("sisys:session:2") == 0
        # 缓存键应保留
        assert await fake_redis.exists("sisys:cache:semantic:1") == 1

    async def test_cleanup_empty_namespace(self) -> None:
        """空命名空间应返回 0"""
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        deleted = await cleanup.cleanup_namespace("nonexistent")
        assert deleted == 0

    async def test_cleanup_with_custom_batch_size(self) -> None:
        """自定义 batch_size 应正常工作"""
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        for i in range(5):
            await fake_redis.set(f"sisys:session:{i}", "data")

        deleted = await cleanup.cleanup_namespace("session", batch_size=2)
        # 由于 SCAN 的迭代特性，最终应删除所有匹配键
        assert deleted >= 4
        # 验证所有键被删除
        assert await fake_redis.exists("sisys:session:0") == 0
        assert await fake_redis.exists("sisys:session:4") == 0

    async def test_context_manager(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        async with cleanup:
            pass

    async def test_empty_namespace_raises_validation_error(self) -> None:
        """空命名空间字符串应抛出 ValidationError"""
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        with pytest.raises(ValidationError, match="namespace cannot be empty"):
            await cleanup.cleanup_namespace("")

    async def test_connection_error_propagates(self) -> None:
        """Redis 连接错误应向上传播"""
        import redis.asyncio as aioredis

        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        # 模拟 scan 抛出 ConnectionError
        async def failing_scan(*args, **kwargs):
            raise aioredis.ConnectionError("connection lost")

        setattr(fake_redis, "scan", failing_scan)
        try:
            with pytest.raises(aioredis.ConnectionError):
                await cleanup.cleanup_namespace("session")
        finally:
            delattr(fake_redis, "scan")
