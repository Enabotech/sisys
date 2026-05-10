"""SystemException — 系统级异常.

基础设施故障，如配置错误、网络错误、存储错误等。
"""

from __future__ import annotations

from src.domain.exceptions.base_exceptions import BaseException


class SystemException(BaseException):
    """系统级异常，基础设施故障."""

    code = "EXCEPTION_1XX"


class ConfigurationError(SystemException):
    """配置错误."""

    code = "EXCEPTION_101"
    message = "Configuration error"


class NetworkError(SystemException):
    """网络故障."""

    code = "EXCEPTION_102"
    message = "Network error"


class StorageError(SystemException):
    """存储服务故障."""

    code = "EXCEPTION_103"
    message = "Storage error"


class MessageBusError(SystemException):
    """消息总线故障."""

    code = "EXCEPTION_104"
    message = "Message bus error"


__all__ = [
    "SystemException",
    "ConfigurationError",
    "NetworkError",
    "StorageError",
    "MessageBusError",
]
