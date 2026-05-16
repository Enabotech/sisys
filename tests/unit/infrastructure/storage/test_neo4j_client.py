"""Neo4jClient 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.neo4j.neo4j_manager import Neo4jManager


class _AsyncCM:
    """辅助类：模拟异步上下文管理器。"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def mock_driver():
    """模拟异步 Neo4j 驱动。"""
    return MagicMock()


@pytest.fixture
def mock_session():
    """模拟 Neo4j 会话。"""
    return MagicMock()


@pytest.fixture
def wrapper(mock_driver: MagicMock):
    """注入 mock 驱动的 Neo4jManager 实例。"""
    return Neo4jManager(mock_driver, database="test_db")


class TestNeo4jClientWrapper:
    """Neo4jManager 测试类。"""

    def test_init_with_driver(self, mock_driver: MagicMock):
        """测试构造函数注入驱动。"""
        wrapper = Neo4jManager(mock_driver, database="sisys_db")
        assert wrapper._driver is mock_driver
        assert wrapper._database == "sisys_db"

    def test_get_client_returns_injected(self, wrapper: Neo4jManager, mock_driver: MagicMock):
        """测试 get_client 返回注入的驱动。"""
        assert wrapper.get_client() is mock_driver

    def test_get_async_driver_returns_injected(self, wrapper: Neo4jManager, mock_driver: MagicMock):
        """测试 get_async_driver 返回注入的驱动（向后兼容）。"""
        assert wrapper.get_async_driver() is mock_driver

    async def test_health_check_success(self, wrapper: Neo4jManager, mock_driver: MagicMock, mock_session: MagicMock):
        """测试健康检查成功。"""
        async def mock_run(*args, **kwargs):
            result_mock = MagicMock()
            result_mock.single = AsyncMock(return_value=("1",))
            return result_mock

        mock_session.run = mock_run
        mock_driver.session.return_value = _AsyncCM(mock_session)

        result = await wrapper.health_check()
        assert result is True

    async def test_health_check_failure(self, wrapper: Neo4jManager, mock_driver: MagicMock):
        """测试健康检查失败。"""
        mock_driver.session.side_effect = Exception("Connection refused")

        result = await wrapper.health_check()
        assert result is False

    async def test_close(self, wrapper: Neo4jManager, mock_driver: MagicMock):
        """测试关闭连接。"""
        mock_driver.close = AsyncMock()
        await wrapper.close()

        mock_driver.close.assert_called_once()
        assert wrapper._driver is None

    async def test_close_without_driver(self):
        """测试驱动为 None 时关闭不报错。"""
        wrapper = Neo4jManager(MagicMock(), database="neo4j")
        wrapper._driver = None
        await wrapper.close()
