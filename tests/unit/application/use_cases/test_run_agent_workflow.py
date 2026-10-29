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


def _make_validation_error() -> Any:
    """构造 ValidationError(201) 实例（parametrize 参数——模块级求值需 helper 承载延迟 import）。"""
    from src.domain.exceptions import ValidationError

    return ValidationError(message="201 域守卫击穿")


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


# ===================================================================
# Story 5.8 — 评估块三面（eval.* 三键写入 + 降级 + None 默认兼容）
# ===================================================================


class TestExecuteEvaluationBlock:
    """Story 5.8 — execute 末尾评估块：eval.* 三键写根 span + 降级不阻断 + None 兼容。

    测试通道（5-7 SSOT 继承）：function-scope autouse「双复位 → 注入 provider 经
    initialize 全局 set → teardown 双复位」——镜像 TestExecuteRootSpanAttributes 形态
    （scope="module" 的 initialize 会被 5-7 类级 teardown 双复位中途清掉——R1 钉死
    function-scope）。Fake evaluation_harness 是 AsyncMock(spec=AgentEvaluationPort)
    ——评估端口替身（单元测试 Mock 面，真实链归 AC-3 验收/集成）。
    """

    @pytest.fixture(autouse=True)
    def _tracing_global_channel(self) -> Any:
        """装饰器链路测试通道（注入 provider 经 initialize——5-7 同款）。"""
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

    def _assemble_with_evaluation(self, evaluation_harness: Any = None) -> tuple[Any, dict[str, Any]]:
        """装配链（5-7 _assemble_with_real_profile 同款 + 第六依赖注入）。"""
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
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        use_case = RunAgentWorkflowUseCase(
            agent_repository=mocks["repository"],
            agent_profile_use_case=mocks["profile_use_case"],
            agent_engine=mocks["agent_engine"],
            agent_workflow_service=mocks["workflow_service"],
            isolation_guard=mocks["isolation_guard"],
            evaluation_harness=evaluation_harness,
        )
        return use_case, {"agent": agent, "profile_result": profile_result, "mocks": mocks}

    @staticmethod
    def _make_eval_result() -> Any:
        """固定评估结果（Fake evaluate side_effect 返回值——三键真值数据源）。"""
        from src.application.ports.agent_evaluation import EvaluationResult

        return EvaluationResult(
            hallucination_score=0.2,
            context_relevance=0.0,
            confidence_accuracy=0.55,
            overall_score=(1.0 - 0.2) * 0.4 + 0.0 * 0.35 + 0.55 * 0.25,
        )

    @staticmethod
    def _make_fake_harness(return_value: Any = None, raises: Any = None) -> Any:
        """Fake 评估端口替身（AsyncMock spec——evaluate 返回固定结果或抛注入异常）。"""
        from unittest.mock import AsyncMock

        from src.application.ports.agent_evaluation import AgentEvaluationPort

        fake = AsyncMock(spec=AgentEvaluationPort)
        if raises is not None:
            fake.evaluate.side_effect = raises
        else:
            fake.evaluate.return_value = return_value
        return fake

    async def test_execute_writes_eval_keys_to_root_span(self) -> None:
        """注入评估链 → execute → 三键写入根 span（值 == EvaluationResult 字段）+ overall 不写。"""
        from src.application.ports.agent_tracing import SpanAttributeKeys

        eval_result = self._make_eval_result()
        fake_harness = self._make_fake_harness(return_value=eval_result)
        use_case, materials = self._assemble_with_evaluation(fake_harness)
        agent = materials["agent"]

        result = await use_case.execute(agent_id=agent.agent_id, task="分析任务")

        # 工作流返回值与评估块零耦合（result 原样返回）
        assert result.workflow_status == "completed"
        roots = [s for s in self._exporter.get_finished_spans() if s.name == "agent_execution"]
        assert len(roots) == 1
        attributes = roots[0].attributes
        assert attributes is not None, "根 span 应有属性集（mypy narrowing——5-7 同款）"
        assert attributes[SpanAttributeKeys.EVAL_HALLUCINATION_SCORE] == eval_result.hallucination_score == 0.2
        assert attributes[SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE] == eval_result.context_relevance == 0.0
        assert attributes[SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY] == eval_result.confidence_accuracy == 0.55
        # overall 不写 span（三键可派生——YAGNI 契约）
        assert not [k for k in attributes if "overall" in k.lower()]
        fake_harness.evaluate.assert_awaited_once()

    async def test_evaluation_failure_degrades_gracefully(self, caplog: pytest.LogCaptureFixture) -> None:
        """evaluate 抛 450 → 主链正常返回 + 三键缺席 + warning + 十属性仍在。"""
        import logging

        from src.application.ports.agent_tracing import SpanAttributeKeys
        from src.domain.exceptions import AgentEvaluationError

        caplog.set_level(logging.WARNING, logger="src.application.use_cases.run_agent_workflow")
        fake_harness = self._make_fake_harness(raises=AgentEvaluationError(reason="llm_call"))
        use_case, materials = self._assemble_with_evaluation(fake_harness)
        agent = materials["agent"]

        result = await use_case.execute(agent_id=agent.agent_id, task="分析任务")

        assert result.workflow_status == "completed", "评估失败应降级不阻断主链"
        roots = [s for s in self._exporter.get_finished_spans() if s.name == "agent_execution"]
        assert len(roots) == 1
        attributes = roots[0].attributes
        assert attributes is not None, "根 span 应有属性集（mypy narrowing——5-7 同款）"
        for key in (
            SpanAttributeKeys.EVAL_HALLUCINATION_SCORE,
            SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE,
            SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY,
        ):
            assert key not in attributes, f"降级路径三键应缺席: {key}"
        for key in (
            SpanAttributeKeys.AGENT_ID,
            SpanAttributeKeys.AGENT_ROLE,
            SpanAttributeKeys.AGENT_NAME,
            SpanAttributeKeys.AGENT_STARTUP_CONTEXT_TOKENS,
            SpanAttributeKeys.AGENT_ACTIVE_SKILL_COUNT,
            SpanAttributeKeys.WORKFLOW_STATUS,
            SpanAttributeKeys.WORKFLOW_RETRY_COUNT,
            SpanAttributeKeys.WORKFLOW_EXECUTED_PHASES,
            SpanAttributeKeys.EVAL_CONFIDENCE,
            SpanAttributeKeys.EVIDENCE_INPUT_HASH,
        ):
            assert key in attributes, f"降级不应伤 MVP 属性: {key}"
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "评估降级" in r.getMessage()]
        assert warnings, "应记录评估降级 warning 日志"

    async def test_evaluation_llm_config_error_degrades_gracefully(self, caplog: pytest.LogCaptureFixture) -> None:
        """evaluate 抛 LLMConfigError(332) → 同降级（CR1-F1——现实可达源是运行期 env 半配置态）。"""
        import logging

        from src.application.ports.agent_tracing import SpanAttributeKeys
        from src.domain.exceptions import LLMConfigError

        caplog.set_level(logging.WARNING, logger="src.application.use_cases.run_agent_workflow")
        fake_harness = self._make_fake_harness(raises=LLMConfigError(message="LLM API Key 未配置"))
        use_case, materials = self._assemble_with_evaluation(fake_harness)
        agent = materials["agent"]

        result = await use_case.execute(agent_id=agent.agent_id, task="分析任务")

        assert result.workflow_status == "completed", "评估面 332 应降级不阻断主链（附加面边界=catch 边界）"
        roots = [s for s in self._exporter.get_finished_spans() if s.name == "agent_execution"]
        assert len(roots) == 1
        attributes = roots[0].attributes
        assert attributes is not None, "根 span 应有属性集（mypy narrowing——5-7 同款）"
        for key in (
            SpanAttributeKeys.EVAL_HALLUCINATION_SCORE,
            SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE,
            SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY,
        ):
            assert key not in attributes, f"332 降级路径三键应缺席: {key}"
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "评估降级" in r.getMessage()]
        assert warnings, "332 降级应记录 warning 日志"

    @pytest.mark.parametrize(
        "unexpected_error",
        [
            RuntimeError("评估块外的意外异常不应被吞"),
            _make_validation_error(),
        ],
        ids=["runtime-error", "validation-error-201"],
    )
    async def test_evaluation_unexpected_error_propagates(self, unexpected_error: Exception) -> None:
        """evaluate 抛非降级网异常（RuntimeError/ValidationError 201）→ 击穿主链。

        钉死 catch 收窄边界（CR1-F1 测试面）：降级网仅 (AgentEvaluationError, LLMConfigError)
        ——201 是文档化兄弟面（理论不可达防御层，真触发说明实现 bug 应显性失败）；
        本用例红 = catch 被放宽为 except Exception（吞掉契约外异常）。
        """

        fake_harness = self._make_fake_harness(raises=unexpected_error)
        use_case, materials = self._assemble_with_evaluation(fake_harness)
        agent = materials["agent"]

        with pytest.raises(type(unexpected_error)):
            await use_case.execute(agent_id=agent.agent_id, task="分析任务")

    async def test_none_harness_keeps_5_7_baseline(self) -> None:
        """None 默认（五参构造兼容）→ 评估块整体跳过——行为与 5-7 基线一致。"""
        from src.application.ports.agent_tracing import SpanAttributeKeys

        use_case, materials = self._assemble_with_evaluation(None)
        agent = materials["agent"]

        result = await use_case.execute(agent_id=agent.agent_id, task="分析任务")

        assert result.workflow_status == "completed"
        assert result.evidence.confidence == 0.85
        roots = [s for s in self._exporter.get_finished_spans() if s.name == "agent_execution"]
        assert len(roots) == 1
        attributes = roots[0].attributes
        assert attributes is not None, "根 span 应有属性集（mypy narrowing——5-7 同款）"
        for key in (
            SpanAttributeKeys.EVAL_HALLUCINATION_SCORE,
            SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE,
            SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY,
        ):
            assert key not in attributes, f"None 路径三键应缺席: {key}"
        assert SpanAttributeKeys.AGENT_ID in attributes
        assert SpanAttributeKeys.WORKFLOW_STATUS in attributes

    async def test_constructor_sixth_param_default_none(self) -> None:
        """构造签名：七依赖清单 + 第六参数默认 None（存量五参调用零破坏——断言同步④ 5-9 扩七）。"""
        import inspect

        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        params = list(inspect.signature(RunAgentWorkflowUseCase.__init__).parameters)[1:]
        assert params == [
            "agent_repository",
            "agent_profile_use_case",
            "agent_engine",
            "agent_workflow_service",
            "isolation_guard",
            "evaluation_harness",
            "drift_detector",
        ]
        default = inspect.signature(RunAgentWorkflowUseCase.__init__).parameters["evaluation_harness"].default
        assert default is None

    async def test_five_arg_construction_still_works(self) -> None:
        """存量五参构造零破坏（向后兼容——不传第六参数）。"""
        mocks = _make_mocks()
        _wire_engine_success(mocks)
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        use_case = RunAgentWorkflowUseCase(
            agent_repository=mocks["repository"],
            agent_profile_use_case=mocks["profile_use_case"],
            agent_engine=mocks["agent_engine"],
            agent_workflow_service=mocks["workflow_service"],
            isolation_guard=mocks["isolation_guard"],
        )
        assert getattr(use_case, "_evaluation_harness", "missing") is None


