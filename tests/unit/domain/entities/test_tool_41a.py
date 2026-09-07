"""Story 4.1a: Tool 实体增强 + ToolExecution 聚合根单元测试

TDD 红→绿→重构循环 A: Tool 4 新字段（rule_version, reliability_score, execution_count, slug）
TDD 红→绿→重构循环 B: ToolExecution 聚合根 + 6 状态机

测试目标（CLAUDE.md §5 单元测试原则）：
- 单元测试 Mock 端口，禁止真实服务
- 覆盖正向/边界/反向场景
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.entities.tool_execution import ToolExecution, ToolExecutionState
from src.domain.exceptions import (
    EntityStateTransitionError,
    EntityValidationError,
)


def _make_tool(**kwargs) -> Tool:
    """工厂函数：构造测试 Tool 实体"""
    defaults: dict = {
        "tool_id": uuid.uuid4(),
        "name": "Test Tool",
        "description": "Test description",
        "category": ToolCategory.ANALYSIS,
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
        "status": ToolStatus.ACTIVE,
        "version": "1.0.0",
    }
    defaults.update(kwargs)
    return Tool(**defaults)


# ============================================================================
# TDD 循环 A: Tool 实体 4 新字段
# ============================================================================


class TestToolNewFields:
    """Tool 实体新增 4 字段测试"""

    def test_tool_has_rule_version_field(self) -> None:
        """Tool 实体应包含 rule_version 字段"""
        tool = _make_tool(rule_version="BLM-v3.2")
        assert tool.rule_version == "BLM-v3.2"

    def test_tool_rule_version_default(self) -> None:
        """rule_version 默认值"""
        tool = _make_tool()
        assert tool.rule_version is None or isinstance(tool.rule_version, str)

    def test_tool_has_reliability_score_field(self) -> None:
        """Tool 实体应包含 reliability_score 字段"""
        tool = _make_tool(reliability_score=0.85)
        assert tool.reliability_score == 0.85

    def test_tool_reliability_score_default_zero(self) -> None:
        """reliability_score 默认值"""
        tool = _make_tool()
        assert tool.reliability_score == 0.0

    def test_tool_reliability_score_must_be_in_range(self) -> None:
        """reliability_score 必须 ∈ [0.0, 1.0]"""
        with pytest.raises(EntityValidationError):
            _make_tool(reliability_score=1.5)
        with pytest.raises(EntityValidationError):
            _make_tool(reliability_score=-0.1)

    def test_tool_has_execution_count_field(self) -> None:
        """Tool 实体应包含 execution_count 字段"""
        tool = _make_tool(execution_count=100)
        assert tool.execution_count == 100

    def test_tool_execution_count_default_zero(self) -> None:
        """execution_count 默认值为 0"""
        tool = _make_tool()
        assert tool.execution_count == 0

    def test_tool_execution_count_must_be_non_negative(self) -> None:
        """execution_count 必须 ≥ 0"""
        with pytest.raises(EntityValidationError):
            _make_tool(execution_count=-1)

    def test_tool_has_slug_field(self) -> None:
        """Tool 实体应包含 slug 字段"""
        tool = _make_tool(slug="pestel-analysis")
        assert tool.slug == "pestel-analysis"

    def test_tool_slug_default_none(self) -> None:
        """slug 默认值为 None（向后兼容）"""
        tool = _make_tool()
        assert tool.slug is None or isinstance(tool.slug, str)

    def test_tool_slug_must_be_kebab_case(self) -> None:
        """slug 必须为 kebab-case 格式（小写 + 连字符）"""
        with pytest.raises(EntityValidationError):
            _make_tool(slug="PestelAnalysis")
        with pytest.raises(EntityValidationError):
            _make_tool(slug="pestel_analysis")
        with pytest.raises(EntityValidationError):
            _make_tool(slug="pestel--analysis")

    def test_tool_slug_optional_no_crash(self) -> None:
        """slug 为 None 时不破坏现有功能"""
        tool = _make_tool(slug=None)
        assert tool.slug is None


class TestToolCatalogBackwardCompatibility:
    """Story 4.1 已注册的 23 个 TOOL_CATALOG 实例不被破坏"""

    def test_existing_tool_constructs_without_new_fields(self) -> None:
        """不带新字段的 Tool 构造必须正常"""
        tool = _make_tool()
        assert tool.tool_id is not None

    def test_existing_tool_validates_pass(self) -> None:
        """不带新字段的 Tool 校验必须通过"""
        tool = _make_tool()
        tool.validate()
        assert True


# ============================================================================
# TDD 循环 B: ToolExecution 聚合根 + 6 状态机
# ============================================================================


def _make_tool_execution(**kwargs) -> ToolExecution:
    """工厂函数：构造测试 ToolExecution 实体"""
    state = kwargs.get("state", ToolExecutionState.IDLE)
    is_terminal = state in {ToolExecutionState.COMPLETED, ToolExecutionState.FAILED}
    defaults: dict = {
        "execution_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "tool_id": uuid.uuid4(),
        "tool_version": "1.0.0",
        "state": state,
        "started_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC) if is_terminal else None,
        "retry_count": 0,
        "failure_reason": None,
        "plan": None,
        "code": None,
        "result": None,
        "observation": None,
        "validation": None,
        "evidence_package": None,
        "state_version": 0,
    }
    defaults.update(kwargs)
    return ToolExecution(**defaults)


class TestToolExecutionState:
    """ToolExecutionState 枚举测试"""

    def test_state_enum_has_six_values(self) -> None:
        """枚举应包含 6 个值"""
        states = {s.value for s in ToolExecutionState}
        assert len(states) == 6

    def test_state_enum_contains_all_states(self) -> None:
        """枚举应包含 IDLE/PLANNING/EXECUTING/VALIDATING/COMPLETED/FAILED"""
        expected = {"IDLE", "PLANNING", "EXECUTING", "VALIDATING", "COMPLETED", "FAILED"}
        actual = {s.name for s in ToolExecutionState}
        assert actual == expected


class TestToolExecutionAggregateRoot:
    """ToolExecution 聚合根字段测试"""

    def test_create_initial_idle(self) -> None:
        """创建初始 IDLE 状态"""
        te = _make_tool_execution()
        assert te.state == ToolExecutionState.IDLE

    def test_required_fields_present(self) -> None:
        """必填字段完整"""
        te = _make_tool_execution()
        assert te.execution_id is not None
        assert te.tenant_id is not None
        assert te.tool_id is not None
        assert te.tool_version is not None
        assert te.started_at is not None
        assert te.state_version >= 0

    def test_retry_count_must_be_non_negative(self) -> None:
        """retry_count 必须 ≥ 0"""
        with pytest.raises(EntityValidationError):
            _make_tool_execution(retry_count=-1)


class TestToolExecutionStateMachine:
    """状态机迁移测试"""

    def test_idle_to_planning_allowed(self) -> None:
        """IDLE → PLANNING 合法"""
        te = _make_tool_execution(state=ToolExecutionState.IDLE)
        te.transition_to(ToolExecutionState.PLANNING)
        assert te.state == ToolExecutionState.PLANNING

    def test_planning_to_executing_allowed(self) -> None:
        """PLANNING → EXECUTING 合法"""
        te = _make_tool_execution(state=ToolExecutionState.PLANNING)
        te.transition_to(ToolExecutionState.EXECUTING)
        assert te.state == ToolExecutionState.EXECUTING

    def test_executing_to_validating_allowed(self) -> None:
        """EXECUTING → VALIDATING 合法"""
        te = _make_tool_execution(state=ToolExecutionState.EXECUTING)
        te.transition_to(ToolExecutionState.VALIDATING)
        assert te.state == ToolExecutionState.VALIDATING

    def test_validating_to_completed_allowed(self) -> None:
        """VALIDATING → COMPLETED 合法"""
        te = _make_tool_execution(state=ToolExecutionState.VALIDATING)
        te.transition_to(ToolExecutionState.COMPLETED)
        assert te.state == ToolExecutionState.COMPLETED

    def test_validating_to_failed_allowed(self) -> None:
        """VALIDATING → FAILED 合法"""
        te = _make_tool_execution(state=ToolExecutionState.VALIDATING)
        te.transition_to(ToolExecutionState.FAILED)
        assert te.state == ToolExecutionState.FAILED

    def test_planning_to_failed_allowed(self) -> None:
        """PLANNING → FAILED 合法（中间态可转 FAILED）"""
        te = _make_tool_execution(state=ToolExecutionState.PLANNING)
        te.transition_to(ToolExecutionState.FAILED)
        assert te.state == ToolExecutionState.FAILED

    def test_executing_to_failed_allowed(self) -> None:
        """EXECUTING → FAILED 合法"""
        te = _make_tool_execution(state=ToolExecutionState.EXECUTING)
        te.transition_to(ToolExecutionState.FAILED)
        assert te.state == ToolExecutionState.FAILED

    def test_idle_to_executing_illegal(self) -> None:
        """IDLE → EXECUTING 非法（跳过中间态）"""
        te = _make_tool_execution(state=ToolExecutionState.IDLE)
        with pytest.raises(EntityStateTransitionError):
            te.transition_to(ToolExecutionState.EXECUTING)

    def test_planning_to_completed_illegal(self) -> None:
        """PLANNING → COMPLETED 非法（跳过 EXECUTING/VALIDATING）"""
        te = _make_tool_execution(state=ToolExecutionState.PLANNING)
        with pytest.raises(EntityStateTransitionError):
            te.transition_to(ToolExecutionState.COMPLETED)

    def test_completed_to_idle_illegal(self) -> None:
        """COMPLETED → IDLE 非法（终态反向）"""
        te = _make_tool_execution(state=ToolExecutionState.COMPLETED)
        with pytest.raises(EntityStateTransitionError):
            te.transition_to(ToolExecutionState.IDLE)

    def test_failed_to_executing_illegal(self) -> None:
        """FAILED → EXECUTING 非法（终态反向）"""
        te = _make_tool_execution(state=ToolExecutionState.FAILED)
        with pytest.raises(EntityStateTransitionError):
            te.transition_to(ToolExecutionState.EXECUTING)

    def test_completed_is_terminal(self) -> None:
        """COMPLETED 是终态"""
        te = _make_tool_execution(state=ToolExecutionState.COMPLETED)
        assert te.can_transition_to(ToolExecutionState.IDLE) is False
        assert te.can_transition_to(ToolExecutionState.PLANNING) is False

    def test_can_transition_to_helper(self) -> None:
        """can_transition_to 辅助方法"""
        te = _make_tool_execution(state=ToolExecutionState.IDLE)
        assert te.can_transition_to(ToolExecutionState.PLANNING) is True
        assert te.can_transition_to(ToolExecutionState.COMPLETED) is False


class TestToolExecutionTerminalInvariants:
    """终态不变量校验"""

    def test_terminal_state_requires_completed_at(self) -> None:
        """终态必须有 completed_at"""
        with pytest.raises(EntityValidationError):
            _make_tool_execution(
                state=ToolExecutionState.COMPLETED,
                completed_at=None,
            )

    def test_terminal_failed_requires_completed_at(self) -> None:
        """FAILED 终态必须有 completed_at"""
        with pytest.raises(EntityValidationError):
            _make_tool_execution(
                state=ToolExecutionState.FAILED,
                completed_at=None,
            )

    def test_non_terminal_no_completed_at(self) -> None:
        """非终态不应有 completed_at"""
        te = _make_tool_execution(
            state=ToolExecutionState.EXECUTING,
            completed_at=None,
        )
        assert te.completed_at is None


class TestToolExecutionStateVersion:
    """乐观锁 state_version 测试"""

    def test_state_version_increments_on_transition(self) -> None:
        """每次 transition_to 增加 state_version"""
        te = _make_tool_execution(state=ToolExecutionState.IDLE)
        initial_version = te.state_version
        te.transition_to(ToolExecutionState.PLANNING)
        assert te.state_version > initial_version
