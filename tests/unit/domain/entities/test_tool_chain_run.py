"""ToolChainRun 聚合根单元测试（Story 4.2 AC-4）

测试覆盖：
1. ToolChainRun 13 字段 + NodeRunStatus 6 字段 + CostAudit 8 字段
2. ToolChainRunState 5 值（PENDING/RUNNING/COMPLETED/COMPLETED_WITH_ERRORS/FAILED）
3. VALID_TRANSITIONS 矩阵（4 主链边 + 3 终态）
4. transition_to() 合法迁移 + 非法迁移抛 EntityStateTransitionError
5. 终态必有 completed_at + 非终态 completed_at 为 None
6. 非法迁移计数（state_version 乐观锁递增）
"""

from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities.tool_chain import FailureStrategy
from src.domain.entities.tool_chain_run import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    CostAudit,
    NodeRunStatus,
    ToolChainRun,
    ToolChainRunState,
)
from src.domain.exceptions import EntityStateTransitionError, EntityValidationError

# ============================================================================
# 工厂函数
# ============================================================================


def _make_run(
    state: ToolChainRunState = ToolChainRunState.PENDING,
    completed_at: datetime | None = None,
) -> ToolChainRun:
    """构造 ToolChainRun 测试实例"""
    started = datetime.now(UTC)
    if completed_at is None and state in TERMINAL_STATES:
        completed_at = started + timedelta(seconds=10)
    return ToolChainRun(
        chain_run_id=uuid.uuid4(),
        chain_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        state=state,
        started_at=started,
        completed_at=completed_at,
        failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
        cost_audit={},
    )


# ============================================================================
# 1. 字段完整性
# ============================================================================


def test_tool_chain_run_has_thirteen_init_fields() -> None:
    """ToolChainRun 13 init 字段"""
    field_names = {f.name for f in fields(ToolChainRun) if f.init}
    expected = {
        "chain_run_id",
        "chain_id",
        "tenant_id",
        "state",
        "started_at",
        "completed_at",
        "node_runs",
        "failed_nodes",
        "total_duration_sec",
        "critical_path_sec",
        "parallel_speedup_ratio",
        "failure_strategy",
        "cost_audit",
        "state_version",
    }
    assert field_names == expected


def test_node_run_status_has_six_fields() -> None:
    """NodeRunStatus 6 字段"""
    field_names = {f.name for f in fields(NodeRunStatus)}
    expected = {
        "node_id",
        "state",
        "started_at",
        "completed_at",
        "error",
        "tool_result",
    }
    assert field_names == expected


def test_cost_audit_has_eight_fields() -> None:
    """CostAudit 8 字段"""
    field_names = {f.name for f in fields(CostAudit)}
    expected = {
        "llm_prompt_tokens",
        "llm_completion_tokens",
        "llm_total_tokens",
        "sandbox_duration_sec",
        "api_calls",
        "parallel_speedup_ratio",
        "critical_path_sec",
        "wall_clock_sec",
    }
    assert field_names == expected


def test_cost_audit_to_dict() -> None:
    """CostAudit.to_dict() 序列化为 dict（兼容 ToolChainExecuted.cost_audit）"""
    audit = CostAudit(
        llm_prompt_tokens=100,
        llm_completion_tokens=50,
        llm_total_tokens=150,
        sandbox_duration_sec=1.5,
        api_calls=3,
        parallel_speedup_ratio=2.0,
        critical_path_sec=10.0,
        wall_clock_sec=5.0,
    )
    d = audit.to_dict()
    assert d["llm_prompt_tokens"] == 100
    assert d["parallel_speedup_ratio"] == 2.0


# ============================================================================
# 2. ToolChainRunState 5 值
# ============================================================================


def test_tool_chain_run_state_has_five_values() -> None:
    """ToolChainRunState 5 值（无 CANCELLED）"""
    assert len(ToolChainRunState) == 5
    assert ToolChainRunState.PENDING.value == "PENDING"
    assert ToolChainRunState.RUNNING.value == "RUNNING"
    assert ToolChainRunState.COMPLETED.value == "COMPLETED"
    assert ToolChainRunState.COMPLETED_WITH_ERRORS.value == "COMPLETED_WITH_ERRORS"
    assert ToolChainRunState.FAILED.value == "FAILED"


# ============================================================================
# 3. 状态机迁移矩阵
# ============================================================================


def test_valid_transitions_matrix() -> None:
    """VALID_TRANSITIONS 矩阵：4 主链边 + 3 终态 set()"""
    # PENDING → {RUNNING}
    assert VALID_TRANSITIONS[ToolChainRunState.PENDING] == {ToolChainRunState.RUNNING}
    # RUNNING → {COMPLETED, COMPLETED_WITH_ERRORS, FAILED}
    assert VALID_TRANSITIONS[ToolChainRunState.RUNNING] == {
        ToolChainRunState.COMPLETED,
        ToolChainRunState.COMPLETED_WITH_ERRORS,
        ToolChainRunState.FAILED,
    }
    # 终态无迁移
    assert VALID_TRANSITIONS[ToolChainRunState.COMPLETED] == set()
    assert VALID_TRANSITIONS[ToolChainRunState.COMPLETED_WITH_ERRORS] == set()
    assert VALID_TRANSITIONS[ToolChainRunState.FAILED] == set()


