"""领域层沙箱执行端口模块

定义沙箱执行适配器的接口协议，基础设施层负责实现（如 DockerSandboxAdapter / AioDockerSandboxAdapter）

Story 4.4 扩展:
- 通过默认参数扩展 start_container / execute_code 入参,**保持向后兼容**
- 新增 health_check() 方法用于熔断器 + 启动探针
- 既有 4.1a 调用点（1 参 / 2 参位置调用）通过默认参数沿用旧行为
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.domain.exceptions.sandbox_exceptions import (
    ContainerStartError,
    ContainerStopError,
    ExecutionError,
    SandboxError,
)
from src.domain.value_objects.container_spec import ContainerSpec

__all__ = [
    "SandboxError",
    "ContainerStartError",
    "ExecutionError",
    "ContainerStopError",
    "ContainerSpec",
]


@runtime_checkable
class SandboxExecutor(Protocol):
    """沙箱执行协议端口,由基础设施层实现

    定义启动、执行代码、停止沙箱容器、检查容器状态的接口,用于会话隔离。

    Story 4.4 向后兼容扩展:
    - 既有 4 个方法保持调用行为不变(默认参数扩展,既有调用点零修改)
    - 新增 health_check() 方法用于监控与熔断器集成
    """

    async def start_container(
        self,
        session_id: str,
        spec: ContainerSpec | None = None,
    ) -> None:
        """为指定会话启动沙箱容器

        Args:
            session_id: 会话唯一标识
            spec: 容器规格(可选,默认 None → 沿用实现默认配置)

        Raises:
            ContainerStartError: 容器启动失败
        """
        ...

    async def execute_code(
        self,
        session_id: str,
        code: str,
        *,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        """在沙箱中执行代码

        Args:
            session_id: 会话标识
            code: 待执行的代码
            timeout_sec: 执行超时(秒,可选 keyword-only,默认 None → 沿用实现默认)

        Returns:
            执行结果字典,包含 status、output、error 键

        Raises:
            ExecutionError: 执行失败
        """
        ...

    async def stop_container(self, session_id: str, *, reason: str = "explicit_stop") -> None:
        """停止并清理沙箱容器

        Args:
            session_id: 会话标识
            reason: 终止原因(可选 keyword-only,默认 "explicit_stop";
                用于 SandboxSessionTerminated.termination_reason 事件字段,
                如 idle_timeout / explicit_stop / timeout_abort)

        Raises:
            ContainerStopError: 容器停止失败
        """
        ...

    async def is_container_running(self, session_id: str) -> bool:
        """检查指定会话的容器是否正在运行

        Args:
            session_id: 会话标识

        Returns:
            容器正在运行返回 True,否则返回 False
        """
        ...

    async def health_check(self) -> bool:
        """Docker daemon 健康检查(用于熔断器 + 启动探针)

        Returns:
            daemon 可达返回 True,否则 False(**不抛异常**,由调用方决定熔断)
        """
        ...
