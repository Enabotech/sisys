# 统一异常处理设计方案

**状态：** 设计方案
**创建日期：** 2026-05-10
**作者：** Agimtech
**评审状态：** 待评审

---

## 1. 现状分析

### 1.1 当前问题

| 问题 | 描述 | 影响 |
|------|------|------|
| **散落定义** | 异常类散布在 domain/ports、application/use_cases、infrastructure/storage 等15+个文件中 | 难以维护、重复定义 |
| **无层次结构** | 所有异常继承自 Exception，缺少分类体系 | 无法按类型统一处理 |
| **重复定义** | `PermissionDeniedError`、`ComplianceLockError` 在多处重复定义 | 混淆与不一致 |
| **映射缺失** | 基础设施层 SDK 错误（如 S3Error）无统一映射机制 | 错误信息不友好 |
| **无追踪机制** | 异常不含错误码、上下文、追踪ID | 排查困难 |
| **日志不规范** | catch-and-log 模式各异，错误级别不统一 | 日志分析困难 |
| **API 转换重复** | 每个 API 端点重复编写 try/except HTTP 转换 | 代码冗余 |

### 1.2 当前异常分布

```
src/domain/exceptions/invalid_state_error.py          # 仅1个
src/domain/ports/audit_service.py                     # AuditError
src/domain/ports/auth_service.py                      # AuthenticationError
src/domain/ports/password_validation_service.py       # PasswordValidationError
src/domain/ports/storage.py                          # ComplianceLockError
src/domain/services/memory_service.py                 # MemoryVersionConflictError, MemoryNotFoundError
src/application/use_cases/role_management.py          # RoleAlreadyExistsError, RoleNotFoundError, ...
src/application/ports/sandbox_port.py                 # SandboxError, ContainerStartError, ...
src/infrastructure/messaging/outbox/outbox.py         # InvalidStateTransitionError
src/infrastructure/messaging/event_store.py            # VersionError
src/infrastructure/storage/minio/client_adapter.py   # BucketNotFoundError, PermissionDeniedError, ...
src/infrastructure/security/permission_middleware.py  # PermissionDeniedError, InsufficientTokenError
```

### 1.3 违反的架构原则

- **单一职责原则**：异常定义应集中管理
- **开闭原则**：新增异常类型应扩展而非修改现有代码
- **依赖倒置**：领域层异常应与具体实现无关

---

## 2. 业界最佳实践对标

### 2.1 主流框架异常体系

| 框架 | 异常基类 | 层次结构 | 特点 |
|------|---------|---------|------|
| **Java Spring** | RuntimeException → BusinessException | 三层分类（业务/系统/基础设施） | 统一异常处理器 + @ExceptionHandler |
| **Python Django** | DjangoException → ValidationError | 散射状 | 中间件统一处理 |
| **Go** | error 接口 + errors.New() | 轻量，无层级 | 错误包装 + 错误链 |
| **Rust** | std::error::Error trait | 轻量接口 | 错误枚举 + 错误链 |
| **C# .NET** | Exception → ApplicationException | 二叉分类（系统/应用） | 全局异常过滤器 |

### 2.2 推荐模式：分层异常体系

```
BaseException (抽象根)
├── SystemException (系统级)
│   ├── ConfigurationError
│   ├── NetworkError
│   └── InfrastructureError
├── BusinessException (业务级)
│   ├── ValidationError
│   ├── NotFoundError
│   └── ConflictError
└── ExternalException (外部服务)
    ├── ThirdPartyError
    └── TimeoutError
```

### 2.3 关键设计要点

1. **错误码体系**：每类异常分配唯一错误码，便于追踪
2. **错误链**：保留原始异常信息，支持 cause 追溯
3. **上下文携带**：异常含请求ID、会话ID等调试信息
4. **统一日志格式**：结构化日志，便于分析
5. **HTTP 映射表**：异常类型 → HTTP 状态码自动映射

---

## 3. 设计方案

