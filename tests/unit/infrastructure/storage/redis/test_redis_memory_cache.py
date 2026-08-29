"""RedisMemoryCache 单元测试。

验证 RedisMemoryCache 的键构建、TTL 随机化、记忆操作。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.redis.redis_memory_cache import (
    DEFAULT_TTL_MAX,
    DEFAULT_TTL_MIN,
    RedisMemoryCache,
)


class TestRedisMemoryCache:
    """RedisMemoryCache 测试套件。"""

    @pytest.fixture
    def mock_adapter(self) -> MagicMock:
        adapter = MagicMock()
        adapter.get = AsyncMock(return_value=None)
        adapter.set = AsyncMock(return_value=True)
        adapter.delete = AsyncMock(return_value=True)
        adapter.exists = AsyncMock(return_value=True)
        adapter.delete_pattern = AsyncMock(return_value=2)
        adapter.set_with_ttl = AsyncMock(return_value=True)
        adapter.set_nx = AsyncMock(return_value=True)
        adapter.eval = AsyncMock()
        return adapter

    @pytest.mark.asyncio
    async def test_get_memory_user(self, mock_adapter: MagicMock) -> None:
        """user 类型记忆应使用正确键。"""
        cache = RedisMemoryCache(mock_adapter)
        mock_adapter.get.return_value = "content"
        result = await cache.get_memory("user", "u1", "记忆A")
        assert result == "content"
        mock_adapter.get.assert_called_once_with("memory:user:u1:记忆A")

    @pytest.mark.asyncio
    async def test_get_memory_group(self, mock_adapter: MagicMock) -> None:
        """group 类型记忆应使用正确键。"""
        cache = RedisMemoryCache(mock_adapter)
        await cache.get_memory("group", "g1", "团队记忆")
        mock_adapter.get.assert_called_once_with("memory:group:g1:团队记忆")

    @pytest.mark.asyncio
    async def test_set_memory_uses_ttl(self, mock_adapter: MagicMock) -> None:
        """set_memory 应调用 set_with_ttl，无 ttl 时使用随机 TTL。"""
        cache = RedisMemoryCache(mock_adapter)
        await cache.set_memory("user", "u1", "name", "content")
        mock_adapter.set_with_ttl.assert_called_once()
        args, kwargs = mock_adapter.set_with_ttl.call_args
        assert kwargs.get("ttl", args[2] if len(args) > 2 else None) is not None
        ttl_value = kwargs.get("ttl", args[2] if len(args) > 2 else 0)
        assert ttl_value >= DEFAULT_TTL_MIN
        assert ttl_value <= DEFAULT_TTL_MAX

    @pytest.mark.asyncio
    async def test_set_memory_with_explicit_ttl(self, mock_adapter: MagicMock) -> None:
        """显式 TTL 应被使用。"""
        cache = RedisMemoryCache(mock_adapter)
        await cache.set_memory("user", "u1", "name", "content", ttl=123)
        args, kwargs = mock_adapter.set_with_ttl.call_args
        ttl_value = kwargs.get("ttl", args[2] if len(args) > 2 else 0)
        assert ttl_value == 123

    @pytest.mark.asyncio
    async def test_delete_memory(self, mock_adapter: MagicMock) -> None:
        """delete_memory 应委派底层 delete。"""
        cache = RedisMemoryCache(mock_adapter)
        await cache.delete_memory("user", "u1", "name")
        mock_adapter.delete.assert_called_once_with("memory:user:u1:name")

    @pytest.mark.asyncio
    async def test_invalidate_owner(self, mock_adapter: MagicMock) -> None:
        """invalidate_owner 应删除该 owner 的所有匹配键。"""
        cache = RedisMemoryCache(mock_adapter)
        result = await cache.invalidate_owner("user", "u1")
        assert result == 2
        mock_adapter.delete_pattern.assert_called_once_with("memory:user:u1:*")

    def test_build_key_user(self) -> None:
        """_build_key 用户类型。"""
        cache = RedisMemoryCache(MagicMock())
        key = cache._build_key("user", "u1", "name")
        assert key == "memory:user:u1:name"

    def test_build_key_group(self) -> None:
        """_build_key 群组类型。"""
        cache = RedisMemoryCache(MagicMock())
        key = cache._build_key("group", "g1", "name")
        assert key == "memory:group:g1:name"

    def test_build_pattern_user(self) -> None:
        """_build_pattern 用户类型。"""
        cache = RedisMemoryCache(MagicMock())
        pattern = cache._build_pattern("user", "u1")
        assert pattern == "memory:user:u1:*"

    def test_build_pattern_group(self) -> None:
        """_build_pattern 群组类型。"""
        cache = RedisMemoryCache(MagicMock())
        pattern = cache._build_pattern("group", "g1")
        assert pattern == "memory:group:g1:*"

    def test_generate_ttl_in_range(self) -> None:
        """_generate_ttl 返回值在有效范围内。"""
        cache = RedisMemoryCache(MagicMock())
        for _ in range(50):
            ttl = cache._generate_ttl()
            assert DEFAULT_TTL_MIN <= ttl <= DEFAULT_TTL_MAX
