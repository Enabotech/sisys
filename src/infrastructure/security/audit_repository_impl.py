"""基础设施层审计仓储模块

基于 SQLAlchemy 异步实现 AuditRepositoryPort 接口，提供审计日志的持久化存储和查询
Session 通过 ContextVar 由 middleware 或 test fixture 提供，无需构造器注入
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ports.audit_repository import (
    AuditRepositoryPort,
    AuditSearchCriteria,
    AuditSearchResult,
)
from src.infrastructure.storage.postgresql.models.audit import AuditLogModel
from src.infrastructure.storage.postgresql.session_context import get_session


class AuditRepository(AuditRepositoryPort):
    """审计仓储实现，基于 SQLAlchemy 异步持久化审计日志

    Attributes:
        _session: 通过 ContextVar 获取的 SQLAlchemy 异步会话
    """

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    async def save(self, audit_data: dict[str, Any]) -> UUID:
        """保存审计日志.

        Args:
            audit_data: 审计日志数据字典

        Returns:
            UUID 保存的审计日志 ID
        """
        # 从 audit_data 中提取字段
        log_id = UUID(audit_data["log_id"])
        timestamp = datetime.fromisoformat(audit_data["timestamp"])
        actor = audit_data.get("actor", "")
        action_type = audit_data.get("action_type", "")
        target_resource = audit_data.get("target_resource", "")
        old_value = audit_data.get("old_value", {})
        new_value = audit_data.get("new_value", {})
        correction_level = audit_data.get("correction_level")
        checksum = audit_data.get("checksum", "")
        correlation_id = audit_data.get("correlation_id")
        archived = audit_data.get("archived", False)
        archived_at = audit_data.get("archived_at")
        if archived_at and isinstance(archived_at, str):
            archived_at = datetime.fromisoformat(archived_at)

        # 创建模型实例
        audit_log = AuditLogModel(
            log_id=log_id,
            timestamp=timestamp,
            actor=actor,
            action_type=action_type,
            target_resource=target_resource,
            old_value=old_value,
            new_value=new_value,
            correction_level=correction_level,
            checksum=checksum,
            correlation_id=correlation_id,
            archived=archived,
            archived_at=archived_at,
        )

        self._session.add(audit_log)
        await self._session.flush()
        return log_id

    async def get_by_id(self, log_id: UUID) -> dict[str, Any] | None:
        """根据 ID 获取审计日志.

        Args:
            log_id: 审计日志 UUID

        Returns:
            dict 审计日志数据，或 None
        """
        result = await self._session.execute(select(AuditLogModel).where(AuditLogModel.log_id == log_id))
        audit_log = result.scalar_one_or_none()
        if audit_log is None:
            return None
        return audit_log.to_dict()

    async def search(self, criteria: AuditSearchCriteria) -> AuditSearchResult:
        """搜索审计日志.

        Args:
            criteria: 搜索条件

        Returns:
            AuditSearchResult 包含 items, total, offset, limit
        """
        # 构建查询条件
        conditions = []

        if criteria.start_time:
            conditions.append(AuditLogModel.timestamp >= criteria.start_time)
        if criteria.end_time:
            conditions.append(AuditLogModel.timestamp <= criteria.end_time)
        if criteria.actor:
            conditions.append(AuditLogModel.actor == criteria.actor)
        if criteria.action_type:
            conditions.append(AuditLogModel.action_type.like(f"%{criteria.action_type}%"))
        if criteria.target_resource:
            conditions.append(AuditLogModel.target_resource.like(f"%{criteria.target_resource}%"))

        # 构建基础查询
        query = select(AuditLogModel)
        if conditions:
            if criteria.match_any:
                query = query.where(or_(*conditions))
            else:
                query = query.where(and_(*conditions))

        # 获取总数
        count_query = select(AuditLogModel)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        count_result = await self._session.execute(count_query)
        total = len(count_result.scalars().all())

        # 应用分页和排序
        query = query.order_by(AuditLogModel.timestamp.desc())
        query = query.offset(criteria.offset).limit(criteria.limit)

        # 执行查询
        result = await self._session.execute(query)
        audit_logs = result.scalars().all()

        items = tuple(audit_log.to_dict() for audit_log in audit_logs)

        return AuditSearchResult(
            items=items,
            total=total,
            offset=criteria.offset,
            limit=criteria.limit,
        )

    async def update_archive_status(
        self,
        log_id: UUID,
        archived: bool,
        archived_at: datetime | None = None,
    ) -> bool:
        """更新归档状态.

        Args:
            log_id: 审计日志 UUID
            archived: 是否已归档
            archived_at: 归档时间

        Returns:
            True 如果更新成功
        """
        result = await self._session.execute(select(AuditLogModel).where(AuditLogModel.log_id == log_id))
        audit_log = result.scalar_one_or_none()
        if audit_log is None:
            return False

        audit_log.archived = archived
        if archived_at:
            audit_log.archived_at = archived_at

        await self._session.flush()
        return True

    async def get_archive_status(self, log_id: UUID) -> dict[str, Any] | None:
        """获取归档状态.

        Args:
            log_id: 审计日志 UUID

        Returns:
            dict 包含 archived, archived_at 等字段，或 None
        """
        result = await self._session.execute(select(AuditLogModel).where(AuditLogModel.log_id == log_id))
        audit_log = result.scalar_one_or_none()
        if audit_log is None:
            return None

        return {
            "log_id": str(audit_log.log_id),
            "archived": audit_log.archived,
            "archived_at": audit_log.archived_at.isoformat() if audit_log.archived_at else None,
            "retention_days": 2555,
        }
