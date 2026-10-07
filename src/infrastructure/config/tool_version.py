"""基础设施层工具版本配置模块（Story 4-6）

模式对齐 SandboxConfig（frozen dataclass + from_env + 解析失败抛
ConfigurationError）——组合根解析后以标量注入应用层服务（分层红线：
应用层禁止 import infrastructure）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError


@dataclass(frozen=True)
class ToolVersionConfig:
    """工具版本管理配置。

    Attributes:
        max_retained_versions: 每工具版本保留上限（默认 10，软约束——
            可淘汰 DEPRECATED 不足时保护态优先）
    """

    max_retained_versions: int = 10

    @classmethod
    def from_env(cls) -> ToolVersionConfig:
        """从环境变量加载配置。

        Returns:
            ToolVersionConfig 实例

        Raises:
            ConfigurationError: 环境变量值非整数或低于下限 1
        """
        raw = os.getenv("TOOL_VERSION_MAX_RETAINED", "10")
        try:
            value = int(raw)
        except ValueError as exc:
            raise ConfigurationError(message=f"Invalid TOOL_VERSION_MAX_RETAINED value: {raw}") from exc
        if value < 1:
            raise ConfigurationError(message=f"TOOL_VERSION_MAX_RETAINED must be >= 1, got {value}")
        return cls(max_retained_versions=value)


__all__ = ["ToolVersionConfig"]