def test_terminal_states_set() -> None:
    """TERMINAL_STATES 包含 COMPLETED / COMPLETED_WITH_ERRORS / FAILED"""
    assert TERMINAL_STATES == frozenset(
        {
            ToolChainRunState.COMPLETED,
            ToolChainRunState.COMPLETED_WITH_ERRORS,
            ToolChainRunState.FAILED,
        }
    )


# ============================================================================
# 4. transition_to 行为
# ============================================================================


def test_transition_pending_to_running() -> None:
    """合法迁移 PENDING → RUNNING"""
    run = _make_run(state=ToolChainRunState.PENDING)
    initial_version = run.state_version
    run.transition_to(ToolChainRunState.RUNNING)
    assert run.state == ToolChainRunState.RUNNING
    assert run.state_version == initial_version + 1


def test_transition_running_to_completed() -> None:
    """合法迁移 RUNNING → COMPLETED"""
    run = _make_run(state=ToolChainRunState.RUNNING)
    run.transition_to(ToolChainRunState.COMPLETED)
    assert run.state == ToolChainRunState.COMPLETED


def test_transition_running_to_completed_with_errors() -> None:
    """合法迁移 RUNNING → COMPLETED_WITH_ERRORS"""
    run = _make_run(state=ToolChainRunState.RUNNING)
    run.transition_to(ToolChainRunState.COMPLETED_WITH_ERRORS)
    assert run.state == ToolChainRunState.COMPLETED_WITH_ERRORS


def test_transition_running_to_failed() -> None:
    """合法迁移 RUNNING → FAILED"""
    run = _make_run(state=ToolChainRunState.RUNNING)
    run.transition_to(ToolChainRunState.FAILED)
    assert run.state == ToolChainRunState.FAILED


def test_transition_pending_to_completed_raises() -> None:
    """非法迁移 PENDING → COMPLETED（跳过 RUNNING）抛 EntityStateTransitionError"""
    run = _make_run(state=ToolChainRunState.PENDING)
    with pytest.raises(EntityStateTransitionError) as exc_info:
        run.transition_to(ToolChainRunState.COMPLETED)
    assert exc_info.value.from_status == "PENDING"
    assert exc_info.value.to_status == "COMPLETED"


def test_transition_completed_to_running_raises() -> None:
    """终态 COMPLETED → RUNNING（反向迁移）抛 EntityStateTransitionError"""
    run = _make_run(state=ToolChainRunState.COMPLETED)
    with pytest.raises(EntityStateTransitionError):
        run.transition_to(ToolChainRunState.RUNNING)


def test_can_transition_to_returns_bool() -> None:
    """can_transition_to 返回 bool"""
    run = _make_run(state=ToolChainRunState.PENDING)
    assert run.can_transition_to(ToolChainRunState.RUNNING) is True
    assert run.can_transition_to(ToolChainRunState.COMPLETED) is False


# ============================================================================
# 5. 终态 completed_at 校验
# ============================================================================


def test_terminal_state_without_completed_at_raises() -> None:
    """终态无 completed_at 触发 EntityValidationError"""
    started = datetime.now(UTC)
    with pytest.raises(EntityValidationError):
        ToolChainRun(
            chain_run_id=uuid.uuid4(),
            chain_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            state=ToolChainRunState.COMPLETED,
            started_at=started,
            completed_at=None,  # 显式 None，绕过 factory 默认填充
            failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
        )


def test_non_terminal_state_with_completed_at_raises() -> None:
    """非终态设了 completed_at 触发 EntityValidationError"""
    with pytest.raises(EntityValidationError):
        _make_run(state=ToolChainRunState.RUNNING, completed_at=datetime.now(UTC))


def test_terminal_state_with_completed_at_ok() -> None:
    """终态 + completed_at 正常构造"""
    run = _make_run(state=ToolChainRunState.COMPLETED)
    assert run.completed_at is not None


# ============================================================================
# 6. 不变量
# ============================================================================


def test_run_frozen() -> None:
    """ToolChainRun frozen 不可变"""
    run = _make_run()
    with pytest.raises(FrozenInstanceError):
        run.state = ToolChainRunState.RUNNING  # type: ignore[misc]


def test_negative_state_version_raises() -> None:
    """state_version < 0 触发 EntityValidationError"""
    with pytest.raises(EntityValidationError) as exc_info:
        ToolChainRun(
            chain_run_id=uuid.uuid4(),
            chain_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            state=ToolChainRunState.PENDING,
            started_at=datetime.now(UTC),
            completed_at=None,
            failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
            cost_audit={},
            state_version=-1,
        )
    assert exc_info.value.context["field"] == "state_version"


def test_default_node_runs_failed_nodes_and_metrics() -> None:
    """默认值正确：node_runs={} / failed_nodes=() / metrics=None"""
    run = _make_run()
    assert run.node_runs == {}
    assert run.failed_nodes == ()
    assert run.total_duration_sec is None
    assert run.critical_path_sec is None
    assert run.parallel_speedup_ratio is None
