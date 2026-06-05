# 统一异常处理设计方案

**状态：** 已实现
**创建日期：** 2026-05-10
**最后修订日期：** 2026-06-04
**作者：** Agimtech
**评审状态：** 已评审

---

## 1. 现状分析

### 1.1 迁移前问题（已解决）

| 问题 | 描述 | 影响 |
|------|------|------|
| **散落定义** | 异常类散布在 domain/ports、application/use_cases、infrastructure/storage 等15+个文件中 | 难以维护、重复定义 |
| **无层次结构** | 所有异常继承自 Exception，缺少分类体系 | 无法按类型统一处理 |
| **重复定义** | `PermissionDeniedError`、`ComplianceLockError` 在多处重复定义 | 混淆与不一致 |
| **映射缺失** | 基础设施层 SDK 错误（如 S3Error）无统一映射机制 | 错误信息不友好 |
| **无追踪机制** | 异常不含错误码、上下文、追踪ID | 排查困难 |
| **日志不规范** | catch-and-log 模式各异，错误级别不统一 | 日志分析困难 |
| **API 转换重复** | 每个 API 端点重复编写 try/except HTTP 转换 | 代码冗余 |

### 1.2 迁移后残留问题（已解决）

| 问题 | 描述 | 影响范围 | 状态 |
|------|------|----------|------|
| **双重处理模式** | `auth.py` 等 5 个接口文件仍手动 `raise HTTPException`，绕过统一 `ExceptionHandlers` | 丢失错误码/上下文/结构化日志 | ✅ 已修复（仅 OAuth2 WWW-Authenticate 合法保留） |
| **重复 ErrorResponse 模型** | 5 个文件各自定义 `ErrorResponse(BaseModel)`，未合并到共享模块 | API 响应格式不一致 | ✅ 已合并到 `shared_models.py` |
| **越界异常** | `TransferNotFoundError`、`TransferNotApprovedError` 继承 Python 内置 `Exception` 而非领域 `BaseException` | 绕过集中处理器，仅被兜底捕获返回 500 | ✅ 已迁移到 `transfer_exceptions.py` |
| **错误码碰撞** | EXCEPTION_301 被 6 个类共享，EXCEPTION_302/303 各被 2 个类共享 | 违反唯一编码原则，监控告警无法精确定位 | ✅ 已全部分配独立编码 |
| **指标集成缺口** | `ExceptionMetricsPort` 已定义但未集成到 `ExceptionHandlers`；composition_root 注册路径错误 | 异常指标采集不可用 | ✅ 已集成并修复注册路径 |
| **ValueError 语义模糊** | 全系统 186 处 `raise ValueError` 与领域异常体系并存，语义模糊、错误码丢失 | 监控告警粗粒度、调用方无法精确处理 | ✅ 已全量迁移为领域异常（详见 `sisys-value-error-refactor.md`） |

### 1.3 异常分布

#### 迁移后集中管理结构

```
src/domain/exceptions/              # 统一管理（12 个模块）
├── __init__.py                     # 统一导出（42 个符号）
├── base_exceptions.py              # BaseException 根类
├── system_exceptions.py            # SystemException + 4 个具体类
├── business_exceptions.py          # BusinessException + 8 个具体类
├── external_exceptions.py          # ExternalException + 4 个具体类
├── service_exceptions.py           # AuditError, PasswordValidationError, ComplianceLockError
│                                   # + 5 个安全服务异常（层次违规，见 §3.7）
│                                   # 注：后 5 个类仅通过模块直接导入可用，未包含在包级 __init__.py 重导出中
├── storage_exceptions.py           # 6 个存储相关异常
├── role_exceptions.py              # 4 个角色管理异常
├── sandbox_exceptions.py           # 4 个沙箱异常
├── embedding_exceptions.py         # 3 个嵌入服务异常（306-308）
├── permission_exceptions.py        # InsufficientTokenError
└── event_exceptions.py             # VersionError
```

#### 残留散落位置（已清理）

```
# 已纳入领域异常体系（Phase 4 + ValueError 迁移完成）：
# - TransferNotFoundError/TransferNotApprovedError → src/domain/exceptions/transfer_exceptions.py
# - permission_middleware.py → 仅 OAuth2 WWW-Authenticate 合法保留（4 处）
# - ValueError → 领域异常全量迁移（186 处，116 文件变更）
#   详见 sisys-value-error-refactor.md
```

### 1.4 违反的架构原则

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
│   └── StorageError
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
6. **二级编码**：领域+原因双层分类（参考 Google `domain+reason`、Stripe `type+code`），已应用于嵌入服务异常（306-308）

---

## 3. 设计方案

### 3.1 异常层次结构

```python
# src/domain/exceptions/base_exceptions.py

class BaseException(Exception):  # noqa: N818
    """异常层次结构根类.

    此基类定义在领域层（src/domain/exceptions/），仅使用 Python 标准库。
    HTTP 状态码等 Web 层关注点不在此定义，由接口层异常处理器负责映射。
    """

    code: str = "EXCEPTION_000"
    message: str = "Unknown error"
    cause: Exception | None = None
    context: dict = {}

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.cause = cause
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为字典格式，便于序列化和日志记录."""
        result = {
            "code": self.code,
            "message": self.message,
            "context": self.context,
        }
        if self.cause:
            # 领域异常 cause 递归序列化，保留完整错误链
            if isinstance(self.cause, BaseException):
                result["cause"] = self.cause.to_dict()
            else:
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
```

#### 完整异常层次图

