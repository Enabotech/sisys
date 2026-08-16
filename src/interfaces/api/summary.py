"""接口层摘要生成 REST API 路由模块

提供契约化结构化摘要生成的 API 端点。
遵循六边形架构：接口层通过 DI 容器获取应用服务实例。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from src.domain.ports.auth_service import AuthenticationError, AuthServicePort
from src.domain.ports.resolver import get_resolver
from src.domain.value_objects.token_payload import TokenPayload

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ===================================================================
# 请求/响应 Schema
# ===================================================================


class SummaryRequest(BaseModel):
    """摘要生成请求

    Attributes:
        query_text: 查询文本
        perspective: 摘要视角类型（financial/market/technical）
        top_k: 检索结果数量（可选，默认 10）
        tenant_id: 租户 ID（可选）
    """

    query_text: str = Field(..., min_length=1, description="查询文本")
    perspective: str = Field(
        ...,
        pattern="^(financial|market|technical)$",
        description="摘要视角类型（financial/market/technical）",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="检索结果数量")
    tenant_id: str | None = Field(default=None, description="租户 ID")


class SummaryResponse(BaseModel):
    """摘要生成响应

    Attributes:
        summary: 结构化摘要对象
        query_text: 原始查询文本
        perspective: 摘要视角类型
        confidence_score: LLM 自评置信度
        source_documents: 来源文档 ID 列表
    """

    summary: dict[str, Any]
    query_text: str
    perspective: str
    confidence_score: float
    source_documents: list[str]


# ===================================================================
# 认证依赖
# ===================================================================


def get_current_user_dependency(
    auth_service: AuthServicePort | None = None,
) -> Callable:
    """创建当前用户认证依赖

    Args:
        auth_service: 认证服务实例（可选，默认从 DI 容器获取）

    Returns:
        依赖注入函数
    """
    if auth_service is None:
        auth_service = get_resolver().resolve("auth_service")

    async def get_current_user(
        token: str | None = Depends(oauth2_scheme),
    ) -> TokenPayload | None:
        if not token:
            return None
        try:
            return await auth_service.verify_token(token)
        except AuthenticationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

    return get_current_user


# ===================================================================
# 路由工厂
# ===================================================================


def create_summary_router(
    summary_service: Any | None = None,
    auth_service: AuthServicePort | None = None,
    get_current_user_override: Callable | None = None,
) -> APIRouter:
    """创建摘要生成路由

    Args:
        summary_service: 摘要生成服务实例（可选，默认从 DI 容器获取）
        auth_service: 认证服务实例（可选，默认从 DI 容器获取）
        get_current_user_override: 测试用认证覆盖

    Returns:
        APIRouter 实例
    """
    router = APIRouter(prefix="/api/v1/search", tags=["search"])

    # 延迟获取服务实例，避免模块导入时 DI 容器未初始化
    _summary_service: Any = summary_service
    _auth_service: AuthServicePort | None = auth_service

    def _get_summary_service() -> Any:
        nonlocal _summary_service
        if _summary_service is None:
            _summary_service = get_resolver().resolve("summary_generation_service")
        return _summary_service

    async def _get_current_user(
        token: str | None = Depends(oauth2_scheme),
    ) -> TokenPayload | None:
        """验证 Bearer token 返回当前用户"""
        nonlocal _auth_service
        if not token:
            return None
        if _auth_service is None:
            _auth_service = get_resolver().resolve("auth_service")
        try:
            return await _auth_service.verify_token(token)
        except AuthenticationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

    # 允许测试覆盖认证依赖
    current_user_dep = get_current_user_override or _get_current_user

    @router.post("/summary", response_model=SummaryResponse, summary="生成契约化结构化摘要")
    async def generate_summary(
        request: SummaryRequest,
        current_user: TokenPayload | None = Depends(current_user_dep),
    ) -> SummaryResponse:
        """生成契约化结构化摘要

        根据视角类型生成结构化摘要（财务/市场/技术），
        输出符合预定义 JSON Schema 的结构化摘要。
        """
        del current_user  # 仅认证

        try:
            result = await _get_summary_service().generate_summary(
                query_text=request.query_text,
                search_results=[],
                perspective=request.perspective,
                tenant_id=request.tenant_id,
            )

            # 提取来源文档 ID
            source_documents: list[str] = []
            summary_dict = {}
            confidence_score = 0.0

            if hasattr(result, "model_dump"):
                summary_dict = result.model_dump()
                confidence_score = summary_dict.get("confidence_score", 0.0)

            return SummaryResponse(
                summary=summary_dict,
                query_text=request.query_text,
                perspective=request.perspective,
                confidence_score=confidence_score,
                source_documents=source_documents,
            )
        except Exception as e:
            from src.domain.exceptions import BaseException
            from src.interfaces.api.exception_handlers import _get_http_status

            if isinstance(e, BaseException):
                http_status = _get_http_status(e)
                raise HTTPException(status_code=http_status, detail=str(e))
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return router


# 模块级默认实例
summary_router = create_summary_router()


__all__ = [
    "SummaryRequest",
    "SummaryResponse",
    "create_summary_router",
    "summary_router",
]