### 3.1 异常层次结构

```python
# src/domain/exceptions/__init__.py

class BaseException(Exception):
    """异常层次结构根类.

    注意：此基类定义在领域层（src/domain/exceptions/），仅使用Python标准库。
    HTTP状态码等Web层关注点不在此定义，由接口层异常处理器负责映射。
    """
    code: str = "EXCEPTION_000"
    message: str = "Unknown error"

    def __init__(
        self,
        message: str | None = None,
        cause: BaseException | None = None,
        context: dict | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.cause = cause
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        result = {
            "code": self.code or "EXCEPTION_000",
            "message": self.message or "Unknown error",
            "context": self.context or {},
        }
        if self.cause:
            result["cause"] = {
                "type": type(self.cause).__name__,
                "message": str(self.cause),
            }
        return result


# === 系统级异常（System）===
class SystemException(BaseException):
    """系统级异常，基础设施故障."""
    code = "EXCEPTION_1XX"


class ConfigurationError(SystemException):
    """配置错误."""
    code = "EXCEPTION_101"
    message = "Configuration error"


class NetworkError(SystemException):
    """网络故障."""
    code = "EXCEPTION_102"
    message = "Network error"


class StorageError(SystemException):
    """存储服务故障."""
    code = "EXCEPTION_103"
    message = "Storage error"


class MessageBusError(SystemException):
    """消息总线故障."""
    code = "EXCEPTION_104"
    message = "Message bus error"


# === 业务级异常（Business）===
class BusinessException(BaseException):
    """业务级异常，业务规则违反."""
    code = "EXCEPTION_2XX"


class ValidationError(BusinessException):
    """验证失败."""
    code = "EXCEPTION_201"
    message = "Validation error"


class NotFoundError(BusinessException):
    """资源不存在."""
    code = "EXCEPTION_202"
    message = "Resource not found"


class ConflictError(BusinessException):
    """资源冲突（版本冲突、状态冲突等）."""
    code = "EXCEPTION_203"
    message = "Resource conflict"


class PermissionDeniedError(BusinessException):
    """权限不足."""
    code = "EXCEPTION_204"
    message = "Permission denied"


class AuthenticationError(BusinessException):
    """认证失败."""
    code = "EXCEPTION_205"
    message = "Authentication failed"


class InvalidStateError(BusinessException):
    """无效状态."""
    code = "EXCEPTION_206"
    message = "Invalid state"


class InvalidStateTransitionError(InvalidStateError):
    """状态转换异常（保留 from_status/to_status 接口）.

    用于 Outbox 等状态机的状态转换验证。
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
        super().__init__(message or f"Invalid transition from {from_status} to {to_status}")


class BusinessRuleViolationError(BusinessException):
    """业务规则违反."""
    code = "EXCEPTION_207"
    message = "Business rule violation"


# === 外部服务异常（External）===
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


# === 抽象中间类（禁止直接实例化）===
class SystemExceptionMeta(type):
    """确保 SystemException 子类定义了具体错误码."""
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if bases and name != "SystemException":
            # 占位码集合（中间类的标记值）
            placeholder_codes = {"EXCEPTION_1XX", "EXCEPTION_2XX", "EXCEPTION_3XX"}
            if not hasattr(cls, 'code') or cls.code in placeholder_codes:
                if name not in ('SystemException', 'BusinessException', 'ExternalException'):
                    raise TypeError(f"{name} must define a concrete code")
        return cls
```

