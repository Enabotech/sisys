"""ExternalException — 外部服务异常.

第三方服务错误，如超时、服务不可用等。
"""

from __future__ import annotations

from src.domain.exceptions.base_exceptions import BaseException


class ExternalException(BaseException):
    """外部服务异常."""

    code = "EXCEPTION_3XX"


class ThirdPartyError(ExternalException):
    """第三方服务错误."""

    code = "EXCEPTION_301"
    message = "Third party service error"


class TimeoutError(ExternalException):
    """外部服务超时."""

    code = "EXCEPTION_302"
    message = "External service timeout"


class ServiceUnavailableError(ExternalException):
    """外部服务不可用."""

    code = "EXCEPTION_303"
    message = "Service unavailable"


class UnknownError(ExternalException):
    """未知错误（未预期异常兜底）."""

    code = "EXCEPTION_999"
    message = "Unknown error"


__all__ = [
    "ExternalException",
    "ThirdPartyError",
    "TimeoutError",
    "ServiceUnavailableError",
    "UnknownError",
]
