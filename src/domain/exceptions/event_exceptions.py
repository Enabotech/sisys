"""领域层 事件异常模块

定义事件存储相关异常
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import ConflictError


class VersionError(ConflictError):
    """乐观锁冲突异常"""

    code = "EXCEPTION_203"
    message = "Version conflict"


__all__ = [
    "VersionError",
]
