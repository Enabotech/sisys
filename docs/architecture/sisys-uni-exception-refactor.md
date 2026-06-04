# 统一异常处理重构详细设计

**状态：** 待实施
**创建日期：** 2026-06-04
**作者：** Agimtech
**前置文档：** [统一异常处理设计方案（第二轮评审修订）](./sisys-uni-exception-design.md)
**设计规则：** R1（领域层统一抽象）/ R2（端口组合继承）/ R3（基础设施实现）/ R4（接口层适配）

---

## 1. 重构目标与范围

### 1.1 重构目标

| # | 目标 | 现状 | 预期 |
|---|------|------|------|
| G1 | 错误码全局唯一 | EXCEPTION_301 被 6 类共享，201/202/203/204/206 各被多类共享 | 每个异常类拥有唯一编码 |
| G2 | 指标集成可用 | composition_root 路径错误、ExceptionHandlers 未调用 record_exception、app.py 未注册处理器/中间件 | 异常指标从请求链路自动采集 |
| G3 | 接口层异常统一 | 6 个文件共 51 处手动 `raise HTTPException`（仅 12 处 OAuth2 合法） | 除 OAuth2 外零 HTTPException |
| G4 | 无越界异常 | TransferNotFoundError/TransferNotApprovedError 继承 Python 内置 Exception | 所有异常纳入领域层次 |
| G5 | 消除重复代码 | 5 处重复 ErrorResponse 模型、4 处重复 get_current_user 依赖 | 共享模块统一管理 |

### 1.2 不在本次范围

- **ValueError→领域异常迁移**（~50 处跨 9 个实体文件）：影响面过大，独立迭代处理。本次仅添加 ValueError 兜底处理器作为临时方案。
- **性能优化**：异常处理路径不涉及性能敏感场景。

### 1.3 执行顺序与依赖

```
Phase 1（基础）         Phase 2（接线）          Phase 3（迁移）
  代码去重/死代码清理     指标/中间件/共享模型     接口层 HTTPException 消除
       │                      │                        │
       └──────────┬───────────┘                        │
                  │                                    │
                  └──────────── Phase 4（领域清理）─────┘
                                    │
                              Phase 5（验证）
```

- Phase 1 和 Phase 2 可并行开发（无共享文件）
- Phase 3 依赖 Phase 1（新编码）+ Phase 2（处理器已接线）
- Phase 4 可独立推进
- Phase 5 在所有 Phase 完成后执行

---

## 2. Phase 1：错误码去重与死代码清理

### 2.1 删除 5 个死代码类

- [ ] 从 `src/domain/exceptions/service_exceptions.py` 删除以下 5 个类（L66-124）
- [ ] 更新同文件 `__all__` 列表，移除 5 个类名

**删除清单**（全局搜索确认零引用）：

| 类名 | 当前编码 | 继承 | 引用数 |
|------|---------|------|--------|
| `IntrusionDetectionError` | EXCEPTION_301 | SystemException | 0 |
| `DataIntegrityError` | EXCEPTION_302 | SystemException | 0 |
| `BackupError` | EXCEPTION_303 | SystemException | 0 |
| `EncryptionError` | EXCEPTION_304 | SystemException | 0 |
| `ContainerSecurityError` | EXCEPTION_305 | SystemException | 0 |

```python
# src/domain/exceptions/service_exceptions.py — 删除后 __all__
__all__ = [
    "AuditError",
    "PasswordValidationError",
    "ComplianceLockError",
]
```

### 2.2 沙箱异常重编码

- [ ] 修改 `src/domain/exceptions/sandbox_exceptions.py` 4 个编码

| 类名 | 旧编码 | 新编码 |
|------|--------|--------|
| `SandboxError` | EXCEPTION_301 | EXCEPTION_309 |
| `ContainerStartError` | EXCEPTION_301 | EXCEPTION_310 |
| `ExecutionError` | EXCEPTION_301 | EXCEPTION_311 |
| `ContainerStopError` | EXCEPTION_301 | EXCEPTION_312 |

```python
# src/domain/exceptions/sandbox_exceptions.py — 修改后
class SandboxError(ExternalException):
    """沙箱执行基础异常"""
    code = "EXCEPTION_309"
    message = "Sandbox error"


class ContainerStartError(SandboxError):
    """容器启动失败"""
    code = "EXCEPTION_310"
    message = "Container start error"


class ExecutionError(SandboxError):
    """代码执行失败"""
    code = "EXCEPTION_311"
    message = "Execution error"


class ContainerStopError(SandboxError):
    """容器停止失败"""
    code = "EXCEPTION_312"
    message = "Container stop error"
```

