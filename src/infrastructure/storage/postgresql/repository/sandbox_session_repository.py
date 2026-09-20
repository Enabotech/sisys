"""基础设施层 PostgreSQL SandboxSession 仓储模块

Story 4.4 — Docker 沙箱执行。

实现 SandboxSessionRepositoryPort 端口，使用 PostgreSQL 持久化沙箱会话。
对应 sandbox_sessions 表（migration 015），3 索引：
- (tenant_id, state) 复合索引
- (state, last_activity_at) 复合索引
- container_id UNIQUE 索引

设计决策：
- **不继承 PostgreSQLAdapter[L2RdbPort]**（主键字符串，与 L2RdbPort 的 UUID 主键约束冲突）
- **直接实现 SandboxSessionRepositoryPort**，独立管理 session_context
- 与既有项目惯例一致（4.1a/4.2/4.3 仓储都用 Postgres 实现）

参考样板：src/infrastructure/storage/postgresql/repository/schema_validation_record_repository.py
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import func, select

from src.domain.entities.sandbox_session import SandboxSession, SandboxSessionState
from src.domain.exceptions import EntityStateTransitionError, InvalidStateError
from src.domain.ports.sandbox_session_repository import (
    SandboxSessionQuery,
    SandboxSessionRepositoryPort,
)
from src.infrastructure.storage.postgresql.models.sandbox_session import SandboxSessionModel
from src.infrastructure.storage.postgresql.session_context import get_session

logger = logging.getLogger(__name__)

_VALID_STATES: frozenset[str] = frozenset({"RUNNING", "TERMINATED", "FAILED"})


class PostgreSQLSandboxSessionRepository(SandboxSessionRepositoryPort):
    """PostgreSQL 沙箱会话仓储

    实现 SandboxSessionRepositoryPort 全部 7 个方法：
    - get_by_session_id (按字符串主键查询)
    - save (乐观锁 CAS — 仅 state_version 回退报错)
    - delete_by_session_id
    - list_all
    - find_by_query (SandboxSessionQuery 多字段)
    - list_idle_sessions (last_activity_at < threshold)
    - count_active (state == RUNNING)

    Session 通过 ContextVar 自动注入（与既有 Postgres 仓储一致）
    """

    def __init__(self) -> None:
        self._model_class = SandboxSessionModel

    @property
    def _session(self) -> Any:
        """从 ContextVar 获取 AsyncSession"""
        try:
            return get_session()
        except RuntimeError as exc:
            raise InvalidStateError(
                "PostgreSQLSandboxSessionRepository requires an active AsyncSession. "
                "Ensure SessionMiddleware or session_context() is active."
            ) from exc

    # ------------------------------------------------------------------
    # 实体/模型转换
    # ------------------------------------------------------------------

    def _to_entity(self, model: SandboxSessionModel) -> SandboxSession:
        """ORM 模型 → 领域实体"""
        if model.state not in _VALID_STATES:
            logger.warning(
                "Invalid state %r in DB for sandbox_session %s, defaulting to RUNNING",
                model.state,
                model.session_id,
            )
            state_str: SandboxSessionState = "RUNNING"
        else:
            # ORM model.state is str; validated by SandboxSession.__post_init__
            state_str = cast("SandboxSessionState", model.state)
        # state 字段为 Literal["RUNNING", "TERMINATED", "FAILED"]
        return SandboxSession(
            session_id=model.session_id,
            tenant_id=model.tenant_id,
            container_id=model.container_id,
            image_digest=model.image_digest or "",
            started_at=model.started_at,
            last_activity_at=model.last_activity_at,
            terminated_at=model.terminated_at,
            resource_limits=model.resource_limits or {},
            state=state_str,
            state_version=model.state_version,
        )

    def _to_model(self, entity: SandboxSession) -> SandboxSessionModel:
        """领域实体 → ORM 模型（save 前构造新实例用于 merge）"""
        return SandboxSessionModel(
            session_id=entity.session_id,
            tenant_id=entity.tenant_id,
            container_id=entity.container_id,
            image_digest=entity.image_digest,
            started_at=entity.started_at,
            last_activity_at=entity.last_activity_at,
            terminated_at=entity.terminated_at,
            resource_limits=dict(entity.resource_limits),
            state=entity.state,
            state_version=entity.state_version,
        )

    # ------------------------------------------------------------------
    # SandboxSessionRepositoryPort 实现
    # ------------------------------------------------------------------

    async def get_by_session_id(self, session_id: str) -> SandboxSession | None:
        """按 session_id 主键查询"""
        stmt = select(self._model_class).where(self._model_class.session_id == session_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, session: SandboxSession) -> SandboxSession:
        """保存会话（insert or update，乐观锁 CAS）

        若已存在 session_id 且 state_version 回退（新 < 旧），抛 EntityStateTransitionError。
        state_version 自增（with_activity_updated/with_terminated 内部 +1）视为合法状态变更。
        """
        existing = await self.get_by_session_id(session.session_id)
        if existing is not None and existing.state_version > session.state_version:
            raise EntityStateTransitionError(
                from_status=f"v{existing.state_version}",
                to_status=f"v{session.state_version}",
                message=(
                    f"state_version regression for session {session.session_id} "
                    f"(existing=v{existing.state_version}, new=v{session.state_version})"
                ),
                entity_type="SandboxSession",
                entity_id=session.session_id,
            )
        # 使用 merge 实现 INSERT-or-UPDATE 语义（与 PostgreSQLAdapter 一致）
        model = self._to_model(session)
        merged = await self._session.merge(model)
        await self._session.flush()
        await self._session.refresh(merged)
        return self._to_entity(merged)

    async def delete_by_session_id(self, session_id: str) -> None:
        """按 session_id 删除"""
        stmt = select(self._model_class).where(self._model_class.session_id == session_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def list_all(self) -> list[SandboxSession]:
        """列出所有会话"""
        stmt = select(self._model_class).order_by(self._model_class.started_at.desc())
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_query(self, query: SandboxSessionQuery) -> list[SandboxSession]:
        """通过 SandboxSessionQuery 多字段查询"""
        stmt = select(self._model_class)
        if query.tenant_id is not None:
            stmt = stmt.where(self._model_class.tenant_id == query.tenant_id)
        if query.state is not None:
            stmt = stmt.where(self._model_class.state == query.state)
        if query.idle_threshold is not None:
            # 命中 (state, last_activity_at) 复合索引
            stmt = stmt.where(
                cast("Any", self._model_class).state == "RUNNING",
                cast("Any", self._model_class).last_activity_at < query.idle_threshold,
            )
        stmt = stmt.order_by(self._model_class.started_at.desc()).offset(query.offset).limit(query.limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_idle_sessions(self, threshold: datetime) -> list[SandboxSession]:
        """列出空闲会话（last_activity_at < threshold 且 state == RUNNING）

        命中 (state, last_activity_at) 复合索引
        """
        stmt = (
            select(self._model_class)
            .where(
                cast("Any", self._model_class).state == "RUNNING",
                cast("Any", self._model_class).last_activity_at < threshold,
            )
            .order_by(self._model_class.last_activity_at.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_active(self, tenant_id: uuid.UUID | None = None) -> int:
        """统计活跃会话数（state == RUNNING）

        命中 (tenant_id, state) 复合索引
        """
        stmt = select(func.count()).select_from(self._model_class).where(cast("Any", self._model_class).state == "RUNNING")
        if tenant_id is not None:
            stmt = stmt.where(self._model_class.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)


__all__ = ["PostgreSQLSandboxSessionRepository"]