```
BaseException (EXCEPTION_000) — 抽象根，领域层
├── SystemException (EXCEPTION_1XX) — 系统级/基础设施故障
│   ├── ConfigurationError (101)
│   ├── NetworkError (102)
│   │   └── [storage] MinIOConnectionError (102)
│   ├── StorageError (103)
│   ├── MessageBusError (104)
│   └── [service] AuditError (105)
│       └── [service] IntrusionDetectionError (301) ⚠️ 编码违规
│       └── [service] DataIntegrityError (302) ⚠️ 编码违规
│       └── [service] BackupError (303) ⚠️ 编码违规
│       └── [service] EncryptionError (304) ⚠️ 编码违规
│       └── [service] ContainerSecurityError (305) ⚠️ 编码违规
├── BusinessException (EXCEPTION_2XX) — 业务规则违反
│   ├── ValidationError (201)
│   │   └── [service] PasswordValidationError (201)
│   │   └── [storage] BucketNameValidationError (201)
│   │   └── [entity] EntityValidationError (242) ← 实体不变量验证
│   ├── NotFoundError (202)
│   │   └── [storage] MemoryNotFoundError (202)
│   │   └── [storage] BucketNotFoundError (202)
│   │   └── [role] RoleNotFoundError (202)
│   ├── ConflictError (203)
│   │   └── [storage] MemoryVersionConflictError (203)
│   │   └── [role] RoleAlreadyExistsError (203)
│   │   └── [role] CannotDeleteRoleWithUsersError (203)
│   │   └── [event] VersionError (203)
│   ├── PermissionDeniedError (204)
│   │   └── [storage] MemoryAccessDeniedError (204)
│   │   └── [permission] InsufficientTokenError (204)
│   ├── AuthenticationError (205)
│   ├── InvalidStateError (206)
│   │   └── [service] ComplianceLockError (206)
│   │   └── InvalidStateTransitionError (208)
│   │       └── [entity] EntityStateTransitionError (243) ← 实体状态转换守卫
│   └── BusinessRuleViolationError (207)
│       └── [role] CannotDeleteSystemRoleError (207)
│       └── [entity] EntityBusinessRuleError (244) ← 实体跨字段业务约束
└── ExternalException (EXCEPTION_3XX) — 外部服务错误
    ├── ThirdPartyError (301)
    │   └── [embedding] EmbeddingAPIError (306)
    │   └── [embedding] EmbeddingResponseError (307)
    ├── [embedding] EmbeddingModelError (308) — 直接继承 ExternalException
    ├── TimeoutError (302)
    ├── ServiceUnavailableError (303)
    ├── [sandbox] SandboxError (301) ⚠️ 编码碰撞
    │   ├── ContainerStartError (301)
    │   ├── ExecutionError (301)
    │   └── ContainerStopError (301)
    └── UnknownError (999)
```

> **⚠️ 错误码碰撞与层次违规（已知问题）**
>
> 以下编码违反了"每类异常唯一编码"原则，需在后续迭代中解决：
>
> | 编码 | 碰撞类 | 根因 |
> |------|--------|------|
> | EXCEPTION_301 | ThirdPartyError, SandboxError, ContainerStartError, ExecutionError, ContainerStopError, IntrusionDetectionError | 沙箱异常复用父类编码；IntrusionDetectionError 层次违规 |
> | EXCEPTION_302 | TimeoutError, DataIntegrityError | DataIntegrityError 层次违规 |
> | EXCEPTION_303 | ServiceUnavailableError, BackupError | BackupError 层次违规 |
> | EXCEPTION_304 | EncryptionError | 层次违规：继承 SystemException 但使用 3XX 编码 |
> | EXCEPTION_305 | ContainerSecurityError | 层次违规：继承 SystemException 但使用 3XX 编码 |
>
> **推荐修复方案**：
> 1. 沙箱异常分配独立编码 309-312
> 2. 安全服务异常（IntrusionDetectionError~ContainerSecurityError）重新编码为 106-110，匹配其 SystemException 父类所属的 1XX 范围

### 3.2 实际实现：模块化异常结构

`legacy.py` 已废弃，异常按职责拆分为独立模块：

```
src/domain/exceptions/
├── __init__.py              # 统一导出（42 个符号）
├── base_exceptions.py       # BaseException, SystemException, BusinessException, ExternalException
├── system_exceptions.py     # ConfigurationError, NetworkError, StorageError, MessageBusError
├── business_exceptions.py   # ValidationError, NotFoundError, ConflictError, PermissionDeniedError, ...
│                            # + EntityValidationError(242), EntityStateTransitionError(243), EntityBusinessRuleError(244)
├── external_exceptions.py   # ThirdPartyError, TimeoutError, ServiceUnavailableError, UnknownError
├── service_exceptions.py    # AuditError(105), PasswordValidationError(201), ComplianceLockError(206)
│                            # + IntrusionDetectionError(301)⚠️, DataIntegrityError(302)⚠️,
│                            #   BackupError(303)⚠️, EncryptionError(304)⚠️, ContainerSecurityError(305)⚠️
│                            # 注：后 5 个类需通过模块直接导入（from .service_exceptions import ...）
├── storage_exceptions.py    # MemoryVersionConflictError, MemoryNotFoundError, BucketNotFoundError, ...
├── role_exceptions.py       # RoleAlreadyExistsError, RoleNotFoundError, ...
├── sandbox_exceptions.py    # SandboxError, ContainerStartError, ExecutionError, ContainerStopError
├── embedding_exceptions.py  # EmbeddingAPIError(306), EmbeddingResponseError(307), EmbeddingModelError(308)
├── permission_exceptions.py # InsufficientTokenError
└── event_exceptions.py      # VersionError
```

