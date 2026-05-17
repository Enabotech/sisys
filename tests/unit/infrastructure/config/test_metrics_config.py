"""MetricsConfig 单元测试

验证 MetricsConfig 配置模型正确
Story 1.13: K8s 动态扩缩容

Reference: src/infrastructure/config/metrics.py
"""

from __future__ import annotations

import os
from unittest import mock

from src.infrastructure.config.metrics import MetricsConfig


class TestMetricsConfigDefaults:
    """验证默认配置值。"""

    def test_default_enabled_is_false(self) -> None:
        """验证默认启用状态为 false。"""
        config = MetricsConfig()
        assert config.enabled is False

    def test_default_path(self) -> None:
        """验证默认路径。"""
        config = MetricsConfig()
        assert config.path == "/metrics"

    def test_default_auth_enabled_is_false(self) -> None:
        """验证默认认证状态为 false。"""
        config = MetricsConfig()
        assert config.auth_enabled is False

    def test_default_port(self) -> None:
        """验证默认端口。"""
        config = MetricsConfig()
        assert config.port == 8080


class TestMetricsConfigFromEnv:
    """验证从环境变量创建配置。"""

    def test_from_env_defaults(self) -> None:
        """验证默认环境变量值。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = MetricsConfig.from_env()
            assert config.enabled is False
            assert config.path == "/metrics"
            assert config.auth_enabled is False
            assert config.port == 8080

    def test_from_env_enabled_true(self) -> None:
        """验证 enabled 为 true 的环境变量。"""
        with mock.patch.dict(os.environ, {"METRICS_ENABLED": "true"}):
            config = MetricsConfig.from_env()
            assert config.enabled is True

    def test_from_env_enabled_1(self) -> None:
        """验证 enabled 为 1 的环境变量。"""
        with mock.patch.dict(os.environ, {"METRICS_ENABLED": "1"}):
            config = MetricsConfig.from_env()
            assert config.enabled is True

    def test_from_env_enabled_yes(self) -> None:
        """验证 enabled 为 yes 的环境变量。"""
        with mock.patch.dict(os.environ, {"METRICS_ENABLED": "yes"}):
            config = MetricsConfig.from_env()
            assert config.enabled is True

    def test_from_env_enabled_false(self) -> None:
        """验证 enabled 为 false 的环境变量。"""
        with mock.patch.dict(os.environ, {"METRICS_ENABLED": "false"}):
            config = MetricsConfig.from_env()
            assert config.enabled is False

    def test_from_env_custom_path(self) -> None:
        """验证自定义路径。"""
        with mock.patch.dict(os.environ, {"METRICS_PATH": "/custom/metrics"}):
            config = MetricsConfig.from_env()
            assert config.path == "/custom/metrics"

    def test_from_env_auth_enabled(self) -> None:
        """验证认证启用。"""
        with mock.patch.dict(os.environ, {"METRICS_AUTH_ENABLED": "true"}):
            config = MetricsConfig.from_env()
            assert config.auth_enabled is True

    def test_from_env_custom_port(self) -> None:
        """验证自定义端口。"""
        with mock.patch.dict(os.environ, {"METRICS_PORT": "9090"}):
            config = MetricsConfig.from_env()
            assert config.port == 9090

    def test_from_env_invalid_port_fallback(self) -> None:
        """验证无效端口时的回退。"""
        with mock.patch.dict(os.environ, {"METRICS_PORT": "invalid"}):
            config = MetricsConfig.from_env()
            assert config.port == 8080

    def test_from_env_empty_port_fallback(self) -> None:
        """验证空字符串端口时的回退。"""
        with mock.patch.dict(os.environ, {"METRICS_PORT": ""}):
            config = MetricsConfig.from_env()
            assert config.port == 8080


class TestMetricsConfigAllFields:
    """验证完整配置字段。"""

    def test_create_with_all_fields(self) -> None:
        """验证创建带所有字段的配置。"""
        config = MetricsConfig(
            enabled=True,
            path="/custom/path",
            auth_enabled=True,
            port=9999,
        )
        assert config.enabled is True
        assert config.path == "/custom/path"
        assert config.auth_enabled is True
        assert config.port == 9999

    def test_dataclass_fields_modifiable(self) -> None:
        """验证 dataclass 字段可修改（非 frozen）。"""
        config = MetricsConfig()
        # MetricsConfig 不是 frozen dataclass，字段可以修改
        config.port = 9999
        assert config.port == 9999

    def test_dataclass_repr(self) -> None:
        """验证 dataclass 的 repr。"""
        config = MetricsConfig(enabled=True, path="/test", port=1234)
        repr_str = repr(config)
        assert "MetricsConfig" in repr_str
        assert "enabled=True" in repr_str
        assert "port=1234" in repr_str
