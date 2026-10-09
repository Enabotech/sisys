"""基础设施层错误案例 PostgreSQL 仓储（Story 4.7 AC-5）

PostgreSQLErrorCaseRepository——自然键精确查询 + 幂等计数回填。

并发 upsert 容错（4-6 CR1-4 教训）：UNIQUE 冲突 flush 后 session 进
PendingRollback，须 begin_nested() SAVEPOINT 包裹冲突段，回滚 SAVEPOINT 后
重读既有行做增量合并。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.domain.entities.error_case import ErrorCase
from src.domain.exceptions import StorageError
from src.domain.ports.error_case_repository import ErrorCaseRepositoryPort
from src.domain.value_objects.validation_feedback import FeedbackOutcome
from src.infrastructure.storage.postgresql.models.error_case import ErrorCaseModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import (
    PostgreSQLAdapter,
)

__all__ = ["PostgreSQLErrorCaseRepository"]


class PostgreSQLErrorCaseRepository(PostgreSQLAdapter[ErrorCase, ErrorCaseModel], ErrorCaseRepositoryPort):
    """错误案例 PostgreSQL 仓储（migration 017 主实现）。"""

    pk_column = "case_id"

    def __init__(self) -> None:
        """初始化仓储（绑定 ErrorCaseModel）。"""
        super().__init__(ErrorCaseModel)

    # ---- ORM 转换钩子 ----

    def _to_entity(self, model: ErrorCaseModel) -> ErrorCase:
        """ORM 模型 → 领域实体。"""
        return ErrorCase(
            case_id=model.case_id,
            tenant_id=model.tenant_id,
            tool_id=model.tool_id,
            error_signature=model.error_signature,
            error_category=model.error_category,
            stderr_excerpt=model.stderr_excerpt or "",
            fix_summary=model.fix_summary or "",
            outcome=FeedbackOutcome(model.outcome),
            recovered_count=model.recovered_count,
            infeasible_count=model.infeasible_count,
            occurrence_count=model.occurrence_count,
            last_seen_at=model.last_seen_at,
            created_at=model.created_at,
        )

    def _to_model(self, entity: ErrorCase) -> ErrorCaseModel:
        """领域实体 → ORM 模型。"""
        return ErrorCaseModel(
            case_id=entity.case_id,
            tenant_id=entity.tenant_id,
            tool_id=entity.tool_id,
            error_signature=entity.error_signature,
            error_category=entity.error_category,
            stderr_excerpt=(entity.stderr_excerpt or "")[:2000],
            fix_summary=(entity.fix_summary or "")[:2000],
            outcome=entity.outcome.value,
            recovered_count=entity.recovered_count,
            infeasible_count=entity.infeasible_count,
            occurrence_count=entity.occurrence_count,
            last_seen_at=entity.last_seen_at,
            created_at=entity.created_at,
        )

    # ---- 端口方法 ----

    async def get_by_natural_key(
        self,
        tenant_id: uuid.UUID,
        tool_id: uuid.UUID,
        error_signature: str,
    ) -> ErrorCase | None:
        """按自然键精确查询。"""
        stmt = select(ErrorCaseModel).where(
            ErrorCaseModel.tenant_id == tenant_id,
            ErrorCaseModel.tool_id == tool_id,
            ErrorCaseModel.error_signature == error_signature,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model is not None else None

    async def record_case(self, case: ErrorCase) -> ErrorCase:
        """记录案例（自然键 upsert 幂等计数——增量累加语义见端口 docstring）.

        Raises:
            StorageError: SAVEPOINT 重读后仍异常（不可恢复的存储故障）
        """
        try:
            async with self._session.begin_nested():
                existing = await self.get_by_natural_key(case.tenant_id, case.tool_id, case.error_signature)
                if existing is None:
                    self._session.add(self._to_model(case))
                    await self._session.flush()
                    return case
                merged = self._merge_existing(existing, case)
                await self._update_existing(merged)
                return merged
        except IntegrityError:
            # UNIQUE 冲突（并发对手已建行）：SAVEPOINT 已回滚，重读合并
            try:
                async with self._session.begin_nested():
                    existing = await self.get_by_natural_key(case.tenant_id, case.tool_id, case.error_signature)
                    if existing is None:
                        raise StorageError(
                            message="error_cases UNIQUE 冲突后重读仍无行（数据不一致）",
                        ) from None
                    merged = self._merge_existing(existing, case)
                    await self._update_existing(merged)
                    return merged
            except IntegrityError as exc:
                raise StorageError(
                    message="error_cases 并发回填重试仍冲突",
                    cause=exc,
                ) from exc

    # ---- 内部辅助 ----

    def _merge_existing(self, existing: ErrorCase, case: ErrorCase) -> ErrorCase:
        """增量合并（分类计数累加 + occurrence 守恒 + outcome/fix_summary 覆写规则）."""
        recovered = existing.recovered_count + case.recovered_count
        infeasible = existing.infeasible_count + case.infeasible_count
        fix_summary = case.fix_summary if case.outcome == FeedbackOutcome.RECOVERED else existing.fix_summary
        return ErrorCase(
            case_id=existing.case_id,
            tenant_id=existing.tenant_id,
            tool_id=existing.tool_id,
            error_signature=existing.error_signature,
            error_category=existing.error_category,  # 首写定格
            stderr_excerpt=existing.stderr_excerpt,
            fix_summary=fix_summary,
            outcome=case.outcome,
            recovered_count=recovered,
            infeasible_count=infeasible,
            occurrence_count=recovered + infeasible,
            last_seen_at=datetime.now(UTC),
            created_at=existing.created_at,
        )

    async def _update_existing(self, merged: ErrorCase) -> None:
        """按主键更新既有行。"""
        from sqlalchemy import update

        stmt = (
            update(ErrorCaseModel)
            .where(ErrorCaseModel.case_id == merged.case_id)
            .values(
                fix_summary=merged.fix_summary,
                outcome=merged.outcome.value,
                recovered_count=merged.recovered_count,
                infeasible_count=merged.infeasible_count,
                occurrence_count=merged.occurrence_count,
                last_seen_at=merged.last_seen_at,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