统一导出（`from src.domain.exceptions import *`，共 42 个符号）：
- 抽象根类：`BaseException`
- 系统级：`SystemException`, `ConfigurationError`, `NetworkError`, `StorageError`, `MessageBusError`
- 业务级：`BusinessException`, `ValidationError`, `NotFoundError`, `ConflictError`, `PermissionDeniedError`, `AuthenticationError`, `InvalidStateError`, `InvalidStateTransitionError`, `BusinessRuleViolationError`, `EntityValidationError`, `EntityStateTransitionError`, `EntityBusinessRuleError`
- 外部服务：`ExternalException`, `ThirdPartyError`, `TimeoutError`, `ServiceUnavailableError`, `UnknownError`
- 服务异常：`AuditError`, `PasswordValidationError`, `ComplianceLockError`
- 存储异常：`MemoryVersionConflictError`, `MemoryNotFoundError`, `BucketNotFoundError`, `MinIOConnectionError`, `BucketNameValidationError`, `MemoryAccessDeniedError`
- 角色异常：`RoleAlreadyExistsError`, `RoleNotFoundError`, `CannotDeleteSystemRoleError`, `CannotDeleteRoleWithUsersError`
- Sandbox异常：`SandboxError`, `ContainerStartError`, `ExecutionError`, `ContainerStopError`
- 嵌入服务异常：`EmbeddingAPIError`, `EmbeddingResponseError`, `EmbeddingModelError`
- 权限异常：`InsufficientTokenError`
- 事件异常：`VersionError`

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
# 未显式映射的异常通过 MRO 回退到基类默认值：
#   - EmbeddingAPIError/EmbeddingResponseError → ThirdPartyError → 502
#   - EmbeddingModelError → ExternalException → 502
#   - IntrusionDetectionError~ContainerSecurityError → SystemException → 500
#   - InsufficientTokenError → PermissionDeniedError → 403
#   - VersionError → ConflictError → 409
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
    # MRO 匹配回退
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

        注意：BaseException（领域根类）须在 Exception 之前注册。
        Starlette 对更具体的异常类型优先匹配：当领域异常抛出时
        BaseException handler 先于 Exception handler 命中。
        """
        self._app.add_exception_handler(RequestValidationError, self._handle_validation_error)
        self._app.add_exception_handler(PydanticValidationError, self._handle_pydantic_error)
        self._app.add_exception_handler(BaseException, self._handle_exception)
        self._app.add_exception_handler(Exception, self._handle_unexpected_error)

    async def _handle_exception(
        self, request: Request, exc: Exception
    ) -> JSONResponse:
        """处理领域基类异常，自动映射到 HTTP 状态码.

        Starlette add_exception_handler 要求 handler 参数类型为 Exception 或其父类，
        因此参数使用 Exception，内部通过 isinstance 分流到领域 BaseException。
        """
        if not isinstance(exc, BaseException):
            return await self._handle_unexpected_error(request, exc)
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
            # to_dict() 失败时的降级处理
            error_dict = {
                "code": getattr(exc, 'code', None) or "EXCEPTION_999",
                "message": str(exc)[:500],
                "context": getattr(exc, 'context', None) or {},
            }
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
        self, request: Request, exc: Exception
    ) -> JSONResponse:
        """处理请求验证错误."""
        if not isinstance(exc, RequestValidationError):
            raise TypeError(f"Expected RequestValidationError, got {type(exc).__name__}")
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
        self, request: Request, exc: Exception
    ) -> JSONResponse:
        """处理 Pydantic 验证错误."""
        if not isinstance(exc, PydanticValidationError):
            raise TypeError(f"Expected PydanticValidationError, got {type(exc).__name__}")
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
    ExceptionHandlers(app)
```

#### 3.3.1 双重处理模式（已知偏差）

尽管集中式 `ExceptionHandlers` 已注册，以下接口文件仍手动捕获领域异常并 re-raise 为 `HTTPException`：

| 文件 | 手动 HTTPException 数 | 模式 |
|------|----------------------|------|
| `src/interfaces/api/auth.py` | ~17 处 | 捕获 AuthenticationError、RoleAlreadyExistsError 等后 raise HTTPException |
| `src/interfaces/api/document_upload.py` | ~12 处 | 上传状态验证、文件检查直接 HTTPException |
| `src/interfaces/api/crawler.py` | ~4 处 | 服务通信错误直接 HTTPException |
| `src/interfaces/api/audit.py` | ~5 处 | 审计操作错误直接 HTTPException |
| `src/interfaces/api/equilibrium_security.py` | ~1 处 | 认证检查直接 HTTPException |
| `src/infrastructure/security/permission_middleware.py` | ~11 处 | 所有认证/权限失败使用 raw HTTPException |

**影响**：
- 错误码（`code`）丢失 — API 响应无法携带 `EXCEPTION_XXX` 编码
- 上下文（`context`）丢失 — 无法传递 request_id、操作详情等调试信息
- 结构化日志跳过 — `ExceptionHandlers` 的日志流程不触发
- 响应格式不一致 — 手动 HTTPException 使用 `{"detail": "..."}` 而非标准 `{"error": {...}, "request_id": "..."}` 格式

**修复建议**：见 §3.8 决策指南。`auth.py` 中的 OAuth2 Bearer token 提取属于可接受的例外（需要 `WWW-Authenticate` header），其余均应迁移到集中处理器。

#### 3.3.2 完整编码分配表

| 编码 | 类名 | 继承 | HTTP |
|------|------|------|------|
| EXCEPTION_000 | BaseException | Exception | 500 |
| EXCEPTION_1XX | SystemException | BaseException | 500 |
| EXCEPTION_101 | ConfigurationError | SystemException | 500 |
| EXCEPTION_102 | NetworkError | SystemException | 500 |
| EXCEPTION_103 | StorageError | SystemException | 500 |
| EXCEPTION_104 | MessageBusError | SystemException | 500 |
| EXCEPTION_105 | AuditError | SystemException | 500 |
| EXCEPTION_106 | MinIOConnectionError | NetworkError | 500 |
| EXCEPTION_2XX | BusinessException | BaseException | 400 |
| EXCEPTION_201 | ValidationError | BusinessException | 400 |
| EXCEPTION_202 | NotFoundError | BusinessException | 404 |
| EXCEPTION_203 | ConflictError | BusinessException | 409 |
| EXCEPTION_204 | PermissionDeniedError | BusinessException | 403 |
| EXCEPTION_205 | AuthenticationError | BusinessException | 401 |
| EXCEPTION_206 | InvalidStateError | BusinessException | 409 |
| EXCEPTION_207 | BusinessRuleViolationError | BusinessException | 422 |
| EXCEPTION_208 | InvalidStateTransitionError | InvalidStateError | 409 |
| EXCEPTION_211 | MemoryNotFoundError | NotFoundError | 404 |
| EXCEPTION_212 | BucketNotFoundError | NotFoundError | 404 |
| EXCEPTION_213 | MemoryVersionConflictError | ConflictError | 409 |
| EXCEPTION_214 | BucketNameValidationError | ValidationError | 400 |
| EXCEPTION_215 | MemoryAccessDeniedError | PermissionDeniedError | 403 |
| EXCEPTION_221 | RoleNotFoundError | NotFoundError | 404 |
| EXCEPTION_222 | RoleAlreadyExistsError | ConflictError | 409 |
| EXCEPTION_223 | CannotDeleteRoleWithUsersError | ConflictError | 409 |
| EXCEPTION_224 | CannotDeleteSystemRoleError | BusinessRuleViolationError | 422 |
| EXCEPTION_231 | PasswordValidationError | ValidationError | 400 |
| EXCEPTION_232 | ComplianceLockError | InvalidStateError | 409 |
| EXCEPTION_241 | InsufficientTokenError | PermissionDeniedError | 403 |
| EXCEPTION_251 | VersionError | ConflictError | 409 |
| EXCEPTION_261 | TransferNotFoundError | NotFoundError | 404 |
| EXCEPTION_262 | TransferNotApprovedError | InvalidStateError | 409 |
| EXCEPTION_3XX | ExternalException | BaseException | 502 |
| EXCEPTION_301 | ThirdPartyError | ExternalException | 502 |
| EXCEPTION_302 | TimeoutError | ExternalException | 504 |
| EXCEPTION_303 | ServiceUnavailableError | ExternalException | 503 |
| EXCEPTION_306 | EmbeddingAPIError | ThirdPartyError | 502 |
| EXCEPTION_307 | EmbeddingResponseError | ThirdPartyError | 502 |
| EXCEPTION_308 | EmbeddingModelError | ExternalException | 502 |
| EXCEPTION_309 | SandboxError | ExternalException | 502 |
| EXCEPTION_310 | ContainerStartError | SandboxError | 502 |
| EXCEPTION_311 | ExecutionError | SandboxError | 502 |
| EXCEPTION_312 | ContainerStopError | SandboxError | 502 |
| EXCEPTION_999 | UnknownError | ExternalException | 500 |

### 3.4 外部 SDK 错误映射器

```python
# src/infrastructure/messaging/error_mapper.py

"""外部 SDK 错误到异常的标准化映射.

