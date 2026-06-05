"""RedisManager 单元测试

验证 Redis 异步连接管理器的生命周期：
- 懒创建连接池和客户端
- 健康检查（PING 成功/失败）
- 连接池关闭和资源释放
"""

from __future__ import annotations

from unittest import mock

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.storage.redis.redis_manager import RedisManager


class TestRedisManagerInit:
    """RedisManager 初始化测试"""

    def test_init_stores_config(self) -> None:
        """初始化应存储配置且连接池为空"""
        config = RedisConfig(host="redis-test", port=6380, db=1)
        manager = RedisManager(config)

        assert manager._config is config
        assert manager._pool is None
        assert manager._redis is None

    def test_init_with_default_config(self) -> None:
        """使用默认配置初始化"""
        config = RedisConfig()
        manager = RedisManager(config)

        assert manager._config.host == "localhost"
        assert manager._config.port == 6379


class TestRedisManagerGetClient:
    """get_client 测试 — 懒创建连接池和 Redis 客户端"""

    def test_get_client_creates_pool_and_client(self) -> None:
        """首次调用 get_client 应创建连接池和客户端"""
        config = RedisConfig(host="test-host", port=6379, db=0, max_connections=5)
        manager = RedisManager(config)

        with mock.patch("redis.asyncio.ConnectionPool") as mock_pool_cls, mock.patch("redis.asyncio.Redis") as mock_redis_cls:
            mock_pool = mock.MagicMock()
            mock_pool_cls.return_value = mock_pool
            mock_client = mock.MagicMock()
            mock_redis_cls.return_value = mock_client

            client = manager.get_client()

            # 验证连接池创建参数
            mock_pool_cls.assert_called_once_with(
                host="test-host",
                port=6379,
                db=0,
                password=None,
                max_connections=5,
                socket_timeout=5.0,
                decode_responses=True,
            )
            mock_redis_cls.assert_called_once_with(connection_pool=mock_pool)
            assert client is mock_client

    def test_get_client_returns_cached_client(self) -> None:
        """第二次调用应返回缓存的客户端不重新创建"""
        config = RedisConfig()
        manager = RedisManager(config)

        with mock.patch("redis.asyncio.ConnectionPool") as mock_pool_cls, mock.patch("redis.asyncio.Redis") as mock_redis_cls:
            mock_pool_cls.return_value = mock.MagicMock()
            mock_redis_cls.return_value = mock.MagicMock()

            client1 = manager.get_client()
            client2 = manager.get_client()

            assert client1 is client2
            # 连接池和客户端各只创建一次
            assert mock_pool_cls.call_count == 1
            assert mock_redis_cls.call_count == 1

    def test_get_client_with_password(self) -> None:
        """带密码的连接池创建"""
        config = RedisConfig(host="secure-host", password="secret")  # pragma: allowlist secret
        manager = RedisManager(config)

        with mock.patch("redis.asyncio.ConnectionPool") as mock_pool_cls, mock.patch("redis.asyncio.Redis") as mock_redis_cls:
            mock_pool_cls.return_value = mock.MagicMock()
            mock_redis_cls.return_value = mock.MagicMock()

            manager.get_client()

            call_kwargs = mock_pool_cls.call_args.kwargs
            assert call_kwargs["password"] == "secret"  # pragma: allowlist secret


class TestRedisManagerHealthCheck:
    """health_check 测试"""

    async def test_health_check_returns_true(self) -> None:
        """PING 成功返回 True"""
        config = RedisConfig()
        manager = RedisManager(config)

        with mock.patch("redis.asyncio.ConnectionPool"), mock.patch("redis.asyncio.Redis") as mock_redis_cls:
            mock_client = mock.MagicMock()
            mock_client.ping = mock.AsyncMock(return_value=True)
            mock_redis_cls.return_value = mock_client

            result = await manager.health_check()

            assert result is True
            mock_client.ping.assert_awaited_once()

    async def test_health_check_returns_false_on_error(self) -> None:
        """PING 失败返回 False"""
        config = RedisConfig()
        manager = RedisManager(config)

        with mock.patch("redis.asyncio.ConnectionPool"), mock.patch("redis.asyncio.Redis") as mock_redis_cls:
            mock_client = mock.MagicMock()
            mock_client.ping = mock.AsyncMock(side_effect=ConnectionError("no connection"))
            mock_redis_cls.return_value = mock_client

            result = await manager.health_check()

            assert result is False


class TestRedisManagerClose:
    """close 测试 — 资源释放"""

    async def test_close_releases_pool_and_client(self) -> None:
        """close 应断开连接池并清理引用"""
        config = RedisConfig()
        manager = RedisManager(config)

        with mock.patch("redis.asyncio.ConnectionPool"), mock.patch("redis.asyncio.Redis") as mock_redis_cls:
            mock_client = mock.MagicMock()
            mock_client.close = mock.AsyncMock()
            mock_redis_cls.return_value = mock_client

            mock_pool = mock.MagicMock()
            mock_pool.disconnect = mock.AsyncMock()

            # 手动注入 pool 和 redis 以测试 close
            manager._pool = mock_pool
            manager._redis = mock_client

            await manager.close()

            mock_client.close.assert_awaited_once()
            mock_pool.disconnect.assert_awaited_once()
            assert manager._redis is None
            assert manager._pool is None

    async def test_close_when_not_initialized(self) -> None:
        """未初始化时 close 不报错"""
        config = RedisConfig()
        manager = RedisManager(config)

        # _pool 和 _redis 均为 None — close 应静默完成
        await manager.close()

        assert manager._pool is None
        assert manager._redis is None

    async def test_close_with_redis_but_no_pool(self) -> None:
        """_redis 存在但 _pool 为 None 时仅关闭 redis"""
        config = RedisConfig()
        manager = RedisManager(config)

        mock_client = mock.MagicMock()
        mock_client.close = mock.AsyncMock()
        manager._redis = mock_client
        manager._pool = None

        await manager.close()

        mock_client.close.assert_awaited_once()
        assert manager._redis is None
