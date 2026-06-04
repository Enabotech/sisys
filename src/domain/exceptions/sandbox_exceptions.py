"""领域层沙箱异常模块

定义沙箱执行相关的领域异常，包括容器启动失败、代码执行失败、容器停止失败等。
每个异常类分配独立编码（309-312），确保监控可精确区分故障类型。
"""

from __future__ import annotations

from src.domain.exceptions.external_exceptions import ExternalException


class SandboxError(ExternalException):
    """沙箱基础异常."""

    code = "EXCEPTION_309"
    message = "Sandbox error"


class ContainerStartError(SandboxError):
    """容器启动失败异常."""

    code = "EXCEPTION_310"
    message = "Container start error"


class ExecutionError(SandboxError):
    """代码执行失败异常."""

    code = "EXCEPTION_311"
    message = "Execution error"


class ContainerStopError(SandboxError):
    """容器停止失败异常."""

    code = "EXCEPTION_312"
    message = "Container stop error"


__all__ = [
    "SandboxError",
    "ContainerStartError",
    "ExecutionError",
    "ContainerStopError",
]