```python
# src/domain/exceptions/legacy.py
"""遗留异常包装类，向后兼容.

覆盖所有现有异常类，确保迁移过程无破坏性变更。
所有带属性的遗留异常使用真实继承而非别名，保留原有接口。
"""
from __future__ import annotations
from uuid import UUID

from src.domain.exceptions import (
    BaseException,
    SystemException,
    BusinessException,
    NotFoundError,
    PermissionDeniedError,
    AuthenticationError,
    ValidationError,
    ConflictError,
    InvalidStateError,
    InvalidStateTransitionError,
    BusinessRuleViolationError,
    ExternalException,
    NetworkError,
    TimeoutError,
    ServiceUnavailableError,
    ThirdPartyError,
)

# === 遗留异常包装类（保留原有属性）===

class AuditError(SystemException):
    """审计操作异常."""
    code = "EXCEPTION_101"
    message = "Audit operation failed"


class PasswordValidationError(ValidationError):
    """密码验证失败异常（保留 message + code 属性）."""
    code = "EXCEPTION_201"

    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class ComplianceLockError(InvalidStateError):
    """合规锁定异常."""
    code = "EXCEPTION_206"
    message = "Compliance lock violation"


class MemoryVersionConflictError(ConflictError):
    """版本冲突异常（保留 memory_id 属性）."""
    code = "EXCEPTION_203"

    def __init__(self, memory_id: UUID, message: str = "版本冲突"):
        self.memory_id = memory_id
        super().__init__(message)


class MemoryNotFoundError(NotFoundError):
    """记忆不存在异常（保留 memory_id 属性）."""
    code = "EXCEPTION_202"

    def __init__(self, memory_id: UUID, message: str = "记忆不存在"):
        self.memory_id = memory_id
        super().__init__(message)


class RoleAlreadyExistsError(ConflictError):
    """角色已存在异常（保留 name 属性）."""
    code = "EXCEPTION_203"

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Role with name '{name}' already exists")


class RoleNotFoundError(NotFoundError):
    """角色不存在异常（保留 role_id 属性）."""
    code = "EXCEPTION_202"

    def __init__(self, role_id: UUID):
        self.role_id = role_id
        super().__init__(f"Role with id '{role_id}' not found")


class CannotDeleteSystemRoleError(BusinessRuleViolationError):
    """不能删除系统保留角色异常（保留 role_id 属性）."""
    code = "EXCEPTION_207"

    def __init__(self, role_id: UUID):
        self.role_id = role_id
        super().__init__(f"Cannot delete system-reserved role '{role_id}'")


class CannotDeleteRoleWithUsersError(ConflictError):
    """不能删除有关联用户的角色异常（保留 role_id + user_count 属性）."""
    code = "EXCEPTION_203"

    def __init__(self, role_id: UUID, user_count: int):
        self.role_id = role_id
        self.user_count = user_count
        super().__init__(f"Cannot delete role '{role_id}' - {user_count} users are assigned to this role")


# MinIO 异常
class BucketNotFoundError(NotFoundError):
    """Bucket 不存在异常."""
    code = "EXCEPTION_202"
    message = "Bucket not found"


class MinIOConnectionError(NetworkError):
    """MinIO 连接错误."""
    code = "EXCEPTION_102"
    message = "MinIO connection error"


# 基础设施层异常
class VersionError(ConflictError):
    """乐观锁冲突异常."""
    code = "EXCEPTION_203"
    message = "Version conflict"


# Sandbox 异常（来自 src/application/ports/sandbox_port.py）
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


# 权限中间件异常（来自 src/infrastructure/security/permission_middleware.py）
class InsufficientTokenError(PermissionDeniedError):
    """Token 信息不足异常."""
    code = "EXCEPTION_204"
    message = "Insufficient token"

__all__ = [
    # 基类和三层异常
    "BaseException",
    "SystemException",
    "BusinessException",
    "ExternalException",
    # 具体异常
    "NotFoundError",
    "PermissionDeniedError",
    "AuthenticationError",
    "ValidationError",
    "ConflictError",
    "InvalidStateError",
    "InvalidStateTransitionError",
    "BusinessRuleViolationError",
    # 遗留别名
    "AuditError",
    "PasswordValidationError",
    "ComplianceLockError",
    "MemoryVersionConflictError",
    "MemoryNotFoundError",
    "RoleAlreadyExistsError",
    "RoleNotFoundError",
    "CannotDeleteSystemRoleError",
    "CannotDeleteRoleWithUsersError",
    "SandboxError",
    "ContainerStartError",
    "ExecutionError",
    "ContainerStopError",
    "VersionError",
    "BucketNotFoundError",
    "MinIOConnectionError",
    "InsufficientTokenError",
    "NetworkError",
    "TimeoutError",
    "ServiceUnavailableError",
    "ThirdPartyError",
]
```

