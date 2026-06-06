"""RedisAdapter 单元测试

验证 L1CachePort 实现中 Redis 字符串操作的正确行为，
包括 get/set/delete/exists/delete_pattern/set_with_ttl 及 raw_client 属性
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.redis.redis_adapter import RedisAdapter


@pytest.fixture
def mock_redis() -> AsyncMock:
    """创建 mock aioredis.Redis 实例"""
    redis = AsyncMock()
    redis.get = AsyncMock()
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    redis.exists = AsyncMock()
    redis.scan_iter = MagicMock()
    return redis


@pytest.fixture
def adapter(mock_redis: AsyncMock) -> RedisAdapter:
    """创建 RedisAdapter 实例"""
    return RedisAdapter(redis_client=mock_redis)


class TestRedisAdapterGet:
    """get 方法测试"""

    async def test_get_returns_decoded_string_for_bytes(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """bytes 类型值应解码为 str 返回"""
        mock_redis.get.return_value = b"hello"

        result = await adapter.get("mykey")

        mock_redis.get.assert_called_once_with("mykey")
        assert result == "hello"

    async def test_get_returns_str_as_is(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """str 类型值应直接返回"""
        mock_redis.get.return_value = "world"

        result = await adapter.get("mykey")

        assert result == "world"

    async def test_get_returns_none_for_missing_key(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """键不存在时应返回 None"""
        mock_redis.get.return_value = None

        result = await adapter.get("missing_key")

        assert result is None


class TestRedisAdapterSet:
    """set 方法测试"""

    async def test_set_with_ttl_uses_setex(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """带 TTL 的 set 应调用 setex"""
        result = await adapter.set("key1", "value1", ttl=300)

        mock_redis.setex.assert_called_once_with("key1", 300, "value1")
        mock_redis.set.assert_not_called()
        assert result is True

    async def test_set_without_ttl_uses_set(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """不带 TTL 的 set 应调用 set"""
        result = await adapter.set("key1", "value1")

        mock_redis.set.assert_called_once_with("key1", "value1")
        mock_redis.setex.assert_not_called()
        assert result is True

    async def test_set_with_explicit_none_ttl_uses_set(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """显式 ttl=None 应调用 set 而非 setex"""
        result = await adapter.set("key1", "value1", ttl=None)

        mock_redis.set.assert_called_once_with("key1", "value1")
        mock_redis.setex.assert_not_called()
        assert result is True

    async def test_set_always_returns_true(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """set 应始终返回 True"""
        assert await adapter.set("k", "v", ttl=10) is True
        assert await adapter.set("k", "v") is True


class TestRedisAdapterDelete:
    """delete 方法测试"""

    async def test_delete_returns_true_when_key_exists(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """删除存在的键应返回 True"""
        mock_redis.delete.return_value = 1

        result = await adapter.delete("existing_key")

        mock_redis.delete.assert_called_once_with("existing_key")
        assert result is True

    async def test_delete_returns_false_when_key_missing(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """删除不存在的键应返回 False"""
        mock_redis.delete.return_value = 0

        result = await adapter.delete("missing_key")

        assert result is False

    async def test_delete_returns_true_for_multiple_deleted(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """delete 返回值大于 0 时应返回 True"""
        mock_redis.delete.return_value = 3

        result = await adapter.delete("key")

        assert result is True


class TestRedisAdapterExists:
    """exists 方法测试"""

    async def test_exists_returns_true_when_key_present(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """键存在时应返回 True"""
        mock_redis.exists.return_value = 1

        result = await adapter.exists("mykey")

        mock_redis.exists.assert_called_once_with("mykey")
        assert result is True

    async def test_exists_returns_false_when_key_absent(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """键不存在时应返回 False"""
        mock_redis.exists.return_value = 0

        result = await adapter.exists("mykey")

        assert result is False


class TestRedisAdapterDeletePattern:
    """delete_pattern 方法测试"""

    @staticmethod
    def _make_async_iter(items: list[bytes]):
        """构造模拟 scan_iter 返回值的异步可迭代对象"""

        async def _gen() -> Any:
            for item in items:
                yield item

        return _gen()

    async def test_delete_pattern_scans_and_deletes_matching_keys(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """应扫描匹配键并批量删除，返回删除数量"""
        mock_redis.scan_iter = MagicMock(return_value=self._make_async_iter([b"key1", b"key2", b"key3"]))

        result = await adapter.delete_pattern("session:*")

        mock_redis.scan_iter.assert_called_once_with(match="session:*")
        mock_redis.delete.assert_called_once_with(b"key1", b"key2", b"key3")
        assert result == 3

    async def test_delete_pattern_returns_zero_when_no_match(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """无匹配键时应返回 0 且不调用 delete"""
        mock_redis.scan_iter = MagicMock(return_value=self._make_async_iter([]))

        result = await adapter.delete_pattern("none:*")

        mock_redis.delete.assert_not_called()
        assert result == 0

    async def test_delete_pattern_single_key(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """匹配单个键时应正确删除并返回 1"""
        mock_redis.scan_iter = MagicMock(return_value=self._make_async_iter([b"only_key"]))

        result = await adapter.delete_pattern("prefix:*")

        mock_redis.delete.assert_called_once_with(b"only_key")
        assert result == 1


class TestRedisAdapterSetWithTtl:
    """set_with_ttl 方法测试"""

    async def test_set_with_ttl_uses_setex(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """set_with_ttl 应调用 setex"""
        result = await adapter.set_with_ttl("key1", "value1", 600)

        mock_redis.setex.assert_called_once_with("key1", 600, "value1")
        assert result is True

    async def test_set_with_ttl_always_returns_true(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """set_with_ttl 应始终返回 True"""
        result = await adapter.set_with_ttl("k", "v", 1)

        assert result is True


class TestRedisAdapterRawClient:
    """raw_client 属性测试"""

    def test_raw_client_returns_underlying_redis(self, adapter: RedisAdapter, mock_redis: AsyncMock) -> None:
        """raw_client 应返回构造时注入的 Redis 实例"""
        assert adapter.raw_client is mock_redis
