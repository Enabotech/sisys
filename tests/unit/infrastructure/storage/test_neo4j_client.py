"""Neo4jClient 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.config.neo4j import Neo4jConfig
from src.infrastructure.storage.neo4j.client import Neo4jClientWrapper


class _AsyncCM:
    """辅助类：模拟异步上下文管理器。"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def mock_async_driver():
    """模拟异步 Neo4j 驱动。"""
    return MagicMock()


@pytest.fixture
def mock_session():
    """模拟 Neo4j 会话。"""
    return MagicMock()


class TestNeo4jClientWrapper:
    """Neo4jClientWrapper 测试类。"""

    def test_default_initialization(self):
        """测试默认初始化。"""
        wrapper = Neo4jClientWrapper()
        assert wrapper._config.host == "localhost"
        assert wrapper._config.bolt_port == 7687
        assert wrapper._config.username == "neo4j"
        assert wrapper._config.password == ""
        assert wrapper._config.database == "neo4j"
        assert wrapper._config.max_connection_pool_size == 50
        assert wrapper._config.connection_timeout == 30.0
        assert wrapper._driver is None

    def test_custom_initialization(self):
        """测试自定义初始化。"""
        config = Neo4jConfig(
            host="neo4j.example.com",
            bolt_port=7687,
            username="admin",
            password="secret",  # pragma: allowlist secret
            database="sisys_db",
            max_connection_pool_size=100,
            connection_timeout=60.0,
        )
        wrapper = Neo4jClientWrapper(config)
        assert wrapper._config.uri == "bolt://neo4j.example.com:7687"
        assert wrapper._config.username == "admin"
        assert wrapper._config.password == "secret"  # pragma: allowlist secret
        assert wrapper._config.database == "sisys_db"
        assert wrapper._config.max_connection_pool_size == 100
        assert wrapper._config.connection_timeout == 60.0

    @patch("src.infrastructure.storage.neo4j.client.AsyncGraphDatabase")
    def test_lazy_initialization(self, mock_db: MagicMock, mock_async_driver: MagicMock):
        """测试懒初始化。"""
        mock_db.driver.return_value = mock_async_driver
        wrapper = Neo4jClientWrapper()
        assert wrapper._driver is None

        driver = wrapper.get_client()
        assert driver is not None
        assert wrapper._driver is mock_async_driver
        mock_db.driver.assert_called_once()

        driver2 = wrapper.get_client()
        assert driver2 is driver
        assert mock_db.driver.call_count == 1

    @patch("src.infrastructure.storage.neo4j.client.AsyncGraphDatabase")
    async def test_health_check_success(self, mock_db: MagicMock, mock_async_driver: MagicMock, mock_session: MagicMock):
        """测试健康检查成功。"""
        mock_db.driver.return_value = mock_async_driver

        async def mock_run(*args, **kwargs):
            result_mock = MagicMock()
            result_mock.single = AsyncMock(return_value=("1",))
            return result_mock

        mock_session.run = mock_run
        mock_async_driver.session.return_value = _AsyncCM(mock_session)

        wrapper = Neo4jClientWrapper()
        result = await wrapper.health_check()
        assert result is True

    @patch("src.infrastructure.storage.neo4j.client.AsyncGraphDatabase")
    async def test_health_check_failure(self, mock_db: MagicMock, mock_async_driver: MagicMock):
        """测试健康检查失败。"""
        mock_db.driver.return_value = mock_async_driver
        mock_async_driver.session.side_effect = Exception("Connection refused")

        wrapper = Neo4jClientWrapper()
        result = await wrapper.health_check()
        assert result is False

    @patch("src.infrastructure.storage.neo4j.client.AsyncGraphDatabase")
    async def test_close(self, mock_db: MagicMock, mock_async_driver: MagicMock):
        """测试关闭连接。"""
        mock_db.driver.return_value = mock_async_driver
        mock_async_driver.close = AsyncMock()

        wrapper = Neo4jClientWrapper()
        wrapper.get_client()
        await wrapper.close()

        mock_async_driver.close.assert_called_once()
        assert wrapper._driver is None

    @patch("src.infrastructure.storage.neo4j.client.AsyncGraphDatabase")
    async def test_close_without_driver(self, mock_db: MagicMock):
        """测试未初始化驱动时关闭连接。"""
        wrapper = Neo4jClientWrapper()
        await wrapper.close()
        mock_db.assert_not_called()