### 3.3 统一异常处理器

```python
# src/interfaces/api/exception_handlers.py

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

from src.domain.exceptions import (
    BaseException,
    SystemException,
    BusinessException,
    ExternalException,
    NotFoundError,
    PermissionDeniedError,
    AuthenticationError,
    ConflictError,
    ValidationError,
    InvalidStateError,
    InvalidStateTransitionError,
    BusinessRuleViolationError,
    ThirdPartyError,
    TimeoutError,
    ServiceUnavailableError,
    NetworkError,
    StorageError,
    MessageBusError,
    ConfigurationError,
    SandboxError,
    UnknownError,
)

# 异常类型 → HTTP 状态码映射表（唯一真相源）
EXCEPTION_HTTP_MAP: dict[type[BaseException], int] = {
    # 三层基类
    SystemException: status.HTTP_500_INTERNAL_SERVER_ERROR,
    BusinessException: status.HTTP_400_BAD_REQUEST,
    ExternalException: status.HTTP_502_BAD_GATEWAY,
    # 具体异常精确覆盖
    NotFoundError: status.HTTP_404_NOT_FOUND,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    ConflictError: status.HTTP_409_CONFLICT,
    ValidationError: status.HTTP_400_BAD_REQUEST,
    InvalidStateError: status.HTTP_409_CONFLICT,
    InvalidStateTransitionError: status.HTTP_409_CONFLICT,
    BusinessRuleViolationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ThirdPartyError: status.HTTP_502_BAD_GATEWAY,
    NetworkError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    StorageError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    MessageBusError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    SandboxError: status.HTTP_502_BAD_GATEWAY,
    TimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
    ServiceUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
    UnknownError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _get_http_status(exc: BaseException) -> int:
    """获取异常对应的HTTP状态码，优先使用具体异常映射."""
    # 精确匹配优先
    for exc_type, http_status in EXCEPTION_HTTP_MAP.items():
        if type(exc) is exc_type:
            return http_status
    # 然后是MRO匹配
    for exc_type, http_status in EXCEPTION_HTTP_MAP.items():
        if isinstance(exc, exc_type):
            return http_status
    return status.HTTP_500_INTERNAL_SERVER_ERROR


class ExceptionHandlers:
    """统一异常处理器注册."""

    def __init__(self, app: FastAPI) -> None:
        self._app = app
        self._register_handlers()

    def _register_handlers(self) -> None:
        """注册全局异常处理器.

        注意：具体异常处理器必须先于基类处理器注册，
        FastAPI 按注册顺序查找匹配，精确匹配优先。
        注意：Exception 必须在 BaseException 之前注册，否则 BaseException 会先匹配。
        """
        self._app.add_exception_handler(RequestValidationError, self._handle_validation_error)
        self._app.add_exception_handler(PydanticValidationError, self._handle_pydantic_error)
        self._app.add_exception_handler(Exception, self._handle_unexpected_error)
        self._app.add_exception_handler(BaseException, self._handle_exception)

    async def _handle_exception(
        self, request: Request, exc: BaseException
    ) -> JSONResponse:
        """处理异常."""
        # 安全获取 request_id，不依赖特定中间件
        request_id = getattr(request.state, "request_id", None) or "unknown"

        # 特殊处理：AuthenticationError 的 locked 状态
        if isinstance(exc, AuthenticationError):
            context = getattr(exc, 'context', {}) or {}
            if context.get("locked"):
                return JSONResponse(
                    status_code=status.HTTP_423_LOCKED,
                    content={
                        "error": {
                            "code": getattr(exc, 'code', "EXCEPTION_205") or "EXCEPTION_205",
                            "message": "Account is locked",
                            "context": context,
                        },
                        "request_id": request_id,
                    },
                    headers={"X-Error-Code": getattr(exc, 'code', "EXCEPTION_205") or "EXCEPTION_205"},
                )

        try:
            error_dict = exc.to_dict()
        except Exception:
            # to_dict() 失败时的降级处理：保留 context 和 cause 信息
            error_dict = {
                "code": getattr(exc, 'code', None) or "EXCEPTION_999",
                "message": str(exc)[:500],
                "context": getattr(exc, 'context', None) or {},
            }
            # 保留 cause 信息
            cause = getattr(exc, 'cause', None)
            if cause:
                error_dict["cause"] = {
                    "type": type(cause).__name__,
                    "message": str(cause),
                }

        content = {
            "error": error_dict,
            "request_id": request_id,
        }

        return JSONResponse(
            status_code=_get_http_status(exc),
            content=content,
            headers={"X-Error-Code": str(getattr(exc, 'code', "EXCEPTION_999") or "EXCEPTION_999")},
        )

    async def _handle_validation_error(
        self, request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """处理请求验证错误."""
        request_id = getattr(request.state, "request_id", None) or "unknown"

        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            })

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "EXCEPTION_201",
                    "message": "Validation error",
                    "context": {"validation_errors": errors},
                },
                "request_id": request_id,
            },
            headers={"X-Error-Code": "EXCEPTION_201"},
        )

    async def _handle_pydantic_error(
        self, request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        """处理 Pydantic 验证错误."""
        request_id = getattr(request.state, "request_id", None) or "unknown"
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "EXCEPTION_201",
                    "message": "Data validation error",
                    "context": {"errors": exc.errors()},
                },
                "request_id": request_id,
            },
        )

    async def _handle_unexpected_error(
        self, request: Request, exc: Exception
    ) -> JSONResponse:
        """处理未预期异常."""
        # 日志记录全量堆栈
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Unexpected error: %s", exc)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "EXCEPTION_999",
                    "message": "Internal server error",
                },
            },
            headers={"X-Error-Code": "EXCEPTION_999"},
        )


def register_exception_handlers(app: FastAPI) -> None:
    """注册异常处理器到 FastAPI 应用.

    实例被 app 引用链持有，无需保留返回值。
    用法：register_exception_handlers(app)  # 初始化时调用一次
    """
    # 实例被 add_exception_handler 内部引用持有，不会被 GC
    ExceptionHandlers(app)
```

