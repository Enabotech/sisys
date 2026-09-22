"""Story 4.4 Round 2: SandboxConfig 单元测试

验证环境变量加载 + 解析失败抛 ConfigurationError(对齐 RedisConfig 先例)。
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import ConfigurationError
from src.infrastructure.config.sandbox import SandboxConfig


class TestSandboxConfig:
    """SandboxConfig 配置测试"""

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """默认配置: idle_timeout=30 分钟, max_concurrent=50"""
        monkeypatch.delenv("SANDBOX_IDLE_TIMEOUT_MINUTES", raising=False)
        monkeypatch.delenv("SANDBOX_MAX_CONCURRENT_CONTAINERS", raising=False)

        config = SandboxConfig.from_env()

        assert config.idle_timeout_minutes == 30
        assert config.max_concurrent_containers == 50

    def test_from_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """环境变量覆盖默认值"""
        monkeypatch.setenv("SANDBOX_IDLE_TIMEOUT_MINUTES", "5")
        monkeypatch.setenv("SANDBOX_MAX_CONCURRENT_CONTAINERS", "10")

        config = SandboxConfig.from_env()

        assert config.idle_timeout_minutes == 5
        assert config.max_concurrent_containers == 10

    def test_invalid_idle_timeout_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SANDBOX_IDLE_TIMEOUT_MINUTES 非整数抛 ConfigurationError"""
        monkeypatch.setenv("SANDBOX_IDLE_TIMEOUT_MINUTES", "not-a-number")

        with pytest.raises(ConfigurationError):
            SandboxConfig.from_env()

    def test_invalid_max_concurrent_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SANDBOX_MAX_CONCURRENT_CONTAINERS 非整数抛 ConfigurationError"""
        monkeypatch.setenv("SANDBOX_MAX_CONCURRENT_CONTAINERS", "abc")

        with pytest.raises(ConfigurationError):
            SandboxConfig.from_env()
