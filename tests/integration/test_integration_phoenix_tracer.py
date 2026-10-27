"""PhoenixTracer 集成测试（Story 5.7 — Task 4：span 树真实链 + P95 + 开销对比）

八场景（Fake LLM 手工装配六阶段链——5-3 集成装配形态 + 零 IO stub 隔离仓储；
自包含零外部服务，OTLP 零外联——测试全用 InMemorySpanExporter）：
① fail-once 成功链 span 树（根 + 六子 + parent 链 + 序列同源）
② 重试轮再入序列（plan/execute/verify/reflect 四方法多实例）
③ 异常链（LLMAPIError → 根/子 span ERROR + 444 包装透传 + AgentDecided 零发布）
④ NoOp 对比链（读法丙：proxy 态前提 + 观察哨计数不变 + 双跑等价）
⑤ eval/drift 四键通道写入实证（组件级注入通道）
⑥ span 记录 P95<5ms（_PERF_CACHE 委托——注入通道，验收 AC-5.1 同缓存）
⑦ 追踪开销<1%（块序钉死：t_untraced×5 → 一次性 initialize → t_traced×5；
  fail-once 链 7 次 structured × 20ms → t_untraced≈140ms、span 恰 10/轮、
  预算 1.4ms、t_untraced 下限守卫 0.13s、正向锚 traced 计数 50）
⑧ trace_id 贯通（span hex == ExecutionContext.trace_id；NoOp 全零）

通道分派（SSOT）：①②③④⑦⑧ 经 initialize 全局通道（autouse 前置双复位 +
teardown 双复位）；⑤⑥ 组件级注入通道（零全局触碰）。

Run with:
    poetry run pytest tests/integration/test_integration_phoenix_tracer.py -v
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from typing import Any, Generator

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group("phoenix-tracer-perf"),
]

#: span 记录 P95 阈值（秒——单源定义，验收侧 import 断言，禁双真源；epics L1746）
SPAN_RECORD_P95_LIMIT_SECONDS = 0.005

#: Fake LLM 每调用延迟（秒——单源；fail-once 链 7 次 structured × 0.02 →
#: t_untraced ≈ 0.14s 确定性量级、span 恰 10/轮、1% 预算 ≈ 1.4ms）
FAKE_LLM_DELAY_SEC = 0.02

#: 采样规格（warmup 1 + 20 采样——5-4/5-5/5-6 委托模式同款形态）
SPAN_RECORD_WARMUP_ROUNDS = 1
SPAN_RECORD_SAMPLE_ROUNDS = 20

#: 开销双跑 k 轮（每块 5 轮取中位数——抗单跑噪声）
OVERHEAD_ROUNDS_PER_BLOCK = 5

#: fail-once 链 span 总数（根 + 9 阶段；7 次 structured——execute 阶段纯工具
#: 循环无 LLM 调用，R3-1 枚举定谳）
FAIL_ONCE_SPAN_COUNT = 10

#: traced 块正向锚（10 span × 5 轮——防 traced 轮静默降级假绿）
TRACED_BLOCK_SPAN_COUNT = 50

#: t_untraced 基准下限守卫（秒——fail-once 链 ~0.14s 标定留抖动余量，防链
#: 被意外加速导致开销比分母失真）
UNTRACED_BASELINE_MIN_SECONDS = 0.13

#: 采样缓存（模块级单槽——集成场景⑥⑦与验收 AC-5.1/5.2 共享同批结果，
#: 同 xdist_group 同 worker 串行保证缓存命中；禁采样双跑）
_PERF_CACHE: dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _otel_global_state_isolation() -> Generator[None, None, None]:
    """OTel 全局状态 function 级双复位（凡 initialize/NoOp 前提用例一律复位义务）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    PhoenixTracer.reset_for_testing()
    yield
    PhoenixTracer.reset_for_testing()


# ===================================================================
# 装配 helpers（零外部服务自包含链——真实服务链 + Fake LLM 唯一豁免面）
# ===================================================================