优先使用类型匹配（isinstance）和错误码属性直接映射。
对于 MinIO S3Error，使用 error.code 属性直接映射（见 map_s3_error）。
装饰器方案仅用于无法使用类型匹配的场景。
"""

import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from src.domain.exceptions import (
    ConflictError,
    InvalidStateError,
    MessageBusError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    SystemException,
    ThirdPartyError,
    TimeoutError,
    ValidationError,
)
from src.domain.exceptions.base_exceptions import BaseException

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
    S3_ERROR_MAP: dict[str, type[BaseException]] = {
        "nosuchbucket": NotFoundError,
        "nosuchkey": NotFoundError,
        "nosuchlifecycleconfiguration": NotFoundError,
        "bucketalreadyexists": ConflictError,
        "bucketalreadyownedbyyou": ConflictError,
        "accessdenied": PermissionDeniedError,
        "forbidden": PermissionDeniedError,
        "invalidobjectstate": InvalidStateError,
        "objectlockconfigurationnotfound": InvalidStateError,
        "requesttimeout": TimeoutError,
        "serviceunavailable": ServiceUnavailableError,
        "internalerror": ThirdPartyError,
        "nosuchupload": NotFoundError,
        "nosuchversion": NotFoundError,
        "entitytoolarge": ValidationError,
        "methodnotallowed": ThirdPartyError,
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
        exc_class = cls.S3_ERROR_MAP.get(code.lower(), ThirdPartyError)
        if exc_class is ThirdPartyError:
            logger.warning("Unknown S3 error code: %s, defaulting to ThirdPartyError", code)
        return exc_class(message=message or f"S3 error: {code}")

    @classmethod
    def map_rabbitmq_error(cls, error_type: str, message: str | None = None) -> BaseException:
        """映射 RabbitMQ 错误为领域异常."""
        exc_class = cls.RABBITMQ_ERROR_MAP.get(error_type, MessageBusError)
        return exc_class(message=message or f"RabbitMQ error: {error_type}")

    @classmethod
    def map_redis_error(cls, error_type: str, message: str | None = None) -> BaseException:
        """映射 Redis 错误为领域异常."""
        exc_class = cls.REDIS_ERROR_MAP.get(error_type, SystemException)
        return exc_class(message=message or f"Redis error: {error_type}")

    @classmethod
    def wrap_external_error(
        cls,
        error: Exception,
        target_exc_class: type[BaseException],
        context: dict | None = None,
    ) -> BaseException:
        """包装外部错误为领域异常.

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
            cause=error if isinstance(error, BaseException) else None,
            context={**(context or {}), "original_error_type": type(error).__name__},
        )


def with_error_mapping(
    error_map: dict[str, type[BaseException]],
    default_exc: type[BaseException] = ThirdPartyError,
    *,
    exact_match: bool = False,
) -> Callable:
    """装饰器：自动映射外部错误（仅用于无法使用类型匹配的场景）.

    注意：这是兜底方案。优先使用 ErrorMapper.map_* 方法直接映射。

    参数：
        exact_match: 为 True 时使用精确匹配（==），避免子串误匹配。
                   为 False（默认）时使用子串匹配（in），用于包含错误消息的场景。
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_str = str(e)
                for key, exc_class in error_map.items():
                    if exact_match:
                        if key.lower() == error_str.lower():
                            raise exc_class(
                                message=str(e),
                                cause=e if isinstance(e, BaseException) else None,
                                context={"original_error_type": type(e).__name__},
                            ) from e
                    else:
                        if key.lower() in error_str.lower():
                            raise exc_class(
                                message=str(e),
                                cause=e if isinstance(e, BaseException) else None,
                                context={"original_error_type": type(e).__name__},
                            ) from e
                raise default_exc(
                    message=str(e),
                    cause=e if isinstance(e, BaseException) else None,
                    context={"original_error_type": type(e).__name__},
                ) from e
        return wrapper
    return decorator
```

### 3.5 结构化日志集成

```python
# src/infrastructure/logging/exception_logger.py

"""异常结构化日志处理器.

所有日志输出均为 JSON 格式，包含异常时附带结构化错误信息。
使用 duck-typing（getattr）检测异常属性，兼容领域异常和非领域异常。
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any


