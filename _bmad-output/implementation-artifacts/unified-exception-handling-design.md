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
    """SISYS 异常层次结构根类."""
    code: str = "SISYS_000"
    message: str = "Unknown error"
    http_status: int = 500

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
    http_status = 500


class ConfigurationError(SystemException):
    """配置错误."""
    code = "SISYS_101"
    message = "Configuration error"


class NetworkError(SystemException):
    """网络故障."""
    code = "SISYS_102"
    message = "Network error"
    http_status = 503


class StorageError(SystemException):
    """存储服务故障."""
    code = "SISYS_103"
    message = "Storage error"
    http_status = 503


class MessageBusError(SystemException):
    """消息总线故障."""
    code = "SISYS_104"
    message = "Message bus error"
    http_status = 503


# === 业务级异常（Business）===
class BusinessException(SisysBaseException):
    """业务级异常，业务规则违反."""
    code = "SISYS_2XX"
    http_status = 400


class ValidationError(BusinessException):
    """验证失败."""
    code = "SISYS_201"
    message = "Validation error"
    http_status = 400


class NotFoundError(BusinessException):
    """资源不存在."""
    code = "SISYS_202"
    message = "Resource not found"
    http_status = 404


class ConflictError(BusinessException):
    """资源冲突."""
    code = "SISYS_203"
    message = "Resource conflict"
    http_status = 409


class PermissionDeniedError(BusinessException):
    """权限不足."""
    code = "SISYS_204"
    message = "Permission denied"
    http_status = 403


class AuthenticationError(BusinessException):
    """认证失败."""
    code = "SISYS_205"
    message = "Authentication failed"
    http_status = 401


class InvalidStateError(BusinessException):
    """无效状态."""
    code = "SISYS_206"
    message = "Invalid state"
    http_status = 422


class BusinessRuleViolationError(BusinessException):
    """业务规则违反."""
    code = "SISYS_207"
    message = "Business rule violation"
    http_status = 422


# === 外部服务异常（External）===
class ExternalException(SisysBaseException):
    """外部服务异常."""
    code = "SISYS_3XX"
    http_status = 502


class ThirdPartyError(ExternalException):
    """第三方服务错误."""
    code = "SISYS_301"
    message = "Third party service error"


class TimeoutError(ExternalException):
    """外部服务超时."""
    code = "SISYS_302"
    message = "External service timeout"
    http_status = 504


class ServiceUnavailableError(ExternalException):
    """外部服务不可用."""
    code = "SISYS_303"
    message = "Service unavailable"
    http_status = 503
```

### 3.2 遗留异常兼容层

```python
# src/domain/exceptions/legacy.py
"""遗留异常别名，向后兼容."""
from src.domain.exceptions import (
    SisysBaseException,
    BusinessException,
    NotFoundError,
    PermissionDeniedError,
    AuthenticationError,
    ValidationError,
    InvalidStateError as DomainInvalidStateError,
)

# 保留原有导入路径
AuditError = BusinessException  # 审计错误归类为业务异常
PasswordValidationError = ValidationError  # 密码验证归类为验证异常
ComplianceLockError = BusinessRuleViolationError  # 合规锁定归类为业务规则异常

