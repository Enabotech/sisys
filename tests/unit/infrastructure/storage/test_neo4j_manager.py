"""Neo4jClient 单元测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.storage.neo4j.neo4j_manager import Neo4jManager


class _AsyncCM:
    """辅助类：模拟异步上下文管理器"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def mock_driver():
    """模拟异步 Neo4j 驱动"""
    return MagicMock()


@pytest.fixture
def mock_session():
    """模拟 Neo4j 会话"""
    return MagicMock()


@pytest.fixture
def wrapper(mock_driver: MagicMock):
    """注入 mock 驱动的 Neo4jManager 实例"""
    return Neo4jManager(mock_driver, database="test_db")


class TestNeo4jManager:
    """Neo4jManager 测试类"""

    def test_init_with_driver(self, mock_driver: MagicMock):
        """测试构造函数注入驱动"""
        wrapper = Neo4jManager(mock_driver, database="sisys_db")
        assert wrapper._driver is mock_driver
        assert wrapper._database == "sisys_db"

    def test_default_database(self, mock_driver: MagicMock):
        """默认数据库名应为 neo4j"""
        manager = Neo4jManager(mock_driver)
        assert manager._database == "neo4j"

    def test_get_client_returns_injected(self, wrapper: Neo4jManager, mock_driver: MagicMock):
        """测试 get_client 返回注入的驱动"""
        assert wrapper.get_client() is mock_driver

    def test_get_async_driver_returns_injected(self, wrapper: Neo4jManager, mock_driver: MagicMock):
        """测试 get_async_driver 返回注入的驱动（向后兼容）"""
        assert wrapper.get_async_driver() is mock_driver

    async def test_health_check_success(self, wrapper: Neo4jManager, mock_driver: MagicMock, mock_session: MagicMock):
        """测试健康检查成功"""

        async def mock_run(*args, **kwargs):
            result_mock = MagicMock()
            result_mock.single = AsyncMock(return_value=("1",))
            return result_mock

        mock_session.run = mock_run
        mock_driver.session.return_value = _AsyncCM(mock_session)

        result = await wrapper.health_check()
        assert result is True

    async def test_health_check_failure(self, wrapper: Neo4jManager, mock_driver: MagicMock):
        """测试健康检查失败"""
        mock_driver.session.side_effect = Exception("Connection refused")

        result = await wrapper.health_check()
        assert result is False

    async def test_health_check_query_error(self, wrapper: Neo4jManager, mock_driver: MagicMock, mock_session: MagicMock):
        """测试查询执行异常"""
        mock_session.run = AsyncMock(side_effect=RuntimeError("Query failed"))
        mock_driver.session.return_value = _AsyncCM(mock_session)

        result = await wrapper.health_check()
        assert result is False

    async def test_close(self, wrapper: Neo4jManager, mock_driver: MagicMock):
        """测试关闭连接"""
        mock_driver.close = AsyncMock()
        await wrapper.close()

        mock_driver.close.assert_called_once()

    @patch("src.infrastructure.storage.neo4j.neo4j_manager.AsyncGraphDatabase")
    def test_from_config_with_explicit_config(self, mock_db: MagicMock) -> None:
        """from_config 应使用显式配置创建驱动"""
        mock_config = MagicMock()
        mock_config.uri = "bolt://localhost:7687"
        mock_config.username = "neo4j"
        mock_config.password = "test_password"  # pragma: allowlist secret
        mock_config.max_connection_pool_size = 50
        mock_config.connection_timeout = 30
        mock_config.database = "production"

        mock_driver = MagicMock()
        mock_db.driver.return_value = mock_driver

        manager = Neo4jManager.from_config(mock_config)

        mock_db.driver.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("neo4j", "test_password"),
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
        )
        assert manager._driver is mock_driver
        assert manager._database == "production"

    @patch("src.infrastructure.storage.neo4j.neo4j_manager.AsyncGraphDatabase")
    @patch("src.infrastructure.storage.neo4j.neo4j_manager.Neo4jConfig")
    def test_from_config_none_loads_from_env(self, mock_config_cls: MagicMock, mock_db: MagicMock) -> None:
        """config=None 应从环境变量加载配置"""
        mock_config = MagicMock()
        mock_config.uri = "bolt://env-host:7687"
        mock_config.username = "env_user"
        mock_config.password = "env_pass"  # pragma: allowlist secret
        mock_config.max_connection_pool_size = 100
        mock_config.connection_timeout = 60
        mock_config.database = "env_db"

        mock_config_cls.from_env.return_value = mock_config
        mock_db.driver.return_value = MagicMock()

        manager = Neo4jManager.from_config(config=None)
        mock_config_cls.from_env.assert_called_once()
        assert manager._database == "env_db"