class ExceptionJsonFormatter(logging.Formatter):
    """异常结构化日志格式化器."""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录.

        包含异常信息时输出结构化错误 JSON，否则输出标准日志 JSON。
        """
        if record.exc_info and record.exc_info[0]:
            exc = record.exc_info[1]
            if exc is not None:
                return self._format_exception(record, exc)
        return self._format_standard(record)

    def _format_exception(self, record: logging.LogRecord, exc: Any) -> str:
        """格式化异常日志，使用 duck-typing 提取异常属性."""
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "error": {
                "code": getattr(exc, "code", None) or "EXCEPTION_000",
                "message": getattr(exc, "message", None) or str(exc),
                "context": getattr(exc, "context", None) or {},
            },
        }
        cause = getattr(exc, "cause", None)
        if cause:
            log_entry["error"]["cause"] = {
                "type": type(cause).__name__,
                "message": str(cause),
            }
        return json.dumps(log_entry)

    def _format_standard(self, record: logging.LogRecord) -> str:
        """格式化标准日志为 JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_entry)


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

### 3.7 错误码分配注册表

| 范围 | 分支 | 已分配编码 | 状态 |
|------|------|-----------|------|
| 000 | BaseException | 000（根类默认） | 正常 |
| 1XX | SystemException | 101 ConfigurationError, 102 NetworkError/MinIOConnectionError, 103 StorageError, 104 MessageBusError, 105 AuditError | 正常 |
| 2XX | BusinessException | 201 ValidationError/PasswordValidationError/BucketNameValidationError/EntityValidationError, 202 NotFoundError/MemoryNotFoundError/BucketNotFoundError/RoleNotFoundError, 203 ConflictError/MemoryVersionConflictError/RoleAlreadyExistsError/CannotDeleteRoleWithUsersError/VersionError, 204 PermissionDeniedError/MemoryAccessDeniedError/InsufficientTokenError, 205 AuthenticationError, 206 InvalidStateError/ComplianceLockError, 207 BusinessRuleViolationError/CannotDeleteSystemRoleError/EntityBusinessRuleError, 208 InvalidStateTransitionError/EntityStateTransitionError | 正常（同编码类语义一致；242-244 为实体专用子类） |
| 3XX | ExternalException | 301 ThirdPartyError/EmbeddingAPIError/EmbeddingResponseError/SandboxError/ContainerStartError/ExecutionError/ContainerStopError ⚠️碰撞, 302 TimeoutError/DataIntegrityError ⚠️碰撞, 303 ServiceUnavailableError/BackupError ⚠️碰撞, 304 EncryptionError ⚠️违规, 305 ContainerSecurityError ⚠️违规, 306 EmbeddingAPIError, 307 EmbeddingResponseError, 308 EmbeddingModelError | 存在碰撞和层次违规 |
| 999 | UnknownError | 兜底 | 正常 |

**碰撞解决计划**（待实施）：

1. **沙箱异常**（SandboxError 301, ContainerStartError 301, ExecutionError 301, ContainerStopError 301）→ 分配独立编码 309-312
2. **安全服务异常**（IntrusionDetectionError 301, DataIntegrityError 302, BackupError 303, EncryptionError 304, ContainerSecurityError 305）→ 重新编码为 106-110（匹配 SystemException 的 1XX 范围），或重分类至 ExternalException（如语义为外部安全服务调用失败）

### 3.8 异常处理决策指南

#### 推荐使用集中处理器（默认）

所有新端点应让领域异常自然上浮到 `ExceptionHandlers`，由其自动完成 HTTP 映射、响应格式化和结构化日志记录。

适用场景：
- 领域异常从应用层传播到 API 边界
- 需要错误码（`code`）、上下文（`context`）、追踪ID（`request_id`）
- 需要结构化日志自动记录

#### 可接受手动 HTTPException 的场景

| 场景 | 原因 | 示例 |
|------|------|------|
| OAuth2 Bearer token 提取 | FastAPI 安全机制依赖 HTTPException 的 `WWW-Authenticate` header | `get_current_user_dependency` 中无 token 或 token 无效 |
| 请求级输入前验证 | 在进入领域逻辑之前快速拒绝 | 参数格式校验、必填字段检查 |
| 外部 API 契约约束 | 特定外部系统要求非标准响应格式 | 第三方回调、Webhook 确认 |

#### 不允许手动 HTTPException 的场景

- **捕获领域异常后 re-raise**：如 `except NotFoundError: raise HTTPException(404, ...)` — 丢失 `code`、`context`、`cause` 链
- **业务逻辑错误使用 HTTPException**：如 `HTTPException(403)` 代替 `PermissionDeniedError`
- **权限中间件使用 raw HTTPException**：如 `permission_middleware.py` 中 11 处直接 `raise HTTPException`

#### 标准错误响应 Schema

所有 API 错误响应应使用以下格式（由 `ExceptionHandlers` 统一生成）：

```json
{
    "error": {
        "code": "EXCEPTION_XXX",
        "message": "Human-readable message",
        "context": {}
    },
    "request_id": "uuid"
}
```

响应头：`X-Error-Code: EXCEPTION_XXX`、`X-Request-ID: uuid`

当前 5 个文件中的重复 `ErrorResponse(BaseModel)` 定义应合并到 `src/interfaces/api/schemas.py` 共享模块。

### 3.9 异常指标集成

#### 端口定义（应用层）

```python
# src/application/ports/exception_metrics_port.py

class ExceptionMetricsPort(Protocol):
    """异常指标采集端口定义.

    应用层定义此端口，基础设施层实现。
    接口层通过此接口记录异常指标。
    """

    def record_exception(self, exception_type: str, code: str | None = None) -> None: ...
```

#### 实现（基础设施层）

```python
# src/infrastructure/logging/exception_metrics_impl.py

@dataclass
class ExceptionMetricsImpl(ExceptionMetricsPort):
    """异常指标收集器（线程安全），支持 Prometheus 格式导出."""
    _counters: dict[str, int] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def record_exception(self, exception_type: str, code: str | None = None) -> None:
        key = f"{exception_type}:{code}" if code else exception_type
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + 1

    def collect(self) -> bytes: ...       # Prometheus 文本格式
    def collect_as_dict(self) -> dict: ... # 字典格式
    def reset(self) -> None: ...          # 测试用
```

全局单例通过 `get_exception_metrics()` 获取。

`ExceptionHandlers` 通过 `ExceptionMetricsPort` 在 `_handle_exception()` 和 `_handle_unexpected_error()` 中调用 `record_exception(type(exc).__name__, exc.code)` 完成指标采集。

