"""Tests for RedisMemoryCache.

RED PHASE: 验证 RedisMemoryCache L1 缓存功能。
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache


class TestRedisMemoryCacheInit:
    """RedisMemoryCache 初始化验证"""

    def test_init_with_redis_client(self):
        """验证使用 redis client 初始化"""
        mock_redis = MagicMock()
        cache = RedisMemoryCache(mock_redis)
        assert cache._redis is not None


class TestRedisMemoryCacheKeyFormat:
    """RedisMemoryCache Key 格式验证"""

    def test_private_memory_key_format(self):
        """验证 Private 记忆 key 格式"""
        mock_redis = MagicMock()
        cache = RedisMemoryCache(mock_redis)

        user_id = str(uuid.uuid4())
        name = "test-memory"

        key = cache._build_key("private", user_id, name)

        assert key == f"memory:user:{user_id}:test-memory"

    def test_group_memory_key_format(self):
        """验证 Group 记忆 key 格式"""
        mock_redis = MagicMock()
        cache = RedisMemoryCache(mock_redis)

        group_id = str(uuid.uuid4())
        name = "team-doc"

        key = cache._build_key("group", group_id, name)

        assert key == f"memory:group:{group_id}:team-doc"


class TestRedisMemoryCacheTTL:
    """RedisMemoryCache TTL 验证"""

    def test_default_ttl_range(self):
        """验证默认 TTL 范围 86400-108000 秒 (24h-30h)"""
        mock_redis = MagicMock()
        cache = RedisMemoryCache(mock_redis)

        ttl = cache._generate_ttl()

        assert 86400 <= ttl <= 108000


class TestRedisMemoryCacheGet:
    """RedisMemoryCache get 方法验证"""

    def test_get_returns_cached_content(self):
        """验证 get 返回缓存内容"""
        mock_redis = MagicMock()
        mock_redis.get.return_value = b"cached memory content"

        cache = RedisMemoryCache(mock_redis)

        user_id = str(uuid.uuid4())
        name = "test-memory"
        result = cache.get("private", user_id, name)

        assert result == "cached memory content"

    def test_get_returns_none_when_not_cached(self):
        """验证 get 在缓存未命中时返回 None"""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        cache = RedisMemoryCache(mock_redis)

        user_id = str(uuid.uuid4())
        name = "test-memory"
        result = cache.get("private", user_id, name)

        assert result is None


class TestRedisMemoryCacheSet:
    """RedisMemoryCache set 方法验证"""

    def test_set_stores_content(self):
        """验证 set 存储内容"""
        mock_redis = MagicMock()

        cache = RedisMemoryCache(mock_redis)

        user_id = str(uuid.uuid4())
        name = "test-memory"
        content = "memory content to cache"

        cache.set("private", user_id, name, content)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == f"memory:user:{user_id}:test-memory"
        assert call_args[0][1] >= 86400  # TTL >= 24h


class TestRedisMemoryCacheDelete:
    """RedisMemoryCache delete 方法验证"""

    def test_delete_removes_cached_content(self):
        """验证 delete 删除缓存"""
        mock_redis = MagicMock()

        cache = RedisMemoryCache(mock_redis)

        user_id = str(uuid.uuid4())
        name = "test-memory"

        cache.delete("private", user_id, name)

        mock_redis.delete.assert_called_once_with(f"memory:user:{user_id}:test-memory")


class TestRedisMemoryCacheInvalidatePattern:
    """RedisMemoryCache invalidate_pattern 方法验证"""

    def test_invalidate_pattern_deletes_matching_keys(self):
        """验证 invalidate_pattern 删除匹配的所有 key"""
        mock_redis = MagicMock()
        mock_redis.keys.return_value = [
            f"memory:user:{uuid.uuid4()}:doc1",
            f"memory:user:{uuid.uuid4()}:doc2",
        ]

        cache = RedisMemoryCache(mock_redis)

        user_id = str(uuid.uuid4())

        cache.invalidate_pattern("private", user_id)

        mock_redis.keys.assert_called_once()
        mock_redis.delete.assert_called_once()
