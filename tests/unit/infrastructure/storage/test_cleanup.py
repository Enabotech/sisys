"""RedisCleanup tests."""

from __future__ import annotations

import fakeredis

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.storage.redis.cleanup import RedisCleanup


def _create_cleanup(fake_redis: fakeredis.FakeRedis) -> RedisCleanup:
    """创建使用 fake Redis 的 Cleanup 工具。"""
    config = RedisConfig()
    cleanup = RedisCleanup(config)
    cleanup._pool = fake_redis.connection_pool
    return cleanup


class TestRedisCleanup:
    """RedisCleanup 测试。"""

    def test_cleanup_session_namespace(self) -> None:
        """清理会话命名空间。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        # 添加一些键
        fake_redis.set("sisys:session:sess-1", "data1")
        fake_redis.set("sisys:session:sess-2", "data2")
        fake_redis.set("sisys:other:key", "data3")

        deleted = cleanup.cleanup_namespace("session")

        assert deleted == 2
        # 其他命名空间的键应不受影响
        assert fake_redis.get("sisys:other:key") == "data3"

    def test_cleanup_empty_namespace(self) -> None:
        """清理空命名空间。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        deleted = cleanup.cleanup_namespace("nonexistent")

        assert deleted == 0

    def test_cleanup_with_pattern(self) -> None:
        """清理匹配模式的键。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        # 添加缓存键
        fake_redis.set("sisys:cache:semantic:vec:1", "data1")
        fake_redis.set("sisys:cache:semantic:vec:2", "data2")
        fake_redis.set("sisys:cache:other:key", "data3")

        deleted = cleanup.cleanup_namespace("cache:semantic")

        assert deleted == 2
        # 其他缓存键应不受影响
        assert fake_redis.get("sisys:cache:other:key") == "data3"

    def test_cleanup_blackboard_namespace(self) -> None:
        """清理黑板命名空间。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        fake_redis.zadd("sisys:blackboard:conv-1", {"entry1": 1.0})
        fake_redis.zadd("sisys:blackboard:conv-2", {"entry2": 2.0})
        fake_redis.set("sisys:session:sess-1", "data")

        deleted = cleanup.cleanup_namespace("blackboard")

        assert deleted == 2
        assert fake_redis.get("sisys:session:sess-1") == "data"

    def test_close(self) -> None:
        """关闭连接池。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        cleanup.close()
        assert cleanup._pool is None
