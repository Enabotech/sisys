"""领域层沙箱执行协议模块

定义沙箱执行适配器的接口协议，基础设施层负责实现（如 DockerSandboxAdapter）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SandboxExecutorProtocol(Protocol):
    """沙箱执行协议端口，由基础设施层实现

    定义启动、执行代码、停止沙箱容器的接口，用于会话隔离
    """

    async def start_container(self, session_id: str) -> None:
        """为指定会话启动沙箱容器

        Args:
            session_id: 会话标识
        """
        ...

    async def execute_code(self, session_id: str, code: str) -> dict[str, Any]:
        """在沙箱中执行代码

        Args:
            session_id: 会话标识
            code: 待执行代码

        Returns:
            执行结果字典，包含 status、output 等字段
        """
        ...

    async def stop_container(self, session_id: str) -> None:
        """停止沙箱容器

        Args:
            session_id: 会话标识
        """
        ...
