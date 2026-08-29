"""RedisSessionCache 单元测试。

使用 AsyncMock 验证 RedisSessionCache 的会话操作，
遵循基础设施层测试规范：Mock 底层适配器，验证端口逻辑。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.redis.redis_session_cache import RedisSessionCache


class TestRedisSessionCache:
    """RedisSessionCache 测试套件。"""

    @pytest.fixture
    def mock_adapter(self) -> MagicMock:
        adapter = MagicMock()
        adapter.get = AsyncMock(return_value=None)
        adapter.set = AsyncMock(return_value=True)
        adapter.delete = AsyncMock(return_value=True)
        adapter.exists = AsyncMock(return_value=True)
        adapter.delete_pattern = AsyncMock(return_value=3)
        adapter.set_with_ttl = AsyncMock(return_value=True)
        adapter.set_nx = AsyncMock(return_value=True)
        adapter.eval = AsyncMock(return_value="ok")
        adapter.raw_client = MagicMock()
        adapter.raw_client.hset = AsyncMock()
        adapter.raw_client.hget = AsyncMock(return_value=None)
        adapter.raw_client.expire = AsyncMock()
        return adapter

    @pytest.mark.asyncio
    async def test_save_and_load_session(self, mock_adapter: MagicMock) -> None:
        """保存并加载会话应返回一致数据。"""
        cache = RedisSessionCache(mock_adapter)
        state = {"key": "value"}
        await cache.save_session("sess-1", "agent-1", state)

        # 模拟 hget 返回序列化数据
        import json

        mock_adapter.raw_client.hget.return_value = json.dumps(
            {"session_id": "sess-1", "agent_id": "agent-1", "state": state}
        ).encode()
        loaded = await cache.load_session("sess-1")
        assert loaded is not None
        assert loaded["session_id"] == "sess-1"
        assert loaded["state"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_load_session_not_found(self, mock_adapter: MagicMock) -> None:
        """加载不存在的会话应返回 None。"""
        cache = RedisSessionCache(mock_adapter)
        result = await cache.load_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session(self, mock_adapter: MagicMock) -> None:
        """删除会话应调用底层 delete。"""
        cache = RedisSessionCache(mock_adapter)
        await cache.delete_session("sess-1")
        mock_adapter.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_exists(self, mock_adapter: MagicMock) -> None:
        """session_exists 应委派底层 exists。"""
        cache = RedisSessionCache(mock_adapter)
        result = await cache.session_exists("sess-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_generic_get_set(self, mock_adapter: MagicMock) -> None:
        """通用 get/set 应委派底层适配器。"""
        cache = RedisSessionCache(mock_adapter)
        await cache.set("k", "v", ttl=100)
        mock_adapter.set.assert_called_once_with("k", "v", 100)
        await cache.get("k")
        mock_adapter.get.assert_called_once_with("k")
