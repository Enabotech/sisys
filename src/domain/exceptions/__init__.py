"""领域层异常模块

领域异常层次结构：
- BaseException: 异常层次结构根类
- SystemException: 系统级异常（基础设施故障）
- BusinessException: 业务级异常（业务规则违反）
- ExternalException: 外部服务异常

架构约束：领域层零依赖，仅使用 Python 标准库
"""

from __future__ import annotations

from src.domain.exceptions.base_exceptions import BaseException
from src.domain.exceptions.business_exceptions import (
    AuthenticationError,
    BusinessException,
    BusinessRuleViolationError,
    ConflictError,
    InvalidStateError,
    InvalidStateTransitionError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from src.domain.exceptions.embedding_exceptions import (
    EmbeddingAPIError,
    EmbeddingModelError,
    EmbeddingResponseError,
)
from src.domain.exceptions.event_exceptions import VersionError
from src.domain.exceptions.external_exceptions import (
    ExternalException,
    ServiceUnavailableError,
    ThirdPartyError,
    TimeoutError,
    UnknownError,
)
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
from src.domain.exceptions.system_exceptions import (
    ConfigurationError,
    MessageBusError,
    NetworkError,
    StorageError,
    SystemException,
)

__all__ = [
    # 抽象根类
    "BaseException",
    # 系统级异常
    "SystemException",
    "ConfigurationError",
    "NetworkError",
    "StorageError",
    "MessageBusError",
    # 业务级异常
    "BusinessException",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "PermissionDeniedError",
    "AuthenticationError",
    "InvalidStateError",
    "InvalidStateTransitionError",
    "BusinessRuleViolationError",
    # 外部服务异常
    "ExternalException",
    "ThirdPartyError",
    "TimeoutError",
    "ServiceUnavailableError",
    "UnknownError",
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
    # 嵌入服务异常
    "EmbeddingAPIError",
    "EmbeddingResponseError",
    "EmbeddingModelError",
    # 权限异常
    "InsufficientTokenError",
    # 事件异常
    "VersionError",
]
