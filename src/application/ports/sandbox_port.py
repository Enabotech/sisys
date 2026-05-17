"""应用层沙箱执行端口模块

定义沙箱任务执行的接口，基础设施层通过 Docker 或 gVisor 实现此端口

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Any, Protocol

from src.domain.exceptions.sandbox_exceptions import (
    ContainerStartError,
    ContainerStopError,
    ExecutionError,
    SandboxError,
)

__all__ = [
    "SandboxError",
    "ContainerStartError",
    "ExecutionError",
    "ContainerStopError",
]


class SandboxExecutor(Protocol):
    """沙箱执行端口接口

    基础设施层提供具体实现（如 DockerSandboxAdapter、GvisorSandboxAdapter）
    """

    async def start_container(self, session_id: str) -> None:
        """为指定会话启动沙箱容器

        Args:
            session_id: 会话唯一标识

        Raises:
            SandboxError: 容器启动失败
        """

    async def execute_code(self, session_id: str, code: str) -> dict[str, Any]:
        """在沙箱中执行代码

        Args:
            session_id: 会话标识
            code: 待执行的代码

        Returns:
            执行结果字典，包含 status、output、error 键

        Raises:
            SandboxError: 执行失败
        """

    async def stop_container(self, session_id: str) -> None:
        """停止并清理沙箱容器

        Args:
            session_id: 会话标识

        Raises:
            SandboxError: 容器停止失败
        """

    async def is_container_running(self, session_id: str) -> bool:
        """检查指定会话的容器是否正在运行

        Args:
            session_id: 会话标识

        Returns:
            容器正在运行返回 True，否则返回 False
        """