**影响范围**：`src/domain/ports/sandbox_executor.py`（Raises 声明）、`src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py`（raise 调用）—— 仅日志/监控可见，不影响 HTTP 映射（MRO 回退到 ExternalException→502）。

### 2.3 存储异常重编码

- [ ] 修改 `src/domain/exceptions/storage_exceptions.py` 6 个编码

| 类名 | 旧编码 | 新编码 |
|------|--------|--------|
| `MemoryNotFoundError` | EXCEPTION_202 | EXCEPTION_211 |
| `BucketNotFoundError` | EXCEPTION_202 | EXCEPTION_212 |
| `MemoryVersionConflictError` | EXCEPTION_203 | EXCEPTION_213 |
| `BucketNameValidationError` | EXCEPTION_201 | EXCEPTION_214 |
| `MemoryAccessDeniedError` | EXCEPTION_204 | EXCEPTION_215 |
| `MinIOConnectionError` | EXCEPTION_102 | EXCEPTION_106 |

### 2.4 角色异常重编码

- [ ] 修改 `src/domain/exceptions/role_exceptions.py` 3 个编码

| 类名 | 旧编码 | 新编码 |
|------|--------|--------|
| `RoleNotFoundError` | EXCEPTION_202 | EXCEPTION_221 |
| `RoleAlreadyExistsError` | EXCEPTION_203 | EXCEPTION_222 |
| `CannotDeleteRoleWithUsersError` | EXCEPTION_203 | EXCEPTION_223 |

> `CannotDeleteSystemRoleError`（EXCEPTION_207）仅与 `BusinessRuleViolationError` 共享父类编码，语义一致（业务规则违反），保持不变。

### 2.5 服务异常重编码

- [ ] 修改 `src/domain/exceptions/service_exceptions.py` 2 个编码

| 类名 | 旧编码 | 新编码 |
|------|--------|--------|
| `PasswordValidationError` | EXCEPTION_201 | EXCEPTION_231 |
| `ComplianceLockError` | EXCEPTION_206 | EXCEPTION_232 |

### 2.6 权限/事件异常重编码

- [ ] 修改 `src/domain/exceptions/permission_exceptions.py`：`InsufficientTokenError` 204→241
- [ ] 修改 `src/domain/exceptions/event_exceptions.py`：`VersionError` 203→251

### 2.7 更新 EXCEPTION_HTTP_MAP

- [ ] 在 `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP` 中添加以下条目

```python
# 添加到 EXCEPTION_HTTP_MAP
SandboxError: status.HTTP_502_BAD_GATEWAY,              # 309
ContainerStartError: status.HTTP_502_BAD_GATEWAY,        # 310
ExecutionError: status.HTTP_502_BAD_GATEWAY,             # 311
ContainerStopError: status.HTTP_502_BAD_GATEWAY,         # 312
MemoryNotFoundError: status.HTTP_404_NOT_FOUND,          # 211
BucketNotFoundError: status.HTTP_404_NOT_FOUND,          # 212
MemoryVersionConflictError: status.HTTP_409_CONFLICT,    # 213
BucketNameValidationError: status.HTTP_400_BAD_REQUEST,  # 214
MemoryAccessDeniedError: status.HTTP_403_FORBIDDEN,      # 215
MinIOConnectionError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 106
RoleNotFoundError: status.HTTP_404_NOT_FOUND,            # 221
RoleAlreadyExistsError: status.HTTP_409_CONFLICT,        # 222
CannotDeleteRoleWithUsersError: status.HTTP_409_CONFLICT, # 223
PasswordValidationError: status.HTTP_400_BAD_REQUEST,    # 231
ComplianceLockError: status.HTTP_409_CONFLICT,           # 232
InsufficientTokenError: status.HTTP_403_FORBIDDEN,       # 241
VersionError: status.HTTP_409_CONFLICT,                  # 251
```

> **注意**：即使不添加这些条目，MRO 回退也能正确映射（如 MemoryNotFoundError→NotFoundError→404）。显式添加是为了提升映射查找性能（精确匹配优先于 MRO 遍历）和文档清晰度。

### 2.8 编写错误码唯一性测试

- [ ] 创建 `tests/unit/domain/exceptions/test_error_code_uniqueness.py`