### 3.10 事件处理器错误模式

系统使用死信队列（DLQ）处理事件消费失败：

- **端口定义**：`src/domain/ports/dead_letter_queue.py` — `DeadLetterQueue` Protocol（`enqueue`、`dequeue`）
- **内存实现**：`src/infrastructure/messaging/inmemory_dead_letter_queue.py` — 开发/测试用
- **持久化实现**：`src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py` — 生产用

错误处理流程：

```
事件消费 → 捕获异常 → 增量 retry_count
    ├── retry_count < max_retries → 重新入队（指数退避+抖动）
    └── retry_count ≥ max_retries → 入 DLQ（记录失败原因）

重试策略（src/infrastructure/messaging/retry/retry_policy.py）：
    base_delay=1.0s, max_delay=60.0s, max_retries=3
    delay = min(base * 2^attempt * jitter, max_delay)
```

事件处理器中的异常应使用领域异常，确保 DLQ 元数据包含完整错误码和上下文信息。

### 3.11 领域实体验证异常

系统中 **186 处 `raise ValueError`** 已全量迁移为领域异常。新增三类实体专用异常：

#### 推荐模式

| 场景 | 推荐异常 | 编码 | HTTP | 适用位置 |
|------|---------|------|------|---------|
| 实体不变量验证（UUID/非空/枚举/数值范围） | `EntityValidationError` | EXCEPTION_242 | 400 | `validate()` / `__post_init__()` |
| 实体状态转换守卫（状态机方法） | `EntityStateTransitionError` | EXCEPTION_243 | 409 | `start()` / `complete()` / `fail()` / `recover()` 等 |
| 实体跨字段业务约束 | `EntityBusinessRuleError` | EXCEPTION_244 | 422 | `validate()` 中的跨字段约束 |
| 配置参数验证 | `ConfigurationError` | EXCEPTION_101 | 500 | `*.from_env()` / `validate()` |
| 应用层输入校验 | `ValidationError` | EXCEPTION_201 | 400 | 用例/服务输入验证 |

#### 迁移原则

- **禁止 `raise ValueError`**：所有验证失败使用领域异常
- **消息文本不变**：迁移仅改变异常类型和上下文，错误消息保持向后兼容
- **分批实施**：每个批次独立 PR，每批全量测试验证无回归

### 3.12 异常注册检查清单

> **适用范围：** 本清单针对「领域异常」—— 即定义在 `src/domain/exceptions/` 下、继承自 `DomainError`（别名 `BaseException`）的异常类。这类异常由 `ExceptionHandlers` 自动映射为 HTTP 响应，携带错误码（`EXCEPTION_NNN`）、上下文（`context`）和追踪 ID（`request_id`）。

#### 异常分类与处理策略（SISYS 全量）

| 类别 | 定义位置 | 根类型 | 处理方式 | 需遵循本清单？ |
|------|---------|--------|---------|:---:|
| **领域异常** | `src/domain/exceptions/` | `DomainError` | `ExceptionHandlers` 自动映射 HTTP + 记录指标 | ✅ 是 |
| **Python 内置异常** | 全系统禁止主动 `raise ValueError` | `Exception` | 不应出现（如出现则落入 `_handle_unexpected_error` → 500） | 🔴 禁止新增 |
| **FastAPI 异常** | `interfaces/api/` | `RequestValidationError` | `_handle_validation_error` → 400 | ❌ 否（框架原生） |
| **Pydantic 异常** | `interfaces/api/` | `PydanticValidationError` | `_handle_pydantic_error` → 422 | ❌ 否（框架原生） |
| **第三方 SDK 异常** | 外部库（`S3Error` 等） | 各 SDK 定义 | `ErrorMapper.map_*()` 映射为领域异常 | 🟡 仅映射规则 |
| **基础设施内部异常** | `infrastructure/` | `RuntimeError` 等 | 由调用方捕获后转为领域异常或记录日志 | 🟡 转为领域异常时是 |

> **关键决策规则：** 任何需要向 API 消费者传达的**业务/系统/外部错误**，必须定义为领域异常（遵循本清单）。仅在以下场景使用其他异常：
> - **OAuth2 Bearer token 提取**：必须用 `HTTPException(401, headers={"WWW-Authenticate": "Bearer"})`（FastAPI 安全机制要求）
> - **第三方 SDK 调用**：原始异常由 `ErrorMapper` 包装为领域异常后重新抛出
> - **禁止 `raise ValueError`**：所有验证失败使用领域异常（详见 [`sisys-value-error-refactor.md`](sisys-value-error-refactor.md)）

---

新增领域异常类时必须按三阶段依次完成。每阶段包含强制项（🔴）和建议项（🟡）。

---

#### 阶段 A：设计阶段（Task 0 — 规范先行）

> **原则**：异常是领域契约的一部分，须在 SDD 规范定义阶段完成设计，禁止在实现 Task 中临时拼凑。

| # | 强制 | 检查项 | 说明 |
|---|------|--------|------|
| A1 | 🔴 | **确定归属模块** | 按职责归入 `src/domain/exceptions/` 下适当模块（`system`/`business`/`external`/`storage`/`role`/`service`/`sandbox`/`embedding`/`permission`/`event`/`transfer`）．若现有模块均不匹配，评估是否新建模块 |
| A2 | 🔴 | **选择正确基类** | `SystemException`（1XX）用于基础设施故障；`BusinessException`（2XX）用于业务规则违反；`ExternalException`（3XX）用于外部服务错误．禁止直接继承 Python 内置 `Exception` |
| A3 | 🔴 | **分配唯一编码** | 从对应范围选取：系统 101-199、业务 201-299、外部 301-399．运行 `grep -r "EXCEPTION_NNN" src/domain/exceptions/` 验证无碰撞 |
| A4 | 🔴 | **设计构造器参数** | 携带领域上下文（如 `transfer_id`、`role_id`、`user_count`），避免仅含字符串消息．参数通过 `context` 字典暴露给 API 响应和结构化日志 |
| A5 | 🔴 | **设计错误消息** | 面向调用方（API 消费者/运维），包含资源标识但不泄露内部实现细节（如 SQL 语句、堆栈路径） |
| A6 | 🟡 | **评估二级编码** | 同一领域内多种失败模式时使用二级编码（参考 Google `domain+reason`、嵌入服务 306-308 模式），如 `EmbeddingAPIError(306)` / `EmbeddingResponseError(307)` |

