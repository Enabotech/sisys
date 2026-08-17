"""接口层检索相关性评估 REST API 路由模块

提供检索相关性评估的 API 端点（LLM-as-a-Judge 多维评估）。
遵循六边形架构：接口层通过 DI 容器获取应用服务实例。

设计决策：
- 系统内部通过 resolver.resolve("layered_retrieval_service") 执行真实检索后评估，
  不接受客户端直接传入 search_results（防止客户端伪造高分结果绕过质量守卫）
- 领域异常透传到全局 ExceptionHandlers（不捕获异常抛 HTTPException，
  避免丢失 code/request_id/X-Error-Code 响应头）
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


class EvaluateRequest(BaseModel):
    """检索相关性评估请求

    Attributes:
        query_text: 查询文本
        tenant_id: 租户 ID（可选）
    """

    query_text: str = Field(..., min_length=1, description="查询文本")
    tenant_id: str | None = Field(default=None, description="租户 ID")


class EvaluateResponse(BaseModel):
    """检索相关性评估响应

    Attributes:
        overall_score: 综合评分（0-1）
        context_relevance: 上下文相关性评分（0-1）
        completeness: 完整性评分（0-1）
        timeliness: 时效性评分（0-1）
        context_relevance_reason: 相关性判断理由
        completeness_reason: 完整性判断理由
        timeliness_reason: 时效性判断理由
        should_block: 是否阻断摘要生成
        block_reason: 阻断理由（should_block=True 时为"数据不足"，否则为 None）
    """

    overall_score: float
    context_relevance: float
    completeness: float
    timeliness: float
    context_relevance_reason: str
    completeness_reason: str
    timeliness_reason: str
    should_block: bool
    block_reason: str | None


# ===================================================================
# 路由工厂
# ===================================================================


def create_evaluate_router(
    evaluate_service: Any | None = None,
    auth_service: AuthServicePort | None = None,
    get_current_user_override: Callable | None = None,
    layered_retrieval: Any | None = None,
) -> APIRouter:
    """创建检索相关性评估路由

    Args:
        evaluate_service: 评估服务实例（可选，默认从 DI 容器获取）
        auth_service: 认证服务实例（可选，默认从 DI 容器获取）
        get_current_user_override: 测试用认证覆盖
        layered_retrieval: 分层检索服务实例（可选，默认从 DI 容器获取）

    Returns:
        APIRouter 实例
    """
    router = APIRouter(prefix="/api/v1/search", tags=["search"])

    # 延迟获取服务实例，避免模块导入时 DI 容器未初始化
    _evaluate_service: Any = evaluate_service
    _auth_service: AuthServicePort | None = auth_service
    _layered_retrieval: Any = layered_retrieval

    def _get_evaluate_service() -> Any:
        nonlocal _evaluate_service
        if _evaluate_service is None:
            _evaluate_service = get_resolver().resolve("relevance_evaluation_service")
        return _evaluate_service

    def _get_layered_retrieval() -> Any:
        nonlocal _layered_retrieval
        if _layered_retrieval is None:
            _layered_retrieval = get_resolver().resolve("layered_retrieval_service")
        return _layered_retrieval

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

    @router.post("/evaluate", response_model=EvaluateResponse, summary="检索相关性评估")
    async def evaluate_search(
        request: EvaluateRequest,
        current_user: TokenPayload | None = Depends(current_user_dep),
    ) -> EvaluateResponse:
        """执行检索相关性评估（LLM-as-a-Judge 多维评估）

        系统内部执行检索并评估检索结果（相关性/完整性/时效性），
        综合评分 < 0.6 时标注"数据不足"并阻断摘要生成。
        """
        del current_user  # 仅认证

        # 系统内部执行真实检索（不接受客户端传入检索结果，防止伪造高分绕过质量守卫）
        layered_retrieval = _get_layered_retrieval()
        search_results = await layered_retrieval.search_top_down(
            query_text=request.query_text,
            target_level="L4",
            collection="documents",
            limit=10,
            tenant_id=request.tenant_id,
            filter_payload=None,
        )

        # 执行评估（领域异常透传到全局 ExceptionHandlers）
        evaluate_service = _get_evaluate_service()
        result = await evaluate_service.evaluate(
            query_text=request.query_text,
            search_results=search_results,
        )

        return EvaluateResponse(
            overall_score=result.overall_score,
            context_relevance=result.context_relevance,
            completeness=result.completeness,
            timeliness=result.timeliness,
            context_relevance_reason=result.context_relevance_reason,
            completeness_reason=result.completeness_reason,
            timeliness_reason=result.timeliness_reason,
            should_block=result.should_block,
            block_reason=result.block_reason,
        )

    return router


# 模块级默认实例
evaluate_router = create_evaluate_router()


__all__ = [
    "EvaluateRequest",
    "EvaluateResponse",
    "create_evaluate_router",
    "evaluate_router",
]
