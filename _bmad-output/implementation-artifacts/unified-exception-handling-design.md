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

class SisysBaseException(Exception):
    """SISYS 异常层次结构根类.

    注意：此基类定义在领域层（src/domain/exceptions/），仅使用Python标准库。
    HTTP状态码等Web层关注点不在此定义，由接口层异常处理器负责映射。
    """
    code: str = "SISYS_000"
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
        return {
            "code": self.code,
            "message": self.message,
            "context": self.context,
        }


# === 系统级异常（System）===
class SystemException(SisysBaseException):
    """系统级异常，基础设施故障."""
    code = "SISYS_1XX"


class ConfigurationError(SystemException):
    """配置错误."""
    code = "SISYS_101"
    message = "Configuration error"


class NetworkError(SystemException):
    """网络故障."""
    code = "SISYS_102"
    message = "Network error"


class StorageError(SystemException):
    """存储服务故障."""
    code = "SISYS_103"
    message = "Storage error"


class MessageBusError(SystemException):
    """消息总线故障."""
    code = "SISYS_104"
    message = "Message bus error"


# === 业务级异常（Business）===
class BusinessException(SisysBaseException):
    """业务级异常，业务规则违反."""
    code = "SISYS_2XX"


class ValidationError(BusinessException):
    """验证失败."""
    code = "SISYS_201"
    message = "Validation error"


class NotFoundError(BusinessException):
    """资源不存在."""
    code = "SISYS_202"
    message = "Resource not found"


class ConflictError(BusinessException):
    """资源冲突（版本冲突、状态冲突等）."""
    code = "SISYS_203"
    message = "Resource conflict"


class PermissionDeniedError(BusinessException):
    """权限不足."""
    code = "SISYS_204"
    message = "Permission denied"


class AuthenticationError(BusinessException):
    """认证失败."""
    code = "SISYS_205"
    message = "Authentication failed"


class InvalidStateError(BusinessException):
    """无效状态."""
    code = "SISYS_206"
    message = "Invalid state"


class BusinessRuleViolationError(BusinessException):
    """业务规则违反."""
    code = "SISYS_207"
    message = "Business rule violation"


# === 外部服务异常（External）===
class ExternalException(SisysBaseException):
    """外部服务异常."""
    code = "SISYS_3XX"


class ThirdPartyError(ExternalException):
    """第三方服务错误."""
    code = "SISYS_301"
    message = "Third party service error"


class TimeoutError(ExternalException):
    """外部服务超时."""
    code = "SISYS_302"
    message = "External service timeout"


class ServiceUnavailableError(ExternalException):
    """外部服务不可用."""
    code = "SISYS_303"
    message = "Service unavailable"


# === 抽象中间类（禁止直接实例化）===
class SystemExceptionMeta(type):
    """确保 SystemException 子类定义了具体错误码."""
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        # 中间类（SystemException本身）不需要具体码
        if bases and name != "SystemException":
            if not hasattr(cls, 'code') or cls.code == "SISYS_1XX":
                if name not in ('SystemException', 'BusinessException', 'ExternalException'):
                    raise TypeError(f"{name} must define a concrete code like 'SISYS_1XX'")
        return cls
```

### 3.2 遗留异常兼容层

```python
# src/domain/exceptions/legacy.py
"""遗留异常别名，向后兼容.

覆盖所有现有异常类，确保迁移过程无破坏性变更。
"""
from src.domain.exceptions import (
    SisysBaseException,
    SystemException,
    BusinessException,
    NotFoundError,
    PermissionDeniedError,
    AuthenticationError,
    ValidationError,
    ConflictError,
    InvalidStateError as DomainInvalidStateError,
    ExternalException,
    NetworkError,
    TimeoutError,
    ServiceUnavailableError,
    ThirdPartyError,
)

# === 领域层异常 ===

# 审计错误是系统级基础设施问题（非业务规则违反）
AuditError = SystemException

PasswordValidationError = ValidationError
ComplianceLockError = BusinessException  # 合规锁定是业务规则违反

# 领域服务异常
MemoryVersionConflictError = ConflictError  # 版本冲突是冲突类
MemoryNotFoundError = NotFoundError

# === 应用层异常 ===

RoleAlreadyExistsError = ConflictError
RoleNotFoundError = NotFoundError
CannotDeleteSystemRoleError = BusinessRuleViolationError
CannotDeleteRoleWithUsersError = ConflictError

# 沙箱异常
SandboxError = ExternalException
ContainerStartError = ExternalException
ExecutionError = ExternalException
ContainerStopError = ExternalException

# === 基础设施层异常 ===

InvalidStateTransitionError = DomainInvalidStateError  # 合并到已有状态异常
VersionError = SystemException

# MinIO 异常
BucketNotFoundError = NotFoundError
MinIOConnectionError = NetworkError

# 权限异常
InsufficientTokenError = AuthenticationError

# ComplianceLockError 归类为业务规则违反
ComplianceLockError = BusinessRuleViolationError

# InvalidStateTransitionError 保留原始接口，继承自 InvalidStateError
InvalidStateTransitionError = InvalidStateError  # 接口兼容：from_status, to_status

# VersionError 是乐观锁冲突，不是系统错误
VersionError = ConflictError

__all__ = [
    # 基类和三层异常
    "SisysBaseException",
    "SystemException",
    "BusinessException",
    "ExternalException",
    # 具体异常
    "NotFoundError",
    "PermissionDeniedError",
    "AuthenticationError",
    "ValidationError",
    "ConflictError",
    "DomainInvalidStateError",
    "BusinessException",
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
    "InvalidStateTransitionError",
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
    SisysBaseException,
    SystemException,
    BusinessException,
    ExternalException,
)