### 3.4 外部 SDK 错误映射器

```python
# src/infrastructure/messaging/error_mapper.py

"""外部 SDK 错误到异常的标准化映射.

注意：优先使用类型匹配（isinstance）而非字符串匹配。
对于 MinIO S3Error，应使用 error.code 属性直接映射（见 map_s3_error）。
装饰器方案仅用于无法使用类型匹配的场景。
"""

import logging
from functools import wraps
from typing import Callable, TypeVar

from src.domain.exceptions import (
    BaseException,
    ExternalException,
    ThirdPartyError,
    TimeoutError,
    ServiceUnavailableError,
    SystemException,
    StorageError,
    NetworkError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
    BusinessRuleViolationError,
    MessageBusError,
    InvalidStateError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorMapper:
    """外部错误标准化映射器.

    使用示例：
        try:
            await client.stat(bucket, object_key)
        except S3Error as e:
            raise ErrorMapper.map_s3_error(e.code, e.message) from e
    """

    # MinIO S3Error 映射（使用 error.code 直接查找，非字符串匹配）
    # 注意：UnknownError 作为兜底返回，确保始终返回领域异常而非原始 S3Error
    # 使用 .get(code.lower()) 支持大小写不敏感查找
    S3_ERROR_MAP: dict[str, type[BaseException]] = {
        "nosuchbucket": NotFoundError,
        "nosuchkey": NotFoundError,
        "nosuchlifecycleconfiguration": NotFoundError,
        "bucketalreadyexists": ConflictError,
        "bucketalreadyownedbyyou": ConflictError,
        "accessdenied": PermissionDeniedError,
        "forbidden": PermissionDeniedError,
        "invalidobjectstate": InvalidStateError,  # WORM 对象状态限制是状态错误
        "objectlockconfigurationnotfound": InvalidStateError,  # WORM 配置缺失是状态错误
        "requesttimeout": TimeoutError,
        "serviceunavailable": ServiceUnavailableError,
        "internalerror": ThirdPartyError,  # S3 内部错误，非业务错误
        "nosuchupload": NotFoundError,
        "nosuchversion": NotFoundError,
        "entitytoolarge": ValidationError,
        "methodnotallowed": ThirdPartyError,  # S3 层面方法限制是外部服务错误
        "slowdown": ServiceUnavailableError,
    }

    # RabbitMQ 错误映射
    RABBITMQ_ERROR_MAP: dict[str, type[BaseException]] = {
        "ConnectionError": NetworkError,
        "ChannelError": MessageBusError,
        "TimeoutError": TimeoutError,
    }

    # Redis 错误映射
    REDIS_ERROR_MAP: dict[str, type[BaseException]] = {
        "ConnectionError": NetworkError,
        "TimeoutError": TimeoutError,
        "ClusterDownError": ServiceUnavailableError,
    }

    @classmethod
    def map_s3_error(cls, code: str, message: str | None = None) -> BaseException:
        """映射 MinIO S3 错误.

        Args:
            code: S3Error.code 属性值（如 "NoSuchBucket"）
            message: 原始错误消息

        Returns:
            对应的异常实例
        """
        # 大小写不敏感查找，支持各种大小写变体
        exc_class = cls.S3_ERROR_MAP.get(code.lower(), ThirdPartyError)
        if exc_class is ThirdPartyError:
            logger.warning("Unknown S3 error code: %s, defaulting to ThirdPartyError", code)
        return exc_class(message=message or f"S3 error: {code}")

    @classmethod
    def map_rabbitmq_error(cls, error_type: str, message: str | None = None) -> ExternalException:
        """映射 RabbitMQ 错误."""
        exc_class = cls.RABBITMQ_ERROR_MAP.get(error_type, MessageBusError)
        return exc_class(message=message or f"RabbitMQ error: {error_type}")

    @classmethod
    def map_redis_error(cls, error_type: str, message: str | None = None) -> SystemException:
        """映射 Redis 错误."""
        exc_class = cls.REDIS_ERROR_MAP.get(error_type, SystemException)
        return exc_class(message=message or f"Redis error: {error_type}")

    @classmethod
    def wrap_external_error(
        cls,
        error: Exception,
        target_exc_class: type[ExternalException],
        context: dict | None = None,
    ) -> ExternalException:
        """包装外部错误为异常.

        推荐用法（替代装饰器）：
            try:
                await external_call()
            except SomeError as e:
                raise ErrorMapper.wrap_external_error(
                    e, TargetException, {"operation": "xxx"}
                ) from e
        """
        logger.warning("Wrapping external error: %s -> %s", type(error).__name__, target_exc_class.__name__)
        return target_exc_class(
            message=str(error),
            cause=error,
            context=context,
        )


def with_error_mapping(
    error_map: dict[str, type[ExternalException]],
    default_exc: type[ExternalException] = ThirdPartyError,
    *,
    exact_match: bool = False,
) -> Callable:
    """装饰器：自动映射外部错误（仅用于无法使用类型匹配的场景）.

    注意：这是兜底方案。优先使用 ErrorMapper.map_* 方法直接映射。

    参数：
        exact_match: 为 True 时使用精确匹配（==），避免子串误匹配。
                   为 False（默认）时使用子串匹配（in），用于包含错误消息的场景。

    推荐用法：
        class MyAdapter:
            # 精确匹配：用于错误码字面量比较
            @with_error_mapping({"ConnectionError": NetworkError}, exact_match=True)
            async def connect(self):
                ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_str = str(e)
                for key, exc_class in error_map.items():
                    if exact_match:
                        if key.lower() == error_str.lower():
                            raise exc_class(message=str(e), cause=e) from None
                    else:
                        # 子串匹配（仅用于错误消息包含明确错误码的场景）
                        if key.lower() in error_str.lower():
                            raise exc_class(message=str(e), cause=e) from None
                raise default_exc(message=str(e), cause=e) from None
        return wrapper
    return decorator
```