#### 阶段 B：实现阶段（编码 Task）

| # | 强制 | 检查项 | 说明 |
|---|------|--------|------|
| B1 | 🔴 | **模块级导出** | 在所在模块的 `__all__` 列表中注册类名 |
| B2 | 🔴 | **包级重导出** | 在 `src/domain/exceptions/__init__.py` 中：添加 `from` 导入 → 加入 `__all__` → 按注释分组正确归类 |
| B3 | 🔴 | **Google 风格 docstring** | 包含 `Attributes:` 段（code/message/自定义属性），中文注释 |
| B4 | 🔴 | **EXCEPTION_HTTP_MAP 映射** | 在 `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP` 中添加条目，即使 MRO 回退可正确映射也应显式声明（优化精确匹配性能 + 文档清晰） |
| B5 | 🟡 | **ErrorMapper 映射** | 如异常包装外部 SDK 错误（MinIO/RabbitMQ/Redis），在 `src/infrastructure/messaging/error_mapper.py` 的相应 `*_ERROR_MAP` 字典中添加条目 |
| B6 | 🟡 | **事件通道配置** | 如异常触发死信队列（DLQ）重试/入队，在 `config/event_channels.yaml` 中配置对应通道 |
| B7 | 🔴 | **禁止抑制注释** | 不得在异常定义中添加 `# noqa`、`# type: ignore`、`# pylint: disable` 等抑制注释．如 Ruff/MyPy 报错，必须通过代码修改解决根因 |

#### 阶段 C：验证阶段（质量门禁）

| # | 强制 | 检查项 | 说明 |
|---|------|--------|------|
| C1 | 🔴 | **编码唯一性测试** | 运行 `pytest tests/unit/domain/exceptions/test_error_code_uniqueness.py -v`，确认新增编码未被任何已有类使用 |
| C2 | 🔴 | **构造与 to_dict() 测试** | 在 `tests/unit/domain/exceptions/` 添加或更新测试：默认消息、自定义消息、`to_dict()` 输出结构、`cause` 链正确性 |
| C3 | 🔴 | **HTTP 映射测试** | 在 `tests/unit/interfaces/api/test_exception_handlers.py` 中：验证 `EXCEPTION_HTTP_MAP` 包含新异常类型、`_get_http_status` 返回正确状态码、HTTP 集成测试返回正确 JSON 结构 |
| C4 | 🔴 | **更新设计文档** | 更新本文档 §3.7 错误码注册表（编码/类名/继承/HTTP），更新层次图（§3.1）如新增模块 |
| C5 | 🔴 | **更新 story-template.md** | 如新增异常模块或编码范围，同步更新故事模板中的领域异常清单（确保后续 Story 的 Task 0 规范定义包含新模块） |
| C6 | 🟡 | **BDD 验收场景** | 在 Story 的 Gherkin feature 文件中添加异常路径场景（如 `Scenario: 资源不存在返回 404`），确保异常传播的端到端行为被验收 |
| C7 | 🟡 | **指标告警阈值** | 如新异常代表关键故障模式，在 `src/infrastructure/logging/exception_metrics_impl.py` 中评估是否需要添加告警规则 |

---

#### 快速自检脚本

```bash
# 阶段 A: 编码碰撞检查
grep -r "EXCEPTION_XXX" src/domain/exceptions/  # 替换 XXX 为目标编码

# 阶段 B: 导出完整性检查
python -c "from src.domain.exceptions import NewErrorName; print('✅ 导入成功')"

# 阶段 C: 测试验证
poetry run pytest tests/unit/domain/exceptions/test_error_code_uniqueness.py -v
poetry run pytest tests/unit/interfaces/api/test_exception_handlers.py -v -k "NewErrorName"
poetry run ruff check src/domain/exceptions/ src/interfaces/api/exception_handlers.py
```

---

## 4. 实施阶段

### 4.1 阶段一：基础设施

建立异常根类、三层体系、模块化文件、统一处理器、SDK 映射器、结构化日志。

### 4.2 阶段二：API/应用/基础设施层迁移

- 领域端口异常归类至新体系
- 应用层用例异常迁移
- 基础设施 SDK 错误统一映射

### 4.3 阶段三：完善与优化

结构化日志集成、异常监控指标实现、回归测试。

### 4.4 阶段四：残留清理与 ValueError 全量迁移（已完成）

- 错误码碰撞解决、共享 ErrorResponse 模型
- 手动 HTTPException → 领域异常（OAuth2 合法保留）
- ValueError → 领域异常全量迁移（186 处，116 文件变更，详见 [`sisys-value-error-refactor.md`](sisys-value-error-refactor.md)）
- 移除 `_handle_value_error` 兜底处理器

---

## 5. 文件变更清单（完整版）

### 新建文件

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/domain/exceptions/__init__.py` | 新建 | 异常根类与三层异常体系（统一导出，127 行，42 符号） |
| `src/domain/exceptions/base_exceptions.py` | 新建 | BaseException, SystemException, BusinessException, ExternalException |
| `src/domain/exceptions/system_exceptions.py` | 新建 | ConfigurationError, NetworkError, StorageError, MessageBusError |
| `src/domain/exceptions/business_exceptions.py` | 新建 | ValidationError, NotFoundError, ConflictError, PermissionDeniedError, ... |
| `src/domain/exceptions/external_exceptions.py` | 新建 | ThirdPartyError, TimeoutError, ServiceUnavailableError, UnknownError |
| `src/domain/exceptions/service_exceptions.py` | 新建 | AuditError, PasswordValidationError, ComplianceLockError, IntrusionDetectionError, DataIntegrityError, BackupError, EncryptionError, ContainerSecurityError |
| `src/domain/exceptions/storage_exceptions.py` | 新建 | Memory*, Bucket*, MinIO* 等存储相关异常 |
| `src/domain/exceptions/role_exceptions.py` | 新建 | Role* 等角色管理异常 |
| `src/domain/exceptions/sandbox_exceptions.py` | 新建 | SandboxError, ContainerStartError, ExecutionError, ContainerStopError |
| `src/domain/exceptions/embedding_exceptions.py` | 新建 | EmbeddingAPIError(306), EmbeddingResponseError(307), EmbeddingModelError(308) |
| `src/domain/exceptions/permission_exceptions.py` | 新建 | InsufficientTokenError |
| `src/domain/exceptions/event_exceptions.py` | 新建 | VersionError |
| `src/interfaces/api/exception_handlers.py` | 新建 | FastAPI 统一异常处理器 |
| `src/interfaces/api/middleware/exception_context.py` | 新建 | 异常上下文中间件 |
| `src/infrastructure/messaging/error_mapper.py` | 新建 | SDK 错误映射器 |
| `src/infrastructure/logging/exception_logger.py` | 新建 | 结构化日志格式化器 |
| `src/infrastructure/logging/exception_metrics_impl.py` | 新建 | ExceptionMetricsPort 实现，Prometheus 格式导出 |
| `src/application/ports/exception_metrics_port.py` | 新建 | 异常指标采集端口定义（应用层 Protocol） |

### 删除文件

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/domain/exceptions/legacy.py` | 删除 | 已拆分为 12 个模块化文件 |

