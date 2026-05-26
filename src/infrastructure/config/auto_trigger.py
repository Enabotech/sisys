"""基础设施层自动触发配置模块

提供自动触发机制的配置，包括心跳间隔和最大重试次数
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AutoTriggerConfig:
    """自动触发机制配置

    使用 from_env() 类方法从环境变量加载配置

    Attributes:
        trigger_enabled: 是否启用自动触发机制
        heartbeat_interval_seconds: 心跳间隔（秒）
        trigger_max_retries: 最大重试次数
    """

    trigger_enabled: bool = True
    heartbeat_interval_seconds: int = 60
    trigger_max_retries: int = 3

    @classmethod
    def from_env(cls) -> AutoTriggerConfig:
        """从环境变量加载配置

        Args:
            无（从 os.environ 读取）

        Returns:
            AutoTriggerConfig 实例

        Raises:
            ValueError: 环境变量值不合法时抛出
        """
        enabled_str = os.getenv("TRIGGER_ENABLED", "true").lower()
        interval_str = os.getenv("HEARTBEAT_INTERVAL_SECONDS", "60")
        retries_str = os.getenv("TRIGGER_MAX_RETRIES", "3")

        try:
            interval = int(interval_str)
            if interval <= 0:
                raise ValueError(f"HEARTBEAT_INTERVAL_SECONDS must be positive: {interval}")
        except ValueError as e:
            raise ValueError(f"Invalid HEARTBEAT_INTERVAL_SECONDS value: {interval_str}") from e

        try:
            max_retries = int(retries_str)
            if max_retries < 0:
                raise ValueError(f"TRIGGER_MAX_RETRIES must be non-negative: {max_retries}")
        except ValueError as e:
            raise ValueError(f"Invalid TRIGGER_MAX_RETRIES value: {retries_str}") from e

        return cls(
            trigger_enabled=enabled_str in ("true", "1", "yes", "on"),
            heartbeat_interval_seconds=interval,
            trigger_max_retries=max_retries,
        )
