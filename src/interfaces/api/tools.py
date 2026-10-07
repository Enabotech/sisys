"""接口层工具版本管理路由（Story 4-6 — 6 端点 / 5 path）

create_tools_router 路由工厂（domain_dictionary.py 先例：三级降级认证
override → 参数注入 → DI 容器）+ Pydantic schema 定义在路由文件内 +
_to_version_response() 显式映射 helper。

端点（AC-6 表）：
- POST/GET /api/v1/tools/{tool_id}/versions —— 注册（201）/列表（200）
- POST /api/v1/tools/{tool_id}/versions/{version}/publish —— 发布（200）
- POST /api/v1/tools/{tool_id}/rollback —— 回滚（200）
- POST /api/v1/tools/{tool_id}/abort-canary —— 放弃灰度（200）
- GET  /api/v1/tools/{tool_id}/versions/traffic —— 流量视图（200）
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.domain.entities.tool_version import ToolVersion

# ============================================================================
# Pydantic Schema（路由文件内定义——domain_dictionary 先例）
# ============================================================================


class ToolVersionCreate(BaseModel):
    """注册请求体。"""

    version: str = Field(description="SemVer 版本号（X.Y.Z 强校验）")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="输入 JSON Schema 快照")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="输出 JSON Schema 快照")


class PublishRequest(BaseModel):
    """发布请求体（权重域 (0,100]——0 无业务语义）。"""

    traffic_weight: int = Field(default=100, ge=1, le=100, description="发布权重")


class RollbackRequest(BaseModel):
    """回滚请求体（target 缺省 = 最近稳定版）。"""

    target_version: str | None = Field(default=None, description="显式回滚目标（曾稳定版本）")


class ToolVersionResponse(BaseModel):
    """版本详情响应。"""

    version_id: str
    tool_id: str
    version: str
    status: str
    traffic_weight: int
    required_rollout_mode: str
    last_stable_at: datetime | None
    created_at: datetime


class ToolVersionListResponse(BaseModel):
    """版本列表响应。"""

    items: list[ToolVersionResponse]
    total: int


class TrafficViewResponse(BaseModel):
    """流量分布视图响应（无活跃版本时三字段 null）。"""

    stable_version: str | None
    canary_version: str | None
    canary_weight: int | None


# ============================================================================
# 响应映射 helper
# ============================================================================


def _to_version_response(tv: ToolVersion) -> ToolVersionResponse:
    """实体 → 响应模型显式映射。"""
    return ToolVersionResponse(
        version_id=str(tv.version_id),
        tool_id=str(tv.tool_id),
        version=tv.version,
        status=tv.status.value,
        traffic_weight=tv.traffic_weight,
        required_rollout_mode=tv.required_rollout_mode,
        last_stable_at=tv.last_stable_at,
        created_at=tv.created_at,
    )


def get_current_user_dependency(auth_service: Any):
    """认证依赖工厂（domain_dictionary 先例三级降级第二级）。"""

    async def get_current_user(token: str | None = None) -> Any:
        """校验 Bearer Token 并返回用户 Payload。"""
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            payload = auth_service.verify_token(token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload

    return get_current_user


# ============================================================================
# 路由工厂（三级降级认证）
# ============================================================================


def create_tools_router(
    tool_version_service: Any | None = None,
    auth_service: Any | None = None,
    get_current_user_override: Any | None = None,
) -> APIRouter:
    """创建工具版本管理路由。

    三级降级认证（domain_dictionary.py:201-227 先例）：
    1. override（测试注入）
    2. auth_service 参数（依赖工厂构造）
    3. DI 容器 resolve("auth_service")
    """
    router = APIRouter(prefix="/api/v1/tools", tags=["tools"])

    if get_current_user_override is not None:
        get_current_user = get_current_user_override
    elif auth_service is not None:
        get_current_user = get_current_user_dependency(auth_service)
    else:

        async def get_current_user() -> Any:
            """DI 容器降级：resolve auth_service 构造认证依赖。"""
            from src.domain.ports.resolver import Resolver

            resolver = Resolver()
            service = resolver.resolve("auth_service")
            dependency = get_current_user_dependency(service)
            return await dependency()

    def _service() -> Any:
        """解析版本服务（参数注入优先，DI 容器降级）。"""
        if tool_version_service is not None:
            return tool_version_service
        from src.domain.ports.resolver import Resolver

        return Resolver().resolve("tool_version_service")

    @router.post(
        "/{tool_id}/versions",
        response_model=ToolVersionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def register_version(
        tool_id: uuid.UUID,
        body: ToolVersionCreate,
        _: Any = Depends(get_current_user),
    ) -> ToolVersionResponse:
        """注册工具新版本（兼容性分级拦截：critical 409/397）。"""
        tv = await _service().register_version(
            tool_id=tool_id,
            version=body.version,
            input_schema=body.input_schema,
            output_schema=body.output_schema,
        )
        return _to_version_response(tv)

    @router.get("/{tool_id}/versions", response_model=ToolVersionListResponse)
    async def list_versions(
        tool_id: uuid.UUID,
        _: Any = Depends(get_current_user),
    ) -> ToolVersionListResponse:
        """列出工具全部版本（注册时间升序）。"""
        versions = await _service().list_versions(tool_id)
        return ToolVersionListResponse(
            items=[_to_version_response(tv) for tv in versions],
            total=len(versions),
        )

    @router.post("/{tool_id}/versions/{version}/publish", response_model=ToolVersionResponse)
    async def publish_version(
        tool_id: uuid.UUID,
        version: str,
        body: PublishRequest | None = None,
        _: Any = Depends(get_current_user),
    ) -> ToolVersionResponse:
        """发布版本（灰度发起/调档/直接全量/promote 转正）。"""
        weight = body.traffic_weight if body is not None else 100
        tv = await _service().publish_version(tool_id=tool_id, version=version, traffic_weight=weight)
        return _to_version_response(tv)

    @router.post("/{tool_id}/rollback", response_model=ToolVersionResponse)
    async def rollback(
        tool_id: uuid.UUID,
        body: RollbackRequest | None = None,
        _: Any = Depends(get_current_user),
    ) -> ToolVersionResponse:
        """一键回滚（缺省目标防 ping-pong；显式目标 404/409 分立）。"""
        target = body.target_version if body is not None else None
        tv = await _service().rollback(tool_id=tool_id, target_version=target)
        return _to_version_response(tv)

    @router.post("/{tool_id}/abort-canary", response_model=ToolVersionResponse)
    async def abort_canary(
        tool_id: uuid.UUID,
        _: Any = Depends(get_current_user),
    ) -> ToolVersionResponse:
        """放弃灰度（STABLE 不动，流量全回 STABLE）。"""
        tv = await _service().abort_canary(tool_id=tool_id)
        return _to_version_response(tv)

    @router.get("/{tool_id}/versions/traffic", response_model=TrafficViewResponse)
    async def get_version_traffic(
        tool_id: uuid.UUID,
        _: Any = Depends(get_current_user),
    ) -> TrafficViewResponse:
        """查询当前流量分布。"""
        view = await _service().get_version_traffic(tool_id)
        return TrafficViewResponse(**view)

    return router


# 模块级单例（app.py 挂载形态——domain_dictionary:506 先例）
tools_router = create_tools_router()


__all__ = [
    "ToolVersionCreate",
    "ToolVersionListResponse",
    "ToolVersionResponse",
    "create_tools_router",
    "get_current_user_dependency",
    "tools_router",
]
