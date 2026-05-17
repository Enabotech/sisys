"""SISYS 接口层审计日志 API 路由模块。

提供审计日志检索、完整性验证、归档管理的 REST API 端点。
遵循六边形架构：接口层仅依赖应用层用例和领域端口

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# =============================================================================
# Request/Response Models
# =============================================================================


class AuditLogResponse(BaseModel):
    """审计日志响应。

    Attributes:
        log_id: 日志 ID
        timestamp: 日志时间戳
        actor: 操作者
        action_type: 操作类型
        target_resource: 目标资源
        old_value: 变更前值
        new_value: 变更后值
        correction_level: 修正级别
        checksum: 校验和
        archived: 是否已归档
        archived_at: 归档时间
        correlation_id: 关联 ID
    """

    log_id: str
    timestamp: datetime | None = None
    actor: str | None = None
    action_type: str | None = None
    target_resource: str | None = None
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    correction_level: int | None = None
    checksum: str | None = None
    archived: bool = False
    archived_at: datetime | None = None
    correlation_id: str | None = None


class AuditLogListResponse(BaseModel):
    """审计日志列表响应。

    Attributes:
        items: 日志条目列表
        total: 总数
        offset: 偏移量
        limit: 每页数量
    """

    items: list[AuditLogResponse]
    total: int
    offset: int
    limit: int


class IntegrityVerifyRequest(BaseModel):
    """完整性验证请求。

    Attributes:
        log_ids: 待验证的日志 ID 列表（可选，为空则验证全部）
    """

    log_ids: list[str] | None = None


class IntegrityVerifyDetail(BaseModel):
    """验证详情."""

    log_id: str
    status: str
    message: str | None = None


class IntegrityVerifyResponse(BaseModel):
    """完整性验证响应."""

    total: int
    passed: int
    failed: int
    details: list[IntegrityVerifyDetail]


class ArchiveStatusResponse(BaseModel):
    """归档状态响应."""

    log_id: str
    archived: bool
    archived_at: datetime | None = None
    retention_days: int = 2555


class ArchiveRequest(BaseModel):
    """归档请求."""

    older_than_days: int = Field(default=30, ge=1)


class ArchiveResponse(BaseModel):
    """归档响应."""

    archived_count: int


class ErrorResponse(BaseModel):
    """错误响应."""

    detail: str


# =============================================================================
# Router Factory
# =============================================================================


def create_audit_router(
    get_audit_service,  # Callable that returns AuditServicePort
    get_audit_repository=None,  # Callable that returns AuditRepositoryPort
    get_current_user=None,  # Optional auth dependency
) -> APIRouter:
    """创建审计日志路由.

    Args:
        get_audit_service: 获取审计服务的工厂函数
        get_audit_repository: 获取审计仓储的工厂函数（用于检索操作）
        get_current_user: 可选的当前用户认证依赖

    Returns:
        APIRouter 实例
    """
    router = APIRouter(prefix="/audit", tags=["audit"])

    @router.get("/logs", response_model=AuditLogListResponse)
    async def search_audit_logs(
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        actor: str | None = None,
        action_type: str | None = None,
        target_resource: str | None = None,
        offset: int = 0,
        limit: int = 20,
        match_any: bool = False,
    ):
        """查询审计日志.

        支持多维检索（时间/actor/action_type/target_resource）
        """
        from src.domain.ports.audit_repository import AuditSearchCriteria

        audit_repository = get_audit_repository()
        criteria = AuditSearchCriteria(
            start_time=start_time,
            end_time=end_time,
            actor=actor,
            action_type=action_type,
            target_resource=target_resource,
            offset=offset,
            limit=limit,
            match_any=match_any,
        )
        result = await audit_repository.search(criteria)

        return AuditLogListResponse(
            items=[
                AuditLogResponse(
                    log_id=item["log_id"],
                    timestamp=datetime.fromisoformat(item["timestamp"]) if item.get("timestamp") else None,
                    actor=item.get("actor"),
                    action_type=item.get("action_type"),
                    target_resource=item.get("target_resource"),
                    old_value=item.get("old_value"),
                    new_value=item.get("new_value"),
                    correction_level=item.get("correction_level"),
                    checksum=item.get("checksum"),
                    archived=item.get("archived", False),
                    archived_at=datetime.fromisoformat(item["archived_at"]) if item.get("archived_at") else None,
                    correlation_id=item.get("correlation_id"),
                )
                for item in result.items
            ],
            total=result.total,
            offset=result.offset,
            limit=result.limit,
        )

    @router.get("/logs/{log_id}", response_model=AuditLogResponse)
    async def get_audit_log(log_id: str):
        """获取审计日志详情."""
        audit_repository = get_audit_repository()
        try:
            log_uuid = UUID(log_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid log_id format",
            )

        result = await audit_repository.get_by_id(log_uuid)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit log not found",
            )

        return AuditLogResponse(
            log_id=result["log_id"],
            timestamp=datetime.fromisoformat(result["timestamp"]) if result.get("timestamp") else None,
            actor=result.get("actor"),
            action_type=result.get("action_type"),
            target_resource=result.get("target_resource"),
            old_value=result.get("old_value"),
            new_value=result.get("new_value"),
            correction_level=result.get("correction_level"),
            checksum=result.get("checksum"),
            archived=result.get("archived", False),
            archived_at=datetime.fromisoformat(result["archived_at"]) if result.get("archived_at") else None,
            correlation_id=result.get("correlation_id"),
        )

    @router.post("/verify", response_model=IntegrityVerifyResponse)
    async def verify_integrity(request: IntegrityVerifyRequest):
        """批量验证日志完整性.

        SHA256 校验和验证，支持指定 log_ids 或全部
        """
        audit_service = get_audit_service()

        log_ids = None
        if request.log_ids:
            try:
                log_ids = [UUID(lid) for lid in request.log_ids]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid log_id format",
                )

        result = await audit_service.verify_batch(log_ids)

        return IntegrityVerifyResponse(
            total=result["total"],
            passed=result["passed"],
            failed=result["failed"],
            details=[
                IntegrityVerifyDetail(
                    log_id=d["log_id"],
                    status=d["status"],
                    message=d.get("message"),
                )
                for d in result["details"]
            ],
        )

    @router.get("/archive/status", response_model=ArchiveStatusResponse)
    async def get_archive_status(log_id: str):
        """查询归档状态."""
        audit_repository = get_audit_repository()
        try:
            log_uuid = UUID(log_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid log_id format",
            )

        result = await audit_repository.get_archive_status(log_uuid)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit log not found",
            )

        return ArchiveStatusResponse(
            log_id=result["log_id"],
            archived=result["archived"],
            archived_at=datetime.fromisoformat(result["archived_at"]) if result.get("archived_at") else None,
            retention_days=result.get("retention_days", 2555),
        )

    @router.post("/archive", response_model=ArchiveResponse)
    async def archive_logs(request: ArchiveRequest):
        """手动归档审计日志.

        归档超过指定天数的审计日志到 WORM 存储
        """
        audit_service = get_audit_service()

        count = await audit_service.archive(older_than_days=request.older_than_days)

        return ArchiveResponse(archived_count=count)

    return router
