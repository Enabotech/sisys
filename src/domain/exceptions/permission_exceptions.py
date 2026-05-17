"""领域层权限异常模块

定义权限相关异常，如 Token 信息不足等

异常来源：
- src/infrastructure/security/permission_middleware.py → InsufficientTokenError

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import PermissionDeniedError


class InsufficientTokenError(PermissionDeniedError):
    """Token 信息不足异常

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_204"
    message = "Insufficient token"


__all__ = [
    "InsufficientTokenError",
]