```python
"""验证所有领域异常编码全局唯一"""

import src.domain.exceptions as exc_module


def test_all_error_codes_unique():
    """收集所有异常类的 code 属性，验证无重复"""
    classes = []
    for name in exc_module.__all__:
        cls = getattr(exc_module, name)
        if isinstance(cls, type) and issubclass(cls, Exception):
            classes.append(cls)
    codes = [cls.code for cls in classes if hasattr(cls, "code")]
    duplicates = [c for c in set(codes) if codes.count(c) > 1]
    assert not duplicates, f"重复编码: {duplicates}"


def test_all_codes_match_pattern():
    """验证所有编码符合 EXCEPTION_NNN 格式"""
    for name in exc_module.__all__:
        cls = getattr(exc_module, name)
        if isinstance(cls, type) and issubclass(cls, Exception):
            code = getattr(cls, "code", None)
            if code and not code.startswith("EXCEPTION_"):
                pass  # 占位类（如 EXCEPTION_1XX）跳过
            elif code:
                import re
                assert re.match(r"^EXCEPTION_\d{3}$", code), f"{name}: 编码格式错误 {code}"
```

### 2.9 Phase 1 完整编码分配表（重构后）

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
| EXCEPTION_231 | PasswordValidationError | ValidationError | 400 |
| EXCEPTION_232 | ComplianceLockError | InvalidStateError | 409 |
| EXCEPTION_241 | InsufficientTokenError | PermissionDeniedError | 403 |
| EXCEPTION_251 | VersionError | ConflictError | 409 |
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

---

## 3. Phase 2：基础设施接线

### 3.1 创建 ExceptionMetricsAdapter

- [ ] 新建 `src/infrastructure/monitoring/exception_metrics_adapter.py`

```python
"""基础设施层异常指标适配器模块

适配 ExceptionMetricsImpl 为 ExceptionMetricsPort，注册于 composition_root。
遵循 R3（基础设施层实现应用层端口），委托给同层 ExceptionMetricsImpl。
"""

from __future__ import annotations

from src.application.ports.exception_metrics_port import ExceptionMetricsPort
from src.infrastructure.logging.exception_metrics_impl import ExceptionMetricsImpl


class ExceptionMetricsAdapter(ExceptionMetricsPort):
    """异常指标适配器，委托给 ExceptionMetricsImpl

    Attributes:
        _impl: 实际的异常指标收集器实例
    """

    def __init__(self) -> None:
        """初始化适配器"""
        self._impl = ExceptionMetricsImpl()

    def record_exception(self, exception_type: str, code: str | None = None) -> None:
        """记录异常发生

        Args:
            exception_type: 异常类型名称
            code: 可选的错误码
        """
        self._impl.record_exception(exception_type, code)
```

### 3.2 修复 composition_root 注册路径

- [ ] 修改 `src/composition_root.py` L794 的 impl 路径

```python
# 修改前（路径不存在）：
register_port(
    name="exception_metrics",
    impl="src.infrastructure.monitoring.exception_metrics_adapter.ExceptionMetricsAdapter",
    module="src.infrastructure.monitoring.exception_metrics_adapter",
    ...
)

# 修改后（指向实际适配器）：
register_port(
    name="exception_metrics",
    impl="src.infrastructure.monitoring.exception_metrics_adapter.ExceptionMetricsAdapter",
    module="src.infrastructure.monitoring.exception_metrics_adapter",
    ...
)
# 注：impl 字符串不变，但此文件现在存在了（Task 3.1 创建）
```

### 3.3 ExceptionHandlers 集成 ExceptionMetricsPort

- [ ] 修改 `src/interfaces/api/exception_handlers.py`：添加 `_record()` 方法，`__init__` 接受可选 metrics 参数

