"""ToolVersionConfig 单元测试（Story 4-6 Task 4 TDD 红→绿）

SandboxConfig.from_env() 先例模式：frozen dataclass + 环境变量覆盖 +
非法值 ConfigurationError(101)。
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import ConfigurationError
from src.infrastructure.config.tool_version import ToolVersionConfig


class TestToolVersionConfig:
    """配置类测试。"""

    def test_default_max_retained_10(self) -> None:
        config = ToolVersionConfig()
        assert config.max_retained_versions == 10

    def test_frozen_dataclass(self) -> None:
        import dataclasses

        assert dataclasses.is_dataclass(ToolVersionConfig)
        config = ToolVersionConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(config, "max_retained_versions", 5)  # 动态赋值触发 frozen 守护

    def test_from_env_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TOOL_VERSION_MAX_RETAINED", raising=False)
        config = ToolVersionConfig.from_env()
        assert config.max_retained_versions == 10

    def test_from_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TOOL_VERSION_MAX_RETAINED", "20")
        config = ToolVersionConfig.from_env()
        assert config.max_retained_versions == 20

    def test_from_env_invalid_raises_101(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TOOL_VERSION_MAX_RETAINED", "not-a-number")
        with pytest.raises(ConfigurationError) as exc_info:
            ToolVersionConfig.from_env()
        assert exc_info.value.code == "EXCEPTION_101"

    def test_from_env_lower_bound(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """下限校验：保留数 ≥1（0 或负数非法）。"""
        monkeypatch.setenv("TOOL_VERSION_MAX_RETAINED", "0")
        with pytest.raises(ConfigurationError):
            ToolVersionConfig.from_env()
