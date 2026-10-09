"""内存错误案例库仓储实现（Story 4.7 AC-5）

InMemoryErrorCaseRepository——单测/验收装配用内存实现（生产为 PostgreSQL 实现）。

- 自然键 (tenant_id, tool_id, error_signature) 字典索引——精确查表
- record_case 幂等计数（增量累加 + occurrence 守恒 + outcome/fix_summary 覆写规则）
- 双端深拷贝隔离（4-6 CR1-2：调用方对返回实体的就地改写不污染仓储）
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime

from src.domain.entities.error_case import ErrorCase
from src.domain.ports.error_case_repository import ErrorCaseRepositoryPort
from src.domain.value_objects.validation_feedback import FeedbackOutcome

__all__ = ["InMemoryErrorCaseRepository"]


def _detached(case: ErrorCase) -> ErrorCase:
    """返回与仓储内部存储完全隔离的副本（双端副本纪律）."""
    return copy.deepcopy(case)


class InMemoryErrorCaseRepository(ErrorCaseRepositoryPort):
    """内存错误案例库仓储（自然键索引 + 幂等计数回填）"""

    def __init__(self) -> None:
        """初始化索引结构（自然键 → 案例副本）."""
        self._cases: dict[tuple[uuid.UUID, uuid.UUID, str], ErrorCase] = {}

    async def get_by_natural_key(
        self,
        tenant_id: uuid.UUID,
        tool_id: uuid.UUID,
        error_signature: str,
    ) -> ErrorCase | None:
        """按自然键精确查询（返回深拷贝副本）."""
        case = self._cases.get((tenant_id, tool_id, error_signature))
        return _detached(case) if case is not None else None

    async def record_case(self, case: ErrorCase) -> ErrorCase:
        """记录案例（自然键 upsert 幂等计数——增量累加语义见端口 docstring）."""
        key = (case.tenant_id, case.tool_id, case.error_signature)
        existing = self._cases.get(key)
        if existing is None:
            stored = _detached(case)
        else:
            recovered = existing.recovered_count + case.recovered_count
            infeasible = existing.infeasible_count + case.infeasible_count
            # fix_summary 覆写规则：仅 RECOVERED 回填覆写（R8-20 最近一次成功）；
            # MARKED_INFEASIBLE 不动（R1-10 防冲掉修复配方）
            fix_summary = case.fix_summary if case.outcome == FeedbackOutcome.RECOVERED else existing.fix_summary
            stored = ErrorCase(
                case_id=existing.case_id,
                tenant_id=existing.tenant_id,
                tool_id=existing.tool_id,
                error_signature=existing.error_signature,
                error_category=existing.error_category,  # 首写定格（R9-16）
                stderr_excerpt=existing.stderr_excerpt,
                fix_summary=fix_summary,
                outcome=case.outcome,
                recovered_count=recovered,
                infeasible_count=infeasible,
                occurrence_count=recovered + infeasible,
                last_seen_at=datetime.now(UTC),
                created_at=existing.created_at,
            )
        self._cases[key] = stored
        return _detached(stored)