```python
# 修改 ExceptionHandlers 类
from src.application.ports.exception_metrics_port import ExceptionMetricsPort


class ExceptionHandlers:
    """统一异常处理器注册"""

    def __init__(
        self,
        app: FastAPI,
        metrics: ExceptionMetricsPort | None = None,
    ) -> None:
        """初始化异常处理器

        Args:
            app: FastAPI 应用实例
            metrics: 可选的异常指标采集端口
        """
        self._app = app
        self._metrics = metrics
        self._register_handlers()

    def _record(self, exc: Exception) -> None:
        """记录异常指标

        Args:
            exc: 捕获的异常实例
        """
        if self._metrics is None:
            return
        code = getattr(exc, "code", None) if isinstance(exc, BaseException) else None
        self._metrics.record_exception(type(exc).__name__, code)

    # 在 _handle_exception 末尾调用 self._record(exc)
    # 在 _handle_unexpected_error 末尾调用 self._record(exc)
    # 在 _handle_validation_error 末尾调用 self._record(exc)


def register_exception_handlers(
    app: FastAPI,
    metrics: ExceptionMetricsPort | None = None,
) -> None:
    """注册异常处理器到 FastAPI 应用

    Args:
        app: FastAPI 应用实例
        metrics: 可选的异常指标采集端口
    """
    ExceptionHandlers(app, metrics)
```

### 3.4 app.py 注册处理器与中间件

- [ ] 修改 `src/interfaces/api/app.py`：注册 ExceptionHandlers + ExceptionContextMiddleware

```python
# src/interfaces/api/app.py — 修改后
from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(lifespan=_lifespan)
    # 注册中间件（顺序：先添加的后执行，ExceptionContextMiddleware 需在最外层）
    app.add_middleware(ExceptionContextMiddleware)
    # 注册统一异常处理器
    register_exception_handlers(app)
    return app
```

> **注意**：metrics 实例在 `bootstrap()` 完成后才可 resolve，而 `create_app()` 可能在 `bootstrap()` 之前调用（测试场景）。此时 ExceptionHandlers 使用 `metrics=None`，指标采集静默跳过。生产环境应在 lifespan 启动后通过延迟 resolve 注入 metrics。

### 3.5 创建共享 ErrorResponse 模型

- [ ] 新建 `src/interfaces/api/shared_models.py`

```python
"""接口层共享响应模型模块

提供 API 路由共用的 Pydantic 响应模型，避免重复定义。
遵循 R4（接口层统一管理外部响应格式）。
"""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """标准错误响应模型（用于 OpenAPI 文档）

    Attributes:
        detail: 错误详情
    """

    detail: str
```

- [ ] 替换 5 处重复定义，改为 `from src.interfaces.api.shared_models import ErrorResponse`

| 文件 | 删除行 | 操作 |
|------|--------|------|
| `src/interfaces/api/auth.py` | L150-157 `class ErrorResponse` | 删除类定义，添加 import |
| `src/interfaces/api/document_upload.py` | L100-107 `class ErrorResponse` | 同上 |
| `src/interfaces/api/crawler.py` | L102-109 `class ErrorResponse` | 同上 |
| `src/interfaces/api/audit.py` | L117-121 `class ErrorResponse` | 同上 |
| `src/interfaces/api/equilibrium_security.py` | L151-155 `class ErrorResponse` | 同上 |

### 3.6 创建共享 get_current_user 依赖

- [ ] 在 `src/interfaces/api/shared_models.py` 中添加共享的 OAuth2 认证依赖

```python
# 添加到 src/interfaces/api/shared_models.py
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from src.domain.ports.auth_service import AuthServicePort, AuthenticationError
from src.domain.value_objects.token_payload import TokenPayload
from fastapi import HTTPException, status

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def create_get_current_user(auth_service: AuthServicePort):
    """创建 get_current_user 依赖工厂

    Args:
        auth_service: 认证服务实例

    Returns:
        依赖函数
    """
    async def get_current_user(
        token: str | None = Depends(oauth2_scheme),
    ) -> TokenPayload:
        """获取当前认证用户

        Args:
            token: OAuth2 Bearer token

        Returns:
            TokenPayload 领域值对象

        Raises:
            HTTPException: 用户未认证（OAuth2 需要 WWW-Authenticate header）
        """
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return await auth_service.verify_token(token)
        except AuthenticationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return get_current_user
```

> **设计说明**：OAuth2 Bearer token 提取必须使用 `HTTPException`（需要 `WWW-Authenticate` header），这是 FastAPI/Starlette 安全机制的要求，属于 §3.8 决策指南中"可接受手动 HTTPException"的场景。

---

## 4. Phase 3：接口层迁移

### 4.1 auth.py 迁移（19→2 处 HTTPException）

#### 4.1.1 移除 7 处冗余 catch+rethrow

