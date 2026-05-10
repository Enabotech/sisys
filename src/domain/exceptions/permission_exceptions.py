"""Permission Exceptions — 权限相关异常.

异常来源：
- src/infrastructure/security/permission_middleware.py → InsufficientTokenError
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import PermissionDeniedError


class InsufficientTokenError(PermissionDeniedError):
    """Token 信息不足异常."""

    code = "EXCEPTION_204"
    message = "Insufficient token"


__all__ = [
    "InsufficientTokenError",
]
