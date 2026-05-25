"""RedisSessionCache 单元测试

验证 L1 委托方法和会话特定方法的正确行为
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.storage.redis.redis_session_cache import RedisSessionCache


@pytest.fixture
def mock_adapter() -> AsyncMock:
    """创建 mock RedisAdapter"""
    adapter = AsyncMock()
    adapter.get = AsyncMock(return_value="value")
    adapter.set = AsyncMock(return_value=True)
    adapter.delete = AsyncMock(return_value=True)
    adapter.exists = AsyncMock(return_value=True)
    adapter.delete_pattern = AsyncMock(return_value=3)
    adapter.set_with_ttl = AsyncMock(return_value=True)

    # raw_client for session-specific operations
    raw_client = AsyncMock()
    raw_client.hset = AsyncMock()
    raw_client.expire = AsyncMock()
    raw_client.hget = AsyncMock()
    adapter.raw_client = raw_client

    return adapter


@pytest.fixture
def session_cache(mock_adapter: AsyncMock) -> RedisSessionCache:
    """创建 RedisSessionCache 实例"""
    return RedisSessionCache(adapter=mock_adapter)


class TestRedisSessionCacheL1Delegation:
    """L1CachePort 委托方法测试"""

    async def test_get_delegates_to_adapter(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """get 应委托给 adapter.get"""
        result = await session_cache.get("key1")
        mock_adapter.get.assert_called_once_with("key1")
        assert result == "value"

    async def test_set_delegates_to_adapter(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """set 应委托给 adapter.set"""
        result = await session_cache.set("key1", "val1", ttl=60)
        mock_adapter.set.assert_called_once_with("key1", "val1", 60)
        assert result is True

    async def test_set_default_ttl(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """set 默认 ttl=None 应传递给 adapter"""
        await session_cache.set("key1", "val1")
        mock_adapter.set.assert_called_once_with("key1", "val1", None)

    async def test_delete_delegates_to_adapter(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """delete 应委托给 adapter.delete"""
        result = await session_cache.delete("key1")
        mock_adapter.delete.assert_called_once_with("key1")
        assert result is True

    async def test_exists_delegates_to_adapter(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """exists 应委托给 adapter.exists"""
        result = await session_cache.exists("key1")
        mock_adapter.exists.assert_called_once_with("key1")
        assert result is True

    async def test_delete_pattern_delegates_to_adapter(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """delete_pattern 应委托给 adapter.delete_pattern"""
        result = await session_cache.delete_pattern("session:*")
        mock_adapter.delete_pattern.assert_called_once_with("session:*")
        assert result == 3

    async def test_set_with_ttl_delegates_to_adapter(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """set_with_ttl 应委托给 adapter.set_with_ttl"""
        result = await session_cache.set_with_ttl("key1", "val1", 300)
        mock_adapter.set_with_ttl.assert_called_once_with("key1", "val1", 300)
        assert result is True


class TestRedisSessionCacheSessionMethods:
    """SessionCachePort 会话方法测试"""

    async def test_save_session_stores_hash(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """save_session 应使用 HSET 存储序列化数据"""
        state = {"step": 1, "data": "test"}
        await session_cache.save_session("sess-1", "agent-1", state, ttl=3600)

        # Verify HSET was called with correct key and serialized data
        mock_adapter.raw_client.hset.assert_called_once()
        call_args = mock_adapter.raw_client.hset.call_args
        assert call_args[0][0] == "sisys:session:sess-1"
        assert call_args[0][1] == "data"

        # Verify TTL was set
        mock_adapter.raw_client.expire.assert_called_once_with("sisys:session:sess-1", 3600)

        # Verify data contains all fields
        stored_data = json.loads(call_args[0][2])
        assert stored_data["session_id"] == "sess-1"
        assert stored_data["agent_id"] == "agent-1"
        assert stored_data["state"] == state

    async def test_save_session_default_ttl(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """save_session 默认 TTL 应为 86400"""
        await session_cache.save_session("sess-2", "agent-2", {})
        mock_adapter.raw_client.expire.assert_called_once_with("sisys:session:sess-2", 86400)

    async def test_load_session_returns_dict(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """load_session 应反序列化并返回字典"""
        data = json.dumps({"session_id": "sess-1", "agent_id": "agent-1", "state": {"step": 1}})
        mock_adapter.raw_client.hget.return_value = data

        result = await session_cache.load_session("sess-1")
        assert result is not None
        assert result["session_id"] == "sess-1"
        assert result["state"]["step"] == 1

    async def test_load_session_returns_none_when_missing(
        self, session_cache: RedisSessionCache, mock_adapter: AsyncMock
    ) -> None:
        """load_session 对不存在的会话应返回 None"""
        mock_adapter.raw_client.hget.return_value = None
        result = await session_cache.load_session("nonexistent")
        assert result is None

    async def test_load_session_returns_none_for_non_dict(
        self, session_cache: RedisSessionCache, mock_adapter: AsyncMock
    ) -> None:
        """load_session 对非字典数据应返回 None"""
        mock_adapter.raw_client.hget.return_value = json.dumps([1, 2, 3])
        result = await session_cache.load_session("sess-bad")
        assert result is None

    async def test_delete_session_uses_adapter(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """delete_session 应通过 adapter.delete 删除"""
        await session_cache.delete_session("sess-1")
        mock_adapter.delete.assert_called_once_with("sisys:session:sess-1")

    async def test_session_exists_uses_adapter(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """session_exists 应通过 adapter.exists 检查"""
        result = await session_cache.session_exists("sess-1")
        mock_adapter.exists.assert_called_once_with("sisys:session:sess-1")
        assert result is True

    async def test_session_exists_false(self, session_cache: RedisSessionCache, mock_adapter: AsyncMock) -> None:
        """session_exists 对不存在会话应返回 False"""
        mock_adapter.exists.return_value = False
        result = await session_cache.session_exists("nonexistent")
        assert result is False
