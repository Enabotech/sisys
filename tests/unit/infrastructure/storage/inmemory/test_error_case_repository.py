"""Story 4.7: InMemory 错误案例仓储单元测试.

覆盖 get_by_natural_key 精确查询 / record_case 自然键 upsert 幂等计数
（recovered/infeasible 分类计数 + occurrence 守恒）/ 深拷贝隔离（4-6 CR1-2）。

TDD 红→绿：本文件先于端口与 InMemory 实现（Subtask 4.1）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.error_case import ErrorCase
from src.domain.value_objects.validation_feedback import FeedbackOutcome
from src.infrastructure.storage.inmemory.error_case_repository import InMemoryErrorCaseRepository

_SIG = "e" * 64


def _make_case(
    tenant_id: uuid.UUID,
    tool_id: uuid.UUID,
    signature: str = _SIG,
    *,
    outcome: str = "RECOVERED",
    fix_summary: str = "",
    recovered: int = 1,
    infeasible: int = 0,
) -> ErrorCase:
    """构造回填形态案例（分类计数为本次增量、occurrence=合计——R3-2 定谳形态）."""
    return ErrorCase(
        tenant_id=tenant_id,
        tool_id=tool_id,
        error_signature=signature,
        error_category="SCHEMA_VIOLATION",
        stderr_excerpt="err",
        fix_summary=fix_summary,
        outcome=FeedbackOutcome(outcome),
        recovered_count=recovered,
        infeasible_count=infeasible,
        occurrence_count=recovered + infeasible,
        last_seen_at=datetime.now(UTC),
    )


class TestGetByNaturalKey:
    """精确查询面（V1 语义：自然键 UNIQUE 下至多 1 行）."""

    @pytest.mark.asyncio
    async def test_miss_returns_none(self) -> None:
        """无命中返回 None."""
        repo = InMemoryErrorCaseRepository()
        result = await repo.get_by_natural_key(uuid.uuid4(), uuid.uuid4(), _SIG)
        assert result is None

    @pytest.mark.asyncio
    async def test_exact_hit(self) -> None:
        """精确命中返回案例."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryErrorCaseRepository()
        await repo.record_case(_make_case(tenant, tool))
        result = await repo.get_by_natural_key(tenant, tool, _SIG)
        assert result is not None
        assert result.error_signature == _SIG

    @pytest.mark.asyncio
    async def test_signature_must_match_exactly(self) -> None:
        """签名差一字符即不命中（精确匹配非前缀）."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryErrorCaseRepository()
        await repo.record_case(_make_case(tenant, tool))
        assert await repo.get_by_natural_key(tenant, tool, "f" * 64) is None

    @pytest.mark.asyncio
    async def test_tenant_isolation(self) -> None:
        """跨租户不命中."""
        tool = uuid.uuid4()
        repo = InMemoryErrorCaseRepository()
        await repo.record_case(_make_case(uuid.uuid4(), tool))
        assert await repo.get_by_natural_key(uuid.uuid4(), tool, _SIG) is None


class TestRecordCaseUpsert:
    """自然键 upsert 幂等计数."""

    @pytest.mark.asyncio
    async def test_first_record_creates_row(self) -> None:
        """首记录建行（occurrence=1）."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryErrorCaseRepository()
        result = await repo.record_case(_make_case(tenant, tool, outcome="RECOVERED", fix_summary="配方A"))
        assert result.recovered_count == 1
        assert result.infeasible_count == 0
        assert result.occurrence_count == 1
        assert result.outcome == FeedbackOutcome.RECOVERED

    @pytest.mark.asyncio
    async def test_second_record_increments_no_duplicate(self) -> None:
        """同自然键二次回填：不建重复行，计数递增 + occurrence 守恒."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryErrorCaseRepository()
        await repo.record_case(_make_case(tenant, tool, outcome="RECOVERED", fix_summary="配方A"))
        await repo.record_case(_make_case(tenant, tool, outcome="MARKED_INFEASIBLE", recovered=0, infeasible=1))

        case = await repo.get_by_natural_key(tenant, tool, _SIG)
        assert case is not None
        assert case.recovered_count == 1
        assert case.infeasible_count == 1
        assert case.occurrence_count == 2
        assert case.outcome == FeedbackOutcome.MARKED_INFEASIBLE

    @pytest.mark.asyncio
    async def test_infeasible_backfill_keeps_fix_summary(self) -> None:
        """不可行回填不动 fix_summary（防冲掉修复配方——R1-10）."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryErrorCaseRepository()
        await repo.record_case(_make_case(tenant, tool, outcome="RECOVERED", fix_summary="历史配方"))
        await repo.record_case(_make_case(tenant, tool, outcome="MARKED_INFEASIBLE", recovered=0, infeasible=1))

        case = await repo.get_by_natural_key(tenant, tool, _SIG)
        assert case is not None
        assert case.fix_summary == "历史配方"

    @pytest.mark.asyncio
    async def test_recovered_backfill_overwrites_fix_summary(self) -> None:
        """恢复回填覆写 fix_summary（最近一次成功——R8-20）."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryErrorCaseRepository()
        await repo.record_case(_make_case(tenant, tool, outcome="RECOVERED", fix_summary="旧配方"))
        await repo.record_case(_make_case(tenant, tool, outcome="RECOVERED", fix_summary="新配方"))

        case = await repo.get_by_natural_key(tenant, tool, _SIG)
        assert case is not None
        assert case.fix_summary == "新配方"
        assert case.recovered_count == 2

    @pytest.mark.asyncio
    async def test_last_seen_at_refreshed(self) -> None:
        """回填刷新 last_seen_at."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryErrorCaseRepository()
        first = await repo.record_case(_make_case(tenant, tool))
        import asyncio

        await asyncio.sleep(0.01)
        second = await repo.record_case(_make_case(tenant, tool, outcome="MARKED_INFEASIBLE", recovered=0, infeasible=1))
        assert second.last_seen_at > first.last_seen_at


class TestDeepCopyIsolation:
    """深拷贝防护（4-6 CR1-2：双端副本防共享引用污染）."""

    @pytest.mark.asyncio
    async def test_returned_case_mutation_does_not_leak(self) -> None:
        """调用方修改返回实例不污染仓储内部."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryErrorCaseRepository()
        await repo.record_case(_make_case(tenant, tool, fix_summary="原配方"))

        case = await repo.get_by_natural_key(tenant, tool, _SIG)
        assert case is not None
        case.fix_summary = "被调用方篡改"
        case.recovered_count = 99

        fresh = await repo.get_by_natural_key(tenant, tool, _SIG)
        assert fresh is not None
        assert fresh.fix_summary == "原配方"
        assert fresh.recovered_count == 1
