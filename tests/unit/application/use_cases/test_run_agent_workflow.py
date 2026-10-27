"""RunAgentWorkflowUseCase 单元测试（Story 5-3 — 单 Agent 标准工作流）

覆盖执行用例的编排契约（5-2 六步编排形态对齐）：
- 守卫序：443（get_by_id None）→ 441（非 CEO）→ 装配（先档案加载后
  build_context 材料传参——单向装配）→ submit_graph
- parameters["agent_id"] 必须 str 序列化（str(agent_id)——DC-5/R2-F13）
- 阻塞执行语义：submit 返回即终态，get_graph_status 单次断言终态（COMPLETED）
- get_graph_result 取终态 state → 结果组装（chain/evidence 直读 VO 实例
  ——禁做 dict→VO 反序列化层，R2-F15）
- AgentWorkflowResult 五字段（executed_phases 自终态 state 直读；
  workflow_status 同源 evidence.status——R2-F7）
- AgentDecided 发布由引擎承担（用例零 publish 调用——防双发，DC-6）
- 失败传播 444（引擎 DomainError 透传后用例零改写）

Run with:
    poetry run pytest tests/unit/application/use_cases/test_run_agent_workflow.py -v
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.entities.agent import AgentRole, AgentStatus
from src.domain.value_objects.flow_status import FlowStatus


def _make_agent(role: AgentRole = AgentRole.CEO) -> Any:
    """构造 Agent 实体（守卫数据源）。"""
    from src.domain.entities.agent import Agent

    agent = Agent(agent_id=uuid.uuid4(), role=role, name="CEO Agent")
    agent.status = AgentStatus.IDLE
    return agent


def _make_mocks() -> dict[str, Any]:
    """构造五依赖 mock（仓储/档案用例/引擎/工作流服务/隔离守卫——Story 5.5 第五依赖）。"""
    from src.application.ports.isolation_guard import IsolationGuardPort
    from src.domain.events.enums import IsolationLevel
    from src.domain.ports.agent_engine import AgentEnginePort
    from src.domain.value_objects.isolation_policy import get_isolation_policy

    repository = AsyncMock()
    repository.get_by_id.return_value = _make_agent()

    profile_use_case = AsyncMock()
    profile_use_case.execute.return_value = Mock(
        profile=Mock(),
        tools_l1=(),
        agent_id=None,
        role=AgentRole.CEO,
    )

    agent_engine = AsyncMock(spec=AgentEnginePort)
    workflow_service = Mock()
    workflow_service.build_context.return_value = Mock()

    # 隔离守卫替身（默认放行语义：executable 返回 L4 策略 / tool 放行静默）
    isolation_guard = AsyncMock(spec=IsolationGuardPort)
    isolation_guard.ensure_agent_executable.return_value = get_isolation_policy(IsolationLevel.L4_HARD)

    return {
        "repository": repository,
        "profile_use_case": profile_use_case,
        "agent_engine": agent_engine,
        "workflow_service": workflow_service,
        "isolation_guard": isolation_guard,
    }


def _make_use_case(mocks: dict[str, Any]) -> Any:
    """构造 RunAgentWorkflowUseCase（R2 组合五依赖具名——Story 5.5 追加隔离守卫）。"""
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

    return RunAgentWorkflowUseCase(
        agent_repository=mocks["repository"],
        agent_profile_use_case=mocks["profile_use_case"],
        agent_engine=mocks["agent_engine"],
        agent_workflow_service=mocks["workflow_service"],
        isolation_guard=mocks["isolation_guard"],
    )


def _make_final_state(status: str = "completed") -> dict[str, Any]:
    """构造引擎终态 state（get_graph_result 返回形态——VO 实例直读）。"""
    from src.domain.value_objects.chain_of_thought import ChainOfThought
    from src.domain.value_objects.task_evidence import TaskEvidencePackage

    return {
        "executed_phases": ["perceive", "plan", "execute", "verify", "package"],
        "retry_count": 0,
        "evidence": TaskEvidencePackage(
            input_hash="a" * 64,
            task_breakdown=("执行分析",),
            tool_trace=(),
            artifacts_snapshot=(),
            confidence=0.85,
            confidence_rationale="结构化检查通过",
            citations=(),
            status=status,
            failure_reason="" if status == "completed" else "验证未通过",
        ),
        "chain": ChainOfThought(
            input_summary="任务摘要",
            reflection="一次通过",
            tools_used=(),
            constraints_check="约束符合",
            final_answer='{"answer": "ok"}',
        ),
    }


def _wire_engine_success(mocks: dict[str, Any], state: dict[str, Any] | None = None) -> None:
    """接线引擎 mock 成功路径（submit→run_id / status→COMPLETED / result→state）。"""
    final_state = state if state is not None else _make_final_state()
    engine = mocks["agent_engine"]
    engine.submit_graph.return_value = "run-123"
    engine.get_graph_status.return_value = FlowStatus.COMPLETED
    engine.get_graph_result.return_value = final_state


# ===================================================================
# 守卫序（443 → 441 → 装配 → submit）
# ===================================================================


class TestGuardSequence:
    """守卫序断言（5-2 先例形态——calls 序验证）。"""

    async def test_agent_not_found_raises_443_before_anything(self) -> None:
        """443 守卫最先：get_by_id 返回 None → AgentNotFoundError。"""
        from src.domain.exceptions import AgentNotFoundError

        mocks = _make_mocks()
        mocks["repository"].get_by_id.return_value = None
        use_case = _make_use_case(mocks)

        with pytest.raises(AgentNotFoundError) as exc_info:
            await use_case.execute(agent_id=uuid.uuid4(), task="任务")
        assert exc_info.value.code == "EXCEPTION_443"
        mocks["profile_use_case"].execute.assert_not_awaited()
        mocks["agent_engine"].submit_graph.assert_not_awaited()

    async def test_non_ceo_role_raises_441(self) -> None:
        """441 守卫次之：非 CEO 角色（档案目录不存在，先 441 才可达）。"""
        from src.domain.exceptions import AgentRoleNotSupportedError

        mocks = _make_mocks()
        mocks["repository"].get_by_id.return_value = _make_agent(role=AgentRole.CFO)
        use_case = _make_use_case(mocks)

        with pytest.raises(AgentRoleNotSupportedError) as exc_info:
            await use_case.execute(agent_id=uuid.uuid4(), task="任务")
        assert exc_info.value.code == "EXCEPTION_441"

    async def test_orchestration_call_sequence(self) -> None:
        """装配调用序：get_by_id → profile.execute → build_context → submit_graph
        （单向装配——用例先加载档案再传材料，R1-F23）。"""
        mocks = _make_mocks()
        _wire_engine_success(mocks)
        use_case = _make_use_case(mocks)

        agent_id = uuid.uuid4()
        await use_case.execute(agent_id=agent_id, task="任务描述")

        mocks["repository"].get_by_id.assert_awaited_once_with(agent_id)
        mocks["profile_use_case"].execute.assert_awaited_once_with(agent_id=agent_id)
        mocks["workflow_service"].build_context.assert_called_once_with(
            mocks["profile_use_case"].execute.return_value, "任务描述"
        )


class TestSubmitParameters:
    """submit_graph 参数契约（str(agent_id) 序列化——R2-F13）。"""

    async def test_parameters_agent_id_is_str_serialized(self) -> None:
        """parameters["agent_id"] 必须 str（UUID 实例直塞引擎收敛位抛 AttributeError）。"""
        mocks = _make_mocks()
        _wire_engine_success(mocks)
        use_case = _make_use_case(mocks)

        agent_id = uuid.uuid4()
        await use_case.execute(agent_id=agent_id, task="任务")

        engine = mocks["agent_engine"]
        engine.submit_graph.assert_awaited_once()
        call_kwargs = engine.submit_graph.await_args.kwargs
        graph_name = call_kwargs.get("graph_name") or engine.submit_graph.await_args.args[0]
        parameters = call_kwargs.get("parameters") or engine.submit_graph.await_args.args[1]
        assert graph_name == "SingleAgentWorkflow"
        assert parameters["agent_id"] == str(agent_id), "agent_id 必须 str 序列化入 parameters"
        assert isinstance(parameters["agent_id"], str)
        assert parameters["task"] == "任务"
        assert parameters["context"] is mocks["workflow_service"].build_context.return_value

    async def test_get_graph_status_called_once(self) -> None:
        """阻塞语义：submit 返回即终态——status 单次断言（不轮询）。"""
        mocks = _make_mocks()
        _wire_engine_success(mocks)
        use_case = _make_use_case(mocks)

        await use_case.execute(agent_id=uuid.uuid4(), task="任务")

        engine = mocks["agent_engine"]
        engine.get_graph_status.assert_awaited_once_with("run-123")
        assert engine.get_graph_status.await_count == 1


# ===================================================================
# 结果组装（五字段 DTO + VO 直读）
# ===================================================================


class TestResultAssembly:
    """AgentWorkflowResult 组装（get_graph_result 终态 state 数据源）。"""

    async def test_result_five_fields(self) -> None:
        """五字段：chain/evidence/workflow_status/retry_count/executed_phases。"""
        from src.application.ports.agent_workflow import AgentWorkflowResult

        mocks = _make_mocks()
        _wire_engine_success(mocks)
        use_case = _make_use_case(mocks)

        result = await use_case.execute(agent_id=uuid.uuid4(), task="任务")
        assert isinstance(result, AgentWorkflowResult)
        assert result.workflow_status == "completed"  # 同源 evidence.status（R2-F7）
        assert result.retry_count == 0
        assert result.executed_phases == ("perceive", "plan", "execute", "verify", "package")
        assert result.evidence is mocks["agent_engine"].get_graph_result.return_value["evidence"]
        assert result.chain is mocks["agent_engine"].get_graph_result.return_value["chain"], "VO 直读（禁反序列化层）"

    async def test_failed_terminal_result(self) -> None:
        """失败完成态：workflow_status=failed（同源 evidence.status）。"""
        mocks = _make_mocks()
        _wire_engine_success(mocks, state=_make_final_state(status="failed"))
        use_case = _make_use_case(mocks)

        result = await use_case.execute(agent_id=uuid.uuid4(), task="任务")
        assert result.workflow_status == "failed"

    async def test_use_case_does_not_publish_events(self) -> None:
        """用例零 publish 调用（AgentDecided 发布由引擎承担——防双发 DC-6）。"""
        # 用例依赖中无 event_publisher（构造四依赖），此测试锚定接口面：
        # 若未来加入发布依赖，构造签名变更会使本测试红
        import inspect

        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        init_params = inspect.signature(RunAgentWorkflowUseCase.__init__).parameters
        assert "event_publisher" not in init_params, "用例不得注入 event_publisher（防双发）"


class TestErrorPropagation:
    """失败传播（引擎 DomainError 透传后用例零改写）。"""

    async def test_engine_444_propagates_unchanged(self) -> None:
        """引擎 444 透传（用例不包装不改写）。"""
        from src.domain.exceptions.agent_exceptions import AgentWorkflowError

        mocks = _make_mocks()
        mocks["agent_engine"].submit_graph.side_effect = AgentWorkflowError(agent_id="a", phase="plan", reason="LLM 失败")
        use_case = _make_use_case(mocks)

        with pytest.raises(AgentWorkflowError) as exc_info:
            await use_case.execute(agent_id=uuid.uuid4(), task="任务")
        assert exc_info.value.code == "EXCEPTION_444"


# ===================================================================
# Story 5-5 追加：入口 fail-closed 隔离检查（第五依赖接线）
# ===================================================================


class TestIsolationGuardWiring:
    """入口隔离检查接线契约（Story 5.5——441 后、档案加载前 fail-closed）。

    编排骨位: 443 存在 → 441 角色 → guard.ensure_agent_executable → 档案加载
    → 装配 → 图执行（DC-6——guard 在角色守卫后[既有序零回归]、档案加载前
    [fail-closed 于最早可判定点]）。
    """

    async def test_guard_called_exactly_once_before_profile_loading(self) -> None:
        """放行路径: ensure_agent_executable 恰一次且先于档案加载（顺序断言）。"""
        mocks = _make_mocks()
        _wire_engine_success(mocks)
        use_case = _make_use_case(mocks)

        agent_id = uuid.uuid4()
        await use_case.execute(agent_id=agent_id, task="任务")

        mocks["isolation_guard"].ensure_agent_executable.assert_awaited_once_with(agent_id)
        mocks["profile_use_case"].execute.assert_awaited_once()

    async def test_guard_447_denies_execution_before_profile_loading(self) -> None:
        """447 fail-closed: guard 抛 447 → execute 向上抛且 profile/engine 零调用
        （隔离态不可证明即拒绝——无档案读取无图执行无事件，零副作用）。"""
        from src.domain.exceptions import IsolationStateNotInitializedError

        mocks = _make_mocks()
        mocks["isolation_guard"].ensure_agent_executable.side_effect = IsolationStateNotInitializedError(agent_id="missing")
        use_case = _make_use_case(mocks)

        with pytest.raises(IsolationStateNotInitializedError) as exc_info:
            await use_case.execute(agent_id=uuid.uuid4(), task="任务")
        assert exc_info.value.code == "EXCEPTION_447"
        mocks["profile_use_case"].execute.assert_not_awaited()
        mocks["agent_engine"].submit_graph.assert_not_awaited()
        mocks["workflow_service"].build_context.assert_not_called()

    async def test_guard_443_passthrough(self) -> None:
        """guard 抛 443 → 透传（守卫序异常族原样向上）。"""
        from src.domain.exceptions import AgentNotFoundError

        mocks = _make_mocks()
        mocks["isolation_guard"].ensure_agent_executable.side_effect = AgentNotFoundError(agent_id="missing")
        use_case = _make_use_case(mocks)

        with pytest.raises(AgentNotFoundError) as exc_info:
            await use_case.execute(agent_id=uuid.uuid4(), task="任务")
        assert exc_info.value.code == "EXCEPTION_443"
        mocks["profile_use_case"].execute.assert_not_awaited()

    async def test_role_guard_precedes_isolation_guard(self) -> None:
        """441 仍先于 guard（角色守卫在前的既有序保持——非 CEO 角色不到达隔离检查）。"""
        from src.domain.exceptions import AgentRoleNotSupportedError

        mocks = _make_mocks()
        mocks["repository"].get_by_id.return_value = _make_agent(role=AgentRole.CFO)
        use_case = _make_use_case(mocks)

        with pytest.raises(AgentRoleNotSupportedError):
            await use_case.execute(agent_id=uuid.uuid4(), task="任务")
        mocks["isolation_guard"].ensure_agent_executable.assert_not_awaited()


# ===================================================================
# Story 5.7 — execute 根 span 与 MVP 十项属性（@trace + 属性写入块）
# ===================================================================


class TestExecuteRootSpanAttributes:
    """Story 5.7 — 根 span 自动创建 + MVP 十项业务属性逐键断言 + NoOp 基线等价。

    测试通道（SSOT）：被装饰方法 span 只经全局 API 可观测——function-scope
    autouse「双复位 → 注入 provider 经 initialize 全局 set → teardown 双复位」。
    """

    @pytest.fixture(autouse=True)
    def _tracing_global_channel(self) -> Any:
        """装饰器链路测试通道（注入 provider 经 initialize——R2 传播补）。"""
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        from src.infrastructure.config.phoenix import PhoenixConfig
        from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

        PhoenixTracer.reset_for_testing()
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = PhoenixTracer(
            config=PhoenixConfig(enabled=True, project_name="sisys-agent", sampling_ratio=1.0),
            tracer_provider=provider,
        )
        assert tracer.initialize() is True
        self._exporter = exporter
        yield exporter
        PhoenixTracer.reset_for_testing()

    def _assemble_with_real_profile(self) -> tuple[Any, dict[str, Any]]:
        """装配链（profile stub 带真实计量值——Mock auto-attr 会炸 OTel set_attribute 类型校验）。"""
        from types import SimpleNamespace

        mocks = _make_mocks()
        agent = mocks["repository"].get_by_id.return_value
        profile_result = SimpleNamespace(
            agent_id=agent.agent_id,
            role=AgentRole.CEO,
            profile=Mock(),
            tools_l1=(Mock(), Mock(), Mock()),
            startup_context_tokens=4321,
        )
        mocks["profile_use_case"].execute.return_value = profile_result
        _wire_engine_success(mocks)
        use_case = _make_use_case(mocks)
        return use_case, {"agent": agent, "profile_result": profile_result, "mocks": mocks}

    async def test_execute_root_span_with_ten_attributes(self) -> None:
        """execute → agent_execution 根 span + MVP 十项属性逐键相等（数据源钉死——AC-3.1）。"""
        from src.application.ports.agent_tracing import SpanAttributeKeys

        use_case, materials = self._assemble_with_real_profile()
        agent = materials["agent"]
        profile_result = materials["profile_result"]

        result = await use_case.execute(agent_id=agent.agent_id, task="分析任务")

        roots = [s for s in self._exporter.get_finished_spans() if s.name == "agent_execution"]
        assert len(roots) == 1, "应恰有一个 agent_execution 根 span"
        root = roots[0]
        attributes = root.attributes
        assert attributes is not None, "根 span 应有属性集"
        assert attributes[SpanAttributeKeys.AGENT_ID] == str(agent.agent_id)
        assert attributes[SpanAttributeKeys.AGENT_ROLE] == agent.role.value
        assert attributes[SpanAttributeKeys.AGENT_NAME] == agent.name
        assert attributes[SpanAttributeKeys.AGENT_STARTUP_CONTEXT_TOKENS] == profile_result.startup_context_tokens
        assert attributes[SpanAttributeKeys.AGENT_ACTIVE_SKILL_COUNT] == len(profile_result.tools_l1) == 3
        assert attributes[SpanAttributeKeys.WORKFLOW_STATUS] == result.workflow_status == "completed"
        assert attributes[SpanAttributeKeys.WORKFLOW_RETRY_COUNT] == result.retry_count == 0
        assert attributes[SpanAttributeKeys.WORKFLOW_EXECUTED_PHASES] == tuple(result.executed_phases)
        assert attributes[SpanAttributeKeys.EVAL_CONFIDENCE] == result.evidence.confidence == 0.85
        assert attributes[SpanAttributeKeys.EVIDENCE_INPUT_HASH] == result.evidence.input_hash == "a" * 64

    async def test_execute_noop_baseline_matches_5_3(self) -> None:
        """NoOp（全局未 set）下 execute 返回值与 5-3 基线一致（装饰器 overhead 仅一层函数调用）。"""
        import opentelemetry.trace as otel_trace
        from opentelemetry.trace import ProxyTracerProvider

        from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

        PhoenixTracer.reset_for_testing()  # NoOp 前提（前置双复位——R3-2 前提测试条款）
        assert isinstance(otel_trace.get_tracer_provider(), ProxyTracerProvider)

        use_case, _ = self._assemble_with_real_profile()
        result = await use_case.execute(agent_id=uuid.uuid4(), task="分析任务")

        assert result.workflow_status == "completed"
        assert result.retry_count == 0
        assert result.executed_phases == ("perceive", "plan", "execute", "verify", "package")
        assert result.evidence.input_hash == "a" * 64