- [ ] `login()`（L272-282）：移除 `except AuthenticationError` 块，让异常自然上浮
- [ ] `refresh_token()`（L316-320）：同上
- [ ] `create_role()`（L413-417）：移除 `except RoleAlreadyExistsError` 块
- [ ] `update_role()`（L540-549）：移除 `except RoleNotFoundError` 和 `except RoleAlreadyExistsError` 块
- [ ] `delete_role()`（L583-597）：移除 `except RoleNotFoundError`、`except CannotDeleteSystemRoleError`、`except CannotDeleteRoleWithUsersError` 块

```python
# 迁移前：
try:
    role = await role_service.create_role(...)
    return RoleResponse(...)
except RoleAlreadyExistsError:
    raise HTTPException(status_code=409, detail=f"Role '{request.name}' already exists")

# 迁移后（直接让 RoleAlreadyExistsError 上浮到 ExceptionHandlers→409）：
role = await role_service.create_role(...)
return RoleResponse(...)
```

#### 4.1.2 替换 5 处 admin 角色检查

- [ ] L391-395, L515-519, L574-578, L626-630, L688-691：改用 `PermissionDeniedError`

```python
# 迁移前：
if not current_user.has_any_role("admin"):
    raise HTTPException(status_code=403, detail="Admin role required")

# 迁移后：
if not current_user.has_any_role("admin"):
    raise PermissionDeniedError("Admin role required")
```

#### 4.1.3 替换 5 处 null 检查

- [ ] L472-476, L540-544, L584-587, L634-638, L695-699：改用 `NotFoundError`

```python
# 迁移前：
role = await role_service.get_role(UUID(role_id))
if not role:
    raise HTTPException(status_code=404, detail=f"Role '{role_id}' not found")

# 迁移后：
role = await role_service.get_role(UUID(role_id))
if not role:
    raise NotFoundError(f"Role '{role_id}' not found", context={"role_id": role_id})
```

#### 4.1.4 保留 2 处 OAuth2 HTTPException

- [ ] `get_current_user_dependency`（L191-204）：保持不变（OAuth2 WWW-Authenticate 要求）

### 4.2 document_upload.py 迁移（12→4 处 HTTPException）

#### 4.2.1 替换 6 处 ValueError 捕获

- [ ] L251, L292：`except ValueError` → `raise ValidationError(str(e))`
- [ ] L355-356, L376-377：含 `"不存在" in str(e)` 字符串判断的 ValueError → `raise NotFoundError` / `raise ValidationError`

```python
# 迁移前（脆弱的字符串判断）：
except ValueError as e:
    if "不存在" in str(e):
        raise HTTPException(status_code=410, detail=str(e))
    raise HTTPException(status_code=400, detail=str(e))

# 迁移后：
except ValueError as e:
    raise ValidationError(str(e), cause=e)
```

#### 4.2.2 替换 2 处 null 检查

- [ ] L340（`info is None`）：→ `raise NotFoundError("Upload session expired", context={"upload_id": upload_id})`
- [ ] L417（`doc is None`）：→ `raise NotFoundError("文档不存在", context={"document_id": document_id})`

#### 4.2.3 合并重复的 get_current_user

- [ ] 删除 L110-140 和 L191-211 两处重复的 `get_current_user_dependency`
- [ ] 使用 `shared_models.create_get_current_user(auth_service)` 统一注入

#### 4.2.4 保留 4 处 OAuth2 HTTPException

- [ ] 合并后的共享 `get_current_user` 中的 2 处 `raise HTTPException(401)` 保持不变

### 4.3 crawler.py 迁移（4→0 处 HTTPException）

- [ ] L168-173, L205-210, L234-239, L261-265：4 处 `except Exception` → `ServiceUnavailableError`

```python
# 迁移前：
except Exception as e:
    logger.error("Failed to submit crawler task: %s", e)
    raise HTTPException(status_code=503, detail=f"Crawler service unavailable: {e}")

# 迁移后：
except Exception as e:
    logger.error("Failed to submit crawler task: %s", e)
    raise ServiceUnavailableError(
        f"Crawler service unavailable: {e}",
        cause=e,
    ) from e
```

### 4.4 audit.py 迁移（5→0 处 HTTPException）

- [ ] L205-208, L245-248, L273-276：3 处 `except ValueError` → `raise ValidationError("Invalid log_id format")`
- [ ] L212-215, L280-283：2 处 null 检查 → `raise NotFoundError("Audit log not found")`

### 4.5 equilibrium_security.py 迁移（1→1 处，修复安全漏洞）

