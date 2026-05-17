"""基础设施层自动执行配置模块

提供自动执行机制的配置，包括沙箱类型、快照 TTL 和资源限制

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AutoExecuteConfig:
    """自动执行机制配置

    使用 from_env() 类方法从环境变量加载配置

    Attributes:
        enabled: 是否启用自动执行机制
        sandbox_type: 沙箱类型（docker/gvisor）
        snapshot_ttl_seconds: 状态快照 TTL（默认 24 小时）
        resource_limits: 资源限制配置字典
    """

    enabled: bool = True
    sandbox_type: str = "docker"
    snapshot_ttl_seconds: int = 86400  # 24 hours
    resource_limits: dict[str, Any] | None = None

    @classmethod
    def from_env(cls) -> AutoExecuteConfig:
        """从环境变量加载配置

        Args:
            无（从 os.environ 读取）

        Returns:
            AutoExecuteConfig 实例
        """
        enabled = os.getenv("EXECUTE_ENABLED", "true").lower() in ("true", "1", "yes")
        sandbox_type = os.getenv("SANDBOX_TYPE", "docker")
        snapshot_ttl = int(os.getenv("SNAPSHOT_TTL_SECONDS", "86400"))

        resource_limits_str = os.getenv("RESOURCE_LIMITS", "{}")
        try:
            resource_limits = json.loads(resource_limits_str)
        except json.JSONDecodeError:
            resource_limits = None

        return cls(
            enabled=enabled,
            sandbox_type=sandbox_type,
            snapshot_ttl_seconds=snapshot_ttl,
            resource_limits=resource_limits,
        )

    def validate(self) -> bool:
        """验证配置合法性

        Returns:
            合法返回 True，否则返回 False
        """
        if self.sandbox_type not in ("docker", "gvisor"):
            return False
        if self.snapshot_ttl_seconds < 60 or self.snapshot_ttl_seconds > 2592000:
            return False  # 1 minute to 30 days
        return True
