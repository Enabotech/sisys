"""Legacy Exception Wrappers — 遗留异常包装类.

向后兼容：覆盖所有现有异常类，确保迁移过程无破坏性变更。
所有带属性的遗留异常使用真实继承而非别名，保留原有接口。

异常来源映射：
- src/domain/ports/audit_service.py → AuditError
- src/domain/ports/auth_service.py → AuthenticationError
- src/domain/ports/password_validation_service.py → PasswordValidationError
- src/domain/ports/storage.py → ComplianceLockError
- src/domain/services/memory_service.py → MemoryVersionConflictError, MemoryNotFoundError
- src/application/use_cases/role_management.py → RoleAlreadyExistsError, RoleNotFoundError, ...
- src/application/ports/sandbox_port.py → SandboxError, ContainerStartError, ...
- src/infrastructure/messaging/outbox/outbox.py → InvalidStateTransitionError
- src/infrastructure/messaging/event_store.py → VersionError
- src/infrastructure/storage/minio/client_adapter.py → BucketNotFoundError, MinIOConnectionError, ...
- src/infrastructure/security/permission_middleware.py → PermissionDeniedError, InsufficientTokenError
"""

from __future__ import annotations

from uuid import UUID

from src.domain.exceptions.business_exceptions import (
    BusinessRuleViolationError,
    ConflictError,
    InvalidStateError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from src.domain.exceptions.external_exceptions import ExternalException
from src.domain.exceptions.system_exceptions import NetworkError, SystemException


# === 审计服务异常 ===
class AuditError(SystemException):
    """审计操作异常."""

    code = "EXCEPTION_105"
    message = "Audit operation failed"


# === 密码验证异常 ===
class PasswordValidationError(ValidationError):
    """密码验证失败异常（保留 message + code 属性）."""

    code = "EXCEPTION_201"

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        self.code = code or self.__class__.code
        super().__init__(message)


# === 存储端口异常 ===
class ComplianceLockError(InvalidStateError):
    """合规锁定异常."""

    code = "EXCEPTION_206"
    message = "Compliance lock violation"


# === 记忆服务异常 ===
class MemoryVersionConflictError(ConflictError):
    """版本冲突异常（保留 memory_id 属性）."""

    code = "EXCEPTION_203"

    def __init__(self, memory_id: UUID, message: str = "版本冲突") -> None:
        self.memory_id = memory_id
        super().__init__(message)


class MemoryNotFoundError(NotFoundError):
    """记忆不存在异常（保留 memory_id 属性）."""

    code = "EXCEPTION_202"

    def __init__(self, memory_id: UUID, message: str = "记忆不存在") -> None:
        self.memory_id = memory_id
        super().__init__(message)


# === 角色管理异常 ===
class RoleAlreadyExistsError(ConflictError):
    """角色已存在异常（保留 name 属性）."""

    code = "EXCEPTION_203"

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Role with name '{name}' already exists")


class RoleNotFoundError(NotFoundError):
    """角色不存在异常（保留 role_id 属性）."""

    code = "EXCEPTION_202"

    def __init__(self, role_id: UUID) -> None:
        self.role_id = role_id
        super().__init__(f"Role with id '{role_id}' not found")


class CannotDeleteSystemRoleError(BusinessRuleViolationError):
    """不能删除系统保留角色异常（保留 role_id 属性）."""

    code = "EXCEPTION_207"

    def __init__(self, role_id: UUID) -> None:
        self.role_id = role_id
        super().__init__(f"Cannot delete system-reserved role '{role_id}'")


class CannotDeleteRoleWithUsersError(ConflictError):
    """不能删除有关联用户的角色异常（保留 role_id + user_count 属性）."""

    code = "EXCEPTION_203"

    def __init__(self, role_id: UUID, user_count: int) -> None:
        self.role_id = role_id
        self.user_count = user_count
        super().__init__(f"Cannot delete role '{role_id}' - {user_count} users are assigned to this role")


# === MinIO 存储异常 ===
class BucketNotFoundError(NotFoundError):
    """Bucket 不存在异常."""

    code = "EXCEPTION_202"
    message = "Bucket not found"


class MinIOConnectionError(NetworkError):
    """MinIO 连接错误."""

    code = "EXCEPTION_102"
    message = "MinIO connection error"


# === 消息事件存储异常 ===
class VersionError(ConflictError):
    """乐观锁冲突异常."""

    code = "EXCEPTION_203"
    message = "Version conflict"


# === Sandbox 沙箱异常 ===
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


# === 权限中间件异常 ===
class InsufficientTokenError(PermissionDeniedError):
    """Token 信息不足异常."""

    code = "EXCEPTION_204"
    message = "Insufficient token"


# === 其他待迁移异常 ===
class MemoryAccessDeniedError(PermissionDeniedError):
    """记忆访问被拒绝异常."""

    code = "EXCEPTION_204"
    message = "Memory access denied"


class BucketNameValidationError(ValidationError):
    """Bucket 名称验证失败异常."""

    code = "EXCEPTION_201"
    message = "Bucket name validation failed"


__all__ = [
    # 审计
    "AuditError",
    # 密码验证
    "PasswordValidationError",
    # 存储
    "ComplianceLockError",
    # 记忆服务
    "MemoryVersionConflictError",
    "MemoryNotFoundError",
    # 角色管理
    "RoleAlreadyExistsError",
    "RoleNotFoundError",
    "CannotDeleteSystemRoleError",
    "CannotDeleteRoleWithUsersError",
    # MinIO
    "BucketNotFoundError",
    "MinIOConnectionError",
    # 消息事件
    "VersionError",
    # Sandbox
    "SandboxError",
    "ContainerStartError",
    "ExecutionError",
    "ContainerStopError",
    # 权限
    "InsufficientTokenError",
    # 其他
    "MemoryAccessDeniedError",
    "BucketNameValidationError",
]
