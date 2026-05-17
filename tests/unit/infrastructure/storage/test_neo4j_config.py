"""Neo4jConfig 单元测试

测试配置模型的字段验证、默认值和 from_env 方法
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.infrastructure.config.neo4j import Neo4jConfig


class TestNeo4jConfig:
    """Neo4jConfig 测试类。"""

    def test_default_values(self):
        """测试默认值是否正确。"""
        config = Neo4jConfig()
        assert config.host == "localhost"
        assert config.bolt_port == 7687
        assert config.uri == "bolt://localhost:7687"
        assert config.username == "neo4j"
        assert config.password == ""
        assert config.database == "neo4j"
        assert config.max_connection_pool_size == 50
        assert config.connection_timeout == 30.0
        assert config.max_retry_time == 30.0

    def test_custom_values(self):
        """测试自定义值。"""
        config = Neo4jConfig(
            host="neo4j.example.com",
            bolt_port=7687,
            username="admin",
            password="secret",  # pragma: allowlist secret
            database="sisys_db",
            max_connection_pool_size=100,
            connection_timeout=60.0,
            max_retry_time=45.0,
        )
        assert config.host == "neo4j.example.com"
        assert config.bolt_port == 7687
        assert config.uri == "bolt://neo4j.example.com:7687"
        assert config.username == "admin"
        assert config.password == "secret"  # pragma: allowlist secret
        assert config.database == "sisys_db"
        assert config.max_connection_pool_size == 100
        assert config.connection_timeout == 60.0
        assert config.max_retry_time == 45.0

    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_defaults(self):
        """测试从环境变量加载配置的默认行为。"""
        config = Neo4jConfig.from_env()
        assert config.host == "localhost"
        assert config.bolt_port == 7687
        assert config.uri == "bolt://localhost:7687"
        assert config.username == "neo4j"
        assert config.password == ""
        assert config.database == "neo4j"
        assert config.max_connection_pool_size == 50
        assert config.connection_timeout == 30.0
        assert config.max_retry_time == 30.0

    @patch.dict(
        os.environ,
        {
            "NEO4J_HOST": "neo4j.example.com",
            "NEO4J_BOLT_PORT": "7687",
            "NEO4J_USERNAME": "admin",
            "NEO4J_PASSWORD": "test-password",  # pragma: allowlist secret
            "NEO4J_DATABASE": "sisys_db",
            "NEO4J_MAX_POOL_SIZE": "100",
            "NEO4J_CONNECT_TIMEOUT": "60.0",
            "NEO4J_MAX_RETRY_TIME": "45.0",
        },
        clear=True,
    )
    def test_from_env_custom_values(self):
        """测试从环境变量加载自定义值。"""
        config = Neo4jConfig.from_env()
        assert config.host == "neo4j.example.com"
        assert config.bolt_port == 7687
        assert config.uri == "bolt://neo4j.example.com:7687"
        assert config.username == "admin"
        assert config.password == "test-password"  # pragma: allowlist secret
        assert config.database == "sisys_db"
        assert config.max_connection_pool_size == 100
        assert config.connection_timeout == 60.0
        assert config.max_retry_time == 45.0

    @patch.dict(os.environ, {"NEO4J_MAX_POOL_SIZE": "invalid"}, clear=True)
    def test_from_env_invalid_pool_size(self):
        """测试无效连接池大小应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Invalid NEO4J_MAX_POOL_SIZE"):
            Neo4jConfig.from_env()

    @patch.dict(os.environ, {"NEO4J_CONNECT_TIMEOUT": "invalid"}, clear=True)
    def test_from_env_invalid_timeout(self):
        """测试无效超时应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Invalid NEO4J_CONNECT_TIMEOUT"):
            Neo4jConfig.from_env()

    @patch.dict(os.environ, {"NEO4J_MAX_RETRY_TIME": "invalid"}, clear=True)
    def test_from_env_invalid_retry_time(self):
        """测试无效重试时间应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Invalid NEO4J_MAX_RETRY_TIME"):
            Neo4jConfig.from_env()
