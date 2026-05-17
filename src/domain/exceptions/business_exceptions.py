"""领域层 业务级异常模块

定义业务级异常，用于表示业务规则违反，如验证失败、资源不存在、资源冲突等

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from src.domain.exceptions.base_exceptions import BaseException


class BusinessException(BaseException):
    """业务级异常，业务规则违反."""

    code = "EXCEPTION_2XX"


class ValidationError(BusinessException):
    """验证失败"""

    code = "EXCEPTION_201"
    message = "Validation error"


class NotFoundError(BusinessException):
    """资源不存在"""

    code = "EXCEPTION_202"
    message = "Resource not found"


class ConflictError(BusinessException):
    """资源冲突（版本冲突、状态冲突等）"""

    code = "EXCEPTION_203"
    message = "Resource conflict"


class PermissionDeniedError(BusinessException):
    """权限不足"""

    code = "EXCEPTION_204"
    message = "Permission denied"


class AuthenticationError(BusinessException):
    """认证失败"""

    code = "EXCEPTION_205"
    message = "Authentication failed"


class InvalidStateError(BusinessException):
    """无效状态"""

    code = "EXCEPTION_206"
    message = "Invalid state"


class BusinessRuleViolationError(BusinessException):
    """业务规则违反"""

    code = "EXCEPTION_207"
    message = "Business rule violation"


class InvalidStateTransitionError(InvalidStateError):
    """状态转换异常（保留 from_status/to_status 接口）

    用于 Outbox 等状态机的状态转换验证
    """

    code = "EXCEPTION_208"

    def __init__(
        self,
        from_status: str,
        to_status: str,
        message: str | None = None,
    ) -> None:
        self.from_status = from_status
        self.to_status = to_status
        context = {"from_status": from_status, "to_status": to_status}
        if message:
            super().__init__(
                f"Invalid state transition: {from_status} → {to_status}: {message}",
                context=context,
            )
        else:
            super().__init__(
                f"Invalid state transition: {from_status} → {to_status}",
                context=context,
            )


__all__ = [
    "BusinessException",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "PermissionDeniedError",
    "AuthenticationError",
    "InvalidStateError",
    "BusinessRuleViolationError",
    "InvalidStateTransitionError",
]
