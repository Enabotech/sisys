"""接口层战略档案 REST API 路由模块

提供战略档案查询、详情、归档触发接口。
遵循六边形架构：接口层通过 DI 容器获取应用服务实例。
"""

from __future__ import annotations

import base64
import logging
import uuid
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from src.domain.entities.strategic_archive import ArchiveType
from src.domain.ports.archive_repository import ArchiveQuery
from src.domain.ports.auth_service import AuthenticationError, AuthServicePort
from src.domain.value_objects.token_payload import TokenPayload

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ===================================================================
# 请求/响应 Schema
# ===================================================================


class ArchiveRequest(BaseModel):
    """归档请求

    Attributes:
        plan_id: 规划 ID
        plan_type: 规划类型（SP/BP）
        archive_type: 档案类型（默认 assumption）
        assumptions: 关键假设变量
        decision_basis: 决策依据
        execution_deviation: 实际执行偏差
        evidence_blob: 证据包内容（Base64 编码）
    """

    plan_id: uuid.UUID = Field(..., description="规划 ID")
    plan_type: str = Field(default="SP", pattern="^(SP|BP)$", description="规划类型")
    archive_type: str = Field(
        default="assumption",
        pattern="^(assumption|decision|deviation|evidence_package)$",
        description="档案类型",
    )
    assumptions: dict[str, Any] = Field(default_factory=dict, description="关键假设变量")
    decision_basis: dict[str, Any] = Field(default_factory=dict, description="决策依据")
    execution_deviation: dict[str, Any] = Field(default_factory=dict, description="实际执行偏差")
    evidence_blob: str | None = Field(default=None, max_length=10485760, description="证据包内容（Base64 编码，最大 10MB）")


class ArchiveResponse(BaseModel):
    """档案响应

    Attributes:
        archive_id: 档案 ID
        plan_id: 规划 ID
        plan_type: 规划类型
        archive_type: 档案类型
        assumptions: 关键假设变量
        decision_basis: 决策依据
        execution_deviation: 实际执行偏差
        metadata_ref: L2 元数据引用
        embedding_ref: L3 向量引用
        blob_ref: L4 对象存储引用
        graph_ref: L5 图存储引用
        created_at: 创建时间
        archived_at: 归档时间
    """

    archive_id: str
    plan_id: str | None = None
    plan_type: str = ""
    archive_type: str = ""
    assumptions: dict[str, Any] = Field(default_factory=dict)
    decision_basis: dict[str, Any] = Field(default_factory=dict)
    execution_deviation: dict[str, Any] = Field(default_factory=dict)
    metadata_ref: str = ""
    embedding_ref: str | None = None
    blob_ref: str | None = None
    graph_ref: str | None = None
    created_at: str | None = None
    archived_at: str | None = None


# ===================================================================
# 认证依赖
# ===================================================================


def get_current_user_dependency(auth_service: AuthServicePort) -> Callable:
    """创建 get_current_user 依赖工厂

    Args:
        auth_service: 认证服务端口

    Returns:
        get_current_user 依赖函数
    """

    async def get_current_user(
        token: str | None = Depends(oauth2_scheme),
    ) -> TokenPayload:
        """验证 Bearer token 返回当前用户

        Args:
            token: Bearer token

        Returns:
            当前用户 TokenPayload

        Raises:
            HTTPException: 未认证或 token 无效
        """
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        result: TokenPayload = await auth_service.verify_token(token)
        return result

    return get_current_user


# ===================================================================
# 路由工厂
# ===================================================================