- [ ] 替换 L181-198 的伪造 `get_current_user`（硬编码 admin 用户，无 JWT 验证）
- [ ] 使用 `shared_models.create_get_current_user(auth_service)` 注入真实认证

```python
# 迁移前（安全漏洞）：
async def get_current_user(authorization: str | None = None) -> TokenPayload:
    if not authorization:
        raise HTTPException(status_code=401, ...)
    # 未验证 JWT，直接伪造 admin 用户
    return TokenPayload(user_id=uuid.uuid4(), username="admin", roles=("admin",))

# 迁移后：
# 使用 shared_models 中的共享 get_current_user 依赖
```

### 4.6 permission_middleware.py 迁移（10→5 处 HTTPException）

#### 4.6.1 保留 5 处 OAuth2 HTTPException

- [ ] L36-39（缺失 Authorization）、L44-48（空 header）、L52-56（格式错误）、L69-73（token 验证失败）：保持 `HTTPException(401, headers={"WWW-Authenticate": "Bearer"})`
- [ ] L222 的 `except HTTPException: return None`（CurrentUser.optional 吞没异常）：保持不变

#### 4.6.2 替换 2 处配置错误

- [ ] L60-63：`raise HTTPException(500, "JWT service not configured")` → `raise ConfigurationError("JWT service not configured")`
- [ ] L110-113：`raise HTTPException(500, "Permission service not configured")` → `raise ConfigurationError("Permission service not configured")`

#### 4.6.3 替换 4 处权限/角色拒绝

- [ ] L122-125：→ `raise PermissionDeniedError(f"Permission denied: {resource}:{action}")`
- [ ] L158-161：→ `raise PermissionDeniedError(f"Required role: one of {roles}")`
- [ ] L188-191：→ `raise PermissionDeniedError(f"Missing required roles: {missing_roles}")`
- [ ] L298-301：→ `raise PermissionDeniedError(f"Permission denied: {resource}:{action}")`

---

## 5. Phase 4：领域层清理

### 5.1 创建 Transfer 相关领域异常

- [ ] 新建 `src/domain/exceptions/transfer_exceptions.py`

```python
"""领域层跨境传输异常模块

将 TransferNotFoundError/TransferNotApprovedError 从基础设施层迁移到领域层，
纳入统一异常层次结构。遵循 R1（领域层统一抽象基础异常）。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import InvalidStateError, NotFoundError


class TransferNotFoundError(NotFoundError):
    """跨境传输请求未找到异常

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_261"
    message = "Transfer request not found"

    def __init__(self, transfer_id: str) -> None:
        """初始化

        Args:
            transfer_id: 传输请求 ID
        """
        self.transfer_id = transfer_id
        super().__init__(
            f"Transfer request {transfer_id} not found",
            context={"transfer_id": transfer_id},
        )


class TransferNotApprovedError(InvalidStateError):
    """跨境传输请求未审批通过时执行操作异常

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_262"
    message = "Transfer request not approved"

    def __init__(self, transfer_id: str, status_value: str) -> None:
        """初始化

        Args:
            transfer_id: 传输请求 ID
            status_value: 当前状态
        """
        self.transfer_id = transfer_id
        super().__init__(
            f"Transfer request {transfer_id} is not approved (status: {status_value})",
            context={"transfer_id": transfer_id, "status": status_value},
        )


__all__ = [
    "TransferNotFoundError",
    "TransferNotApprovedError",
]
```

### 5.2 迁移 cross_border_transfer_service_impl.py

- [ ] 删除 L20-25 的内联 `TransferNotFoundError(Exception)` 和 `TransferNotApprovedError(Exception)` 定义
- [ ] 添加 `from src.domain.exceptions.transfer_exceptions import TransferNotFoundError, TransferNotApprovedError`
- [ ] 更新 `src/domain/exceptions/__init__.py` 导出新类

### 5.3 添加 ValueError 兜底处理器

- [ ] 在 `src/interfaces/api/exception_handlers.py` 添加 ValueError 处理器（临时方案，直到实体层迁移完成）

```python
# 在 ExceptionHandlers._register_handlers 中添加
self._app.add_exception_handler(ValueError, self._handle_value_error)


async def _handle_value_error(
    self, request: Request, exc: ValueError
) -> JSONResponse:
    """处理领域实体验证异常（临时方案）

    领域实体（checkpoint, agent 等）使用 ValueError 做构造器守卫。
    此处理器确保 ValueError 返回 400 而非 500。
    实体层迁移到 ValidationError 后可移除此处理器。
    """
    self._record(exc)
    request_id = getattr(request.state, "request_id", None) or "unknown"
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "EXCEPTION_201",
                "message": str(exc),
                "context": {},
            },
            "request_id": request_id,
        },
        headers={"X-Error-Code": "EXCEPTION_201"},
    )
```