def _make_config(**overrides: Any) -> Any:
    """测试启用配置。"""
    from src.infrastructure.config.phoenix import PhoenixConfig

    base: dict[str, Any] = {
        "enabled": True,
        "endpoint": "http://localhost:4317",
        "project_name": "sisys-agent",
        "sampling_ratio": 1.0,
    }
    base.update(overrides)
    return PhoenixConfig(**base)


def _make_injectable() -> tuple[Any, Any]:
    """注入通道材料：新 TracerProvider + Simple + InMemory（零全局触碰）。"""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _enable_global_tracing() -> tuple[Any, Any]:
    """链级统一通道：注入 provider 经 initialize 全局 set（唯一职责）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    provider, exporter = _make_injectable()
    tracer = PhoenixTracer(config=_make_config(), tracer_provider=provider)
    assert tracer.initialize() is True
    return provider, exporter


def _reset_global() -> None:
    """双复位全局。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    PhoenixTracer.reset_for_testing()


class _StubAgentRepository:
    """零 IO Agent 仓储替身（duck-typing 端口契约——返回真实 Agent 实体）。"""

    def __init__(self, agent: Any) -> None:
        self._agent = agent

    async def get_by_id(self, agent_id: Any) -> Any:
        return self._agent if agent_id == self._agent.agent_id else None


class _StubIsolationRepository:
    """零 IO 隔离仓储替身（恒返回 L4_HARD 初始化态）。"""

    async def save(self, state: Any, ttl: int) -> None:
        return None

    async def get_by_agent_id(self, agent_id: Any) -> Any:
        from src.domain.entities.isolation_state import IsolationState
        from src.domain.events.enums import IsolationLevel

        return IsolationState.initialize(agent_id, IsolationLevel.L4_HARD)

    async def delete(self, agent_id: Any) -> None:
        return None

    async def exists(self, agent_id: Any) -> bool:
        return True


class _StubIsolationSwitchLogRepository:
    """零 IO 日志仓储替身（5-3 验收同款先例）。"""

    async def save(self, log: Any) -> None:
        return None

    async def search(self, query: Any) -> Any:
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