__all__ = [
    "SisysBaseException",
    "BusinessException",
    "NotFoundError",
    "PermissionDeniedError",
    "AuthenticationError",
    "ValidationError",
    "DomainInvalidStateError",
    "AuditError",
    "PasswordValidationError",
    "ComplianceLockError",
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

# 错误码到 HTTP 状态码映射表
EXCEPTION_HTTP_MAP: dict[type[SisysBaseException], int] = {
    SystemException: status.HTTP_500_INTERNAL_SERVER_ERROR,
    BusinessException: status.HTTP_400_BAD_REQUEST,
    ExternalException: status.HTTP_502_BAD_GATEWAY,
}


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
        request_id = request.state.__dict__.get("request_id", "unknown")

        content = {
            "error": exc.to_dict(),
            "request_id": request_id,
            "path": str(request.url),
        }

        return JSONResponse(
            status_code=exc.http_status,
            content=content,
            headers={"X-Error-Code": exc.code},
        )

    async def _handle_validation_error(
        self, request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """处理请求验证错误."""
        request_id = request.state.__dict__.get("request_id", "unknown")

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
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "SISYS_201",
                    "message": "Data validation error",
                    "context": {"errors": exc.errors()},
                },
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


def register_exception_handlers(app: FastAPI) -> ExceptionHandlers:
    """注册异常处理器到 FastAPI 应用."""
    return ExceptionHandlers(app)
```

### 3.4 外部 SDK 错误映射器

```python
# src/infrastructure/messaging/error_mapper.py

"""外部 SDK 错误到 SISYS 异常的标准化映射."""

import logging
from typing import TypeVar, Callable

from src.domain.exceptions import (
    ExternalException,
    ThirdPartyError,
    TimeoutError,
    ServiceUnavailableError,
    SystemException,
    StorageError,
    NetworkError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorMapper:
    """外部错误标准化映射器."""

    # MinIO S3Error 映射
    S3_ERROR_MAP: dict[str, type[ExternalException]] = {
        "NoSuchBucket": StorageError,
        "BucketAlreadyExists": ConflictError,
        "AccessDenied": PermissionDeniedError,
        "Forbidden": PermissionDeniedError,
        "NoSuchKey": NotFoundError,
        "RequestTimeout": TimeoutError,
        "ServiceUnavailable": ServiceUnavailableError,
    }

    # RabbitMQ 错误映射
    RABBITMQ_ERROR_MAP: dict[str, type[ExternalException]] = {
        "ConnectionError": NetworkError,
        "ChannelError": MessageBusError,
        "TimeoutError": TimeoutError,
    }

    # Redis 错误映射
    REDIS_ERROR_MAP: dict[str, type[SystemException]] = {
        "ConnectionError": NetworkError,
        "TimeoutError": TimeoutError,
        "ClusterDownError": ServiceUnavailableError,
    }

    @classmethod
    def map_s3_error(cls, code: str, message: str | None = None) -> ExternalException:
        """映射 MinIO S3 错误."""
        exc_class = cls.S3_ERROR_MAP.get(code, ThirdPartyError)
        return exc_class(message or f"S3 error: {code}")

    @classmethod
    def map_rabbitmq_error(cls, error_type: str, message: str | None = None) -> ExternalException:
        """映射 RabbitMQ 错误."""
        exc_class = cls.RABBITMQ_ERROR_MAP.get(error_type, MessageBusError)
        return exc_class(message or f"RabbitMQ error: {error_type}")

    @classmethod
    def map_redis_error(cls, error_type: str, message: str | None = None) -> SystemException:
        """映射 Redis 错误."""
        exc_class = cls.REDIS_ERROR_MAP.get(error_type, SystemException)
        return exc_class(message or f"Redis error: {error_type}")

    @classmethod
    def wrap_external_error(
        cls,
        error: Exception,
        target_exc_class: type[ExternalException],
        context: dict | None = None,
    ) -> ExternalException:
        """包装外部错误为 SISYS 异常."""
        logger.warning("Wrapping external error: %s -> %s", error, target_exc_class.__name__)
        return target_exc_class(
            message=str(error),
            cause=error,
            context=context,
        )


def with_error_mapping(
    error_map: dict[str, type[ExternalException]],
    default_exc: type[ExternalException] = ThirdPartyError,
) -> Callable:
    """装饰器：自动映射外部错误."""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_str = str(e)
                for key, exc_class in error_map.items():
                    if key.lower() in error_str.lower():
                        raise exc_class(message=str(e), cause=e) from e
                raise default_exc(message=str(e), cause=e) from e
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

### 4.1 阶段一：建立基础设施

1. 创建 `src/domain/exceptions/` 模块
2. 定义 `SisysBaseException` 及三层异常体系
3. 创建 `src/interfaces/api/exception_handlers.py`
4. 迁移 audit_service、auth_service 中的异常定义

### 4.2 阶段二：全面迁移

1. 迁移所有 domain/ports 中的异常
2. 迁移 application/use_cases 中的异常
3. 迁移 infrastructure 中的异常
4. 实现 ErrorMapper 标准化映射

### 4.3 阶段三：完善与优化

1. 实现结构化日志集成
2. 实现异常监控指标
3. 编写回归测试确保无破坏性变更

---

## 5. 文件变更清单

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/domain/exceptions/__init__.py` | 新建 | 异常根类与三层异常体系 |
| `src/domain/exceptions/legacy.py` | 新建 | 遗留异常别名兼容层 |
| `src/interfaces/api/exception_handlers.py` | 新建 | FastAPI 统一异常处理器 |
| `src/interfaces/api/middleware/exception_context.py` | 新建 | 异常上下文中间件 |
| `src/infrastructure/messaging/error_mapper.py` | 新建 | SDK 错误映射器 |
| `src/infrastructure/logging/exception_logger.py` | 新建 | 结构化日志格式化器 |
| `src/domain/ports/audit_service.py` | 修改 | 异常引用切换到新体系 |
| `src/domain/ports/auth_service.py` | 修改 | 异常引用切换到新体系 |
| `src/application/use_cases/role_management.py` | 修改 | 异常定义迁移 |
| `src/infrastructure/storage/minio/client_adapter.py` | 修改 | 使用 ErrorMapper |

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
