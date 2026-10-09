"""Story 4.7: InMemory 演进日志仓储单元测试.

覆盖 save 幂等 upsert（execution_id）/ list_by_query 多字段过滤 + 分页 /
get_by_execution 精确查询 / 深拷贝隔离（4-6 CR1-2）。

TDD 红→绿：本文件先于端口与 InMemory 实现（Subtask 4.1）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.evolution_log_entry import EvolutionLogEntry
from src.domain.ports.evolution_log_repository import EvolutionLogQuery
from src.domain.value_objects.validation_feedback import (
    FeedbackOutcome,
    FixAttempt,
    FixStrategy,
    TriggerCode,
)
from src.infrastructure.storage.inmemory.evolution_log_repository import (
    InMemoryEvolutionLogRepository,
)

_SIG = "f" * 64


def _make_attempt(no: int) -> FixAttempt:
    """构造 attempt 记录."""
    return FixAttempt(
        attempt_no=no,
        error_signature=_SIG,
        fix_strategy=FixStrategy.PURE_LLM,
        stderr_excerpt="err",
        suggested_fix_excerpt="方案",
        succeeded=False,
        detail="retry_failed",
    )


def _make_entry(
    tenant_id: uuid.UUID,
    tool_id: uuid.UUID,
    execution_id: uuid.UUID | None = None,
    *,
    attempts: int = 3,
    final: str = "MARKED_INFEASIBLE",
) -> EvolutionLogEntry:
    """构造演进日志（默认 3 attempt 耗尽形态）."""
    return EvolutionLogEntry(
        tenant_id=tenant_id,
        tool_id=tool_id,
        execution_id=execution_id or uuid.uuid4(),
        trigger_code=TriggerCode.EXCEPTION_389,
        error_signature=_SIG,
        enhanced_retry_count=attempts,
        fix_attempts=tuple(_make_attempt(i) for i in range(1, attempts + 1)),
        duration_sec=1.5,
        final_status=FeedbackOutcome(final),
        tool_version="1.0.0",
    )


class TestSaveIdempotentUpsert:
    """save 幂等（execution_id upsert）."""

    @pytest.mark.asyncio
    async def test_save_then_resave_same_execution_single_row(self) -> None:
        """同 execution_id 重复写入不产生重复行."""
        tenant, tool, exec_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        repo = InMemoryEvolutionLogRepository()
        await repo.save(_make_entry(tenant, tool, exec_id))
        await repo.save(_make_entry(tenant, tool, exec_id, final="RECOVERED", attempts=2))

        logs = await repo.list_by_query(EvolutionLogQuery(tool_id=tool, tenant_id=tenant))
        assert len(logs) == 1
        assert logs[0].final_status == FeedbackOutcome.RECOVERED  # 后写覆盖

    @pytest.mark.asyncio
    async def test_different_execution_creates_rows(self) -> None:
        """不同 execution_id 各一行."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryEvolutionLogRepository()
        await repo.save(_make_entry(tenant, tool))
        await repo.save(_make_entry(tenant, tool))
        logs = await repo.list_by_query(EvolutionLogQuery(tool_id=tool))
        assert len(logs) == 2


class TestListByQuery:
    """Query Object 多字段过滤 + 分页."""

    @pytest.mark.asyncio
    async def test_filter_by_tool(self) -> None:
        """按 tool_id 过滤（跨租户聚合视图）."""
        tenant = uuid.uuid4()
        repo = InMemoryEvolutionLogRepository()
        await repo.save(_make_entry(tenant, uuid.uuid4()))
        await repo.save(_make_entry(tenant, uuid.uuid4()))
        await repo.save(_make_entry(uuid.uuid4(), uuid.uuid4()))

        logs = await repo.list_by_query(EvolutionLogQuery(tool_id=None, tenant_id=tenant))
        assert len(logs) == 2

    @pytest.mark.asyncio
    async def test_filter_by_execution(self) -> None:
        """按 execution_id 过滤."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryEvolutionLogRepository()
        target = _make_entry(tenant, tool)
        await repo.save(target)
        await repo.save(_make_entry(tenant, tool))

        logs = await repo.list_by_query(EvolutionLogQuery(execution_id=target.execution_id))
        assert len(logs) == 1
        assert logs[0].execution_id == target.execution_id

    @pytest.mark.asyncio
    async def test_pagination(self) -> None:
        """limit/offset 分页."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryEvolutionLogRepository()
        for _ in range(5):
            await repo.save(_make_entry(tenant, tool))

        page1 = await repo.list_by_query(EvolutionLogQuery(tool_id=tool, limit=2, offset=0))
        page2 = await repo.list_by_query(EvolutionLogQuery(tool_id=tool, limit=2, offset=2))
        assert len(page1) == 2
        assert len(page2) == 2
        page1_ids = {str(e.execution_id) for e in page1}
        page2_ids = {str(e.execution_id) for e in page2}
        assert not (page1_ids & page2_ids)

    @pytest.mark.asyncio
    async def test_ordered_by_created_at_desc(self) -> None:
        """按 created_at 降序（最近在前——反馈历史观测习惯）."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryEvolutionLogRepository()
        first = _make_entry(tenant, tool)
        first.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        second = _make_entry(tenant, tool)
        await repo.save(first)
        await repo.save(second)

        logs = await repo.list_by_query(EvolutionLogQuery(tool_id=tool))
        assert logs[0].execution_id == second.execution_id


class TestGetByExecution:
    """execution_id 精确查询."""

    @pytest.mark.asyncio
    async def test_hit(self) -> None:
        """命中返回日志."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryEvolutionLogRepository()
        entry = _make_entry(tenant, tool)
        await repo.save(entry)

        found = await repo.get_by_execution(entry.execution_id, tenant)
        assert found is not None
        assert str(found.execution_id) == str(entry.execution_id)

    @pytest.mark.asyncio
    async def test_miss_returns_none(self) -> None:
        """未命中返回 None."""
        repo = InMemoryEvolutionLogRepository()
        assert await repo.get_by_execution(uuid.uuid4(), uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_tenant_isolation(self) -> None:
        """跨租户不可见."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryEvolutionLogRepository()
        entry = _make_entry(tenant, tool)
        await repo.save(entry)
        assert await repo.get_by_execution(entry.execution_id, uuid.uuid4()) is None


class TestDeepCopyIsolation:
    """深拷贝防护."""

    @pytest.mark.asyncio
    async def test_returned_entry_mutation_does_not_leak(self) -> None:
        """调用方修改返回实例不污染仓储."""
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        repo = InMemoryEvolutionLogRepository()
        entry = _make_entry(tenant, tool)
        await repo.save(entry)

        found = await repo.get_by_execution(entry.execution_id, tenant)
        assert found is not None
        found.duration_sec = 999.0
        found.final_status = FeedbackOutcome.RECOVERED

        fresh = await repo.get_by_execution(entry.execution_id, tenant)
        assert fresh is not None
        assert fresh.duration_sec == 1.5
        assert fresh.final_status == FeedbackOutcome.MARKED_INFEASIBLE
