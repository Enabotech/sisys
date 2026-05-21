"""领域层沙箱执行端口模块

定义沙箱执行适配器的接口协议，基础设施层负责实现（如 DockerSandboxAdapter）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

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


@runtime_checkable
class SandboxExecutor(Protocol):
    """沙箱执行协议端口，由基础设施层实现

    定义启动、执行代码、停止沙箱容器、检查容器状态的接口，用于会话隔离
    """

    async def start_container(self, session_id: str) -> None:
        """为指定会话启动沙箱容器

        Args:
            session_id: 会话唯一标识

        Raises:
            ContainerStartError: 容器启动失败
        """
        ...

    async def execute_code(self, session_id: str, code: str) -> dict[str, Any]:
        """在沙箱中执行代码

        Args:
            session_id: 会话标识
            code: 待执行的代码

        Returns:
            执行结果字典，包含 status、output、error 键

        Raises:
            ExecutionError: 执行失败
        """
        ...

    async def stop_container(self, session_id: str) -> None:
        """停止并清理沙箱容器

        Args:
            session_id: 会话标识

        Raises:
            ContainerStopError: 容器停止失败
        """
        ...

    async def is_container_running(self, session_id: str) -> bool:
        """检查指定会话的容器是否正在运行

        Args:
            session_id: 会话标识

        Returns:
            容器正在运行返回 True，否则返回 False
        """
        ...