class _RecordingEventPublisher:
    """记录发布事件的发布器（AgentDecided 零发布断言锚）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(getattr(event, "event_id", "")),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


class _RecordingToolExecutionService:
    """记录 ExecutionContext 的工具执行服务包装（trace_id 贯通断言锚）。"""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.captured_contexts: list[Any] = []

    async def execute(self, tool_id: Any, tool_call: Any, execution_context: Any) -> Any:
        self.captured_contexts.append(execution_context)
        return await self._inner.execute(tool_id, tool_call, execution_context)


class _StubProfileUseCase:
    """零 IO 档案用例替身（duck-typing——返回手工装配的 AgentProfileLoadResult）。

    真实 LoadAgentProfileUseCase 内含 443 守卫（组合根实例绑定 Redis 仓储——
    stub Agent 过不了守卫）；档案材料经无状态 loader/selector 本地加载（5-3
    验收 _assemble_workflow_chain 同款形态）。
    """

    def __init__(self, profile_result: Any) -> None:
        self._profile_result = profile_result

    async def execute(self, agent_id: Any) -> Any:
        return self._profile_result


def _make_fake_llm(
    *,
    verify_mode: str = "fail_once",
    plan_tool_names: tuple[str, ...] = ("PESTEL 分析",),
    delay_sec: float = FAKE_LLM_DELAY_SEC,
    error_schema: Any = None,
) -> Any:
    """六阶段 Fake LLM 替身（外部 SaaS 豁免面——5-3 集成同款 + 异常注入扩展）。"""
    from unittest.mock import AsyncMock

    from src.application.services.agent_workflow_schemas import (
        ChainOfThoughtSchema,
        PerceptionSchema,
        PlanSchema,
        PlanStep,
        ReflectionSchema,
        VerificationSchema,
    )
    from src.domain.exceptions import LLMAPIError
    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    verify_calls = {"count": 0}
    tool_llm_calls = {"count": 0}

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        if delay_sec:
            await asyncio.sleep(delay_sec)
        if error_schema is not None and response_schema is error_schema:
            raise LLMAPIError(message="模拟 LLM API 传输故障（集成注入）")
        if response_schema is PerceptionSchema:
            return PerceptionSchema(summary="任务摘要：新能源车进入战略分析")
        if response_schema is PlanSchema:
            steps = [PlanStep(description=f"执行工具 {name}", tool_name=name, arguments={}) for name in plan_tool_names]
            return PlanSchema(
                steps=steps or [PlanStep(description="零工具直接推理", tool_name="", arguments={})],
                selected_tools=list(plan_tool_names),
            )
        if response_schema is VerificationSchema:
            verify_calls["count"] += 1
            passed = True if verify_mode == "always_pass" else verify_calls["count"] > 1
            return VerificationSchema(
                passed=passed,
                confidence=0.85 if passed else 0.42,
                rationale="结构化检查通过" if passed else f"第 {verify_calls['count']} 次验证未通过：约束缺失",
            )
        if response_schema is ReflectionSchema:
            return ReflectionSchema(
                error_analysis="工具输出缺少关键约束字段",
                revised_plan="补充约束参数后重新执行工具并复核",
                revised=True,
            )
        if response_schema is ChainOfThoughtSchema:
            return ChainOfThoughtSchema(
                input_summary="Fake 回声摘要（应被覆写）",
                reflection="Fake 回声反思（终局合成产物）",
                tools_used=["fake-echo:not-real"],
                constraints_check="Fake 回声约束（终局合成产物）",
                final_answer='{"answer": "三层次进入策略（终局合成）"}',
            )
        raise AssertionError(f"未预期 response_schema: {response_schema!r}")

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> LLMResponse:
        if delay_sec:
            await asyncio.sleep(delay_sec)
        tool_llm_calls["count"] += 1
        stage = (tool_llm_calls["count"] - 1) % 3
        contents = (
            "1. PESTEL 六维度分析：政策支持、经济上行",
            'print("scores = [0.8, 0.7, 0.6]")',
            '{"valid": true, "confidence": 0.92, "issues": []}',
        )
        return LLMResponse(content=contents[stage], model="fake-llm")

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    fake.generate.side_effect = _generate
    return fake


def _build_tool_execution_service(fake_llm: Any) -> Any:
    """工具执行面（真实服务链 + Fake llm + 沙箱替身——5-3 集成同款边界）。"""
    from unittest.mock import AsyncMock

    from src.application.services.retry_helpers import RetryPolicy
    from src.application.services.tool_execution_engine import ToolExecutionEngine
    from src.application.services.tool_execution_service import ToolExecutionService
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()

    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock(return_value="session-fake")
    sandbox.execute_code = AsyncMock(return_value={"status": "ok", "output": '{"P": 0.8, "E": 0.7, "S": 0.6}'})
    sandbox.stop_container = AsyncMock(return_value=None)

    engine = ToolExecutionEngine(
        llm_client=fake_llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0.01),
    )
    return ToolExecutionService(registry=registry, engine=engine)


def _make_registry() -> Any:
    """工具注册服务（InMemory + register_all）。"""
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    return registry


async def _assemble_chain(**fake_kwargs: Any) -> dict[str, Any]:
    """自包含手工装配六阶段全链（真实服务/图/用例/守卫 + Fake LLM 豁免面）。"""
    from src.application.services.agent_workflow_service import AgentWorkflowService
    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
    from src.domain.entities.agent import Agent, AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

    agent = Agent(agent_id=uuid.uuid4(), role=AgentRole.CEO, name="CEO Agent")
    stub_agent_repo: Any = _StubAgentRepository(agent)  # duck-typing 替身经 Any 注入
    isolation_service = IsolationManagementService(
        isolation_repository=_StubIsolationRepository(),
        agent_repository=stub_agent_repo,
        event_publisher=InMemoryEventBus(),
        agent_config_loader=resolve("agent_config_loader"),
        isolation_switch_log_repository=_StubIsolationSwitchLogRepository(),
        audit_service=None,
    )
    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=stub_agent_repo,
        agent_config_loader=resolve("agent_config_loader"),
    )

    fake_llm = _make_fake_llm(**fake_kwargs)
    recording_tool_service = _RecordingToolExecutionService(_build_tool_execution_service(fake_llm))
    service: Any = AgentWorkflowService(
        llm_client=fake_llm,
        tool_execution_service=recording_tool_service,
        skill_loader=resolve("skill_loader"),
        tool_registry_service=_make_registry(),
        isolation_guard=guard,
    )
    recorder = _RecordingEventPublisher()
    engine = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=recorder,
        workflow_service=service,
    )
    # 档案材料（无状态 loader/selector 本地静态加载——零外部服务）
    profile_loader = resolve("agent_profile_loader")
    profile = await profile_loader.load(role=AgentRole.CEO, agent_id=agent.agent_id)
    skill_selector = resolve("skill_selector")
    tools_l1 = await skill_selector.list_active_skills()

    from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult

    profile_result = AgentProfileLoadResult(
        agent_id=agent.agent_id,
        role=AgentRole.CEO,
        profile=profile,
        tools_l1=tools_l1,
        startup_context_tokens=0,
    )
    profile_use_case: Any = _StubProfileUseCase(profile_result)

    use_case = RunAgentWorkflowUseCase(
        agent_repository=stub_agent_repo,
        agent_profile_use_case=profile_use_case,
        agent_engine=engine,
        agent_workflow_service=service,
        isolation_guard=guard,
    )
    return {
        "agent": agent,
        "task": "分析新能源汽车行业进入战略并给出三层次建议",
        "use_case": use_case,
        "recorder": recorder,
        "tool_service": recording_tool_service,
        "profile_result": profile_result,
    }


async def _run_chain(chain: dict[str, Any]) -> tuple[Any, BaseException | None]:
    """执行单轮链（异常捕获返回——透传语义不断言丢失）。"""
    try:
        result = await chain["use_case"].execute(chain["agent"].agent_id, chain["task"])
        return result, None
    except Exception as error:  # 集成场景异常捕获锚（444 断言面）
        return None, error


def _phase_spans_sorted(spans: list[Any]) -> list[Any]:
    """按 start_time 排序的阶段 span（排除根）。"""
    return sorted((s for s in spans if s.name != "agent_execution"), key=lambda s: s.start_time)


# ===================================================================
# 场景①②：fail-once 成功链 span 树 + 重试轮再入
# ===================================================================


async def test_scenario_1_fail_once_span_tree() -> None:
    """场景①：根 + 六子 span 树（parent 链 + 执行序 + 序列 == executed_phases）。"""
    _, exporter = _enable_global_tracing()
    chain = await _assemble_chain(verify_mode="fail_once")

    result, error = await _run_chain(chain)
    assert error is None, f"fail-once 链应成功（重试一轮后通过），实际异常 {error!r}"

    spans = list(exporter.get_finished_spans())
    assert len(spans) == FAIL_ONCE_SPAN_COUNT, f"fail-once 链应根+9 阶段恰 {FAIL_ONCE_SPAN_COUNT} span，实际 {len(spans)}"
    roots = [s for s in spans if s.name == "agent_execution"]
    assert len(roots) == 1 and roots[0].parent is None

    phase_spans = _phase_spans_sorted(spans)
    assert [s.name for s in phase_spans] == [
        "agent.perceive",
        "agent.plan",
        "agent.execute",
        "agent.verify",
        "agent.reflect",
        "agent.plan",
        "agent.execute",
        "agent.verify",
        "agent.package",
    ]
    for span in phase_spans:
        assert span.parent is not None
        assert span.parent.span_id == roots[0].context.span_id, f"子 span {span.name} 的 parent 应为根"
    assert tuple(s.name.split(".", 1)[1] for s in phase_spans) == tuple(result.executed_phases)


async def test_scenario_2_retry_reentry_sequences() -> None:
    """场景②：重试轮四方法再入（plan/execute/verify/reflect 多实例合法）。"""
    _, exporter = _enable_global_tracing()
    chain = await _assemble_chain(verify_mode="fail_once")

    result, error = await _run_chain(chain)
    assert error is None

    phase_names = [s.name for s in _phase_spans_sorted(list(exporter.get_finished_spans()))]
    assert phase_names.count("agent.plan") == 2
    assert phase_names.count("agent.execute") == 2
    assert phase_names.count("agent.verify") == 2
    assert phase_names.count("agent.reflect") == 1
    assert result.retry_count == 1


# ===================================================================
# 场景③：异常链
# ===================================================================


async def test_scenario_3_exception_chain_span_error_and_444() -> None:
    """场景③：LLMAPIError → 子/根 span ERROR + 444 包装透传 + AgentDecided 零发布。"""
    from opentelemetry.trace import StatusCode

    from src.application.services.agent_workflow_schemas import PerceptionSchema
    from src.domain.exceptions.agent_exceptions import AgentWorkflowError

    _, exporter = _enable_global_tracing()
    chain = await _assemble_chain(verify_mode="always_pass", error_schema=PerceptionSchema)

    result, error = await _run_chain(chain)
    assert error is not None and isinstance(error, AgentWorkflowError)
    assert error.code == "EXCEPTION_444"

    spans = list(exporter.get_finished_spans())
    error_spans = [s for s in spans if s.status.status_code == StatusCode.ERROR]
    assert error_spans, "异常路径应有 ERROR span"
    for span in error_spans:
        assert any(event.name == "exception" for event in span.events)
    assert any(s.name == "agent_execution" and s.status.status_code == StatusCode.ERROR for s in spans), "根 span 应 ERROR"
    assert result is None
    decided = [e for e in chain["recorder"].published_events if type(e).__name__ == "AgentDecided"]
    assert decided == [], "异常链不应发布 AgentDecided"


# ===================================================================
# 场景④：NoOp 对比链（读法丙）
# ===================================================================


async def test_scenario_4_noop_equivalence_with_sentinel() -> None:
    """场景④：proxy 态前提 + 观察哨计数不变 + 双跑等价（读法丙）。"""
    import opentelemetry.trace as otel_trace
    from opentelemetry.trace import ProxyTracerProvider

    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    _reset_global()  # NoOp 前提（前置双复位）
    assert isinstance(otel_trace.get_tracer_provider(), ProxyTracerProvider)
    sentinel_provider, sentinel_exporter = _make_injectable()
    PhoenixTracer(config=_make_config(), tracer_provider=sentinel_provider)  # 注入通道待命（不 initialize——读法丙）

    chain = await _assemble_chain(verify_mode="fail_once")
    result, error = await _run_chain(chain)
    assert error is None

    assert len(sentinel_exporter.get_finished_spans()) == 0, "观察哨应零 span（无旁路泄漏）"
    assert isinstance(otel_trace.get_tracer_provider(), ProxyTracerProvider), "全程零全局 set"
    assert result.executed_phases == (
        "perceive",
        "plan",
        "execute",
        "verify",
        "reflect",
        "plan",
        "execute",
        "verify",
        "package",
    )
    assert result.retry_count == 1 and result.workflow_status == "completed"


# ===================================================================
# 场景⑤：eval/drift 通道写入实证（注入通道）
# ===================================================================


async def test_scenario_5_eval_drift_channel_roundtrip() -> None:
    """场景⑤：四键写入 → exporter 断言（通道能力——OD-2 口径）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    provider, exporter = _make_injectable()
    tracer = PhoenixTracer(config=_make_config(), tracer_provider=provider)
    payload = {
        SpanAttributeKeys.EVAL_HALLUCINATION_SCORE: 0.12,
        SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE: 0.87,
        SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY: 0.95,
        SpanAttributeKeys.DRIFT_DETECTED: True,
    }
    with tracer.create_span("eval-drift-channel", attributes=payload) as handle:
        assert handle is not None
    span = exporter.get_finished_spans()[0]
    for key, value in payload.items():
        assert span.attributes.get(key) == value


