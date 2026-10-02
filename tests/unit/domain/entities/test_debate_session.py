"""Story 4.5 — DebateSession 聚合根单元测试

验证状态机（IDLE→GENERATING→SYNTHESIZING→COMPLETED / GENERATING、SYNTHESIZING→FAILED）、
终态不变量与迁移计数（state_version，V1 乐观锁 CAS 预留）。

约束：
- 非法迁移抛 EntityStateTransitionError（EXCEPTION_243），复用不新增
- 终态不变量违反抛 EntityValidationError（EXCEPTION_242）
- validate() 于 __post_init__ 内调用（ToolExecution 同构 :117-119，构造即全量校验）
- 实体不发领域事件（项目惯例：事件由应用服务发布）
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from src.domain.entities.debate_session import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    DebateSession,
    DebateSessionState,
)
from src.domain.exceptions import EntityStateTransitionError, EntityValidationError
from src.domain.value_objects.debate import ConsensusArea, DisagreementArea, RiskView


def _make_risk_view() -> RiskView:
    """构造合法 RiskView（终态回填用）"""
    return RiskView(
        consensus_areas=(ConsensusArea(area="市场潜力", description="双方认可增长潜力", confidence=0.9),),
        disagreement_areas=(
            DisagreementArea(area="进入时机", red_position="立即进入", blue_position="延后观察", risk_note="时机风险"),
        ),
        overall_risk_level="MEDIUM",
        overlap_rate=0.35,
    )


def _make_session(
    debate_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    title: str = "公司是否应在下一财年进入东南亚市场",
    state: DebateSessionState = DebateSessionState.IDLE,
    risk_view: RiskView | None = None,
    failure_reason: str | None = None,
    completed_at: datetime | None = None,
    state_version: int = 0,
) -> DebateSession:
    """构造 DebateSession（测试工厂，默认全合法 IDLE）"""
    return DebateSession(
        debate_id=debate_id if debate_id is not None else uuid.uuid4(),
        tenant_id=tenant_id if tenant_id is not None else uuid.uuid4(),
        title=title,
        state=state,
        risk_view=risk_view,
        failure_reason=failure_reason,
        completed_at=completed_at,
        state_version=state_version,
    )


# ===================================================================
# 状态机结构
# ===================================================================


class TestStateMachineStructure:
    def test_five_states_defined(self) -> None:
        """5 状态完整（小写值序列化友好）"""
        assert DebateSessionState.IDLE.value == "idle"
        assert DebateSessionState.GENERATING.value == "generating"
        assert DebateSessionState.SYNTHESIZING.value == "synthesizing"
        assert DebateSessionState.COMPLETED.value == "completed"
        assert DebateSessionState.FAILED.value == "failed"

    def test_transition_matrix(self) -> None:
        """迁移矩阵：合法路径 + 终态空集"""
        assert VALID_TRANSITIONS[DebateSessionState.IDLE] == {DebateSessionState.GENERATING}
        assert VALID_TRANSITIONS[DebateSessionState.GENERATING] == {
            DebateSessionState.SYNTHESIZING,
            DebateSessionState.FAILED,
        }
        assert VALID_TRANSITIONS[DebateSessionState.SYNTHESIZING] == {
            DebateSessionState.COMPLETED,
            DebateSessionState.FAILED,
        }
        assert VALID_TRANSITIONS[DebateSessionState.COMPLETED] == set()
        assert VALID_TRANSITIONS[DebateSessionState.FAILED] == set()

    def test_terminal_states_frozenset(self) -> None:
        """终态集合 frozenset（COMPLETED/FAILED）"""
        assert TERMINAL_STATES == frozenset({DebateSessionState.COMPLETED, DebateSessionState.FAILED})


# ===================================================================
# 合法全路径迁移 + state_version
# ===================================================================


class TestLegalTransitions:
    def test_full_path_version_increments(self) -> None:
        """IDLE→GENERATING→SYNTHESIZING→COMPLETED 全路径，state_version 0→3"""
        session = _make_session()
        assert session.state is DebateSessionState.IDLE
        assert session.state_version == 0

        session.transition_to(DebateSessionState.GENERATING)
        assert session.state_version == 1
        session.transition_to(DebateSessionState.SYNTHESIZING)
        assert session.state_version == 2
        # 终态前回填 risk_view 与 completed_at
        session.risk_view = _make_risk_view()
        session.completed_at = datetime.now(UTC)
        session.transition_to(DebateSessionState.COMPLETED)
        assert session.state_version == 3
        assert session.state in TERMINAL_STATES

    def test_generating_to_failed_path(self) -> None:
        """GENERATING→FAILED 失败路径（failure_reason 回填）"""
        session = _make_session()
        session.transition_to(DebateSessionState.GENERATING)
        session.failure_reason = "红视角 LLM 生成失败"
        session.transition_to(DebateSessionState.FAILED)
        assert session.state is DebateSessionState.FAILED
        assert session.state_version == 2

    def test_synthesizing_to_failed_path(self) -> None:
        """SYNTHESIZING→FAILED 失败路径"""
        session = _make_session()
        session.transition_to(DebateSessionState.GENERATING)
        session.transition_to(DebateSessionState.SYNTHESIZING)
        session.failure_reason = "合成调用失败"
        session.transition_to(DebateSessionState.FAILED)
        assert session.state is DebateSessionState.FAILED

    def test_can_transition_to(self) -> None:
        """can_transition_to 判定与矩阵一致"""
        session = _make_session()
        assert session.can_transition_to(DebateSessionState.GENERATING) is True
        assert session.can_transition_to(DebateSessionState.SYNTHESIZING) is False
        assert session.can_transition_to(DebateSessionState.FAILED) is False


# ===================================================================
# 非法迁移
# ===================================================================


class TestIllegalTransitions:
    def test_completed_to_generating_raises_243(self) -> None:
        """终态迁出：COMPLETED→GENERATING 抛 243"""
        session = _make_session(
            state=DebateSessionState.COMPLETED,
            risk_view=_make_risk_view(),
            completed_at=datetime.now(UTC),
        )
        with pytest.raises(EntityStateTransitionError) as exc_info:
            session.transition_to(DebateSessionState.GENERATING)
        assert exc_info.value.code == "EXCEPTION_243"

    def test_failed_to_any_raises_243(self) -> None:
        """终态迁出：FAILED→IDLE 抛 243"""
        session = _make_session(state=DebateSessionState.FAILED, failure_reason="失败")
        with pytest.raises(EntityStateTransitionError) as exc_info:
            session.transition_to(DebateSessionState.IDLE)
        assert exc_info.value.code == "EXCEPTION_243"

    def test_idle_to_synthesizing_skip_raises_243(self) -> None:
        """跳态：IDLE→SYNTHESIZING 抛 243"""
        session = _make_session()
        with pytest.raises(EntityStateTransitionError) as exc_info:
            session.transition_to(DebateSessionState.SYNTHESIZING)
        assert exc_info.value.code == "EXCEPTION_243"
        assert exc_info.value.context.get("from_status") == "IDLE"

    def test_idle_to_completed_skip_raises_243(self) -> None:
        """跳态：IDLE→COMPLETED 抛 243"""
        session = _make_session()
        with pytest.raises(EntityStateTransitionError):
            session.transition_to(DebateSessionState.COMPLETED)

    def test_illegal_transition_does_not_bump_version(self) -> None:
        """非法迁移不改变 state 与 state_version"""
        session = _make_session()
        with pytest.raises(EntityStateTransitionError):
            session.transition_to(DebateSessionState.SYNTHESIZING)
        assert session.state is DebateSessionState.IDLE
        assert session.state_version == 0


# ===================================================================
# 终态不变量（构造即校验）
# ===================================================================


class TestTerminalInvariants:
    def test_completed_without_risk_view_raises_242(self) -> None:
        """COMPLETED 必有 risk_view"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_session(state=DebateSessionState.COMPLETED, completed_at=datetime.now(UTC))
        assert exc_info.value.code == "EXCEPTION_242"

    def test_completed_without_completed_at_raises_242(self) -> None:
        """COMPLETED 必有 completed_at"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_session(state=DebateSessionState.COMPLETED, risk_view=_make_risk_view())
        assert exc_info.value.code == "EXCEPTION_242"

    def test_failed_without_failure_reason_raises_242(self) -> None:
        """FAILED 必有 failure_reason"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_session(state=DebateSessionState.FAILED)
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.parametrize(
        "state",
        [DebateSessionState.IDLE, DebateSessionState.GENERATING, DebateSessionState.SYNTHESIZING],
        ids=["idle", "generating", "synthesizing"],
    )
    def test_non_terminal_with_completed_at_raises_242(self, state: DebateSessionState) -> None:
        """非终态不得有 completed_at（三条非终态独立用例）"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_session(state=state, completed_at=datetime.now(UTC))
        assert exc_info.value.code == "EXCEPTION_242"

    def test_completed_with_all_fields_passes(self) -> None:
        """COMPLETED 全字段合法构造"""
        session = _make_session(
            state=DebateSessionState.COMPLETED,
            risk_view=_make_risk_view(),
            completed_at=datetime.now(UTC),
        )
        assert session.risk_view is not None

    def test_failed_with_reason_and_completed_at_passes(self) -> None:
        """FAILED 携带 failure_reason（completed_at 可选）"""
        session = _make_session(
            state=DebateSessionState.FAILED,
            failure_reason="生成失败",
            completed_at=datetime.now(UTC),
        )
        assert session.failure_reason == "生成失败"


# ===================================================================
# validate() 边界
# ===================================================================


class TestValidateBoundaries:
    def test_invalid_debate_id_raises(self) -> None:
        """debate_id 必须 UUID"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_session(debate_id=cast(uuid.UUID, "not-a-uuid"))
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "debate_id"

    def test_invalid_tenant_id_raises(self) -> None:
        """tenant_id 必须 UUID"""
        with pytest.raises(EntityValidationError):
            _make_session(tenant_id=cast(uuid.UUID, "not-a-uuid"))

    def test_empty_title_raises(self) -> None:
        """title 非空"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_session(title="")
        assert exc_info.value.context.get("field") == "title"

    def test_invalid_state_type_raises(self) -> None:
        """state 必须枚举值"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_session(state=cast(DebateSessionState, "generating"))
        assert exc_info.value.context.get("field") == "state"

    def test_naive_started_at_raises(self) -> None:
        """started_at 必须 timezone-aware（注入 naive 后 validate 抛 242）"""
        session = _make_session()
        session.started_at = datetime(2026, 1, 1)  # 注入 naive datetime 绕过构造默认值
        with pytest.raises(EntityValidationError) as exc_info:
            session.validate()
        assert exc_info.value.context.get("field") == "started_at"

    def test_negative_state_version_raises(self) -> None:
        """state_version ≥ 0"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_session(state_version=-1)
        assert exc_info.value.context.get("field") == "state_version"
