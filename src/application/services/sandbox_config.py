"""应用层沙箱配置 dataclass（Story 4.4 Task 6)

定义 SandboxConfig 配置(纯 dataclass,非 pydantic-settings)。
放置在 application 层:CLAUDE.md §5 架构约束 - application 层禁止依赖
infrastructure 层,故配置 dataclass 应放 application 层而非 infrastructure。

配置项:
- IDLE_TIMEOUT_MINUTES: 空闲清理阈值（默认 30 分钟)
- MAX_CONCURRENT_CONTAINERS: 并发容器配额（默认 50)
- DOCKER_SOCKET: Docker daemon URL（默认 unix:///var/run/docker.sock)
- DOCKER_SANDBOX_LABEL: 容器归属标签（默认 sisys.sandbox.session_id)

环境变量读取（通过 SANDBOX_* 前缀):
- SANDBOX_IDLE_TIMEOUT_MINUTES
- SANDBOX_MAX_CONCURRENT_CONTAINERS
- SANDBOX_DOCKER_SOCKET
- SANDBOX_LABEL_KEY
"""

from __future__ import annotations

import os
from dataclasses import dataclass

__all__ = ["SandboxConfig"]


@dataclass(frozen=True)
class SandboxConfig:
    """沙箱配置 dataclass（Story 4.4 Task 6)

    Attributes:
        idle_timeout_minutes: 空闲清理阈值（默认 30 分钟)
        max_concurrent_containers: 并发容器配额（默认 50)
        docker_socket: Docker daemon URL(默认 unix:///var/run/docker.sock)
        label_key: 容器归属 label key（默认 sisys.sandbox.session_id)
    """

    idle_timeout_minutes: int = 30
    max_concurrent_containers: int = 50
    docker_socket: str = "unix:///var/run/docker.sock"
    label_key: str = "sisys.sandbox.session_id"

    @classmethod
    def from_env(cls) -> "SandboxConfig":
        """从环境变量构造配置(支持 SANDBOX_* 前缀)。

        Returns:
            SandboxConfig 实例
        """
        return cls(
            idle_timeout_minutes=int(os.getenv("SANDBOX_IDLE_TIMEOUT_MINUTES", "30")),
            max_concurrent_containers=int(os.getenv("SANDBOX_MAX_CONCURRENT_CONTAINERS", "50")),
            docker_socket=os.getenv("SANDBOX_DOCKER_SOCKET", "unix:///var/run/docker.sock"),
            label_key=os.getenv("SANDBOX_LABEL_KEY", "sisys.sandbox.session_id"),
        )
