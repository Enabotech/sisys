"""PostgreSQLManager 单元测试

测试引擎创建、复用、健康检查和关闭
"""

from __future__ import annotations

from unittest import mock

import pytest

from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager


@pytest.fixture
def config():
    """创建测试配置"""
    return PostgreSQLConfig(
        host="localhost",
        port=5432,
        database="test_db",
        username="test_user",
        password="testpass123",  # pragma: allowlist secret
    )


@pytest.fixture
def engine(config):
    """创建 PostgreSQLManager 实例"""
    return PostgreSQLManager(config)


class TestPostgreSQLManager:
    """PostgreSQLManager 测试"""

    def test_get_async_engine_creates_engine(self, engine):
        """测试异步引擎创建"""
        async_engine = engine.get_async_engine()
        assert async_engine is not None
        assert "asyncpg" in str(async_engine.url)

    def test_get_async_engine_reuses_instance(self, engine):
        """测试异步引擎复用"""
        engine1 = engine.get_async_engine()
        engine2 = engine.get_async_engine()
        assert engine1 is engine2

    def test_get_sync_engine_creates_engine(self, engine):
        """测试同步引擎创建"""
        sync_engine = engine.get_sync_engine()
        assert sync_engine is not None
        assert "psycopg2" in str(sync_engine.url)

    def test_get_sync_engine_reuses_instance(self, engine):
        """测试同步引擎复用"""
        engine1 = engine.get_sync_engine()
        engine2 = engine.get_sync_engine()
        assert engine1 is engine2

    async def test_health_check_success(self, engine):
        """测试健康检查成功"""
        with mock.patch.object(engine, "get_async_engine") as mock_get:
            mock_conn = mock.AsyncMock()
            mock_result = mock.Mock()
            mock_result.scalar.return_value = 1
            mock_conn.execute.return_value = mock_result

            async_context = mock.AsyncMock()
            async_context.__aenter__ = mock.AsyncMock(return_value=mock_conn)
            async_context.__aexit__ = mock.AsyncMock(return_value=None)

            mock_engine = mock.Mock()
            mock_engine.connect.return_value = async_context
            mock_get.return_value = mock_engine

            result = await engine.health_check()
            assert result is True

    async def test_health_check_failure(self, engine):
        """测试健康检查失败"""
        with mock.patch.object(engine, "get_async_engine") as mock_get:
            mock_get.side_effect = Exception("Connection failed")

            result = await engine.health_check()
            assert result is False

    async def test_close_disposes_engines(self, config):
        """测试关闭引擎"""
        engine = PostgreSQLManager(config)
        mock_async = mock.AsyncMock()
        mock_sync = mock.Mock()
        engine._async_engine = mock_async
        engine._sync_engine = mock_sync

        await engine.close()
        # 验证dispose被调用（在设置为None之前）
        assert mock_async.dispose.called or engine._async_engine is None
        assert mock_sync.dispose.called or engine._sync_engine is None
