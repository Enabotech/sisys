"""QdrantManager 生命周期管理单元测试

覆盖 Qdrant 异步客户端的构造、懒初始化、健康检查、优雅关闭等生命周期行为
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager


def _make_config(**overrides):
    """构造模拟 QdrantConfig 实例

    Args:
        **overrides: 需要覆盖的配置字段

    Returns:
        配置好默认值的 MagicMock 实例
    """
    defaults = {
        "host": "localhost",
        "port": 6333,
        "grpc_port": 6334,
        "api_key": None,
        "https": False,
        "timeout": 5.0,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


MOCK_PATH = "src.infrastructure.storage.qdrant.qdrant_manager.AsyncQdrantClient"


class TestQdrantManagerConstructor:
    """QdrantManager 构造器行为测试"""

    def test_uses_provided_config(self):
        """传入自定义配置时，不应从环境变量加载"""
        config = _make_config(host="custom-host", port=9999)

        with patch(MOCK_PATH):
            manager = QdrantManager(config=config)

        assert manager._config is config
        assert manager._config.host == "custom-host"
        assert manager._config.port == 9999

    @patch("src.infrastructure.storage.qdrant.qdrant_manager.QdrantConfig")
    def test_loads_config_from_env_when_none(self, mock_config_cls):
        """未传入配置时，应调用 QdrantConfig.from_env() 加载"""
        mock_config_cls.from_env.return_value = _make_config()

        manager = QdrantManager(config=None)

        mock_config_cls.from_env.assert_called_once()
        assert manager._config is mock_config_cls.from_env.return_value

    def test_client_is_none_initially(self):
        """构造后客户端实例应为 None（懒初始化）"""
        config = _make_config()

        with patch(MOCK_PATH):
            manager = QdrantManager(config=config)

        assert manager._client is None


class TestQdrantManagerGetClient:
    """QdrantManager.get_client 懒初始化行为测试"""

    def test_first_call_creates_client(self):
        """首次调用应通过 _create_client 创建新客户端"""
        config = _make_config()
        mock_client_instance = MagicMock()

        with patch(MOCK_PATH, return_value=mock_client_instance) as mock_cls:
            manager = QdrantManager(config=config)
            client = manager.get_client()

        mock_cls.assert_called_once_with(
            host="localhost",
            port=6333,
            grpc_port=6334,
            api_key=None,
            https=False,
            timeout=5,
            prefer_grpc=False,
        )
        assert client is mock_client_instance

    def test_second_call_returns_same_instance(self):
        """第二次调用应返回与第一次相同的客户端实例"""
        config = _make_config()
        mock_client_instance = MagicMock()

        with patch(MOCK_PATH, return_value=mock_client_instance):
            manager = QdrantManager(config=config)
            first = manager.get_client()
            second = manager.get_client()

        assert first is second

    def test_timeout_none_when_config_timeout_is_none(self):
        """配置中 timeout 为 None 时，传给 AsyncQdrantClient 的 timeout 应为 None"""
        config = _make_config(timeout=None)

        with patch(MOCK_PATH) as mock_cls:
            manager = QdrantManager(config=config)
            manager.get_client()

        _, kwargs = mock_cls.call_args
        assert kwargs["timeout"] is None

    def test_timeout_converted_to_int(self):
        """配置中 timeout 为浮点数时，应转换为整数传给客户端"""
        config = _make_config(timeout=12.7)

        with patch(MOCK_PATH) as mock_cls:
            manager = QdrantManager(config=config)
            manager.get_client()

        _, kwargs = mock_cls.call_args
        assert kwargs["timeout"] == 12
        assert isinstance(kwargs["timeout"], int)


class TestQdrantManagerGetAsyncClient:
    """QdrantManager.get_async_client 别名行为测试"""

    def test_returns_same_as_get_client(self):
        """get_async_client 应返回与 get_client 相同的客户端实例"""
        config = _make_config()
        mock_client_instance = MagicMock()

        with patch(MOCK_PATH, return_value=mock_client_instance):
            manager = QdrantManager(config=config)
            sync_client = manager.get_client()
            async_client = manager.get_async_client()

        assert async_client is sync_client


class TestQdrantManagerHealthCheck:
    """QdrantManager.health_check 健康检查行为测试"""

    async def test_returns_true_when_collections_succeed(self):
        """get_collections 正常返回时，健康检查应返回 True"""
        config = _make_config()
        mock_client = AsyncMock()
        mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))

        with patch(MOCK_PATH, return_value=mock_client):
            manager = QdrantManager(config=config)
            result = await manager.health_check()

        assert result is True

    async def test_returns_false_on_exception(self):
        """get_collections 抛出异常时，健康检查应返回 False"""
        config = _make_config()
        mock_client = AsyncMock()
        mock_client.get_collections = AsyncMock(side_effect=ConnectionError("连接失败"))

        with patch(MOCK_PATH, return_value=mock_client):
            manager = QdrantManager(config=config)
            result = await manager.health_check()

        assert result is False


class TestQdrantManagerClose:
    """QdrantManager.close 优雅关闭行为测试"""

    async def test_calls_client_close_and_resets_to_none(self):
        """关闭时应调用客户端的 close 方法并将内部引用置为 None"""
        config = _make_config()
        mock_client = AsyncMock()

        with patch(MOCK_PATH, return_value=mock_client):
            manager = QdrantManager(config=config)
            manager.get_client()
            await manager.close()

        mock_client.close.assert_awaited_once()
        assert manager._client is None

    async def test_does_nothing_when_client_is_none(self):
        """客户端为 None 时关闭不应抛出异常"""
        config = _make_config()

        with patch(MOCK_PATH):
            manager = QdrantManager(config=config)

        assert manager._client is None
        await manager.close()
        assert manager._client is None

    async def test_get_client_creates_new_after_close(self):
        """关闭后再次 get_client 应创建新的客户端实例"""
        config = _make_config()
        first_client = AsyncMock()
        second_client = AsyncMock()

        with patch(MOCK_PATH, side_effect=[first_client, second_client]):
            manager = QdrantManager(config=config)
            client_before = manager.get_client()
            assert client_before is first_client

            await manager.close()
            assert manager._client is None

            client_after = manager.get_client()
            assert client_after is second_client
            assert client_after is not first_client