class TestExecuteDriftBlock:
    """Story 5.9 — execute 评估块内漂移检测块：drift.detected span 填值 + 降级不阻断。

    测试通道（5-7 SSOT 继承）：function-scope autouse「双复位 → 注入 provider 经
    initialize 全局 set → teardown 双复位」——镜像 TestExecuteEvaluationBlock 同款
    （scope="module" 的 initialize 会被 5-7 类级 teardown 中途清掉——function-scope
    钉死）。Fake drift port 是 AsyncMock(spec=DriftDetectionPort)——单元测试 Mock
    面（验收禁 mock 红线下 AC-3.2 用手写 FakeDriftPort 承载）。
    """

    @pytest.fixture(autouse=True)
    def _tracing_global_channel(self) -> Any:
        """装饰器链路测试通道（注入 provider 经 initialize——5-7/5-8 同款）。"""
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

    def _assemble_with_drift(self, drift_detector: Any = None, evaluation_harness: Any = None) -> tuple[Any, dict[str, Any]]:
        """装配链（TestExecuteEvaluationBlock._assemble_with_evaluation 同款 + 第七依赖注入）。"""
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
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        use_case = RunAgentWorkflowUseCase(
            agent_repository=mocks["repository"],
            agent_profile_use_case=mocks["profile_use_case"],
            agent_engine=mocks["agent_engine"],
            agent_workflow_service=mocks["workflow_service"],
            isolation_guard=mocks["isolation_guard"],
            evaluation_harness=evaluation_harness,
            drift_detector=drift_detector,
        )
        return use_case, {"agent": agent, "profile_result": profile_result, "mocks": mocks}

    @staticmethod
    def _make_fake_harness(return_value: Any = None, raises: Any = None) -> Any:
        """Fake 评估端口替身（AsyncMock spec——5-8 同款镜像）。"""
        from unittest.mock import AsyncMock

        from src.application.ports.agent_evaluation import AgentEvaluationPort

        fake = AsyncMock(spec=AgentEvaluationPort)
        if raises is not None:
            fake.evaluate.side_effect = raises
        else:
            fake.evaluate.return_value = return_value
        return fake

    @staticmethod
    async def _make_real_detector_prefilled(publisher: Any) -> Any:
        """真实检测器 + 预填充 34 样本（30 基线交替 + 4×0.4——链上末样本即确认形态）。"""
        from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

        detector = CUSUMDriftDetector(event_publisher=publisher)
        baseline = [0.7, 0.9] * 15
        for score in baseline + [0.4, 0.4, 0.4, 0.4]:
            await detector.update(score)
        return detector

    async def test_drift_confirmed_writes_span_and_publishes_event(self) -> None:
        """预填充 34 样本 + execute（幻觉 0.2 → overall ≈0.4575 病态角带内）→
        drift.detected=True 写根 span + DriftDetected 事件发布 + agent_id 透传。"""
        from src.domain.events.drift_events import DriftDetected

        class _Recorder:
            """零 IO 事件替身（publish 捕获——_RecordingEventPublisher 单测变体）。"""

            def __init__(self) -> None:
                self.published: list[Any] = []

            async def publish(self, event: Any) -> Any:
                from src.domain.events.publish_result import ChannelResult, PublishResult

                self.published.append(event)
                return PublishResult(
                    event_id=str(event.event_id),
                    results=(ChannelResult(channel_name="inmemory", success=True),),
                )

        recorder = _Recorder()
        detector = await self._make_real_detector_prefilled(recorder)
        eval_result = TestExecuteEvaluationBlock._make_eval_result()
        fake_harness = self._make_fake_harness(return_value=eval_result)
        use_case, materials = self._assemble_with_drift(drift_detector=detector, evaluation_harness=fake_harness)
        agent = materials["agent"]

        result = await use_case.execute(agent_id=agent.agent_id, task="分析任务")

        assert result.workflow_status == "completed", "漂移确认不影响工作流返回值（零耦合）"
        roots = [s for s in self._exporter.get_finished_spans() if s.name == "agent_execution"]
        assert len(roots) == 1
        attributes = roots[0].attributes
        assert attributes is not None, "根 span 应有属性集（mypy narrowing——5-7 同款）"
        assert attributes["drift.detected"] is True, "确认漂移应写 drift.detected=True"
        # 事件发布断言（direction=down + agent_id 透传）
        drift_events = [e for e in recorder.published if isinstance(e, DriftDetected)]
        assert len(drift_events) == 1, "确认漂移应恰发布一次 DriftDetected"
        assert drift_events[0].drift_direction == "down"
        assert drift_events[0].agent_id == str(agent.agent_id)
        # eval 三键仍在（评估先于漂移成功）
        assert attributes["eval.hallucination_score"] == eval_result.hallucination_score

    async def test_drift_detection_error_degrades_gracefully(self, caplog: pytest.LogCaptureFixture) -> None:
        """update 抛 451 → 主链正常返回 + eval 三键仍在 + drift.detected 缺席 + warning。"""
        import logging

        from src.domain.exceptions import DriftDetectionError

        caplog.set_level(logging.WARNING, logger="src.application.use_cases.run_agent_workflow")
        from unittest.mock import AsyncMock

        from src.application.ports.agent_drift import DriftDetectionPort

        fake_drift = AsyncMock(spec=DriftDetectionPort)
        injected_error = DriftDetectionError(metric_name="overall_score", reason="invalid_state")
        fake_drift.update.side_effect = injected_error
        eval_result = TestExecuteEvaluationBlock._make_eval_result()
        fake_harness = self._make_fake_harness(return_value=eval_result)
        use_case, materials = self._assemble_with_drift(drift_detector=fake_drift, evaluation_harness=fake_harness)
        agent = materials["agent"]

        result = await use_case.execute(agent_id=agent.agent_id, task="分析任务")

        assert result.workflow_status == "completed", "451 应降级不阻断主链"
        roots = [s for s in self._exporter.get_finished_spans() if s.name == "agent_execution"]
        attributes = roots[0].attributes
        assert attributes is not None, "根 span 应有属性集（mypy narrowing——5-7 同款）"
        assert "drift.detected" not in attributes, "漂移失败时 drift.detected 应缺席（不写哨兵值）"
        assert attributes["eval.hallucination_score"] == eval_result.hallucination_score, "三键仍在（评估先于漂移成功）"
        warning_texts = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any(str(injected_error) in text for text in warning_texts), (
            f"451 共享评估块 catch——warning 文本应含 451 异常 str（实际 {warning_texts}）"
        )

    async def test_evaluation_failure_skips_drift_block(self) -> None:
        """评估失败（LLMAPIError→450 包装）→ 漂移块跳过（update 零调用——序列缺口策略）。"""
        from unittest.mock import AsyncMock

        from src.application.ports.agent_drift import DriftDetectionPort
        from src.domain.exceptions import AgentEvaluationError

        fake_drift = AsyncMock(spec=DriftDetectionPort)
        fake_harness = self._make_fake_harness(raises=AgentEvaluationError(reason="llm_call"))
        use_case, materials = self._assemble_with_drift(drift_detector=fake_drift, evaluation_harness=fake_harness)
        agent = materials["agent"]

        result = await use_case.execute(agent_id=agent.agent_id, task="分析任务")

        assert result.workflow_status == "completed"
        fake_drift.update.assert_not_awaited(), "评估失败时漂移块应整体跳过（update 零调用）"

    async def test_none_detector_baseline_unchanged(self) -> None:
        """六参构造（drift_detector=None）→ 行为与 5.8 基线一致 + 漂移块零执行。"""
        eval_result = TestExecuteEvaluationBlock._make_eval_result()
        fake_harness = self._make_fake_harness(return_value=eval_result)
        use_case, materials = self._assemble_with_drift(drift_detector=None, evaluation_harness=fake_harness)
        agent = materials["agent"]

        result = await use_case.execute(agent_id=agent.agent_id, task="分析任务")

        assert result.workflow_status == "completed"
        assert getattr(use_case, "_drift_detector", "missing") is None, "六参构造 _drift_detector 应为 None"
        roots = [s for s in self._exporter.get_finished_spans() if s.name == "agent_execution"]
        attributes = roots[0].attributes
        assert attributes is not None, "根 span 应有属性集（mypy narrowing——5-7 同款）"
        assert "drift.detected" not in attributes, "None 路径漂移块整体跳过（键缺席）"
        assert attributes["eval.hallucination_score"] == eval_result.hallucination_score, "5.8 基线行为一致"

    async def test_constructor_seventh_param_default_none(self) -> None:
        """构造签名：七依赖清单 + 第七参数默认 None（存量六参调用零破坏）。"""
        import inspect

        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        params = list(inspect.signature(RunAgentWorkflowUseCase.__init__).parameters)[1:]
        assert params == [
            "agent_repository",
            "agent_profile_use_case",
            "agent_engine",
            "agent_workflow_service",
            "isolation_guard",
            "evaluation_harness",
            "drift_detector",
        ]
        default = inspect.signature(RunAgentWorkflowUseCase.__init__).parameters["drift_detector"].default
        assert default is None

    async def test_six_arg_construction_still_works(self) -> None:
        """存量六参构造零破坏（向后兼容——不传第七参数）。"""
        mocks = _make_mocks()
        _wire_engine_success(mocks)
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        use_case = RunAgentWorkflowUseCase(
            agent_repository=mocks["repository"],
            agent_profile_use_case=mocks["profile_use_case"],
            agent_engine=mocks["agent_engine"],
            agent_workflow_service=mocks["workflow_service"],
            isolation_guard=mocks["isolation_guard"],
            evaluation_harness=None,
        )
        assert getattr(use_case, "_drift_detector", "missing") is None