### 3.5 结构化日志集成

```python
# src/infrastructure/logging/exception_logger.py

"""异常结构化日志处理器."""

import logging
import json
import traceback
from datetime import datetime, timezone
from typing import Any

from src.domain.exceptions import BaseException


class ExceptionJsonFormatter(logging.Formatter):
    """异常结构化日志格式化器."""

    def format(self, record: logging.LogRecord) -> str:
        if record.exc_info and record.exc_info[0]:
            exc = record.exc_info[1]
            if isinstance(exc, BaseException):
                return self._format_exception(record, exc)
        return self._format_standard(record)

    def _format_exception(
        self, record: logging.LogRecord, exc: BaseException
    ) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "error": {
                "code": exc.code,
                "message": exc.message,
                "context": exc.context,
            },
        }
        if exc.cause:
            log_entry["error"]["cause"] = {
                "type": type(exc.cause).__name__,
                "message": str(exc.cause),
            }
        return json.dumps(log_entry)

    def _format_standard(self, record: logging.LogRecord) -> str:
        return super().format(record)


def configure_exception_logging() -> None:
    """配置异常日志处理器."""
    handler = logging.StreamHandler()
    handler.setFormatter(ExceptionJsonFormatter())

    logger = logging.getLogger("exception")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
```

### 3.6 异常上下文中间件

