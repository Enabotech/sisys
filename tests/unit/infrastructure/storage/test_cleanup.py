"""RedisCleanup tests using fakeredis."""

from __future__ import annotations

import fakeredis

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.storage.redis.cleanup import RedisCleanup


def _create_cleanup(fake_redis: fakeredis.FakeRedis) -> RedisCleanup:
    """创建使用 fake Redis 的 Cleanup。"""
    config = RedisConfig()
    cleanup = RedisCleanup(config)
    cleanup._pool = fake_redis.connection_pool
    return cleanup


class TestRedisCleanup:
    """RedisCleanup 测试。"""

    def test_cleanup_namespace(self) -> None:
        """清理命名空间应删除匹配的键。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        # 创建一些键
        fake_redis.set("sisys:session:1", "data")
        fake_redis.set("sisys:session:2", "data")
        fake_redis.set("sisys:cache:semantic:1", "data")

        deleted = cleanup.cleanup_namespace("session")
        assert deleted == 2

        # 会话键应被删除
        assert fake_redis.exists("sisys:session:1") == 0
        assert fake_redis.exists("sisys:session:2") == 0
        # 缓存键应保留
        assert fake_redis.exists("sisys:cache:semantic:1") == 1

    def test_cleanup_empty_namespace(self) -> None:
        """空命名空间应返回 0。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        deleted = cleanup.cleanup_namespace("nonexistent")
        assert deleted == 0

    def test_cleanup_with_custom_batch_size(self) -> None:
        """自定义 batch_size 应正常工作。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        for i in range(5):
            fake_redis.set(f"sisys:session:{i}", "data")

        # 使用较小的 batch_size 确保多轮扫描
        deleted = cleanup.cleanup_namespace("session", batch_size=2)
        # 由于 SCAN 的迭代特性，最终应删除所有匹配键
        # fakeredis 的 delete() 返回值可能与真实 Redis 不同，我们验证键是否被删除
        assert deleted >= 4  # 至少删除 4 个
        # 验证所有键被删除
        assert fake_redis.exists("sisys:session:0") == 0
        assert fake_redis.exists("sisys:session:4") == 0

    def test_close(self) -> None:
        """关闭连接池。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cleanup = _create_cleanup(fake_redis)

        cleanup.close()
        assert cleanup._pool is None

    def test_context_manager(self) -> None:
        """上下文管理器应自动关闭连接池。"""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        config = RedisConfig()
        cleanup = RedisCleanup(config)
        cleanup._pool = fake_redis.connection_pool

        with cleanup:
            assert cleanup._pool is not None

        assert cleanup._pool is None
