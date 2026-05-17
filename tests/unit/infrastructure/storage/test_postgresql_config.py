"""PostgreSQLConfig 单元测试

TDD 红阶段：验证配置模型的字段、默认值和 from_env 支持
"""

from __future__ import annotations

import os
from unittest import mock

from src.infrastructure.config.postgresql import PostgreSQLConfig


class TestPostgreSQLConfig:
    """PostgreSQLConfig 配置模型测试。"""

    def test_default_values(self):
        """测试默认值设置。"""
        config = PostgreSQLConfig()

        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "sisys"
        assert config.username == "postgres"
        assert config.password == ""
        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.pool_timeout == 30.0
        assert config.pool_recycle == 3600
        assert config.echo is False

    def test_custom_values(self):
        """测试自定义值设置。"""
        config = PostgreSQLConfig(
            host="db.example.com",
            port=5433,
            database="test_db",
            username="test_user",
            password="testpass456",  # pragma: allowlist secret
            pool_size=10,
            max_overflow=20,
            pool_timeout=60.0,
            pool_recycle=7200,
            echo=True,
        )

        assert config.host == "db.example.com"
        assert config.port == 5433
        assert config.database == "test_db"
        assert config.username == "test_user"
        assert config.password == "testpass456"  # pragma: allowlist secret
        assert config.pool_size == 10
        assert config.max_overflow == 20
        assert config.pool_timeout == 60.0
        assert config.pool_recycle == 7200
        assert config.echo is True

    def test_from_env_defaults(self):
        """测试 from_env 使用默认环境变量。"""
        with mock.patch.dict(os.environ, clear=True):
            config = PostgreSQLConfig.from_env()

            assert config.host == "localhost"
            assert config.port == 5432
            assert config.database == "sisys"
            assert config.username == "postgres"
            assert config.password == ""
            assert config.pool_size == 5
            assert config.max_overflow == 10
            assert config.pool_timeout == 30.0
            assert config.pool_recycle == 3600
            assert config.echo is False

    def test_from_env_custom(self):
        """测试 from_env 使用自定义环境变量。"""
        env = {
            "POSTGRES_HOST": "custom-host",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DATABASE": "custom_db",
            "POSTGRES_USERNAME": "custom_user",
            "POSTGRES_PASSWORD": "secret123",  # pragma: allowlist secret
            "POSTGRES_POOL_SIZE": "10",
            "POSTGRES_MAX_OVERFLOW": "20",
            "POSTGRES_POOL_TIMEOUT": "60.0",
            "POSTGRES_POOL_RECYCLE": "7200",
            "POSTGRES_ECHO": "true",
        }

        with mock.patch.dict(os.environ, env, clear=True):
            config = PostgreSQLConfig.from_env()

            assert config.host == "custom-host"
            assert config.port == 5433
            assert config.database == "custom_db"
            assert config.username == "custom_user"
            assert config.password == "secret123"  # pragma: allowlist secret
            assert config.pool_size == 10
            assert config.max_overflow == 20
            assert config.pool_timeout == 60.0
            assert config.pool_recycle == 7200
            assert config.echo is True

    def test_from_env_partial(self):
        """测试 from_env 使用部分环境变量。"""
        env = {
            "POSTGRES_HOST": "custom-host",
            "POSTGRES_PASSWORD": "secret456",  # pragma: allowlist secret
        }

        with mock.patch.dict(os.environ, env, clear=True):
            config = PostgreSQLConfig.from_env()

            assert config.host == "custom-host"
            assert config.password == "secret456"  # pragma: allowlist secret
            # 其他字段使用默认值
            assert config.port == 5432
            assert config.pool_size == 5
