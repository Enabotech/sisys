"""Story 6-1 — RunBlmPlanningUseCase 单元测试（七步编排平移 5-3 模式）。

TDD Task 2 循环 A 载体：七步编排顺序（443→441→447→档案→context→
PlanningStarted→submit_graph→终态组装）；PlanningStarted 发布时机（三守卫
通过后、submit_graph 前——守卫前发布则失败 run 留孤儿事件）；全降级→481
抛出点（终态组装处）；7/8 部分降级→成功 DTO；agent_id str 序列化。

Mock 策略：单元测试 Mock 端口（AsyncMock(spec=Protocol)——protocol_testing_
principles 契约约束）；守卫异常触发面用真实异常类。

Run with:
    poetry run pytest tests/unit/application/test_run_blm_planning.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.blm_planning import (
    BLM_PLANNING_SESSION_PREFIX,
    BlmPlanningContext,
    BlmPlanningServicePort,
)
from src.application.ports.isolation_guard import IsolationGuardPort
from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
from src.domain.entities.agent import Agent, AgentRole
from src.domain.exceptions.agent_exceptions import (
    AgentNotFoundError,
    AgentRoleNotSupportedError,
    IsolationStateNotInitializedError,
)
from src.domain.exceptions.planning_exceptions import PlanningExecutionError
from src.domain.ports.agent_engine import AgentEnginePort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.value_objects.blm_phases import (
    BlmPhase,
    BlmPlanningStatus,
    BlmTimelineEntry,
    InsightStepResult,
    InsightSynthesis,
    MarketInsightStep,
    PerformanceGapArtifacts,
)

if TYPE_CHECKING:
    from src.application.use_cases.get_blm_planning_status import GetBlmPlanningStatusUseCase

AGENT_ID = uuid.uuid4()
TASK = "制定新能源汽车行业五年战略规划"


# ===================================================================
# 测试替身工厂（AsyncMock spec=Port 契约约束）
# ===================================================================


def _make_agent(role: AgentRole = AgentRole.CEO) -> Agent:
    """CEO Agent 实体（默认最小合法形态——name 必填）。"""
    return Agent(agent_id=AGENT_ID, role=role, name="ceo-agent")


def _make_profile_result() -> Any:
    """档案加载结果替身（六档案 VO 面——本用例仅透传给 build_planning_context）。"""
    result = MagicMock()
    result.agent_id = AGENT_ID
    result.role = AgentRole.CEO
    return result


def _make_gap_artifacts(degraded: bool = False) -> PerformanceGapArtifacts:
    return PerformanceGapArtifacts(
        financial_gap="财务差距",
        operational_gap="运营差距",
        root_causes=("根因",),
        portfolio_health="组合健康度",
        degraded=degraded,
        degrade_reason="注入失败" if degraded else "",
    )


def _make_step_result(step: MarketInsightStep, degraded: bool = False) -> InsightStepResult:
    now = datetime.now(UTC)
    return InsightStepResult(
        step=step.value,
        summary="" if degraded else f"{step.value} 摘要",
        findings=() if degraded else ("发现",),
        tool_used="",
        evidence_refs=(),
        degraded=degraded,
        degrade_reason="注入失败" if degraded else "",
        started_at=now,
        completed_at=now,
    )


def _make_synthesis(degraded_inputs: tuple[str, ...] = ()) -> InsightSynthesis:
    self_degraded = "market_insight_synthesis" in degraded_inputs
    return InsightSynthesis(
        conclusions=() if self_degraded else ("综合结论",),
        degraded_inputs=degraded_inputs,
    )


def _make_use_case(
    *,
    agent: Agent | None = None,
    guard_error: Exception | None = None,
    final_state: dict[str, Any] | None = None,
    engine_error: Exception | None = None,
) -> tuple[RunBlmPlanningUseCase, dict[str, Any]]:
    """构造被测用例 + mock 依赖字典。

    Args:
        agent: 仓储返回的 Agent（None 触发 443）。
        guard_error: 隔离守卫注入异常（447 触发面）。
        final_state: 图终态 state（None 触发终态缺失 481）。
        engine_error: 引擎 submit 注入异常。

    Returns:
        (use_case, mocks) 二元组——mocks 供调用序断言。
    """
    from src.domain.value_objects.flow_status import FlowStatus

    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=agent)

    profile_use_case = MagicMock()
    profile_use_case.execute = AsyncMock(return_value=_make_profile_result())

    guard = AsyncMock(spec=IsolationGuardPort)
    if guard_error is not None:
        guard.ensure_agent_executable = AsyncMock(side_effect=guard_error)
    else:
        guard.ensure_agent_executable = AsyncMock(return_value=None)

    engine = AsyncMock(spec=AgentEnginePort)
    if engine_error is not None:
        engine.submit_graph = AsyncMock(side_effect=engine_error)
    else:
        engine.submit_graph = AsyncMock(return_value="run-1")
    engine.get_graph_status = AsyncMock(return_value=FlowStatus.COMPLETED)
    engine.get_graph_result = AsyncMock(return_value=final_state)

    publisher = AsyncMock(spec=EventPublisher)

    blm_service = MagicMock(spec=BlmPlanningServicePort)
    blm_service.build_planning_context = MagicMock(
        return_value=BlmPlanningContext(plan_id="plan-1", agent_id=AGENT_ID, profile_result=_make_profile_result(), task=TASK)
    )

    use_case = RunBlmPlanningUseCase(
        agent_repository=repository,
        agent_profile_use_case=profile_use_case,
        agent_engine=engine,
        blm_planning_service=blm_service,
        isolation_guard=guard,
        event_publisher=publisher,
    )
    return use_case, {
        "repository": repository,
        "profile_use_case": profile_use_case,
        "guard": guard,
        "engine": engine,
        "publisher": publisher,
        "blm_service": blm_service,
    }


def _make_final_state(
    *,
    degraded_steps: tuple[str, ...] = (),
    gap_degraded: bool = False,
    synthesis_degraded_inputs: tuple[str, ...] = (),
) -> dict[str, Any]:
    """构造图终态 state（终态直读组装面）。"""
    gap = _make_gap_artifacts(degraded=gap_degraded)
    steps = tuple(_make_step_result(step, degraded=step.value in degraded_steps) for step in MarketInsightStep)
    synthesis = _make_synthesis(degraded_inputs=synthesis_degraded_inputs)
    return {
        "agent_id": str(AGENT_ID),
        "plan_id": "plan-1",
        "gap_artifacts": gap,
        "insight_step_results": steps,
        "synthesis": synthesis,
        "degraded_steps": degraded_steps,
    }


# ===================================================================
# 七步编排顺序
# ===================================================================


class TestOrchestrationOrder:
    """七步编排（443→441→447→档案→context→PlanningStarted→submit→组装）。"""

    async def test_full_flow_success(self) -> None:
        """完整流程成功：结果 DTO 含全部产物 + agent_id 单一 + plan_id 流转。"""
        state = _make_final_state()
        use_case, mocks = _make_use_case(agent=_make_agent(), final_state=state)
        result = await use_case.execute(agent_id=AGENT_ID, task=TASK)
        assert result.plan_id
        assert result.agent_id == AGENT_ID
        assert result.gap_artifacts is state["gap_artifacts"]
        assert len(result.insight_steps) == 6
        assert result.synthesis is state["synthesis"]
        assert result.execution_ms >= 0

    async def test_guard_sequence_443_441_447(self) -> None:
        """守卫顺序：存在→角色→隔离（后位守卫在前位失败时不触发）。"""
        use_case, mocks = _make_use_case(agent=None)  # 443 触发
        with pytest.raises(AgentNotFoundError):
            await use_case.execute(agent_id=AGENT_ID, task=TASK)
        mocks["guard"].ensure_agent_executable.assert_not_awaited()
        mocks["profile_use_case"].execute.assert_not_awaited()

    async def test_role_guard_441(self) -> None:
        """角色守卫：非 CEO Agent 触发 441（SUPPORTED_ROLES 不扩展）。"""
        use_case, mocks = _make_use_case(agent=_make_agent(role=AgentRole.CTO))
        with pytest.raises(AgentRoleNotSupportedError):
            await use_case.execute(agent_id=AGENT_ID, task=TASK)
        mocks["guard"].ensure_agent_executable.assert_not_awaited()

    async def test_isolation_guard_447_fail_closed(self) -> None:
        """隔离守卫 fail-closed：447 抛出时档案不加载、图不提交。"""
        use_case, mocks = _make_use_case(
            agent=_make_agent(), guard_error=IsolationStateNotInitializedError(agent_id=str(AGENT_ID))
        )
        with pytest.raises(IsolationStateNotInitializedError):
            await use_case.execute(agent_id=AGENT_ID, task=TASK)
        mocks["profile_use_case"].execute.assert_not_awaited()
        mocks["engine"].submit_graph.assert_not_awaited()


class TestPlanningStartedPublishTiming:
    """PlanningStarted 发布时机钦定（三守卫通过后、submit_graph 前）。"""

    async def test_planning_started_published_before_submit(self) -> None:
        """发布序：PlanningStarted 先于 submit_graph（共享事件序记录断言）。"""
        state = _make_final_state()
        use_case, mocks = _make_use_case(agent=_make_agent(), final_state=state)
        call_order: list[str] = []
        original_publish = mocks["publisher"].publish.side_effect

        async def _record_publish(event: Any) -> Any:
            call_order.append("publish")
            return await original_publish(event) if original_publish else None

        original_submit = mocks["engine"].submit_graph.side_effect

        async def _record_submit(graph_name: str, parameters: dict) -> str:
            call_order.append("submit")
            return await original_submit(graph_name, parameters) if original_submit else "run-1"

        mocks["publisher"].publish.side_effect = _record_publish
        mocks["engine"].submit_graph.side_effect = _record_submit
        await use_case.execute(agent_id=AGENT_ID, task=TASK)

        publish_calls = mocks["publisher"].publish.await_args_list
        assert publish_calls, "PlanningStarted 未发布"
        event = publish_calls[0].args[0]
        assert type(event).__name__ == "PlanningStarted"
        # 时机断言：发布先于 submit（三守卫通过后、submit 前——孤儿事件防线）
        assert call_order.index("publish") < call_order.index("submit")

    async def test_planning_started_not_published_when_guard_fails(self) -> None:
        """守卫失败（443）不发布——防孤儿事件。"""
        use_case, mocks = _make_use_case(agent=None)
        with pytest.raises(AgentNotFoundError):
            await use_case.execute(agent_id=AGENT_ID, task=TASK)
        mocks["publisher"].publish.assert_not_awaited()


class TestSubmitParameters:
    """submit_graph 参数面（agent_id str 序列化 + plan_id 入 parameters）。"""

    async def test_agent_id_serialized_as_str(self) -> None:
        """agent_id 必须 str 序列化进 parameters（5-3 直承遗产）。"""
        state = _make_final_state()
        use_case, mocks = _make_use_case(agent=_make_agent(), final_state=state)
        await use_case.execute(agent_id=AGENT_ID, task=TASK)
        args, kwargs = mocks["engine"].submit_graph.await_args
        assert args[0] == "SpBlmGraph"
        parameters = args[1]
        assert parameters["agent_id"] == str(AGENT_ID)
        assert isinstance(parameters["agent_id"], str)
        assert parameters["task"] == TASK
        assert parameters["plan_id"]
        assert parameters["context"] is not None

    async def test_plan_id_explicit_passthrough(self) -> None:
        """显式 plan_id 透传（CLI --plan-id 路径）。"""
        state = _make_final_state()
        use_case, mocks = _make_use_case(agent=_make_agent(), final_state=state)
        explicit = str(uuid.uuid4())
        await use_case.execute(agent_id=AGENT_ID, task=TASK, plan_id=explicit)
        parameters = mocks["engine"].submit_graph.await_args.args[1]
        assert parameters["plan_id"] == explicit


# ===================================================================
# 终态组装：全降级 481 / 部分降级成功
# ===================================================================


class TestDegradationTerminalStates:
    """降级终态语义（481 抛出点钦定=终态组装处）。"""

    async def test_all_degraded_raises_481(self) -> None:
        """全部 8 步降级 → PlanningExecutionError(481)。"""
        all_degraded = ("performance_gap",) + tuple(s.value for s in MarketInsightStep) + ("market_insight_synthesis",)
        assert len(all_degraded) == 8
        state = _make_final_state(
            degraded_steps=all_degraded,
            gap_degraded=True,
            synthesis_degraded_inputs=all_degraded,
        )
        use_case, _mocks = _make_use_case(agent=_make_agent(), final_state=state)
        with pytest.raises(PlanningExecutionError) as exc_info:
            await use_case.execute(agent_id=AGENT_ID, task=TASK)
        assert exc_info.value.code == "EXCEPTION_481"
        assert "8" in exc_info.value.context.get("reason", "")

    async def test_partial_degradation_7_of_8_returns_success(self) -> None:
        """7/8 部分降级（仅 synthesis 未降级）→ 成功 DTO + degraded_steps（防误抛 481）。"""
        # 7 步降级 = performance_gap + 六子步骤全降级，synthesis 正常
        degraded = ("performance_gap",) + tuple(s.value for s in MarketInsightStep)
        state = _make_final_state(degraded_steps=degraded, gap_degraded=True, synthesis_degraded_inputs=degraded)
        assert len(degraded) == 7
        use_case, _mocks = _make_use_case(agent=_make_agent(), final_state=state)
        result = await use_case.execute(agent_id=AGENT_ID, task=TASK)
        assert len(result.degraded_steps) == 7
        assert result.synthesis.conclusions  # synthesis 未降级

    async def test_only_synthesis_degraded_returns_success(self) -> None:
        """仅 synthesis 降级（7/8 镜像）→ 成功 DTO + synthesis 降级形态。"""
        state = _make_final_state(
            degraded_steps=("market_insight_synthesis",),
            synthesis_degraded_inputs=("market_insight_synthesis",),
        )
        use_case, _mocks = _make_use_case(agent=_make_agent(), final_state=state)
        result = await use_case.execute(agent_id=AGENT_ID, task=TASK)
        assert result.degraded_steps == ("market_insight_synthesis",)
        assert result.synthesis.conclusions == ()

    async def test_final_state_missing_raises_481(self) -> None:
        """终态 state 缺失 → PlanningExecutionError（图执行失败终态）。"""
        use_case, _mocks = _make_use_case(agent=_make_agent(), final_state=None)
        with pytest.raises(PlanningExecutionError):
            await use_case.execute(agent_id=AGENT_ID, task=TASK)


# ===================================================================
# 快照会话前缀常量（三层键形态第一层）
# ===================================================================


class TestSessionPrefix:
    """BLM_PLANNING_SESSION_PREFIX 单源常量（Task 2 循环 B 读侧前置）。"""

    def test_prefix_value(self) -> None:
        """前缀钦定 blm-planning-（session_id=前缀+plan_id）。"""
        assert BLM_PLANNING_SESSION_PREFIX == "blm-planning-"

    def test_session_id_composition(self) -> None:
        """session_id 拼接形态（最终键 sisys:snapshot:blm-planning-{plan_id} 第一跳）。"""

        session_id = f"{BLM_PLANNING_SESSION_PREFIX}plan-1"
        assert session_id == "blm-planning-plan-1"


# ===================================================================
# 循环 B：GetBlmPlanningStatusUseCase 读侧
# ===================================================================


def _make_status_snapshot_state(completed_steps: int = 8) -> dict[str, Any]:
    """快照 state_data 种子（序列化契约——与写入方同源钦定）。"""
    now = datetime.now(UTC)
    timeline = [
        {
            "step": "performance_gap",
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
            "status": "completed",
            "summary_excerpt": "阶段 1 摘要",
            "degraded": False,
        }
    ]
    return {
        "plan_id": "plan-1",
        "phase": "market_insight",
        "current_step": "performance_gap",
        "completed_steps": completed_steps,
        "total_steps": 8,
        "degraded_steps": [],
        "timeline": timeline,
    }


class TestGetBlmPlanningStatusUseCase:
    """状态查询用例（读侧——写入方唯一归 BlmPlanningService）。"""

    def _make_status_use_case(self, snapshot: Any) -> GetBlmPlanningStatusUseCase:
        from src.application.use_cases.get_blm_planning_status import GetBlmPlanningStatusUseCase

        repo = AsyncMock(spec=SnapshotRepositoryProtocol)
        repo.load = AsyncMock(return_value=snapshot)
        return GetBlmPlanningStatusUseCase(snapshot_repository=repo)

    async def test_terminal_status_read(self) -> None:
        """终态读取：state_data → BlmPlanningStatus 反序列化（8/8 全 completed）。"""
        snapshot = MagicMock()
        snapshot.state_data = _make_status_snapshot_state(completed_steps=8)
        use_case = self._make_status_use_case(snapshot)
        status = await use_case.execute(plan_id="plan-1")
        assert isinstance(status, BlmPlanningStatus)
        assert status.completed_steps == 8
        assert status.progress_percent == 100.0
        assert status.phase is BlmPhase.MARKET_INSIGHT
        assert len(status.timeline) == 1
        assert isinstance(status.timeline[0], BlmTimelineEntry)

    async def test_mid_execution_status_read(self) -> None:
        """执行中读取（步骤边界快照点——挂起第 2 步读到第 1 步完成）。"""
        snapshot = MagicMock()
        snapshot.state_data = _make_status_snapshot_state(completed_steps=1)
        use_case = self._make_status_use_case(snapshot)
        status = await use_case.execute(plan_id="plan-1")
        assert status.completed_steps == 1
        assert 0 < status.progress_percent < 100

    async def test_no_snapshot_raises_480(self) -> None:
        """无快照 → PlanningNotFoundError(480)（第三态显式失败）。"""
        from src.domain.exceptions.planning_exceptions import PlanningNotFoundError

        use_case = self._make_status_use_case(None)
        with pytest.raises(PlanningNotFoundError) as exc_info:
            await use_case.execute(plan_id="plan-unknown")
        assert exc_info.value.code == "EXCEPTION_480"

    async def test_session_id_prefix_composition(self) -> None:
        """读径 session_id 拼接（经端口 load——用例不自持 Redis 客户端）。"""
        from src.application.use_cases.get_blm_planning_status import GetBlmPlanningStatusUseCase

        snapshot = MagicMock()
        snapshot.state_data = _make_status_snapshot_state()
        repo = AsyncMock(spec=SnapshotRepositoryProtocol)
        repo.load = AsyncMock(return_value=snapshot)
        use_case = GetBlmPlanningStatusUseCase(snapshot_repository=repo)
        await use_case.execute(plan_id="plan-1")
        repo.load.assert_awaited_once_with(f"{BLM_PLANNING_SESSION_PREFIX}plan-1")


class TestChainRecordsAssembly:
    """6-4 Result 携带 chain_records（默认尾字段零破坏 + 读侧 tuple 归一 R2-F5）。"""

    def test_assemble_result_normalizes_list_to_tuple(self) -> None:
        """state 承载 list（投影返回）→ Result 字段 tuple 归一。"""
        use_case, _mocks = _make_use_case(final_state={**_make_final_state(), "chain_records": ["record-a", "record-b"]})
        result = use_case._assemble_result(
            {**_make_final_state(), "chain_records": ["record-a", "record-b"]},
            agent_id=AGENT_ID,
            plan_id="plan-1",
            started=0.0,
        )
        assert isinstance(result.chain_records, tuple), f"chain_records 未归一 tuple: {type(result.chain_records)}"
        assert result.chain_records == ("record-a", "record-b")

    def test_assemble_result_default_empty_tuple_when_key_absent(self) -> None:
        """终态缺键 → 默认空 tuple（零破坏——既有 state 无 chain_records 形态）。"""
        result = _make_use_case()[0]._assemble_result(
            _make_final_state(),
            agent_id=AGENT_ID,
            plan_id="plan-1",
            started=0.0,
        )
        assert result.chain_records == ()