# ===================================================================
# 场景⑥：span 记录 P95<5ms（_PERF_CACHE 委托——验收 AC-5.1 同缓存）
# ===================================================================


async def sample_span_record_perf() -> dict[str, Any]:
    """span 记录计时采样（委托入口——warmup 1 + 20 采样 × create_span 全周期 10 属性）。"""
    if "span_record" in _PERF_CACHE:
        cached: dict[str, Any] = _PERF_CACHE["span_record"]
        return cached

    from src.application.ports.agent_tracing import SpanAttributeKeys
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    provider, exporter = _make_injectable()  # 注入通道（create_span 真 span 前提）
    tracer = PhoenixTracer(config=_make_config(), tracer_provider=provider)
    attributes = {
        SpanAttributeKeys.AGENT_ID: "00000000-0000-0000-0000-000000000001",
        SpanAttributeKeys.AGENT_ROLE: "CEO",
        SpanAttributeKeys.AGENT_NAME: "CEO Agent",
        SpanAttributeKeys.AGENT_STARTUP_CONTEXT_TOKENS: 4321,
        SpanAttributeKeys.AGENT_ACTIVE_SKILL_COUNT: 3,
        SpanAttributeKeys.WORKFLOW_STATUS: "completed",
        SpanAttributeKeys.WORKFLOW_RETRY_COUNT: 1,
        SpanAttributeKeys.WORKFLOW_EXECUTED_PHASES: ("perceive", "plan", "package"),
        SpanAttributeKeys.EVAL_CONFIDENCE: 0.85,
        SpanAttributeKeys.EVIDENCE_INPUT_HASH: "a" * 64,
    }

    latencies: list[float] = []

    def _one_round() -> float:
        started = time.perf_counter()
        with tracer.create_span("span-record-bench", attributes=attributes) as handle:
            assert handle is not None
        return time.perf_counter() - started

    for _ in range(SPAN_RECORD_WARMUP_ROUNDS):
        _one_round()  # warmup 不计入采样
    for _ in range(SPAN_RECORD_SAMPLE_ROUNDS):
        latencies.append(_one_round())

    result = {
        "p95_seconds": statistics.quantiles(latencies, n=SPAN_RECORD_SAMPLE_ROUNDS)[18],
        "samples": latencies,
        "sample_count": len(exporter.get_finished_spans()),
    }
    _PERF_CACHE["span_record"] = result
    return result


