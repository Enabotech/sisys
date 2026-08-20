"""接口层统一异常处理器模块

根据异常类型自动映射到正确的 HTTP 状态码，集成异常指标采集
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from src.application.ports.exception_metrics_port import ExceptionMetricsPort
from src.domain.exceptions import (
    ArchiveConflictError,
    ArchiveNotFoundError,
    ArchiveStorageError,
    AuthenticationError,
    BucketNameValidationError,
    BucketNotFoundError,
    BusinessException,
    BusinessRuleViolationError,
    CannotDeleteRoleWithUsersError,
    CannotDeleteSystemRoleError,
    ChunkingError,
    ComplianceLockError,
    ConfigurationError,
    ConflictError,
    ContainerStartError,
    ContainerStopError,
    DictionaryEntryConflictError,
    DictionaryNotFoundError,
    DictionaryVersionConflictError,
    DocumentVersionConflictError,
    DomainError,
    EntityBusinessRuleError,
    EntityExtractionError,
    EntityStateTransitionError,
    EntityValidationError,
    ExecutionError,
    ExternalException,
    HybridSearchError,
    InsufficientTokenError,
    InvalidStateError,
    InvalidStateTransitionError,
    LayeredRetrievalError,
    LevelTransitionError,
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
    MemoryAccessDeniedError,
    MemoryNotFoundError,
    MemoryVersionConflictError,
    MessageBusError,
    MetadataValidationError,
    MinIOConnectionError,
    NetworkError,
    NotFoundError,
    OCRConnectionError,
    OCRProcessingError,
    PasswordValidationError,
    PermissionDeniedError,
    RelevanceEvaluationBlockedError,
    RelevanceEvaluationError,
    RerankError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    SandboxError,
    ServiceUnavailableError,
    StorageError,
    SummaryGenerationError,
    SummaryPerspectiveNotSupportedError,
    SystemException,
    ThirdPartyError,
    TimeoutError,
    TraceabilityError,
    TraceabilityNotFoundError,
    TransferNotApprovedError,
    TransferNotFoundError,
    UnknownError,
    ValidationError,
    ValidityPeriodConflictError,
    VersionError,
)

logger = logging.getLogger(__name__)


# 异常类型 → HTTP 状态码映射表
EXCEPTION_HTTP_MAP: dict[type[DomainError], int] = {
    # 三层基类
    SystemException: status.HTTP_500_INTERNAL_SERVER_ERROR,
    BusinessException: status.HTTP_400_BAD_REQUEST,
    ExternalException: status.HTTP_502_BAD_GATEWAY,
    # 系统级具体异常
    ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    NetworkError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    StorageError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    MessageBusError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    MinIOConnectionError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 106
    # 业务级具体异常
    ValidationError: status.HTTP_400_BAD_REQUEST,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    InvalidStateError: status.HTTP_409_CONFLICT,
    InvalidStateTransitionError: status.HTTP_409_CONFLICT,
    BusinessRuleViolationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    # 实体验证异常
    EntityValidationError: status.HTTP_400_BAD_REQUEST,
    EntityStateTransitionError: status.HTTP_409_CONFLICT,
    EntityBusinessRuleError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    # 存储子域异常
    MemoryNotFoundError: status.HTTP_404_NOT_FOUND,  # 211
    BucketNotFoundError: status.HTTP_404_NOT_FOUND,  # 212
    MemoryVersionConflictError: status.HTTP_409_CONFLICT,  # 213
    BucketNameValidationError: status.HTTP_400_BAD_REQUEST,  # 214
    MemoryAccessDeniedError: status.HTTP_403_FORBIDDEN,  # 215
    DocumentVersionConflictError: status.HTTP_409_CONFLICT,  # 216
    MetadataValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,  # 217
    ChunkingError: status.HTTP_422_UNPROCESSABLE_ENTITY,  # 218
    # 角色子域异常
    RoleNotFoundError: status.HTTP_404_NOT_FOUND,  # 221
    RoleAlreadyExistsError: status.HTTP_409_CONFLICT,  # 222
    CannotDeleteRoleWithUsersError: status.HTTP_409_CONFLICT,  # 223
    CannotDeleteSystemRoleError: status.HTTP_422_UNPROCESSABLE_ENTITY,  # 224
    # 服务子域异常
    PasswordValidationError: status.HTTP_400_BAD_REQUEST,  # 231
    ComplianceLockError: status.HTTP_409_CONFLICT,  # 232
    # 权限子域异常
    InsufficientTokenError: status.HTTP_403_FORBIDDEN,  # 241
    # 事件子域异常
    VersionError: status.HTTP_409_CONFLICT,  # 251
    # 跨境传输子域异常
    TransferNotFoundError: status.HTTP_404_NOT_FOUND,  # 261
    TransferNotApprovedError: status.HTTP_409_CONFLICT,  # 262
    # 词典管理异常
    DictionaryNotFoundError: status.HTTP_404_NOT_FOUND,  # 270
    DictionaryEntryConflictError: status.HTTP_409_CONFLICT,  # 271
    DictionaryVersionConflictError: status.HTTP_409_CONFLICT,  # 272
    # 档案管理异常
    ArchiveNotFoundError: status.HTTP_404_NOT_FOUND,  # 282
    ArchiveConflictError: status.HTTP_409_CONFLICT,  # 283
    ArchiveStorageError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 284
    ValidityPeriodConflictError: status.HTTP_409_CONFLICT,  # 285
    # 外部服务异常
    ThirdPartyError: status.HTTP_502_BAD_GATEWAY,
    TimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
    ServiceUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
    SandboxError: status.HTTP_502_BAD_GATEWAY,  # 309
    ContainerStartError: status.HTTP_502_BAD_GATEWAY,  # 310
    ExecutionError: status.HTTP_502_BAD_GATEWAY,  # 311
    ContainerStopError: status.HTTP_502_BAD_GATEWAY,  # 312
    # OCR 异常
    OCRConnectionError: status.HTTP_504_GATEWAY_TIMEOUT,  # 320 — 连接超时/不可达
    OCRProcessingError: status.HTTP_502_BAD_GATEWAY,  # 321 — 上游返回错误/响应解析失败
    # LLM 异常
    LLMAPIError: status.HTTP_502_BAD_GATEWAY,  # 330 — LLM API 返回错误
    LLMResponseError: status.HTTP_502_BAD_GATEWAY,  # 331 — 响应解析错误
    LLMConfigError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 332 — 配置错误
    EntityExtractionError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 340 — 实体抽取失败
    RerankError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 350 — 重排序失败（精确注册，避免回退 502）
    RelevanceEvaluationError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 360 — LLM 评估调用失败（精确注册，避免回退 502）
    RelevanceEvaluationBlockedError: status.HTTP_422_UNPROCESSABLE_ENTITY,  # 361 — 检索结果不足被阻断（精确注册，避免回退 400）
    HybridSearchError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 209 — 三路检索通道均失败
    # 分层检索异常
    LayeredRetrievalError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 280 — 分层检索编排失败
    LevelTransitionError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 281 — 层级遍历非法
    # 摘要生成异常
    SummaryGenerationError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 290 — 摘要生成失败
    SummaryPerspectiveNotSupportedError: status.HTTP_400_BAD_REQUEST,  # 291 — 不支持的视角
    # 溯源异常
    TraceabilityError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # 370 — 溯源评估调用失败（精确注册，避免回退 502）
    TraceabilityNotFoundError: status.HTTP_404_NOT_FOUND,  # 371 — 按 ID/文档查询引文未找到（精确注册，避免回退 400）
    UnknownError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _get_http_status(exc: DomainError) -> int:
    """获取异常对应的 HTTP 状态码，优先使用具体异常映射

    Args:
        exc: 领域异常实例

    Returns:
        对应的 HTTP 状态码
    """
    for exc_type, http_status in EXCEPTION_HTTP_MAP.items():
        if type(exc) is exc_type:
            return http_status
    for exc_type, http_status in EXCEPTION_HTTP_MAP.items():
        if isinstance(exc, exc_type):
            return http_status
    return status.HTTP_500_INTERNAL_SERVER_ERROR


class ExceptionHandlers:
    """统一异常处理器注册

    Attributes:
        _app: FastAPI 应用实例
        _metrics: 可选的异常指标采集端口
    """

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

    def _register_handlers(self) -> None:
        """注册所有异常处理器到 FastAPI 应用"""
        self._app.add_exception_handler(RequestValidationError, self._handle_validation_error)
        self._app.add_exception_handler(PydanticValidationError, self._handle_pydantic_error)
        self._app.add_exception_handler(DomainError, self._handle_exception)
        self._app.add_exception_handler(Exception, self._handle_unexpected_error)

    def _record(self, exc: Exception) -> None:
        """记录异常指标

        Args:
            exc: 捕获的异常实例
        """
        if self._metrics is None:
            return
        code = getattr(exc, "code", None) if isinstance(exc, DomainError) else None
        self._metrics.record_exception(type(exc).__name__, code)

    async def _handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """处理领域基类异常，自动映射到 HTTP 状态码

        Args:
            request: 当前 HTTP 请求
            exc: 捕获的异常实例

        Returns:
            JSON 格式的错误响应
        """
        if not isinstance(exc, DomainError):
            return await self._handle_unexpected_error(request, exc)
        request_id = getattr(request.state, "request_id", None) or "unknown"

        # AuthenticationError locked 状态特殊处理
        if isinstance(exc, AuthenticationError):
            context: dict[str, Any] = getattr(exc, "context", {}) or {}
            if context.get("locked"):
                self._record(exc)
                return JSONResponse(
                    status_code=status.HTTP_423_LOCKED,
                    content={
                        "error": {
                            "code": getattr(exc, "code", "EXCEPTION_205") or "EXCEPTION_205",
                            "message": "Account is locked",
                            "context": context,
                        },
                        "request_id": request_id,
                    },
                    headers={"X-Error-Code": getattr(exc, "code", "EXCEPTION_205") or "EXCEPTION_205"},
                )

        try:
            error_dict = exc.to_dict()
        except Exception as to_dict_err:
            logger.warning(
                "to_dict() failed for %s: %s, falling back to manual serialization",
                type(exc).__name__,
                to_dict_err,
            )
            code_raw = getattr(exc, "code", None)
            error_dict = {
                "code": code_raw if code_raw else "EXCEPTION_999",
                "message": str(exc)[:500],
                "context": getattr(exc, "context", None) or {},
            }
            cause = getattr(exc, "cause", None)
            if cause:
                error_dict["cause"] = {
                    "type": type(cause).__name__,
                    "message": str(cause),
                }

        content = {
            "error": error_dict,
            "request_id": request_id,
        }

        self._record(exc)

        return JSONResponse(
            status_code=_get_http_status(exc),
            content=content,
            headers={"X-Error-Code": str(getattr(exc, "code", "EXCEPTION_999") or "EXCEPTION_999")},
        )

    async def _handle_validation_error(self, request: Request, exc: Exception) -> JSONResponse:
        """处理请求参数校验异常

        Args:
            request: 当前 HTTP 请求
            exc: RequestValidationError 实例

        Returns:
            JSON 格式的校验错误响应
        """
        if not isinstance(exc, RequestValidationError):
            raise TypeError(f"Expected RequestValidationError, got {type(exc).__name__}")
        request_id = getattr(request.state, "request_id", None) or "unknown"
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        self._record(exc)

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

    async def _handle_pydantic_error(self, request: Request, exc: Exception) -> JSONResponse:
        """处理 Pydantic 数据校验异常

        Args:
            request: 当前 HTTP 请求
            exc: PydanticValidationError 实例

        Returns:
            JSON 格式的校验错误响应
        """
        if not isinstance(exc, PydanticValidationError):
            raise TypeError(f"Expected PydanticValidationError, got {type(exc).__name__}")
        request_id = getattr(request.state, "request_id", None) or "unknown"
        self._record(exc)
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

    async def _handle_unexpected_error(self, request: Request, exc: Exception) -> JSONResponse:
        """处理未预期的异常，返回 500 内部错误

        Args:
            request: 当前 HTTP 请求
            exc: 未预期的异常实例

        Returns:
            JSON 格式的 500 错误响应
        """
        logger.exception("Unexpected error: %s", exc)
        self._record(exc)
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


def register_exception_handlers(
    app: FastAPI,
    metrics: ExceptionMetricsPort | None = None,
) -> None:
    """注册异常处理器到 FastAPI 应用

    用法：register_exception_handlers(app)  # 初始化时调用一次

    Args:
        app: FastAPI 应用实例
        metrics: 可选的异常指标采集端口
    """
    ExceptionHandlers(app, metrics)
