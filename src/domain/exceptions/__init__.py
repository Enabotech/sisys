"""sisys - Domain Exceptions.

领域异常层次结构：
- BaseException: 异常层次结构根类
- SystemException: 系统级异常（基础设施故障）
- BusinessException: 业务级异常（业务规则违反）
- ExternalException: 外部服务异常

架构约束：领域层零依赖，仅使用 Python 标准库。
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
from src.domain.exceptions.external_exceptions import (
    ExternalException,
    ServiceUnavailableError,
    ThirdPartyError,
    TimeoutError,
    UnknownError,
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
]
