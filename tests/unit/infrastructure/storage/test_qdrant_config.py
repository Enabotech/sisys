"""QdrantConfig 单元测试

测试配置模型的字段验证、默认值和 from_env 方法
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.infrastructure.config.qdrant import QdrantConfig


class TestQdrantConfig:
    """QdrantConfig 测试类。"""

    def test_default_values(self):
        """测试默认值是否正确。"""
        config = QdrantConfig()
        assert config.host == "localhost"
        assert config.port == 6333
        assert config.grpc_port == 6334
        assert config.api_key is None
        assert config.https is False
        assert config.timeout == 30.0
        assert config.max_retries == 3

    def test_custom_values(self):
        """测试自定义值。"""
        config = QdrantConfig(
            host="qdrant.example.com",
            port=8000,
            grpc_port=8001,
            api_key="test-key",  # pragma: allowlist secret
            https=True,
            timeout=60.0,
            max_retries=5,
        )
        assert config.host == "qdrant.example.com"
        assert config.port == 8000
        assert config.grpc_port == 8001
        assert config.api_key == "test-key"  # pragma: allowlist secret
        assert config.https is True
        assert config.timeout == 60.0
        assert config.max_retries == 5

    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_defaults(self):
        """测试从环境变量加载配置的默认行为。"""
        config = QdrantConfig.from_env()
        assert config.host == "localhost"
        assert config.port == 6333
        assert config.grpc_port == 6334
        assert config.api_key is None
        assert config.https is False
        assert config.timeout == 30.0
        assert config.max_retries == 3

    @patch.dict(
        os.environ,
        {
            "QDRANT_HOST": "qdrant.example.com",
            "QDRANT_PORT": "8000",
            "QDRANT_GRPC_PORT": "8001",
            "QDRANT_API_KEY": "test-api-key",  # pragma: allowlist secret
            "QDRANT_HTTPS": "true",
            "QDRANT_TIMEOUT": "60.0",
            "QDRANT_MAX_RETRIES": "5",
        },
        clear=True,
    )
    def test_from_env_custom_values(self):
        """测试从环境变量加载自定义值。"""
        config = QdrantConfig.from_env()
        assert config.host == "qdrant.example.com"
        assert config.port == 8000
        assert config.grpc_port == 8001
        assert config.api_key == "test-api-key"  # pragma: allowlist secret
        assert config.https is True
        assert config.timeout == 60.0
        assert config.max_retries == 5

    @patch.dict(os.environ, {"QDRANT_HTTPS": "1"}, clear=True)
    def test_from_env_https_variants(self):
        """测试 HTTPS 环境变量多种写法。"""
        for value in ("true", "1", "yes"):
            with patch.dict(os.environ, {"QDRANT_HTTPS": value}, clear=True):
                config = QdrantConfig.from_env()
                assert config.https is True

    @patch.dict(os.environ, {"QDRANT_PORT": "invalid"}, clear=True)
    def test_from_env_invalid_port(self):
        """测试无效端口应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Invalid QDRANT_PORT"):
            QdrantConfig.from_env()

    @patch.dict(os.environ, {"QDRANT_GRPC_PORT": "invalid"}, clear=True)
    def test_from_env_invalid_grpc_port(self):
        """测试无效 gRPC 端口应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Invalid QDRANT_GRPC_PORT"):
            QdrantConfig.from_env()

    @patch.dict(os.environ, {"QDRANT_TIMEOUT": "invalid"}, clear=True)
    def test_from_env_invalid_timeout(self):
        """测试无效超时应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Invalid QDRANT_TIMEOUT"):
            QdrantConfig.from_env()

    @patch.dict(os.environ, {"QDRANT_MAX_RETRIES": "invalid"}, clear=True)
    def test_from_env_invalid_max_retries(self):
        """测试无效最大重试次数应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Invalid QDRANT_MAX_RETRIES"):
            QdrantConfig.from_env()
