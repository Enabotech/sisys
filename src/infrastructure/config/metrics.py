"""基础设施层指标端点配置模块

提供 Prometheus /metrics HTTP 端点配置，支持 K8s 动态扩缩容

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class MetricsConfig:
    """Prometheus /metrics 端点配置

    从环境变量读取，支持启用/禁用、路径配置、认证配置

    Attributes:
        enabled: 是否启用 /metrics 端点（默认 false）
        path: 指标端点路径（默认 "/metrics"）
        auth_enabled: 是否启用 Basic Auth 认证（默认 false）
        port: 指标端点端口（默认 8080，与主应用共用）
    """

    enabled: bool = False
    path: str = "/metrics"
    auth_enabled: bool = False
    port: int = 8080

    @classmethod
    def from_env(cls) -> MetricsConfig:
        """从环境变量创建配置

        Args:
            无（从 os.environ 读取）

        Returns:
            MetricsConfig 实例
        """
        enabled = os.getenv("METRICS_ENABLED", "false").lower() in ("true", "1", "yes")
        path = os.getenv("METRICS_PATH", "/metrics")
        auth_enabled = os.getenv("METRICS_AUTH_ENABLED", "false").lower() in ("true", "1", "yes")

        port_str = os.getenv("METRICS_PORT", "8080")
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            port = 8080

        return cls(
            enabled=enabled,
            path=path,
            auth_enabled=auth_enabled,
            port=port,
        )