```python
# src/interfaces/api/middleware/exception_context.py

"""请求上下文注入中间件."""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class ExceptionContextMiddleware(BaseHTTPMiddleware):
    """为每个请求注入唯一追踪ID."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

---

## 4. 迁移策略

### 4.1 阶段一：建立基础设施（2-3 人日）

1. 创建 `src/domain/exceptions/__init__.py` - 异常根类与三层异常体系
2. 创建 `src/domain/exceptions/legacy.py` - 遗留异常别名兼容层（覆盖 25+ 异常）
3. 创建 `src/interfaces/api/exception_handlers.py` - FastAPI 统一异常处理器
4. 创建 `src/interfaces/api/middleware/exception_context.py` - 异常上下文中间件
5. 创建 `src/infrastructure/messaging/error_mapper.py` - SDK 错误映射器
6. 创建 `src/infrastructure/logging/exception_logger.py` - 结构化日志格式化器

### 4.2 阶段二：全面迁移（8-10 人日）

#### 第一批：高优先级（API 层）

| 文件 | 异常数 | 描述 |
|------|--------|------|
| `src/domain/ports/audit_service.py` | 1 | AuditError → SystemException |
| `src/domain/ports/auth_service.py` | 1 | AuthenticationError → BusinessException |
| `src/infrastructure/security/permission_middleware.py` | 2 | PermissionDeniedError, InsufficientTokenError |

#### 第二批：中优先级（应用层）

| 文件 | 异常数 | 描述 |
|------|--------|------|
| `src/application/use_cases/role_management.py` | 4 | RoleAlreadyExistsError 等 |
| `src/application/ports/sandbox_port.py` | 4 | SandboxError 等 |
| `src/domain/services/memory_service.py` | 2 | MemoryVersionConflictError, MemoryNotFoundError |

#### 第三批：低优先级（基础设施层）

| 文件 | 异常数 | 描述 |
|------|--------|------|
| `src/infrastructure/storage/minio/client_adapter.py` | 4 | 使用 ErrorMapper 替代私有 _map_error |
| `src/infrastructure/messaging/outbox/outbox.py` | 1 | InvalidStateTransitionError → InvalidStateError |
| `src/infrastructure/messaging/event_store.py` | 1 | VersionError → SystemException |
| `src/domain/ports/password_validation_service.py` | 1 | PasswordValidationError → ValidationError |
| `src/domain/ports/storage.py` | 1 | ComplianceLockError → BusinessException |

### 4.3 阶段三：完善与优化（3-5 人日）

1. 实现结构化日志集成
2. 实现异常监控指标
3. 编写回归测试确保无破坏性变更
4. 统一 ErrorMapper 与现有 _map_error 方法

---

## 5. 文件变更清单（完整版）

### 新建文件

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/domain/exceptions/__init__.py` | 新建 | 异常根类与三层异常体系 |
| `src/domain/exceptions/legacy.py` | 新建 | 遗留异常别名兼容层（覆盖 25+ 异常） |
| `src/interfaces/api/exception_handlers.py` | 新建 | FastAPI 统一异常处理器 |
| `src/interfaces/api/middleware/exception_context.py` | 新建 | 异常上下文中间件 |
| `src/infrastructure/messaging/error_mapper.py` | 新建 | SDK 错误映射器 |
| `src/infrastructure/logging/exception_logger.py` | 新建 | 结构化日志格式化器 |

