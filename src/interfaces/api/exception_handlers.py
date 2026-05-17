"""SISYS 接口层统一异常处理器模块。

根据异常类型自动映射到正确的 HTTP 状态码

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from src.domain.exceptions import (
    AuthenticationError,
    BaseException,
    BusinessException,
    BusinessRuleViolationError,
    ConfigurationError,
    ConflictError,
    ExternalException,
    InvalidStateError,
    InvalidStateTransitionError,
    MessageBusError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    SandboxError,
    ServiceUnavailableError,
    StorageError,
    SystemException,
    ThirdPartyError,
    TimeoutError,
    UnknownError,
    ValidationError,
)

logger = logging.getLogger(__name__)


# 异常类型 → HTTP 状态码映射表
EXCEPTION_HTTP_MAP: dict[type[BaseException], int] = {
    # 三层基类
    SystemException: status.HTTP_500_INTERNAL_SERVER_ERROR,
    BusinessException: status.HTTP_400_BAD_REQUEST,
    ExternalException: status.HTTP_502_BAD_GATEWAY,
    # 具体异常
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
    """获取异常对应的 HTTP 状态码，优先使用具体异常映射。

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
    """统一异常处理器注册。

    Attributes:
        _app: FastAPI 应用实例
    """

    def __init__(self, app: FastAPI) -> None:
        """初始化异常处理器。

        Args:
            app: FastAPI 应用实例
        """
        self._app = app
        self._register_handlers()

    def _register_handlers(self) -> None:
        """注册所有异常处理器到 FastAPI 应用。"""
        self._app.add_exception_handler(RequestValidationError, self._handle_validation_error)
        self._app.add_exception_handler(PydanticValidationError, self._handle_pydantic_error)
        self._app.add_exception_handler(BaseException, self._handle_exception)
        self._app.add_exception_handler(Exception, self._handle_unexpected_error)

    async def _handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """处理领域基类异常，自动映射到 HTTP 状态码。

        Args:
            request: 当前 HTTP 请求
            exc: 捕获的异常实例

        Returns:
            JSON 格式的错误响应
        """
        if not isinstance(exc, BaseException):
            return await self._handle_unexpected_error(request, exc)
        request_id = getattr(request.state, "request_id", None) or "unknown"

        # AuthenticationError locked 状态特殊处理
        if isinstance(exc, AuthenticationError):
            context: dict[str, Any] = getattr(exc, "context", {}) or {}
            if context.get("locked"):
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
        except Exception:
            error_dict = {
                "code": getattr(exc, "code", None) or "EXCEPTION_999",
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

        return JSONResponse(
            status_code=_get_http_status(exc),
            content=content,
            headers={"X-Error-Code": str(getattr(exc, "code", "EXCEPTION_999") or "EXCEPTION_999")},
        )

    async def _handle_validation_error(self, request: Request, exc: Exception) -> JSONResponse:
        """处理请求参数校验异常。

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
        """处理 Pydantic 数据校验异常。

        Args:
            request: 当前 HTTP 请求
            exc: PydanticValidationError 实例

        Returns:
            JSON 格式的校验错误响应
        """
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

    async def _handle_unexpected_error(self, request: Request, exc: Exception) -> JSONResponse:
        """处理未预期的异常，返回 500 内部错误。

        Args:
            request: 当前 HTTP 请求
            exc: 未预期的异常实例

        Returns:
            JSON 格式的 500 错误响应
        """
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
    """注册异常处理器到 FastAPI 应用。

    用法：register_exception_handlers(app)  # 初始化时调用一次

    Args:
        app: FastAPI 应用实例
    """
    ExceptionHandlers(app)