@pytest.mark.benchmark
async def test_scenario_6_span_record_p95_below_5ms() -> None:
    """场景⑥：P95 < 5ms（exclusive 法 [18]——偏严侧估计量，实测 μs 级裕量 >1000×）。"""
    result = await sample_span_record_perf()
    assert result["p95_seconds"] < SPAN_RECORD_P95_LIMIT_SECONDS, (
        f"span 记录 P95={result['p95_seconds'] * 1000:.2f}ms 应 < {SPAN_RECORD_P95_LIMIT_SECONDS * 1000}ms"
    )
    assert result["sample_count"] == SPAN_RECORD_WARMUP_ROUNDS + SPAN_RECORD_SAMPLE_ROUNDS, "采样计数守卫"


# ===================================================================
# 场景⑦：追踪开销<1%（块序钉死——t_untraced×5 → initialize → t_traced×5）
# ===================================================================


async def sample_tracing_overhead() -> dict[str, Any]:
    """追踪开销双跑采样（委托入口——fail-once 链 k=5+5 轮取中位数）。

    块序钉死（R2-5）：先 t_untraced 块（全局 proxy）×5 → 一次性 initialize →
    t_traced 块×5——禁逐轮交错（幂等闩使交错 reset→initialize 短路假绿）。
    正向锚：t_traced 块结束 exporter span 计数 == 50（防 traced 轮静默降级）。
    """
    if "overhead" in _PERF_CACHE:
        cached_overhead: dict[str, Any] = _PERF_CACHE["overhead"]
        return cached_overhead

    async def _timed_round() -> float:
        chain = await _assemble_chain(verify_mode="fail_once", delay_sec=FAKE_LLM_DELAY_SEC)
        started = time.perf_counter()
        result, error = await _run_chain(chain)
        elapsed = time.perf_counter() - started
        assert error is None
        assert len(result.executed_phases) == 9
        return elapsed

    untraced_times: list[float] = []
    for _ in range(OVERHEAD_ROUNDS_PER_BLOCK):
        untraced_times.append(await _timed_round())

    _, exporter = _enable_global_tracing()  # 一次性 initialize（块间单点切换）
    traced_times: list[float] = []
    for _ in range(OVERHEAD_ROUNDS_PER_BLOCK):
        traced_times.append(await _timed_round())

    traced_span_count = len(exporter.get_finished_spans())
    untraced_median = statistics.median(untraced_times)
    traced_median = statistics.median(traced_times)
    result = {
        "overhead_ratio": (traced_median - untraced_median) / untraced_median,
        "untraced_median_seconds": untraced_median,
        "traced_median_seconds": traced_median,
        "traced_span_count": traced_span_count,
    }
    _PERF_CACHE["overhead"] = result
    return result