### 修改文件（按优先级）

#### P0 - API 层异常迁移

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/domain/ports/audit_service.py` | 修改 | AuditError → SystemException |
| `src/domain/ports/auth_service.py` | 修改 | AuthenticationError → BusinessException |
| `src/interfaces/api/auth.py` | 修改 | 移除 try/except，改用全局异常处理器 |
| `src/infrastructure/security/permission_middleware.py` | 修改 | PermissionDeniedError → 新体系 |

#### P1 - 应用层异常迁移

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/application/use_cases/role_management.py` | 修改 | 4个角色异常类 |
| `src/application/ports/sandbox_port.py` | 修改 | SandboxError 等 4 个 → ExternalException |
| `src/domain/services/memory_service.py` | 修改 | MemoryVersionConflictError → ConflictError |

#### P2 - 基础设施层异常迁移

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/infrastructure/storage/minio/client_adapter.py` | 修改 | 使用 ErrorMapper.map_s3_error |
| `src/infrastructure/messaging/outbox/outbox.py` | 修改 | InvalidStateTransitionError → InvalidStateError |
| `src/infrastructure/messaging/event_store.py` | 修改 | VersionError → SystemException |
| `src/domain/ports/password_validation_service.py` | 修改 | PasswordValidationError → ValidationError |
| `src/domain/ports/storage.py` | 修改 | ComplianceLockError → BusinessException |

---

## 6. 验收标准

| 标准 | 描述 |
|------|------|
| **集中管理** | 所有异常定义在 `src/domain/exceptions/` 下 |
| **层次清晰** | 三层异常体系（System/Business/External） |
| **错误码唯一** | 每个异常有唯一错误码 |
| **HTTP 映射** | API 层自动根据异常类型返回正确 HTTP 状态码 |
| **日志规范** | 异常日志包含错误码、上下文、追踪ID |
| **向后兼容** | 遗留异常引用保持正常工作 |
| **SDK 映射** | MinIO、RabbitMQ、Redis 错误统一映射 |
| **覆盖率** | 异常处理分支覆盖率 ≥90% |

---

## 7. 参考资料

- [Python Exception Hierarchy Best Practices](https://docs.python.org/3/library/exceptions.html)
- [Spring Exception Handling](https://spring.io/blog/2013/11/01/exception-handling-in-spring-mvc)
- [ADR-XXX: 统一异常处理决策记录](./adr-unified-exception-handling.md)
