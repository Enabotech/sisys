"""领域层服务异常模块

定义审计服务、密码验证、存储端口相关异常

异常来源：
- src/domain/ports/audit_service.py → AuditError
- src/domain/ports/password_validation_service.py → PasswordValidationError
- src/domain/ports/storage.py → ComplianceLockError

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import (
    InvalidStateError,
    ValidationError,
)
from src.domain.exceptions.system_exceptions import SystemException


class AuditError(SystemException):
    """审计操作异常

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_105"
    message = "Audit operation failed"


class PasswordValidationError(ValidationError):
    """密码验证失败异常

    Attributes:
        code: 异常编码，可由调用方覆盖
        message: 异常消息
    """

    code = "EXCEPTION_201"

    def __init__(self, message: str, code: str | None = None) -> None:
        """初始化密码验证失败异常

        Args:
            message: 异常消息
            code: 异常编码，为 None 时使用类默认编码
        """
        self.message = message
        self.code = code or self.__class__.code
        super().__init__(message)


class ComplianceLockError(InvalidStateError):
    """合规锁定异常

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_206"
    message = "Compliance lock violation"


__all__ = [
    "AuditError",
    "PasswordValidationError",
    "ComplianceLockError",
]
