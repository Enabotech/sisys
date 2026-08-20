"""接口层溯源 REST API 路由模块

提供高保真溯源（Bounding Box 级）的 API 端点。
遵循六边形架构：接口层通过 DI 容器获取应用服务实例。

设计决策：
- 领域异常透传到全局 ExceptionHandlers（不捕获异常抛 HTTPException，
  避免丢失 code/request_id/X-Error-Code 响应头）
- 响应通过 Pydantic response_model 类型化序列化（引用值对象字段）
- 路由前缀与 summary.py 保持一致（/api/v1/search）
"""

from __future__ import annotations

import logging
import uuid
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


class TraceRequest(BaseModel):
    """溯源请求

    Attributes:
        claim: 结论文本
        top_k: 返回的引文数量上限（默认 10）
        min_confidence: 最小置信度阈值（默认 0.7）
    """

    claim: str = Field(..., min_length=1, description="结论文本")
    top_k: int = Field(default=10, ge=1, le=100, description="返回的引文数量上限")
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="最小置信度阈值")


class TraceResponse(BaseModel):
    """溯源响应

    Attributes:
        claim: 原始结论文本
        citations: 引文列表
        citation_count: 引文总数
        highest_confidence: 最高置信度
        has_bbox_support: 是否有 Bounding Box 坐标支持
    """

    claim: str
    citations: list[dict[str, Any]]
    citation_count: int
    highest_confidence: float
    has_bbox_support: bool


class DocumentCitationsResponse(BaseModel):
    """按文档 ID 查询引文响应

    Attributes:
        document_id: 文档 UUID
        citations: 引文列表
        citation_count: 引文总数
    """

    document_id: uuid.UUID
    citations: list[dict[str, Any]]
    citation_count: int


# ===================================================================
# 路由工厂
# ===================================================================


def create_trace_router(
    trace_service: Any | None = None,
    auth_service: AuthServicePort | None = None,
    get_current_user_override: Callable | None = None,
) -> APIRouter:
    """创建溯源路由

    Args:
        trace_service: 溯源服务实例（可选，默认从 DI 容器获取）
        auth_service: 认证服务实例（可选，默认从 DI 容器获取）
        get_current_user_override: 测试用认证覆盖

    Returns:
        APIRouter 实例
    """
    router = APIRouter(prefix="/api/v1/search", tags=["search"])

    # 延迟获取服务实例，避免模块导入时 DI 容器未初始化
    _trace_service: Any = trace_service
    _auth_service: AuthServicePort | None = auth_service

    def _get_trace_service() -> Any:
        nonlocal _trace_service
        if _trace_service is None:
            _trace_service = get_resolver().resolve("traceability_service")
        return _trace_service

    async def _get_current_user(
        token: str | None = Depends(oauth2_scheme),
    ) -> TokenPayload:
        """验证 Bearer token，未认证请求直接拒绝"""
        nonlocal _auth_service
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if _auth_service is None:
            _auth_service = get_resolver().resolve("auth_service")
        try:
            return await _auth_service.verify_token(token)
        except AuthenticationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 允许测试覆盖认证依赖
    current_user_dep = get_current_user_override or _get_current_user

    @router.post("/trace", response_model=TraceResponse, summary="高保真溯源")
    async def trace_claim(
        request: TraceRequest,
        current_user: TokenPayload = Depends(current_user_dep),
    ) -> TraceResponse:
        """执行高保真溯源

        从结论文本出发，检索相关文档切片，返回带 Bounding Box 坐标的引文列表。
        """
        del current_user  # 仅认证

        trace_service = _get_trace_service()
        result = await trace_service.trace(
            claim=request.claim,
            top_k=request.top_k,
            min_confidence=request.min_confidence,
        )

        return TraceResponse(
            claim=result["claim"],
            citations=[citation.to_dict() for citation in result["citations"]],
            citation_count=result["citation_count"],
            highest_confidence=result["highest_confidence"],
            has_bbox_support=result["has_bbox_support"],
        )

    @router.get("/trace/{document_id}", response_model=DocumentCitationsResponse, summary="按文档 ID 查询引文")
    async def get_citations_by_document(
        document_id: uuid.UUID,
        current_user: TokenPayload = Depends(current_user_dep),
    ) -> DocumentCitationsResponse:
        """按文档 ID 查询所有引文

        从当次溯源缓存中按文档 ID 返回所有引文（MVP 不持久化）。
        """
        del current_user  # 仅认证

        trace_service = _get_trace_service()
        citations = await trace_service.get_citation_by_document(document_id=document_id)

        return DocumentCitationsResponse(
            document_id=document_id,
            citations=[citation.to_dict() for citation in citations],
            citation_count=len(citations),
        )

    return router


# 模块级默认实例
trace_router = create_trace_router()


__all__ = [
    "TraceRequest",
    "TraceResponse",
    "DocumentCitationsResponse",
    "create_trace_router",
    "trace_router",
]
