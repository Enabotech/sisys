"""基础设施层演进日志 PostgreSQL 仓储（Story 4.7 AC-4）

PostgreSQLEvolutionLogRepository——execution_id 幂等 upsert + 失败历史双查询面。
"""

from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy import select

from src.domain.entities.evolution_log_entry import EvolutionLogEntry
from src.domain.ports.evolution_log_repository import (
    EvolutionLogQuery,
    EvolutionLogRepositoryPort,
)
from src.domain.value_objects.validation_feedback import (
    FeedbackOutcome,
    FixAttempt,
    FixStrategy,
    TriggerCode,
)
from src.infrastructure.storage.postgresql.models.evolution_log_entry import (
    EvolutionLogEntryModel,
)
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import (
    PostgreSQLAdapter,
)

__all__ = ["PostgreSQLEvolutionLogRepository"]


def _attempt_to_dict(attempt: FixAttempt) -> dict:
    """FixAttempt → JSONB 摘要 dict（含 attempt_execution_id 回链）."""
    return {
        "attempt_no": attempt.attempt_no,
        "attempt_execution_id": attempt.attempt_execution_id,
        "error_signature": attempt.error_signature,
        "fix_strategy": attempt.fix_strategy.value,
        "stderr_excerpt": attempt.stderr_excerpt,
        "suggested_fix_excerpt": attempt.suggested_fix_excerpt,
        "succeeded": attempt.succeeded,
        "detail": attempt.detail,
    }


def _attempt_from_dict(data: dict) -> FixAttempt:
    """JSONB 摘要 dict → FixAttempt。"""
    return FixAttempt(
        attempt_no=int(data["attempt_no"]),
        attempt_execution_id=str(data.get("attempt_execution_id", "") or ""),
        error_signature=str(data["error_signature"]),
        fix_strategy=FixStrategy(str(data["fix_strategy"])),
        stderr_excerpt=str(data.get("stderr_excerpt", "") or ""),
        suggested_fix_excerpt=str(data.get("suggested_fix_excerpt", "") or ""),
        succeeded=bool(data.get("succeeded", False)),
        detail=str(data.get("detail", "") or ""),
    )


class PostgreSQLEvolutionLogRepository(
    PostgreSQLAdapter[EvolutionLogEntry, EvolutionLogEntryModel], EvolutionLogRepositoryPort
):
    """演进日志 PostgreSQL 仓储（migration 017 主实现）。"""

    pk_column = "log_id"

    def __init__(self) -> None:
        """初始化仓储（绑定 EvolutionLogEntryModel）。"""
        super().__init__(EvolutionLogEntryModel)

    # ---- ORM 转换钩子 ----

    def _to_entity(self, model: EvolutionLogEntryModel) -> EvolutionLogEntry:
        """ORM 模型 → 领域实体。"""
        return EvolutionLogEntry(
            log_id=model.log_id,
            tenant_id=model.tenant_id,
            tool_id=model.tool_id,
            execution_id=model.execution_id,
            trigger_code=TriggerCode(model.trigger_code),
            error_signature=model.error_signature,
            enhanced_retry_count=model.enhanced_retry_count,
            fix_attempts=tuple(_attempt_from_dict(d) for d in (model.fix_attempts or [])),
            duration_sec=float(model.duration_sec),
            final_status=FeedbackOutcome(model.final_status),
            tool_version=model.tool_version or "",
            created_at=model.created_at,
        )

    def _to_model(self, entity: EvolutionLogEntry) -> EvolutionLogEntryModel:
        """领域实体 → ORM 模型。"""
        return EvolutionLogEntryModel(
            log_id=entity.log_id,
            tenant_id=entity.tenant_id,
            tool_id=entity.tool_id,
            execution_id=entity.execution_id,
            tool_version=entity.tool_version,
            trigger_code=entity.trigger_code.value,
            error_signature=entity.error_signature,
            enhanced_retry_count=entity.enhanced_retry_count,
            fix_attempts=[_attempt_to_dict(a) for a in entity.fix_attempts],
            duration_sec=entity.duration_sec,
            final_status=entity.final_status.value,
            created_at=entity.created_at,
        )

    # ---- 端口方法 ----

    async def save(self, entity: EvolutionLogEntry) -> EvolutionLogEntry:
        """保存日志（execution_id upsert 幂等——引擎 save 语义同款）."""
        stmt = select(EvolutionLogEntryModel).where(
            EvolutionLogEntryModel.tenant_id == entity.tenant_id,
            EvolutionLogEntryModel.execution_id == entity.execution_id,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            self._session.add(self._to_model(entity))
            await self._session.flush()
            return entity
        # upsert 覆盖为最新次（幂等重入）
        from sqlalchemy import update

        update_stmt = (
            update(EvolutionLogEntryModel)
            .where(EvolutionLogEntryModel.log_id == existing.log_id)
            .values(
                tool_version=entity.tool_version,
                trigger_code=entity.trigger_code.value,
                error_signature=entity.error_signature,
                enhanced_retry_count=entity.enhanced_retry_count,
                fix_attempts=[_attempt_to_dict(a) for a in entity.fix_attempts],
                duration_sec=entity.duration_sec,
                final_status=entity.final_status.value,
            )
        )
        await self._session.execute(update_stmt)
        await self._session.flush()
        return entity

    async def list_by_query(self, query: EvolutionLogQuery) -> tuple[EvolutionLogEntry, ...]:
        """按查询条件列出（created_at 降序 + 分页）。"""
        model_cls = cast("type[EvolutionLogEntryModel]", self._model_class)
        stmt = select(model_cls)
        if query.tool_id is not None:
            stmt = stmt.where(model_cls.tool_id == query.tool_id)
        if query.tenant_id is not None:
            stmt = stmt.where(model_cls.tenant_id == query.tenant_id)
        if query.execution_id is not None:
            stmt = stmt.where(model_cls.execution_id == query.execution_id)
        stmt = stmt.order_by(model_cls.created_at.desc())
        stmt = stmt.offset(query.offset).limit(query.limit)
        result = await self._session.execute(stmt)
        return tuple(self._to_entity(m) for m in result.scalars().all())

    async def get_by_execution(
        self,
        execution_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> EvolutionLogEntry | None:
        """按 execution_id 精确定位（租户隔离）。"""
        stmt = select(EvolutionLogEntryModel).where(
            EvolutionLogEntryModel.execution_id == execution_id,
            EvolutionLogEntryModel.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model is not None else None
