"""RedisMemoryCache async 实现测试。

验证 RedisMemoryCache 已重构为异步实现。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest


class TestRedisMemoryCacheAsync:
    """RedisMemoryCache 异步实现测试。"""

    @pytest.fixture
    def mock_redis_client(self):
        """创建模拟的 Redis 异步客户端。"""
        return AsyncMock()

    @pytest.fixture
    def cache(self, mock_redis_client):
        """创建 RedisMemoryCache 实例。"""
        from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache

        return RedisMemoryCache(mock_redis_client)

    def test_cache_uses_async_redis(self, cache) -> None:
        """Cache 应使用 redis.asyncio。"""
        assert hasattr(cache, "_redis")

    def test_get_is_async(self, cache) -> None:
        """get 方法应为异步。"""
        assert asyncio.iscoroutinefunction(cache.get)

    def test_set_is_async(self, cache) -> None:
        """set 方法应为异步。"""
        assert asyncio.iscoroutinefunction(cache.set)

    def test_delete_is_async(self, cache) -> None:
        """delete 方法应为异步。"""
        assert asyncio.iscoroutinefunction(cache.delete)

    def test_invalidate_pattern_is_async(self, cache) -> None:
        """invalidate_pattern 方法应为异步。"""
        assert asyncio.iscoroutinefunction(cache.invalidate_pattern)

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, cache, mock_redis_client) -> None:
        """get 应在 key 不存在时返回 None。"""
        mock_redis_client.get.return_value = None

        result = await cache.get("private", "user123", "test-memory")

        assert result is None
        mock_redis_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_returns_decoded_value(self, cache, mock_redis_client) -> None:
        """get 应返回解码后的字符串值。"""
        mock_redis_client.get.return_value = b"test content"

        result = await cache.get("private", "user123", "test-memory")

        assert result == "test content"

    @pytest.mark.asyncio
    async def test_set_calls_setex(self, cache, mock_redis_client) -> None:
        """set 应调用 Redis setex。"""
        mock_redis_client.setex.return_value = True

        result = await cache.set("private", "user123", "test-memory", "content")

        assert result is True
        mock_redis_client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self, cache, mock_redis_client) -> None:
        """set 应使用自定义 TTL。"""
        mock_redis_client.setex.return_value = True

        await cache.set("private", "user123", "test-memory", "content", ttl=3600)

        call_args = mock_redis_client.setex.call_args
        # setex is called with (key, ttl, value)
        args = call_args[0]
        assert args[1] == 3600  # second arg is TTL

    @pytest.mark.asyncio
    async def test_delete_calls_redis_delete(self, cache, mock_redis_client) -> None:
        """delete 应调用 Redis delete。"""
        mock_redis_client.delete.return_value = 1

        result = await cache.delete("private", "user123", "test-memory")

        assert result is True
        mock_redis_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_pattern_uses_scan_iter(self, cache, mock_redis_client) -> None:
        """invalidate_pattern 应使用 scan_iter 而非 keys。"""

        async def mock_scan_iter(match):
            keys = ["memory:user:user123:mem1", "memory:user:user123:mem2"]
            for key in keys:
                yield key

        mock_redis_client.scan_iter = mock_scan_iter
        mock_redis_client.delete.return_value = 2

        count = await cache.invalidate_pattern("private", "user123")

        assert count == 2
        mock_redis_client.delete.assert_called_once()

    def test_build_key_for_user(self, cache) -> None:
        """_build_key 应为 user 类型生成正确格式。"""
        key = cache._build_key("private", "user123", "test-memory")
        assert key == "memory:user:user123:test-memory"

    def test_build_key_for_group(self, cache) -> None:
        """_build_key 应为 group 类型生成正确格式。"""
        key = cache._build_key("group", "group456", "test-memory")
        assert key == "memory:group:group456:test-memory"

    def test_build_pattern_for_user(self, cache) -> None:
        """_build_pattern 应为 user 类型生成正确格式。"""
        pattern = cache._build_pattern("private", "user123")
        assert pattern == "memory:user:user123:*"

    def test_build_pattern_for_group(self, cache) -> None:
        """_build_pattern 应为 group 类型生成正确格式。"""
        pattern = cache._build_pattern("group", "group456")
        assert pattern == "memory:group:group456:*"

    def test_generate_ttl_returns_valid_range(self, cache) -> None:
        """_generate_ttl 应返回 86400-108000 范围内的值。"""
        import random

        random.seed(42)
        ttl = cache._generate_ttl()

        assert 86400 <= ttl <= 108000


class TestRedisMemoryCacheL1CachePortCompliance:
    """Verify RedisMemoryCache has L1CachePort methods — structural check."""

    def test_redis_cache_has_all_required_methods(self) -> None:
        """RedisMemoryCache should have all L1CachePort methods."""
        from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache

        mock_redis = AsyncMock()
        cache = RedisMemoryCache(mock_redis)

        for method_name in ["get", "set", "delete", "invalidate_pattern"]:
            assert hasattr(cache, method_name), f"Missing method: {method_name}"