def create_archive_router(
    archive_service: Any = None,
    auth_service: AuthServicePort | None = None,
    get_current_user_override: Callable | None = None,
) -> APIRouter:
    """创建战略档案 API 路由

    Args:
        archive_service: StrategicArchiveService 实例（可选，默认从 DI 容器获取）
        auth_service: 认证服务实例（可选，默认从 DI 容器获取）
        get_current_user_override: 认证依赖覆盖（测试用）

    Returns:
        APIRouter 实例
    """
    router = APIRouter(prefix="/api/v1/archive", tags=["archive"])

    def _get_service() -> Any:
        if archive_service is not None:
            return archive_service
        from src.domain.ports.resolver import get_resolver

        return get_resolver().resolve("strategic_archive_service")

    if get_current_user_override is not None:
        get_current_user = get_current_user_override
    elif auth_service is not None:
        get_current_user = get_current_user_dependency(auth_service)
    else:

        async def get_current_user(
            token: str | None = Depends(oauth2_scheme),
        ) -> TokenPayload:
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            from src.domain.ports.resolver import get_resolver

            svc: AuthServicePort = get_resolver().resolve("auth_service")
            try:
                result: TokenPayload = await svc.verify_token(token)
                return result
            except AuthenticationError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    @router.get(
        "/entries",
        response_model=list[ArchiveResponse],
        summary="列出档案",
    )
    async def list_entries(
        archive_type: str | None = Query(default=None, description="档案类型过滤"),
        plan_type: str | None = Query(default=None, description="规划类型过滤"),
        plan_id: str | None = Query(default=None, description="规划 ID 过滤"),
        offset: int = Query(default=0, ge=0, description="分页偏移"),
        limit: int = Query(default=20, ge=1, le=1000, description="每页条数"),
        current_user: TokenPayload = Depends(get_current_user),
    ) -> list[ArchiveResponse]:
        """按条件列出档案（分页 + 过滤）

        Args:
            archive_type: 按档案类型过滤
            plan_type: 按规划类型过滤
            plan_id: 按规划 ID 过滤
            offset: 分页偏移
            limit: 每页条数
            current_user: 当前用户

        Returns:
            档案列表
        """
        del current_user  # 仅认证

        parsed_archive_type: ArchiveType | None = None
        if archive_type is not None:
            try:
                parsed_archive_type = ArchiveType(archive_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid archive_type: {archive_type}",
                )
        try:
            parsed_plan_id = uuid.UUID(plan_id) if plan_id else None
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan_id: {plan_id}",
            )
        query = ArchiveQuery(
            archive_type=parsed_archive_type,
            plan_type=plan_type,
            plan_id=parsed_plan_id,
            offset=offset,
            limit=limit,
        )
        service = _get_service()
        archives = await service.query_archive(query)
        return [_to_archive_response(a) for a in archives]

    @router.get(
        "/entries/{archive_id}",
        response_model=ArchiveResponse,
        summary="获取档案详情",
    )
    async def get_entry(
        archive_id: str,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> ArchiveResponse:
        """按 archive_id 获取档案详情

        Args:
            archive_id: 档案 ID
            current_user: 当前用户

        Returns:
            档案详情
        """
        del current_user  # 仅认证
        service = _get_service()
        try:
            parsed_id = uuid.UUID(archive_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid archive_id: {archive_id}",
            )
        archive = await service.get_archive(parsed_id)
        return _to_archive_response(archive)

    @router.post(
        "/archive",
        response_model=ArchiveResponse,
        status_code=status.HTTP_201_CREATED,
        summary="手动触发归档",
    )
    async def archive_plan(
        payload: ArchiveRequest,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> ArchiveResponse:
        """手动触发战略规划归档

        Args:
            payload: 归档请求
            current_user: 当前用户

        Returns:
            已归档的档案
        """
        del current_user  # 仅认证

        evidence_blob = None
        if payload.evidence_blob:
            try:
                evidence_blob = base64.b64decode(payload.evidence_blob, validate=True)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid base64 encoded evidence_blob",
                )
        service = _get_service()
        archive = await service.archive_plan(
            plan_id=payload.plan_id,
            plan_type=payload.plan_type,
            archive_type=ArchiveType(payload.archive_type),
            assumptions=payload.assumptions,
            decision_basis=payload.decision_basis,
            execution_deviation=payload.execution_deviation,
            evidence_blob=evidence_blob,
        )
        return _to_archive_response(archive)

    @router.get(
        "/plans/{plan_id}",
        response_model=list[ArchiveResponse],
        summary="按规划 ID 查询档案",
    )
    async def list_by_plan(
        plan_id: str,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> list[ArchiveResponse]:
        """按规划 ID 列出所有关联档案

        Args:
            plan_id: 规划 ID
            current_user: 当前用户

        Returns:
            档案列表
        """
        del current_user  # 仅认证

        try:
            parsed_plan_id = uuid.UUID(plan_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan_id: {plan_id}",
            )
        query = ArchiveQuery(plan_id=parsed_plan_id)
        service = _get_service()
        archives = await service.query_archive(query)
        return [_to_archive_response(a) for a in archives]

    return router


# ===================================================================
# 响应转换
# ===================================================================


def _to_archive_response(archive: Any) -> ArchiveResponse:
    return ArchiveResponse(
        archive_id=str(archive.archive_id),
        plan_id=str(archive.plan_id) if archive.plan_id else None,
        plan_type=archive.plan_type,
        archive_type=archive.archive_type.value if archive.archive_type else "",
        assumptions=archive.assumptions,
        decision_basis=archive.decision_basis,
        execution_deviation=archive.execution_deviation,
        metadata_ref=archive.metadata_ref,
        embedding_ref=archive.embedding_ref,
        blob_ref=archive.blob_ref,
        graph_ref=archive.graph_ref,
        created_at=archive.created_at.isoformat() if archive.created_at else None,
        archived_at=archive.archived_at.isoformat() if archive.archived_at else None,
    )


archive_router = create_archive_router()

__all__ = ["create_archive_router", "archive_router"]