@pytest.mark.benchmark
async def test_scenario_7_tracing_overhead_below_1_percent() -> None:
    """场景⑦：开销公式断言 + t_untraced 下限守卫 + 正向锚。"""
    result = await sample_tracing_overhead()

    assert result["untraced_median_seconds"] >= UNTRACED_BASELINE_MIN_SECONDS, (
        f"t_untraced 基准 {result['untraced_median_seconds']:.3f}s 应 ≥ {UNTRACED_BASELINE_MIN_SECONDS}s"
        "（防链被意外加速导致分母失真）"
    )
    assert result["traced_span_count"] == TRACED_BLOCK_SPAN_COUNT, (
        f"traced 块 span 计数应恰 {TRACED_BLOCK_SPAN_COUNT}（10 span × 5 轮——正向锚），实际 {result['traced_span_count']}"
    )
    assert result["overhead_ratio"] < 0.01, (
        f"追踪开销比例 {result['overhead_ratio']:.4f} 应 < 1%"
        f"（untraced={result['untraced_median_seconds']:.3f}s traced={result['traced_median_seconds']:.3f}s）"
    )


# ===================================================================
# 场景⑧：trace_id 贯通
# ===================================================================


async def test_scenario_8_trace_id_propagation() -> None:
    """场景⑧：span hex == ExecutionContext.trace_id（工具步前提）；NoOp 全零。"""
    _, exporter = _enable_global_tracing()
    chain = await _assemble_chain(verify_mode="always_pass", plan_tool_names=("PESTEL 分析",))

    _, error = await _run_chain(chain)
    assert error is None

    captured = chain["tool_service"].captured_contexts
    assert captured, "链应含 ≥1 工具步（ExecutionContext 构造点前提）"
    roots = [s for s in exporter.get_finished_spans() if s.name == "agent_execution"]
    assert roots, "应产生根 span"
    expected_hex = format(roots[0].context.trace_id, "032x")
    assert {ctx.trace_id for ctx in captured} == {expected_hex}

    # NoOp 再跑（前置双复位——全零 32 位 hex 降级语义）
    _reset_global()
    chain_noop = await _assemble_chain(verify_mode="always_pass", plan_tool_names=("PESTEL 分析",))
    _, error_noop = await _run_chain(chain_noop)
    assert error_noop is None
    captured_noop = chain_noop["tool_service"].captured_contexts
    assert {ctx.trace_id for ctx in captured_noop} == {"0" * 32}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
