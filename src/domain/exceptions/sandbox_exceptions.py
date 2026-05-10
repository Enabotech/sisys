"""Sandbox Exceptions — 沙箱相关异常.

异常来源：
- src/application/ports/sandbox_port.py → SandboxError, ContainerStartError, ExecutionError, ContainerStopError
- src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py → raises these exceptions
"""

from __future__ import annotations

from src.domain.exceptions.external_exceptions import ExternalException


class SandboxError(ExternalException):
    """沙箱基础异常."""

    code = "EXCEPTION_301"
    message = "Sandbox error"


class ContainerStartError(SandboxError):
    """容器启动失败异常."""

    code = "EXCEPTION_301"
    message = "Container start error"


class ExecutionError(SandboxError):
    """代码执行失败异常."""

    code = "EXCEPTION_301"
    message = "Execution error"


class ContainerStopError(SandboxError):
    """容器停止失败异常."""

    code = "EXCEPTION_301"
    message = "Container stop error"


__all__ = [
    "SandboxError",
    "ContainerStartError",
    "ExecutionError",
    "ContainerStopError",
]
