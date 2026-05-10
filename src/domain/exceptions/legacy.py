"""Legacy Exception Wrappers — DEPRECATED 遗留异常包装类.

警告：此模块已弃用，请使用以下模块的异常：

新模块                                | 异常
-------------------------------------|----------------------------------
service_exceptions                   | AuditError, PasswordValidationError, ComplianceLockError
storage_exceptions                    | MemoryVersionConflictError, MemoryNotFoundError, etc.
role_exceptions                       | RoleAlreadyExistsError, RoleNotFoundError, etc.
sandbox_exceptions                    | SandboxError, ContainerStartError, etc.
permission_exceptions                  | InsufficientTokenError
event_exceptions                      | VersionError

迁移完成后此文件将被删除。保留此文件确保迁移过程无破坏性变更。
"""

from __future__ import annotations

from src.domain.exceptions.event_exceptions import VersionError
from src.domain.exceptions.permission_exceptions import InsufficientTokenError
from src.domain.exceptions.role_exceptions import (
    CannotDeleteRoleWithUsersError,
    CannotDeleteSystemRoleError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
)
from src.domain.exceptions.sandbox_exceptions import (
    ContainerStartError,
    ContainerStopError,
    ExecutionError,
    SandboxError,
)

# 重新导出所有异常，保持向后兼容
from src.domain.exceptions.service_exceptions import (
    AuditError,
    ComplianceLockError,
    PasswordValidationError,
)
from src.domain.exceptions.storage_exceptions import (
    BucketNameValidationError,
    BucketNotFoundError,
    MemoryAccessDeniedError,
    MemoryNotFoundError,
    MemoryVersionConflictError,
    MinIOConnectionError,
)

__all__ = [
    # 服务异常
    "AuditError",
    "PasswordValidationError",
    "ComplianceLockError",
    # 存储异常
    "MemoryVersionConflictError",
    "MemoryNotFoundError",
    "BucketNotFoundError",
    "MinIOConnectionError",
    "BucketNameValidationError",
    "MemoryAccessDeniedError",
    # 角色管理异常
    "RoleAlreadyExistsError",
    "RoleNotFoundError",
    "CannotDeleteSystemRoleError",
    "CannotDeleteRoleWithUsersError",
    # Sandbox异常
    "SandboxError",
    "ContainerStartError",
    "ExecutionError",
    "ContainerStopError",
    # 权限异常
    "InsufficientTokenError",
    # 事件异常
    "VersionError",
]