### 修改文件（按优先级）

#### P0 - API 层异常迁移

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/domain/ports/audit_service.py` | 修改 | AuditError → SystemException |
| `src/domain/ports/auth_service.py` | 修改 | AuthenticationError → BusinessException |
| `src/interfaces/api/auth.py` | 修改 | 移除 try/except，改用全局异常处理器（OAuth2 部分保留） |
| `src/infrastructure/security/permission_middleware.py` | 修改 | PermissionDeniedError → 新体系 |

#### P1 - 应用层异常迁移

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/application/use_cases/role_management.py` | 修改 | 4个角色异常类 |
| `src/domain/ports/sandbox_executor.py` | 修改 | SandboxError 等 4 个 → ExternalException |
| `src/domain/services/memory_service.py` | 修改 | MemoryVersionConflictError → ConflictError |

#### P2 - 基础设施层异常迁移

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/infrastructure/storage/minio/minio_manager.py` | 修改 | 使用 ErrorMapper.map_s3_error |
| `src/infrastructure/messaging/outbox/outbox.py` | 修改 | InvalidStateTransitionError → InvalidStateError |
| `src/infrastructure/messaging/event_store.py` | 修改 | VersionError → ConflictError |
| `src/domain/ports/password_validation_service.py` | 修改 | PasswordValidationError → ValidationError |
| `src/domain/ports/storage.py` | 修改 | ComplianceLockError → BusinessException |

#### P3 - 残留清理（已完成）

| 文件 | 操作 | 描述 |
|------|------|------|
| `src/infrastructure/security/permission_middleware.py` | 修改 | 替换 raw HTTPException 为领域异常 |
| `src/infrastructure/security/cross_border_transfer_service_impl.py` | 修改 | 迁移 TransferNotFoundError/TransferNotApprovedError 到领域层次 |
| `src/interfaces/api/auth.py` | 修改 | 移除非 OAuth2 场景的手动异常捕获 |
| `src/interfaces/api/crawler.py` | 修改 | 移除手动 HTTPException |
| `src/interfaces/api/audit.py` | 修改 | 移除手动 HTTPException |
| `src/interfaces/api/document_upload.py` | 修改 | 移除手动 HTTPException |
| `src/interfaces/api/equilibrium_security.py` | 修改 | 移除手动 HTTPException |
| `src/interfaces/api/schemas.py` | 新建 | 共享 ErrorResponse 模型（替代 5 处重复定义） |
| `src/composition_root.py` | 修改 | 修复 exception_metrics 注册路径 |
| `src/interfaces/api/exception_handlers.py` | 修改 | 集成 ExceptionMetricsPort、移除 ValueError 兜底处理器 |
| `src/domain/exceptions/service_exceptions.py` | 修改 | 解决 5 个类的层次违规/编码碰撞 |

---

## 6. 验收标准

| 标准 | 描述 | 当前状态 |
|------|------|----------|
| **集中管理** | 所有异常定义在 `src/domain/exceptions/` 下 | ✅ 已达标 |
| **层次清晰** | 三层异常体系（System/Business/External） | ✅ 已达标 |
| **错误码唯一** | 每个异常有唯一错误码，无碰撞 | ✅ 已达标（48 个编码全部唯一） |
| **HTTP 映射** | API 层自动根据异常类型返回正确 HTTP 状态码 | ✅ 已达标 |
| **日志规范** | 异常日志包含错误码、上下文、追踪ID | ✅ 已达标 |
| **向后兼容** | 遗留异常引用保持正常工作 | ✅ 已达标 |
| **SDK 映射** | MinIO、RabbitMQ、Redis 错误统一映射 | ✅ 已达标 |
| **覆盖率** | 异常处理分支覆盖率 ≥90% | ✅ 已达标 |
| **指标集成** | ExceptionHandlers 调用 record_exception() 记录异常指标 | ✅ 已达标 |
| **接口层一致性** | 所有 API 端点使用统一异常处理器，无手动 HTTPException（OAuth2 除外） | ✅ 已达标（仅 8 处 OAuth2 合法保留） |
| **共享响应模型** | 错误响应模型统一到 `src/interfaces/api/shared_models.py` | ✅ 已达标 |
| **无越界异常** | 所有异常继承自领域根类，无直接继承 Python 内置 Exception 的情况 | ✅ 已达标 |
| **ValueError 清零** | 全系统零 `raise ValueError`，所有验证使用领域异常（186 处全量迁移） | ✅ 已达标 |

---

## 7. 参考资料

- [Python Exception Hierarchy Best Practices](https://docs.python.org/3/library/exceptions.html)
- [Spring Exception Handling](https://spring.io/blog/2013/11/01/exception-handling-in-spring-mvc)
- [Embedding Service Exception Design](../../src/domain/exceptions/embedding_exceptions.py)（源码级文档，含二级编码设计说明）
- [Dead Letter Queue Protocol](../../src/domain/ports/dead_letter_queue.py)
- [ADR-XXX: 统一异常处理决策记录](./adr-unified-exception-handling.md) *(待创建)*
