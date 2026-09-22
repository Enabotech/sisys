"""基础设施层沙箱配置模块

Story 4.4 — Docker 沙箱执行配置（Round 2 审查修订：消除 idle_timeout/max_concurrent 硬编码）。

模式对齐 RedisConfig（dataclass + from_env + 解析失败抛 ConfigurationError）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError


@dataclass(frozen=True)
class SandboxConfig:
    """Docker 沙箱配置

    Attributes:
        idle_timeout_minutes: 空闲会话 TTL（分钟，默认 30，SandboxSessionReaper 消费）
        max_concurrent_containers: 最大并发容器数（默认 50，适配器/装饰器配额消费）
    """

    idle_timeout_minutes: int = 30
    max_concurrent_containers: int = 50

    @classmethod
    def from_env(cls) -> SandboxConfig:
        """从环境变量加载配置

        Returns:
            SandboxConfig 实例

        Raises:
            ConfigurationError: 当环境变量值无法解析为整数时
        """
        idle_timeout_str = os.getenv("SANDBOX_IDLE_TIMEOUT_MINUTES", "30")
        try:
            idle_timeout_minutes = int(idle_timeout_str)
        except ValueError as e:
            raise ConfigurationError(message=f"Invalid SANDBOX_IDLE_TIMEOUT_MINUTES value: {idle_timeout_str}") from e

        max_concurrent_str = os.getenv("SANDBOX_MAX_CONCURRENT_CONTAINERS", "50")
        try:
            max_concurrent_containers = int(max_concurrent_str)
        except ValueError as e:
            raise ConfigurationError(message=f"Invalid SANDBOX_MAX_CONCURRENT_CONTAINERS value: {max_concurrent_str}") from e

        return cls(
            idle_timeout_minutes=idle_timeout_minutes,
            max_concurrent_containers=max_concurrent_containers,
        )


__all__ = ["SandboxConfig"]
