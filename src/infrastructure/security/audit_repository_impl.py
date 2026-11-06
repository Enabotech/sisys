"""基础设施层审计仓储模块

基于 SQLAlchemy 异步实现 AuditRepositoryPort 接口，提供审计日志的持久化存储和查询
Session 通过 ContextVar 由 middleware 或 test fixture 提供，无需构造器注入
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.ports.audit_repository import (
    AuditRepositoryPort,
    AuditSearchCriteria,
    AuditSearchResult,
)
from src.infrastructure.storage.postgresql.models.audit import AuditLogModel
from src.infrastructure.storage.postgresql.session_context import get_session, session_context

logger = logging.getLogger(__name__)


class AuditRepository(AuditRepositoryPort):
    """审计仓储实现，基于 SQLAlchemy 异步持久化审计日志

    Attributes:
        _session: 通过 ContextVar 获取的 SQLAlchemy 异步会话
        _session_factory: fallback 独立会话工厂（CLI/后台路径——save 专用；
            None 时无 ContextVar session 则 RuntimeError 上抛，配置缺失显式失败）
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        """构造器.

        Args:
            session_factory: fallback 独立会话工厂（isolation_switch_log_repository
                DC-5 双模式同款——CLI set-isolation 路径无 ContextVar session 时
                经工厂走独立会话 commit，消除 MVP 唯一运行通道的 audit 联动
                结构性 100% 降级[核销 R2 批 K10]）。
        """
        self._session_factory = session_factory

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

        # 双模式写入（核销 R2 批 K10——isolation_switch_log_repository DC-5 模板）：
        # 请求路径（ContextVar session）add+flush 随主事务；CLI/后台路径无请求
        # session 时经注入工厂走独立会话 commit。save 与 search 两面均带 fallback
        # （search 的 fallback 为 Story 6-8 新增——executive-view CLI 消费面是
        # search 的首个非 HTTP 消费方；get_by_id/update/get_archive 三方法消费方
        # 均为 HTTP 路由，middleware 恒有 session，维持请求路径单模式）。
        try:
            session = get_session()
        except RuntimeError:
            if self._session_factory is None:
                raise
            async with session_context(self._session_factory):
                independent = get_session()
                independent.add(audit_log)
                await independent.flush()
            logger.info("审计日志经独立会话落库（CLI/后台路径 fallback）: log_id=%s", log_id)
            return log_id

        session.add(audit_log)
        await session.flush()
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
        """搜索审计日志（双模式分派——Story 6-8 executive-view CLI 消费面激活）.

        请求路径（ContextVar session）经 self._session 查询；CLI/后台路径无请求
        session 时经注入工厂走独立会话（镜像 save 双模式与 report get_latest
        fallback 先例——无 fallback 则 CLI 面审计段恒降级，AC-6 生产可用性）.

        Args:
            criteria: 搜索条件

        Returns:
            AuditSearchResult 包含 items, total, offset, limit

        Raises:
            RuntimeError: 无请求 session 且无注入工厂（fail-loud——不吞为空结果）.
        """
        try:
            get_session()
        except RuntimeError:
            if self._session_factory is None:
                raise
            async with session_context(self._session_factory):
                return await self._do_search(criteria)
        return await self._do_search(criteria)

    async def _do_search(self, criteria: AuditSearchCriteria) -> AuditSearchResult:
        """搜索查询体（session 无关——search 双模式共用的单实现）.

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