---

## 6. Phase 5：验证

### 6.1 错误码唯一性测试

- [ ] 运行 `pytest tests/unit/domain/exceptions/test_error_code_uniqueness.py -v`
- [ ] 预期：全部通过，零重复编码

### 6.2 HTTP 映射完整性测试

- [ ] 验证所有 `__all__` 导出的异常类都能通过 `EXCEPTION_HTTP_MAP`（精确匹配或 MRO 回退）得到有效 HTTP 状态码
- [ ] 验证状态码范围合理：SystemException→5XX、BusinessException→4XX、ExternalException→5XX

### 6.3 全量测试套件

- [ ] 运行 `poetry run pytest tests/ -v --tb=short`
- [ ] 预期：所有测试通过（更新受影响的测试断言）

### 6.4 接口层 HTTPException 残留检查

- [ ] 运行以下命令验证仅剩 OAuth2 模式

```bash
grep -rn "raise HTTPException" src/interfaces/api/ --include="*.py" | grep -v "WWW-Authenticate\|oauth2_scheme"
```

- [ ] 预期：`permission_middleware.py` 保留 ~5 处 OAuth2 HTTPException，其余文件零残留

### 6.5 死代码清除验证

```bash
grep -rn "IntrusionDetectionError\|DataIntegrityError\|BackupError\|EncryptionError\|ContainerSecurityError" src/ --include="*.py"
```

- [ ] 预期：仅出现在 `sisys-uni-exception-design.md` 文档的历史记录中，源码零引用

### 6.6 指标集成端到端验证

- [ ] 启动应用，触发一个 404 请求
- [ ] 验证 `/metrics` 端点包含 `sisys_exception_total{exception_type="NotFoundError",code="EXCEPTION_202"}`
- [ ] 验证响应头包含 `X-Request-ID`（ExceptionContextMiddleware 生效）

---

## 7. 风险与缓解策略

### 7.1 响应格式变更

**风险**：客户端解析 `response.json()["detail"]` 的代码将在迁移后失败（统一处理器返回 `{"error": {"code": "...", "message": "..."}, "request_id": "..."}`）。

**缓解**：
1. 迁移前通知所有 API 消费方
2. Phase 3 分文件提交，每个文件一个 PR，降低爆炸半径
3. auth.py 迁移后先部署到 staging 环境验证

### 7.2 分 PR 提交策略

| PR | 内容 | 依赖 |
|----|------|------|
| PR-1 | Phase 1：错误码去重 + 死代码清理 + 唯一性测试 | 无 |
| PR-2 | Phase 2：指标适配器 + 共享模型 + app.py 接线 | 无（可与 PR-1 并行） |
| PR-3 | Phase 3.1：auth.py 迁移 | PR-1 + PR-2 |
| PR-4 | Phase 3.2-3.4：document_upload/crawler/audit 迁移 | PR-1 + PR-2 |
| PR-5 | Phase 3.5-3.6：equilibrium_security/permission_middleware 迁移 | PR-1 + PR-2 |
| PR-6 | Phase 4：Transfer 异常 + ValueError 兜底 | PR-2 |
| PR-7 | Phase 5：全量验证 + 文档更新 | PR-1~6 全部 |

### 7.3 回滚方案

- 每个 PR 独立可回滚
- 错误码变更不影响 HTTP 映射逻辑（基于类型匹配而非编码匹配）
- 如果 Phase 3 导致客户端大面积故障，可通过 Feature Flag 切回旧模式

---

## 8. 重构后预期统计

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| 错误码碰撞数 | 8 个编码被多类共享 | 0（全部唯一） |
| 死代码类 | 5 个 | 0 |
| 手动 HTTPException | 51 处 | ~12 处（仅 OAuth2） |
| 重复 ErrorResponse | 5 处 | 0（共享模块） |
| 重复 get_current_user | 4 处（含 1 处伪造） | 0（共享依赖） |
| 越界异常（继承 Python Exception） | 2 个 | 0 |
| 指标集成 | 不可用 | 端到端可用 |
| 处理器/中间件注册 | 未注册 | 已注册 |
