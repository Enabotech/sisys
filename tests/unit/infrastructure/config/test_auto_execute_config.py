"""AutoExecuteConfig 单元测试。

验证 AutoExecuteConfig 配置类正确实现。
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.infrastructure.config.auto_execute import AutoExecuteConfig


class TestAutoExecuteConfigDefaults:
    """测试默认配置值。"""

    def test_enabled_defaults_to_true(self) -> None:
        """enabled 默认值为 True。"""
        config = AutoExecuteConfig()
        assert config.enabled is True

    def test_sandbox_type_defaults_to_docker(self) -> None:
        """sandbox_type 默认为 docker。"""
        config = AutoExecuteConfig()
        assert config.sandbox_type == "docker"

    def test_snapshot_ttl_defaults_to_86400(self) -> None:
        """snapshot_ttl_seconds 默认为 86400（24小时）。"""
        config = AutoExecuteConfig()
        assert config.snapshot_ttl_seconds == 86400

    def test_resource_limits_defaults_to_none(self) -> None:
        """resource_limits 默认为 None。"""
        config = AutoExecuteConfig()
        assert config.resource_limits is None


class TestAutoExecuteConfigValidate:
    """测试 validate() 方法。"""

    def test_validate_returns_true_for_valid_config(self) -> None:
        """有效配置返回 True。"""
        config = AutoExecuteConfig(
            enabled=True,
            sandbox_type="docker",
            snapshot_ttl_seconds=3600,
        )
        assert config.validate() is True

    def test_validate_invalid_sandbox_type(self) -> None:
        """无效 sandbox_type 返回 False。"""
        config = AutoExecuteConfig(sandbox_type="invalid")
        assert config.validate() is False

    def test_validate_sandbox_type_gvisor(self) -> None:
        """sandbox_type=gvisor 返回 True。"""
        config = AutoExecuteConfig(sandbox_type="gvisor")
        assert config.validate() is True

    def test_validate_snapshot_ttl_too_low(self) -> None:
        """snapshot_ttl_seconds < 60 返回 False。"""
        config = AutoExecuteConfig(snapshot_ttl_seconds=59)
        assert config.validate() is False

    def test_validate_snapshot_ttl_too_high(self) -> None:
        """snapshot_ttl_seconds > 2592000 返回 False。"""
        config = AutoExecuteConfig(snapshot_ttl_seconds=2592001)
        assert config.validate() is False

    def test_validate_snapshot_ttl_at_minimum(self) -> None:
        """snapshot_ttl_seconds=60（最小值）返回 True。"""
        config = AutoExecuteConfig(snapshot_ttl_seconds=60)
        assert config.validate() is True

    def test_validate_snapshot_ttl_at_maximum(self) -> None:
        """snapshot_ttl_seconds=2592000（最大值）返回 True。"""
        config = AutoExecuteConfig(snapshot_ttl_seconds=2592000)
        assert config.validate() is True


class TestAutoExecuteConfigFromEnv:
    """测试 from_env() 类方法。"""

    def test_from_env_default_values(self) -> None:
        """无环境变量时使用默认值。"""
        env_vars = {
            "EXECUTE_ENABLED": "true",
            "SANDBOX_TYPE": "docker",
            "SNAPSHOT_TTL_SECONDS": "86400",
            "RESOURCE_LIMITS": "{}",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            for key in env_vars:
                os.environ.pop(key, None)
            with patch.dict(os.environ, {}, clear=True):
                config = AutoExecuteConfig.from_env()
                assert config.enabled is True
                assert config.sandbox_type == "docker"
                assert config.snapshot_ttl_seconds == 86400

    def test_from_env_enabled_false(self) -> None:
        """EXECUTE_ENABLED=false 解析为 False。"""
        with patch.dict(
            os.environ,
            {"EXECUTE_ENABLED": "false", "SANDBOX_TYPE": "docker", "SNAPSHOT_TTL_SECONDS": "3600"},
            clear=False,
        ):
            config = AutoExecuteConfig.from_env()
            assert config.enabled is False

    def test_from_env_sandbox_type_gvisor(self) -> None:
        """SANDBOX_TYPE=gvisor 正确解析。"""
        with patch.dict(
            os.environ,
            {"EXECUTE_ENABLED": "true", "SANDBOX_TYPE": "gvisor", "SNAPSHOT_TTL_SECONDS": "7200"},
            clear=False,
        ):
            config = AutoExecuteConfig.from_env()
            assert config.sandbox_type == "gvisor"

    def test_from_env_resource_limits_json(self) -> None:
        """RESOURCE_LIMITS 正确解析 JSON。"""
        resource_json = '{"cpu_limit": 2, "memory_limit": "4Gi"}'
        with patch.dict(
            os.environ,
            {
                "EXECUTE_ENABLED": "true",
                "SANDBOX_TYPE": "docker",
                "SNAPSHOT_TTL_SECONDS": "3600",
                "RESOURCE_LIMITS": resource_json,
            },
            clear=False,
        ):
            config = AutoExecuteConfig.from_env()
            assert config.resource_limits == {"cpu_limit": 2, "memory_limit": "4Gi"}

    def test_from_env_invalid_resource_limits_json(self) -> None:
        """RESOURCE_LIMITS 为无效 JSON 时返回 None。"""
        with patch.dict(
            os.environ,
            {
                "EXECUTE_ENABLED": "true",
                "SANDBOX_TYPE": "docker",
                "SNAPSHOT_TTL_SECONDS": "3600",
                "RESOURCE_LIMITS": "not valid json",
            },
            clear=False,
        ):
            config = AutoExecuteConfig.from_env()
            assert config.resource_limits is None


class TestAutoExecuteConfigFrozen:
    """测试 frozen=True 不可变性。"""

    def test_frozen_dataclass(self) -> None:
        """验证 frozen=True 配置正确。"""
        assert hasattr(AutoExecuteConfig, "__dataclass_params__")
        assert AutoExecuteConfig.__dataclass_params__.frozen is True

    def test_cannot_modify_after_creation(self) -> None:
        """创建后不可修改。"""
        config = AutoExecuteConfig()
        with pytest.raises(AttributeError):
            config.enabled = False  # type: ignore
