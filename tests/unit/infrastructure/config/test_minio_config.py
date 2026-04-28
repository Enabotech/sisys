"""MinIOConfig 配置模型测试。

TDD 红→绿→重构循环 A。
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.infrastructure.config.minio import MinIOConfig


class TestMinIOConfigInit:
    """MinIOConfig 初始化测试。"""

    def test_default_values(self):
        """验证默认值正确。"""
        config = MinIOConfig()
        assert config.host == "localhost"
        assert config.port == 9000
        assert config.endpoint == "localhost:9000"
        assert config.access_key == ""
        assert config.secret_key == ""
        assert config.secure is False
        assert config.bucket_prefix == "sisys"
        assert config.connect_timeout == 5.0
        assert config.read_timeout == 30.0

    def test_custom_values(self):
        """验证自定义值。"""
        config = MinIOConfig(
            host="minio.example.com",
            port=9000,
            access_key="my-access",
            secret_key="my-secret",  # pragma: allowlist secret
            secure=True,
            bucket_prefix="my-project",
        )
        assert config.host == "minio.example.com"
        assert config.port == 9000
        assert config.endpoint == "minio.example.com:9000"
        assert config.access_key == "my-access"  # pragma: allowlist secret
        assert config.secret_key == "my-secret"  # pragma: allowlist secret
        assert config.secure is True
        assert config.bucket_prefix == "my-project"


class TestMinIOConfigFromEnv:
    """MinIOConfig from_env 测试。"""

    def test_from_env_defaults(self):
        """无环境变量时使用默认值。"""
        with patch.dict(os.environ, {}, clear=True):
            config = MinIOConfig.from_env()
            assert config.host == "localhost"
            assert config.port == 9000
            assert config.endpoint == "localhost:9000"
            assert config.access_key == ""
            assert config.secret_key == ""
            assert config.secure is False

    def test_from_env_custom_endpoint(self):
        """自定义端点环境变量。"""
        with patch.dict(os.environ, {"MINIO_HOST": "custom.minio", "MINIO_API_PORT": "9000"}):
            config = MinIOConfig.from_env()
            assert config.host == "custom.minio"
            assert config.port == 9000
            assert config.endpoint == "custom.minio:9000"

    def test_from_env_credentials(self):
        """凭证环境变量。"""
        with patch.dict(
            os.environ,
            {
                "MINIO_ROOT_USER": "test-key",
                "MINIO_ROOT_PASSWORD": "test-secret",  # pragma: allowlist secret
            },
        ):
            config = MinIOConfig.from_env()
            assert config.access_key == "test-key"  # pragma: allowlist secret
            assert config.secret_key == "test-secret"  # pragma: allowlist secret

    def test_from_env_secure_flag(self):
        """Secure 标志环境变量。"""
        with patch.dict(os.environ, {"MINIO_SECURE": "true"}):
            config = MinIOConfig.from_env()
            assert config.secure is True

        with patch.dict(os.environ, {"MINIO_SECURE": "false"}):
            config = MinIOConfig.from_env()
            assert config.secure is False

    def test_from_env_timeouts(self):
        """超时环境变量。"""
        with patch.dict(
            os.environ,
            {
                "MINIO_CONNECT_TIMEOUT": "10.0",
                "MINIO_READ_TIMEOUT": "60.0",
            },
        ):
            config = MinIOConfig.from_env()
            assert config.connect_timeout == 10.0
            assert config.read_timeout == 60.0

    def test_from_env_invalid_timeout(self):
        """无效超时值应抛出异常。"""
        with patch.dict(os.environ, {"MINIO_CONNECT_TIMEOUT": "not-a-number"}):
            with pytest.raises(ValueError, match="MINIO_CONNECT_TIMEOUT"):
                MinIOConfig.from_env()