# 异常类型 → HTTP 状态码映射表（唯一真相源）
EXCEPTION_HTTP_MAP: dict[type[SisysBaseException], int] = {
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
    TimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
    ServiceUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _get_http_status(exc: SisysBaseException) -> int:
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
        """注册全局异常处理器."""
        self._app.add_exception_handler(SisysBaseException, self._handle_sisys_exception)
        self._app.add_exception_handler(RequestValidationError, self._handle_validation_error)
        self._app.add_exception_handler(PydanticValidationError, self._handle_pydantic_error)
        self._app.add_exception_handler(Exception, self._handle_unexpected_error)

    async def _handle_sisys_exception(
        self, request: Request, exc: SisysBaseException
    ) -> JSONResponse:
        """处理 SISYS 异常."""
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
                            "code": getattr(exc, 'code', "SISYS_205"),
                            "message": "Account is locked",
                            "context": context,
                        },
                        "request_id": request_id,
                    },
                    headers={"X-Error-Code": str(getattr(exc, 'code', "SISYS_205") or "SISYS_205")},
                )

        try:
            error_dict = exc.to_dict()
        except Exception:
            # to_dict() 失败时的降级处理
            error_dict = {
                "code": str(getattr(exc, 'code', "SISYS_999") or "SISYS_999"),
                "message": str(exc)[:500],
                "context": {},
            }

        content = {
            "error": error_dict,
            "request_id": request_id,
        }

        return JSONResponse(
            status_code=_get_http_status(exc),
            content=content,
            headers={"X-Error-Code": str(getattr(exc, 'code', "SISYS_999") or "SISYS_999")},
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
                    "code": "SISYS_201",
                    "message": "Validation error",
                    "context": {"validation_errors": errors},
                },
                "request_id": request_id,
            },
            headers={"X-Error-Code": "SISYS_201"},
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
                    "code": "SISYS_201",
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
                    "code": "SISYS_999",
                    "message": "Internal server error",
                },
            },
            headers={"X-Error-Code": "SISYS_999"},
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

"""外部 SDK 错误到 SISYS 异常的标准化映射.

注意：优先使用类型匹配（isinstance）而非字符串匹配。
对于 MinIO S3Error，应使用 error.code 属性直接映射（见 map_s3_error）。
装饰器方案仅用于无法使用类型匹配的场景。
"""

import logging
from functools import wraps
from typing import Callable, TypeVar

from src.domain.exceptions import (
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
    MessageBusError,
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
    S3_ERROR_MAP: dict[str, type[SisysBaseException]] = {
        "NoSuchBucket": NotFoundError,
        "NoSuchKey": NotFoundError,
        "BucketAlreadyExists": ConflictError,
        "BucketAlreadyOwnedByYou": ConflictError,
        "AccessDenied": PermissionDeniedError,
        "Forbidden": PermissionDeniedError,
        "InvalidObjectState": SystemException,
        "ObjectLockConfigurationNotFoundError": SystemException,
        "RequestTimeout": TimeoutError,
        "ServiceUnavailable": ServiceUnavailableError,
        "InternalError": SystemException,
        "NoSuchUpload": NotFoundError,
        "EntityTooLarge": ValidationError,
        "MethodNotAllowed": BusinessException,
        "SlowDown": ServiceUnavailableError,
    }

    # RabbitMQ 错误映射
    RABBITMQ_ERROR_MAP: dict[str, type[SisysBaseException]] = {
        "ConnectionError": NetworkError,
        "ChannelError": MessageBusError,
        "TimeoutError": TimeoutError,
    }

    # Redis 错误映射
    REDIS_ERROR_MAP: dict[str, type[SisysBaseException]] = {
        "ConnectionError": NetworkError,
        "TimeoutError": TimeoutError,
        "ClusterDownError": ServiceUnavailableError,
    }

    @classmethod
    def map_s3_error(cls, code: str, message: str | None = None) -> ExternalException:
        """映射 MinIO S3 错误.

        Args:
            code: S3Error.code 属性值（如 "NoSuchBucket"）
            message: 原始错误消息

        Returns:
            对应的 SISYS 异常实例
        """
        exc_class = cls.S3_ERROR_MAP.get(code, ThirdPartyError)
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
        """包装外部错误为 SISYS 异常.

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
) -> Callable:
    """装饰器：自动映射外部错误（仅用于无法使用类型匹配的场景）.

    注意：这是兜底方案。优先使用 ErrorMapper.map_* 方法直接映射。
    装饰器使用字符串子匹配，可能有误匹配风险。

    推荐用法：
        class MyAdapter:
            @with_error_mapping({"ConnectionError": NetworkError})
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

from src.domain.exceptions import SisysBaseException


class ExceptionJsonFormatter(logging.Formatter):
    """异常结构化日志格式化器."""

    def format(self, record: logging.LogRecord) -> str:
        if record.exc_info and record.exc_info[0]:
            exc = record.exc_info[1]
            if isinstance(exc, SisysBaseException):
                return self._format_sisys_exception(record, exc)
        return self._format_standard(record)

    def _format_sisys_exception(
        self, record: logging.LogRecord, exc: SisysBaseException
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
            log_entry["error"]["cause"] = str(exc.cause)
            log_entry["error"]["cause_type"] = type(exc.cause).__name__
        return json.dumps(log_entry)

    def _format_standard(self, record: logging.LogRecord) -> str:
        return super().format(record)


def configure_exception_logging() -> None:
    """配置异常日志处理器."""
    handler = logging.StreamHandler()
    handler.setFormatter(ExceptionJsonFormatter())

    logger = logging.getLogger("sisys")
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
