"""RedisMemoryCache tests — Rule 4 MemoryCachePort implementation.

Verifies RedisMemoryCache composes RedisAdapter and delegates correctly.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache


@pytest.fixture
def mock_redis_client():
    return AsyncMock()


@pytest.fixture
def adapter(mock_redis_client):
    return RedisAdapter(mock_redis_client)


@pytest.fixture
def cache(adapter):
    return RedisMemoryCache(adapter)


class TestRedisMemoryCacheGenericKV:
    """L1CachePort generic KV methods (delegated to RedisAdapter)."""

    def test_cache_has_adapter(self, cache, adapter):
        assert cache._adapter is adapter

    def test_get_is_async(self, cache):
        assert asyncio.iscoroutinefunction(cache.get)

    def test_set_is_async(self, cache):
        assert asyncio.iscoroutinefunction(cache.set)

    def test_delete_is_async(self, cache):
        assert asyncio.iscoroutinefunction(cache.delete)

    @pytest.mark.asyncio
    async def test_get_delegates_to_adapter(self, cache, mock_redis_client):
        mock_redis_client.get.return_value = b"value"
        result = await cache.get("some:key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_set_delegates_to_adapter(self, cache, mock_redis_client):
        mock_redis_client.set.return_value = True
        result = await cache.set("some:key", "value")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_delegates_to_adapter(self, cache, mock_redis_client):
        mock_redis_client.delete.return_value = 1
        result = await cache.delete("some:key")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_delegates_to_adapter(self, cache, mock_redis_client):
        mock_redis_client.exists.return_value = 1
        result = await cache.exists("some:key")
        assert result is True


class TestRedisMemoryCacheMemoryMethods:
    """MemoryCachePort memory-specific methods."""

    @pytest.mark.asyncio
    async def test_get_memory_returns_none_when_not_found(self, cache, mock_redis_client):
        mock_redis_client.get.return_value = None
        result = await cache.get_memory("private", "user123", "test-memory")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_memory_returns_decoded_value(self, cache, mock_redis_client):
        mock_redis_client.get.return_value = b"test content"
        result = await cache.get_memory("private", "user123", "test-memory")
        assert result == "test content"

    @pytest.mark.asyncio
    async def test_set_memory_calls_setex(self, cache, mock_redis_client):
        mock_redis_client.setex.return_value = True
        result = await cache.set_memory("private", "user123", "test-memory", "content")
        assert result is True
        mock_redis_client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_memory_with_custom_ttl(self, cache, mock_redis_client):
        mock_redis_client.setex.return_value = True
        await cache.set_memory("private", "user123", "test-memory", "content", ttl=3600)
        call_args = mock_redis_client.setex.call_args
        assert call_args[0][1] == 3600

    @pytest.mark.asyncio
    async def test_delete_memory_calls_redis_delete(self, cache, mock_redis_client):
        mock_redis_client.delete.return_value = 1
        result = await cache.delete_memory("private", "user123", "test-memory")
        assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_owner_uses_scan_iter(self, cache, mock_redis_client):
        async def mock_scan_iter(match):
            for key in ["memory:user:user123:mem1", "memory:user:user123:mem2"]:
                yield key

        mock_redis_client.scan_iter = mock_scan_iter
        mock_redis_client.delete.return_value = 2

        count = await cache.invalidate_owner("private", "user123")
        assert count == 2

    def test_build_key_for_user(self, cache):
        key = cache._build_key("private", "user123", "test-memory")
        assert key == "memory:user:user123:test-memory"

    def test_build_key_for_group(self, cache):
        key = cache._build_key("group", "group456", "test-memory")
        assert key == "memory:group:group456:test-memory"

    def test_build_pattern_for_user(self, cache):
        pattern = cache._build_pattern("private", "user123")
        assert pattern == "memory:user:user123:*"

    def test_build_pattern_for_group(self, cache):
        pattern = cache._build_pattern("group", "group456")
        assert pattern == "memory:group:group456:*"

    def test_generate_ttl_returns_valid_range(self, cache):
        import random

        random.seed(42)
        ttl = cache._generate_ttl()
        assert 86400 <= ttl <= 108000


class TestRedisMemoryCachePortCompliance:
    """Verify RedisMemoryCache satisfies both L1CachePort and MemoryCachePort."""

    def test_has_l1_cache_port_methods(self):
        from src.domain.ports.l1_cache import L1CachePort

        assert isinstance(RedisMemoryCache(MagicMock()), L1CachePort)

    def test_has_memory_cache_port_methods(self):
        from src.application.ports.memory_cache_port import MemoryCachePort

        assert isinstance(RedisMemoryCache(MagicMock()), MemoryCachePort)
