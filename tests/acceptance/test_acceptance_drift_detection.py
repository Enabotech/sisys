"""验收测试 Story 5.9 - CUSUM 漂移检测与触发重校准（FR-EV-03）。

13 场景三属性分档表（Task 0.6 定稿——Task 6 追加收尾场景成 14 终态）：

| 场景 | 外部服务依赖 | 前置状态（Given 装配） | 断言面（Then） |
|------|-------------|----------------------|---------------|
| AC-1.1 | 零（组件级） | 真实检测器手工构造 + 常量单源 | 预热期/基线冻结/双侧累积和手算锚/s35 确认 severe down |
| AC-1.2 | 零（组件级） | 真实检测器（每形态新实例） | N中M 边界三形态/当前样本条件/确认后复位/基线保持/再确认间隔 |
| AC-1.3 | 零（组件级） | 真实检测器 | 无漂移对照/正向漂移 0.95×8 moderate/degenerate/入参域 201 |
| AC-2.1 | 零（真实检测器 + 零 IO 替身） | 手写 _RecordingEventPublisher | 事件字段真值/agent_id 透传/未确认零发布/事件契约 |
| AC-2.2 | 零（配置读取） | yaml + DEFAULT_MAPPINGS 加载 | 双登记可靠字段逐字一致 |
| AC-2.3 | 零（真实检测器 + 抛异常替身） | 手写 _RaisingEventPublisher | 发布失败 logger.error 降级不上抛 |
| AC-3.1 | 零（Fake LLM 链 + OTel 通道） | 链级 initialize + 检测器预填充 34 样本 | drift.detected 真值（OD-2 兑现）+ 事件发布 |
| AC-3.2 | 零（同上 + FakeDriftPort） | 链级 initialize + 451 注入 | 主链正常 + 三键仍在 + drift 缺席 + warning |
| AC-3.3 | 零（链级 OTel 通道） | 模块加载 + None 路径装配 | 七依赖签名/None 基线/断言同步 ×5 基线 |
| AC-4.1 | 零（组合根 resolve） | get_resolver（conftest session 闩） | resolve 四件/工厂注入/CR1-DF2 防护/契约 11 维度 |
| AC-4.2 | 零（静态扫描） | 交付文件存在 | 零新第三方/domain 收窄/零实例化/静态锚/env 零改动 |
| AC-5.1 | 零（委托集成计时） | _PERF_CACHE["p99"] 委托采样 | P99<100ms + 正向锚 101 |
| AC-5.2 | 零（委托集成回测） | _PERF_CACHE["backtest"] 委托回测 | acc≥0.85 + 确定性 + xdist 组互异 |

span 断言锚（5.7 SSOT 全文唯一口径）：链级场景（AC-3.*）统一通道 = 场景级新
TracerProvider + SimpleSpanProcessor + InMemorySpanExporter 经
PhoenixTracer(config=测试配置, tracer_provider=注入).initialize() → 断言 →
teardown 强制 reset_for_testing() 双复位；组件级场景（AC-1/AC-2）零全局触碰。

检测器状态隔离（本 Story 最大隔离面——SINGLETON 有状态）：全部场景手工构造
新实例（不走 resolve）；场景内序列灌入经场景私有实例——零跨场景状态残留。

Run with:
    poetry run pytest tests/acceptance/test_acceptance_drift_detection.py -v
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Coroutine, Generator

import pytest
from pytest_bdd import given, scenario, then, when

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"

# 文件名不含服务关键词且零外部服务——无 redis/database marker；xdist_group 与集成
# 计时/回测场景逐字同组（loadgroup 同 worker 串行是 _PERF_CACHE 委托缓存命中前提）
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.xdist_group("drift-detection-perf"),
]


@pytest.fixture(scope="module")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """模块级事件循环（BDD 步骤 run_until_complete 专用，禁 @pytest.mark.asyncio）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _otel_global_state_isolation() -> Generator[None, None, None]:
    """OTel 全局状态 function 级双复位兜底（5-7 SSOT——凡 initialize 一律双复位义务）。

    每场景前置 + teardown 双复位（变量复位 + Once 闩锁重建）：兼修已知同进程泄漏源
    （test_event_monitoring::TestInitTracing）与场景间交叉污染。
    """
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    PhoenixTracer.reset_for_testing()
    yield
    PhoenixTracer.reset_for_testing()


@pytest.fixture
def context(event_loop: asyncio.AbstractEventLoop) -> Generator[dict[str, Any], None, None]:
    """场景级共享上下文（dict 形态——R6 骨架）。"""
    ctx: dict[str, Any] = {"_loop": event_loop}
    yield ctx
    exporter = ctx.pop("_exporter", None)
    if exporter is not None:
        exporter.clear()


def _run_async(event_loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, Any]) -> Any:
    """同循环调度（BDD 步骤禁 @pytest.mark.asyncio——context 数据丢失）."""
    return event_loop.run_until_complete(coro)


# ===================================================================
# 装配 helpers（延迟 import 纪律——本 Story 新交付模块一律函数体内 import）
# ===================================================================

#: 手算锚基线序列（[0.7, 0.9]×15——μ₀=0.8，σ₀=statistics.stdev 实算 ≈0.1017）
_BASELINE_SEQUENCE: list[float] = [0.7, 0.9] * 15

#: 漂移注入值（下漂锚——Sₗ 增量 = 0.8 - 0.5×σ₀ - 0.4 ≈ 0.349）
_DOWN_DRIFT_SCORE = 0.4


def _baseline_stats() -> tuple[float, float]:
    """基线统计实算（μ₀/σ₀——statistics.mean/stdev[ddof=1] 同式单源）。"""
    import statistics

    return statistics.mean(_BASELINE_SEQUENCE), statistics.stdev(_BASELINE_SEQUENCE)


def _feed_detector(loop: asyncio.AbstractEventLoop, detector: Any, scores: list[float]) -> list[Any]:
    """逐样本灌入检测器并收集 assessment（同循环调度——预热/检测两阶段统一入口）。"""
    return [loop.run_until_complete(detector.update(score)) for score in scores]


class _RecordingEventPublisher:
    """记录发布事件的发布器（内存替身发布面——15 文件同款定义先例）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(event.event_id) if hasattr(event, "event_id") else "",
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


class _RaisingEventPublisher:
    """恒抛异常的发布器替身（AC-2.3 发布失败降级注入面——duck-typing 端口契约）。"""

    async def publish(self, event: Any) -> Any:
        raise RuntimeError("模拟事件发布通道故障（验收注入）")


class _FakeDriftPort:
    """手写零 IO 漂移检测替身（验收禁 mock 红线——duck-typing 端口契约）。

    update 抛注入异常（AC-3.2 的 451 降级注入面）+ 调用计数（评估降级联动断言锚）；
    正常路径返回合法未确认 DriftAssessment（baseline_ready=True 检测态形态）。
    """

    def __init__(self, update_error: Exception | None = None) -> None:
        self.update_calls = 0
        self.trigger_calls = 0
        self._update_error = update_error

    async def update(self, score: float) -> Any:
        from src.application.ports.agent_drift import DriftAssessment

        self.update_calls += 1
        if self._update_error is not None:
            raise self._update_error
        return DriftAssessment(
            is_drifted=False,
            baseline_ready=True,
            drift_direction="none",
            drift_level="none",
            cusum_high=0.0,
            cusum_low=0.0,
            baseline_mean=0.8,
            baseline_std=0.1,
            observed_value=float(score),
            sample_count=1,
        )

    async def trigger_recalibration(self, assessment: Any, agent_id: str | None = None) -> None:
        self.trigger_calls += 1
        return None


def _make_phoenix_config(**overrides: Any) -> Any:
    """链级测试配置（enabled 全采样——endpoint 仅装配不外联）。"""
    from src.infrastructure.config.phoenix import PhoenixConfig

    kwargs: dict[str, Any] = {
        "enabled": True,
        "endpoint": "http://localhost:4317",
        "project_name": "sisys-agent",
        "sampling_ratio": 1.0,
    }
    kwargs.update(overrides)
    return PhoenixConfig(**kwargs)


def _enable_test_tracing(context: dict[str, Any]) -> None:
    """链级统一通道：注入 provider 经 initialize 履行全局 set（唯一职责——5-7 SSOT）。"""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = PhoenixTracer(config=_make_phoenix_config(), tracer_provider=provider)
    assert tracer.initialize() is True, "注入通道 initialize 应返回 True（全局 set 成功）"
    context["_provider"] = provider
    context["_exporter"] = exporter
    context["_phoenix_tracer"] = tracer


class _StubAgentRepository:
    """零 IO Agent 仓储替身（返回真实 Agent 实体——duck-typing 实现端口契约）。"""

    def __init__(self, agent: Any) -> None:
        self._agent = agent

    async def get_by_id(self, agent_id: Any) -> Any:
        return self._agent if agent_id == self._agent.agent_id else None


class _StubIsolationRepository:
    """零 IO 隔离仓储替身（恒返回 L4_HARD 初始化态——duck-typing 端口契约）。"""

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
    """手写 duck-typing 日志仓储替身（5-3 验收同款先例——零 IO）。"""

    async def save(self, log: Any) -> None:
        return None

    async def search(self, query: Any) -> Any:
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


class _StubProfileUseCase:
    """零 IO 档案用例替身（duck-typing——返回手工装配的 AgentProfileLoadResult）。"""

    def __init__(self, profile_result: Any) -> None:
        self._profile_result = profile_result

    async def execute(self, agent_id: Any) -> Any:
        return self._profile_result


def _make_fake_llm() -> Any:
    """六阶段 + 幻觉检测 Fake LLM 替身（外部 SaaS 豁免面——5-8 先例 + 本地变体）。

    分派键 = response_schema 身份（Schema 两两不同前提）；幻觉分恒 0.2（5-8 helper
    默认值径用——两路径[确认/对照]对末样本全域鲁棒，R2 背书，无需注入参数）。
    """
    from unittest.mock import AsyncMock

    from src.application.services.agent_workflow_schemas import (
        ChainOfThoughtSchema,
        PerceptionSchema,
        PlanSchema,
        PlanStep,
        ReflectionSchema,
        VerificationSchema,
    )
    from src.application.services.evaluation_schemas import HallucinationEvaluationSchema
    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    verify_calls = {"count": 0}
    tool_llm_calls = {"count": 0}

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        if response_schema is HallucinationEvaluationSchema:
            return HallucinationEvaluationSchema(
                rationale="回答与证据材料一致，无幻觉内容",
                hallucination_score=0.2,
            )
        if response_schema is PerceptionSchema:
            return PerceptionSchema(summary="任务摘要：新能源车进入战略分析")
        if response_schema is PlanSchema:
            return PlanSchema(steps=[PlanStep(description="零工具直接推理", tool_name="", arguments={})], selected_tools=[])
        if response_schema is VerificationSchema:
            verify_calls["count"] += 1
            return VerificationSchema(
                passed=True,
                confidence=0.85,
                rationale="结构化检查通过",
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
    """工具执行面替身边界（真实服务链 + Fake llm + 沙箱替身——5-7 先例同款）。"""
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
    """手工组装工具注册服务（InMemoryToolRepository + register_all——5-3 验收同款）。"""
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    return registry


def _prefill_detector(loop: asyncio.AbstractEventLoop, detector: Any, mode: str) -> list[Any]:
    """检测器预填充（链级场景——单次 execute 即确认的轻量替代形态）。

    drift 形态 = 30 基线交替 + 4×0.4（Sₗ 预累积 ≈1.397>h——末样本 [0,1] 全域任意值
    均确认 down，确认解析域 x<1.637 ⊃ [0,1]）；normal 形态 = 30 基线 + 4 交替续灌
    （S 有界 0↔0.049 恒 F——对照场景，禁复用 4×0.4 预填[数学互斥]）。
    """
    if mode == "drift":
        prefill = list(_BASELINE_SEQUENCE) + [_DOWN_DRIFT_SCORE] * 4
    else:
        prefill = list(_BASELINE_SEQUENCE) + [0.7, 0.9, 0.7, 0.9]
    return _feed_detector(loop, detector, prefill)


def _assemble_drift_workflow_chain(context: dict[str, Any], *, drift_detector: Any = None, prefill: str | None = None) -> None:
    """AC-3 链级手工装配（5-8 _assemble_evaluation_workflow_chain 同款 + 第七依赖注入）。

    零工具步（plan 零工具）——evidence 三元组全空 → cr=0.0；评估链 resolver 用替身。
    drift_detector 提供且 prefill 非空时先预填充（场景私有实例——SINGLETON 隔离防线）。
    """
    from src.application.services.agent_workflow_service import AgentWorkflowService
    from src.application.services.evaluation_harness import EvaluationHarness
    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
    from src.domain.entities.agent import Agent, AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

    loop = context["_loop"]
    import uuid as uuid_module

    agent = Agent(agent_id=uuid_module.uuid4(), role=AgentRole.CEO, name="CEO Agent")
    context["agent"] = agent
    context["task"] = "分析新能源汽车行业进入战略并给出三层次建议"

    stub_agent_repo: Any = _StubAgentRepository(agent)
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

    fake_llm = _make_fake_llm()
    context["fake_llm"] = fake_llm
    tool_execution_service = _build_tool_execution_service(fake_llm)

    service: Any = AgentWorkflowService(
        llm_client=fake_llm,
        tool_execution_service=tool_execution_service,
        skill_loader=resolve("skill_loader"),
        tool_registry_service=_make_registry(),
        isolation_guard=guard,
    )
    context["service"] = service

    recorder = _RecordingEventPublisher()
    context["recorder"] = recorder
    context["engine"] = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=recorder,
        workflow_service=service,
    )

    profile_loader = resolve("agent_profile_loader")
    profile = _run_async(loop, profile_loader.load(role=AgentRole.CEO, agent_id=agent.agent_id))
    skill_selector = resolve("skill_selector")
    tools_l1 = _run_async(loop, skill_selector.list_active_skills())

    from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult

    profile_result = AgentProfileLoadResult(
        agent_id=agent.agent_id,
        role=AgentRole.CEO,
        profile=profile,
        tools_l1=tools_l1,
        startup_context_tokens=0,
    )
    profile_use_case: Any = _StubProfileUseCase(profile_result)

    evaluation_harness = EvaluationHarness(llm_client=fake_llm, model_resolver=_make_evaluation_resolver_stub())
    context["evaluation_harness"] = evaluation_harness

    injected_detector = drift_detector
    if injected_detector is not None and prefill is not None:
        _prefill_detector(loop, injected_detector, prefill)
    context["drift_detector"] = injected_detector
    context["use_case"] = RunAgentWorkflowUseCase(
        agent_repository=stub_agent_repo,
        agent_profile_use_case=profile_use_case,
        agent_engine=context["engine"],
        agent_workflow_service=service,
        isolation_guard=guard,
        evaluation_harness=evaluation_harness,
        drift_detector=injected_detector,
    )


#: 测试假密钥占位（resolver 替身基底的连接字段——非真实凭据；5-8 验收同款拆分形态）
_BASE_EVAL_FAKE_KEY = "base-eval-" + "fake-key"


def _make_evaluation_resolver_stub() -> Any:
    """评估链 resolver 替身（连接字段非默认值——5-8 验收同款）。"""
    from src.domain.ports.llm_client import LLMConfig

    class _StaticModelResolverStub:
        """固定基底配置解析替身（评估断言与路由方向解耦）。"""

        def __init__(self, base_config: Any) -> None:
            self.base_config = base_config

        async def resolve_config(self, input_text: str) -> Any:
            return self.base_config

    return _StaticModelResolverStub(
        LLMConfig(model="base-eval-model", endpoint="https://base-eval.example/v1", api_key=_BASE_EVAL_FAKE_KEY)
    )


def _run_workflow(context: dict[str, Any]) -> None:
    """执行 run-task 工作流（异常捕获存 context["caught"]——透传断言锚）。"""
    try:
        context["result"] = _run_async(
            context["_loop"],
            context["use_case"].execute(context["agent"].agent_id, context["task"]),
        )
    except Exception as exc:  # BDD 步骤异常捕获锚（context["caught"] 三段式断言）
        context["caught"] = exc


def _find_root_span(context: dict[str, Any]) -> Any:
    """取 agent_execution 根 span（唯一——链级断言统一入口）。"""
    spans = [s for s in context["_exporter"].get_finished_spans() if s.name == "agent_execution"]
    assert len(spans) == 1, f"应恰有一个 agent_execution 根 span，实际 {len(spans)}"
    return spans[0]


# ===================================================================
# 场景绑定（13 场景全显式——Task 6 追加收尾成 14 终态）
# ===================================================================


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-1.1 - CUSUM 双侧累积和与预热基线",
)
def test_ac_1_1_cusum_two_sided_cumulative_sum_and_warmup_baseline(context: dict[str, Any]) -> None:
    """AC-1.1: 预热期/基线冻结/双侧累积和手算锚/s35 确认 severe down。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-1.2 - N中M 确认与确认后复位",
)
def test_ac_1_2_n_of_m_confirmation_and_reset(context: dict[str, Any]) -> None:
    """AC-1.2: 确认窗边界三形态/当前样本条件/确认后复位/基线保持/再确认间隔锚。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-1.3 - 无漂移对照与正向漂移与防御面",
)
def test_ac_1_3_no_drift_control_upward_drift_and_defenses(context: dict[str, Any]) -> None:
    """AC-1.3: 无漂移对照/0.95×8 上漂 moderate/degenerate/入参域 201。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-2.1 - trigger_recalibration 发布 DriftDetected 事件",
)
def test_ac_2_1_trigger_recalibration_publishes_drift_detected(context: dict[str, Any]) -> None:
    """AC-2.1: 事件字段真值/agent_id 透传/未确认零发布/事件契约三断言。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-2.2 - 事件通道双登记契约",
)
def test_ac_2_2_event_channel_dual_registration(context: dict[str, Any]) -> None:
    """AC-2.2: yaml + DEFAULT_MAPPINGS 双登记可靠字段逐字一致。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-2.3 - 发布失败降级不阻断",
)
def test_ac_2_3_publish_failure_degrades_gracefully(context: dict[str, Any]) -> None:
    """AC-2.3: 替身抛异常 → logger.error 降级不上抛 returns None。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-3.1 - 主链漂移检测执行与 drift.detected span 填值",
)
def test_ac_3_1_main_chain_drift_detection_and_span_fill(context: dict[str, Any]) -> None:
    """AC-3.1: drift.detected span 真值（OD-2[5.7] 兑现锚）+ DriftDetected 事件发布。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-3.2 - 漂移检测降级不阻断主链",
)
def test_ac_3_2_drift_detection_degradation_does_not_block(context: dict[str, Any]) -> None:
    """AC-3.2: 451 注入 → catch 扩 + 三键仍在 + drift 缺席 + warning。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-3.3 - 构造签名七依赖与存量回归基线",
)
def test_ac_3_3_seven_dependency_signature_and_regression_baseline(context: dict[str, Any]) -> None:
    """AC-3.3: 七依赖签名/None 默认基线一致/断言同步 ×5 基线。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-4.1 - 组合根接线与降级防护",
)
def test_ac_4_1_composition_root_wiring_and_degradation_guard(context: dict[str, Any]) -> None:
    """AC-4.1: resolve 四件/工厂第七依赖/CR1-DF2 降级防护/契约 11 维度。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-4.2 - 架构静态扫描",
)
def test_ac_4_2_architecture_static_scan(context: dict[str, Any]) -> None:
    """AC-4.2: 零新第三方/domain 收窄/零实例化/依赖方向/主链静态锚/env 零改动。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-5.1 - 检测延迟 P99 小于 100ms",
)
def test_ac_5_1_detection_latency_p99_below_100ms(context: dict[str, Any]) -> None:
    """AC-5.1: 委托集成计时（P99<100ms 常量单源 + 正向锚 101）。"""


@scenario(
    "test_acceptance_drift_detection.feature",
    "AC-5.2 - 合成序列回测准确率不低于 85%",
)
def test_ac_5_2_synthetic_backtest_accuracy(context: dict[str, Any]) -> None:
    """AC-5.2: 委托回测（acc≥0.85 + 确定性 + xdist 组互异）。"""


# ===================================================================
# AC-1: CUSUMDriftDetector 双侧累积和算法（组件级——零服务依赖）
# ===================================================================


@given("真实 CUSUMDriftDetector 实例已装配（模块常量单源断言）")
def given_real_detector_assembled(context: dict[str, Any]) -> None:
    """手工构造真实检测器（每场景新实例——SINGLETON 状态隔离防线）+ 常量单源六项断言。"""
    from src.infrastructure.monitoring.cusum_detector import (
        CONFIRMATION_M,
        CONFIRMATION_N,
        H_MULTIPLIER,
        K_MULTIPLIER,
        METRIC_NAME,
        WARMUP_SAMPLES,
        CUSUMDriftDetector,
    )

    assert METRIC_NAME == "overall_score"
    assert K_MULTIPLIER == 0.5
    assert H_MULTIPLIER == 5.0
    assert CONFIRMATION_N == 3
    assert CONFIRMATION_M == 5
    assert WARMUP_SAMPLES == 30
    context["detector"] = CUSUMDriftDetector()
    context["baseline"] = list(_BASELINE_SEQUENCE)
    context["mu0"], context["sigma0"] = _baseline_stats()


@when("灌入 30 样本交替基线序列与 5 样本漂移注入序列")
def when_feed_baseline_and_drift_sequences(context: dict[str, Any]) -> None:
    """灌入序列（30 基线 + 5×0.4 漂移注入——s35 确认的手算锚序列）。"""
    sequence = list(_BASELINE_SEQUENCE) + [_DOWN_DRIFT_SCORE] * 5
    context["assessments"] = _feed_detector(context["_loop"], context["detector"], sequence)


@then("预热期行为断言通过（baseline_ready=False + sample_count 递增 + 预热统计 + N=1 时 baseline_std=0.0）")
def then_warmup_phase_behavior(context: dict[str, Any]) -> None:
    """预热期断言（前 30 样本——预热统计手算对照 + N=1 钉死）。"""
    import statistics

    assessments = context["assessments"]
    assert len(assessments) == 35
    mu0, sigma0 = context["mu0"], context["sigma0"]
    for index in range(30):
        assessment = assessments[index]
        assert assessment.baseline_ready is False, f"预热期样本 {index + 1} baseline_ready 应为 False"
        assert assessment.is_drifted is False
        assert assessment.sample_count == index + 1
        window = _BASELINE_SEQUENCE[: index + 1]
        assert assessment.baseline_mean == statistics.mean(window)
        if index == 0:
            assert assessment.baseline_std == 0.0, "N=1 时 baseline_std 应为 0.0（statistics.stdev 需 ≥2 样本）"
        else:
            assert assessment.baseline_std == statistics.stdev(window)
    # 第 30 样本返回 30 样本窗统计（先入窗后统计——与冻结 μ₀/σ₀ 同值）
    assert assessments[29].baseline_mean == mu0
    assert assessments[29].baseline_std == sigma0
    assert sigma0 > 0


@then("第 30 样本起基线冻结断言通过（第 31 样本 baseline_ready=True + 后续样本基线不变）")
def then_baseline_frozen_after_warmup(context: dict[str, Any]) -> None:
    """基线冻结断言（第 31 样本起检测期 + μ₀/σ₀ 不随后续样本变化）。"""
    assessments = context["assessments"]
    mu0, sigma0 = context["mu0"], context["sigma0"]
    assert assessments[30].baseline_ready is True, "第 31 样本起 baseline_ready 应为 True"
    for assessment in assessments[30:]:
        assert assessment.baseline_mean == mu0, "基线冻结：baseline_mean 不应随检测期样本变化"
        assert assessment.baseline_std == sigma0, "基线冻结：baseline_std 不应随检测期样本变化"


@then("双侧累积和逐样本 Sₗ 手算锚断言通过（同式表达式实算）")
def then_two_sided_cumsum_hand_computed_anchor(context: dict[str, Any]) -> None:
    """逐样本 Sₗ 断言（钦定同式表达式 (0.8 - 0.5*sigma0 - 0.4) * n——σ₀ 实算，禁字面量）。"""
    sigma0 = context["sigma0"]
    increment = 0.8 - 0.5 * sigma0 - _DOWN_DRIFT_SCORE
    for n in range(1, 6):
        assessment = context["assessments"][29 + n]
        assert assessment.cusum_low == increment * n, (
            f"s{30 + n} 的 cusum_low 应等于同式闭式（实际 {assessment.cusum_low}，期望 {increment * n}）"
        )
        assert assessment.cusum_high == 0.0, f"s{30 + n} 下漂注入下 cusum_high 应恒 0（实际 {assessment.cusum_high}）"


@then("s35 确认漂移（is_drifted=True + direction=down + level=severe + ratio 同式表达 >8）")
def then_s35_confirms_severe_down(context: dict[str, Any]) -> None:
    """s35 确认断言（窗 (F,T,T,T,T) 计数 4≥3 且当前样本 T——severity 乘法同式）。"""
    sigma0 = context["sigma0"]
    confirmed = context["assessments"][34]
    assert confirmed.is_drifted is True, "s35 应确认漂移"
    assert confirmed.drift_direction == "down"
    assert confirmed.drift_level == "severe"
    assert confirmed.observed_value == _DOWN_DRIFT_SCORE
    assert confirmed.sample_count == 35
    # ratio 同式表达（Sₗ/σ₀ > 8 severe 判定的乘法同式——与 detection 同乘法系）
    assert (0.8 - 0.5 * sigma0 - _DOWN_DRIFT_SCORE) * 5 > 8 * sigma0, "severe 档 ratio 同式断言"
    assert confirmed.cusum_low > 8 * sigma0, "确认时 Sₗ 应 > 8σ₀（severe 域）"


@given("真实 CUSUMDriftDetector 实例已装配（注入手写零 IO publisher 替身）")
def given_detector_with_recording_publisher(context: dict[str, Any]) -> None:
    """装配检测器 + 零 IO publisher 替身（捕获列表——AC-2 断言锚）。"""
    from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

    publisher = _RecordingEventPublisher()
    context["publisher"] = publisher
    context["detector"] = CUSUMDriftDetector(event_publisher=publisher)
    context["baseline"] = list(_BASELINE_SEQUENCE)
    context["mu0"], context["sigma0"] = _baseline_stats()


@given("确认漂移的 DriftAssessment 实例已产出（手算锚序列）")
def given_confirmed_assessment_produced(context: dict[str, Any]) -> None:
    """手算锚序列产出确认 assessment（s35——AC-2 事件字段数据源）。"""
    sequence = list(_BASELINE_SEQUENCE) + [_DOWN_DRIFT_SCORE] * 5
    assessments = _feed_detector(context["_loop"], context["detector"], sequence)
    confirmed = assessments[34]
    assert confirmed.is_drifted is True, "手算锚序列 s35 应确认漂移"
    context["confirmed_assessment"] = confirmed


@when("执行确认窗边界三形态序列与确认后复位序列")
def when_confirmation_window_boundaries_and_reset(context: dict[str, Any]) -> None:
    """边界三形态（各新检测器实例——B 形态不确认不清窗防互染）+ 复位序列执行。"""
    from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

    # 手算锚序列：s31-s34 detection (F,T,T,T) 但窗未满 5 不确认
    anchor_assessments = _feed_detector(
        context["_loop"], CUSUMDriftDetector(), list(_BASELINE_SEQUENCE) + [_DOWN_DRIFT_SCORE] * 4
    )
    context["anchor_prefix_assessments"] = anchor_assessments[30:34]

    # 边界三形态（R2 钦定构造序列——窗口是内部态不可直注，端到端构造）
    boundary_specs = {
        "confirm": [0.35, 0.52, 0.75, 1.0, 0.4],  # (F,T,T,F,T) 计数 3 且当前 T → 确认
        "current_false": [0.35, 0.52, 0.75, 0.75, 1.0],  # (F,T,T,T,F) 计数 3 但当前 F → 不确认
        "count_two": [0.35, 0.52, 0.75, 1.0, 1.0],  # (F,T,T,F,F) 计数 2 → 不确认
    }
    boundary_results: dict[str, list[Any]] = {}
    for name, tail in boundary_specs.items():
        detector = CUSUMDriftDetector()
        full_assessments = _feed_detector(context["_loop"], detector, list(_BASELINE_SEQUENCE) + tail)
        boundary_results[name] = full_assessments[30:]  # 检测期 5 样本切片（预热期样本剔除）
    context["boundary_results"] = boundary_results

    # 复位序列：手算锚 s35 确认后续灌 5×0.4（再确认间隔锚——复位后从零累积）
    reset_detector = CUSUMDriftDetector()
    reset_assessments = _feed_detector(
        context["_loop"], reset_detector, list(_BASELINE_SEQUENCE) + [_DOWN_DRIFT_SCORE] * 5 + [_DOWN_DRIFT_SCORE] * 5
    )
    context["reset_first_confirmed"] = reset_assessments[34]
    context["reset_followups"] = reset_assessments[35:40]


@then("确认窗未满 5 不确认断言通过（s32-s34 detection True 但 is_drifted=False）")
def then_window_not_full_no_confirmation(context: dict[str, Any]) -> None:
    """s32-s34 断言（detection 经 Sₗ > h 同式推导——DTO 不暴露逐样本 detection）。"""
    sigma0 = context["sigma0"]
    increment = 0.8 - 0.5 * sigma0 - _DOWN_DRIFT_SCORE
    for offset, assessment in enumerate(context["anchor_prefix_assessments"], start=1):
        assert assessment.is_drifted is False, f"s{30 + offset} 窗未满 5 不应确认"
        if offset >= 2:
            assert assessment.cusum_low > 5 * sigma0, f"s{30 + offset} Sₗ > h（detection=True 推导断言）"
    assert increment * 2 > 5 * sigma0, "s32 起应满足 detection（Sₗ 越线）"


@then("当前样本条件断言通过（(F,T,T,T,F) 不确认 + (F,T,T,F,T) 确认 + (F,T,T,F,F) 不确认）")
def then_current_sample_condition(context: dict[str, Any]) -> None:
    """N中M 当前样本条件三形态（ISA-18.2 M-of-N 告警宣告语义——确认时刻必在告警态）。"""
    results = context["boundary_results"]
    # (F,T,T,F,T)：计数 3 且当前样本 T → 确认
    confirm_tail = results["confirm"]
    assert all(a.is_drifted is False for a in confirm_tail[:4]), "前 4 样本窗未满不确认"
    assert confirm_tail[4].is_drifted is True, "(F,T,T,F,T) 计数 3 且当前 T 应确认"
    # (F,T,T,T,F)：计数 3 但当前样本 F → 不确认（R1 语义修正）
    current_false_tail = results["current_false"]
    assert all(a.is_drifted is False for a in current_false_tail), "(F,T,T,T,F) 当前样本 F 不应确认"
    # (F,T,T,F,F)：计数 2 → 不确认
    count_two_tail = results["count_two"]
    assert all(a.is_drifted is False for a in count_two_tail), "(F,T,T,F,F) 计数 2 不应确认"


@then("确认后复位断言通过（S 归零重启 + 确认窗清空 + 基线保持 + 再确认间隔锚）")
def then_reset_after_confirmation(context: dict[str, Any]) -> None:
    """复位断言（OD-5：确认即 S 归零 + 窗清空——基线保持 + 5 样本再确认）。"""
    sigma0 = context["sigma0"]
    increment = 0.8 - 0.5 * sigma0 - _DOWN_DRIFT_SCORE
    first_confirmed = context["reset_first_confirmed"]
    followups = context["reset_followups"]
    # S 归零重启：复位后第 1 样本 cusum_low == 单增量（从 0 重新累积）
    assert followups[0].cusum_low == increment, (
        f"复位后第 1 样本 cusum_low 应从零重启（实际 {followups[0].cusum_low}，期望 {increment}）"
    )
    # 确认窗清空：复位后前 4 样本（窗计数不足 3 前）不确认——(F,T,T,T) 窗未满
    for offset in range(4):
        assert followups[offset].is_drifted is False, f"复位后第 {offset + 1} 样本不应确认（窗清空重计）"
    # 再确认间隔锚：复位后第 5 样本再确认（OD-5① 实测 down δ=0.4 间隔 5 样本）
    assert followups[4].is_drifted is True, "复位后第 5 样本应再确认（重复告警节奏锚）"
    assert followups[4].drift_direction == "down"
    # 基线保持：复位后 baseline_mean/std 与首确认时相等
    for followup in followups:
        assert followup.baseline_mean == first_confirmed.baseline_mean, "复位不重估基线（baseline_mean 保持）"
        assert followup.baseline_std == first_confirmed.baseline_std, "复位不重估基线（baseline_std 保持）"


@when("执行无漂移对照续灌与正向漂移注入与 degenerate 基线与入参域越界参数化")
def when_control_upward_degenerate_and_domain_guard(context: dict[str, Any]) -> None:
    """四防御面序列执行（各新检测器实例——场景内序列互染防线）。"""
    from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

    # 无漂移对照：基线后交替续灌 10 样本
    context["control_assessments"] = _feed_detector(
        context["_loop"], CUSUMDriftDetector(), list(_BASELINE_SEQUENCE) + [0.7, 0.9] * 5
    )[30:]
    # 正向漂移：基线后 0.95×8（R1 修正锚——原 0.95×6 不可确认）
    context["upward_assessments"] = _feed_detector(
        context["_loop"], CUSUMDriftDetector(), list(_BASELINE_SEQUENCE) + [0.95] * 8
    )[30:]
    # degenerate：全同值基线 [0.8]×30 + 0.4 注入 10 样本
    context["degenerate_assessments"] = _feed_detector(
        context["_loop"], CUSUMDriftDetector(), [0.8] * 30 + [_DOWN_DRIFT_SCORE] * 10
    )
    # 入参域越界（参数化循环——201 三段式的捕获锚；untyped 通道注入域外类型）
    from src.domain.exceptions import ValidationError

    violations: list[Any] = []
    detector = CUSUMDriftDetector()
    for bad_score in (-0.01, 1.01, True, "0.8"):
        untyped_score: Any = bad_score
        try:
            _run_async(context["_loop"], detector.update(untyped_score))
        except ValidationError as error:
            violations.append((bad_score, error))
        else:
            violations.append((bad_score, None))
    context["domain_guard_violations"] = violations


@then("无漂移对照断言通过（交替序列续灌恒不触发 + S 有界）")
def then_no_drift_control(context: dict[str, Any]) -> None:
    """交替续灌断言（S 在 0↔单增量震荡——同式上界断言）。"""
    sigma0 = context["sigma0"]
    # 上界用与实现完全同序的同式表达式（μ₀ - k - x 的 0.7 形态——Sₗ 单步增量；
    # 0.9-0.8-k 形态与实现计算序不等价，浮点下差 1.5e-16 必假红）
    single_increment = 0.8 - 0.5 * sigma0 - 0.7
    for index, assessment in enumerate(context["control_assessments"], start=1):
        assert assessment.is_drifted is False, f"对照样本 {index} 不应触发"
        peak = max(assessment.cusum_high, assessment.cusum_low)
        assert peak <= single_increment, f"对照样本 {index} S 应有界（实际 {peak}，上界 {single_increment}）"


@then("正向漂移断言通过（0.95×8 确认 up + level=moderate + 前 5 样本余量不触发）")
def then_upward_drift_moderate(context: dict[str, Any]) -> None:
    """上漂锚断言（n≤5 闭式位等 + n≥6 区间比较——1ulp 形态纪律 R3 钉死）。"""
    sigma0 = context["sigma0"]
    upward = context["upward_assessments"]
    increment = 0.95 - 0.8 - 0.5 * sigma0
    # n=1..5 闭式位等（已数值实证安全）
    for n in range(1, 6):
        assert upward[n - 1].cusum_high == increment * n, f"上漂 n={n} Sₕ 同式闭式断言"
    # 前 5 样本余量 2.5% 不触发（非边界形态——余量语义显式化）
    assert increment * 5 < 5 * sigma0, "n=5 时 Sₕ 仍在 h 之下（余量 ≈2.5%）"
    for n in range(1, 6):
        assert upward[n - 1].is_drifted is False, f"上漂 n={n} 不应确认"
    # n=6/7：detection 越线但不确认（窗计数不足 3）
    assert upward[5].cusum_high > 5 * sigma0, "n=6 首次 detection（Sₕ 越线）"
    assert upward[5].is_drifted is False and upward[6].is_drifted is False, "n=6/7 窗计数不足不确认"
    # s38 确认：n≥6 一律区间比较（闭式与逐次累加差 1ulp——禁精确等式）
    confirmed = upward[7]
    assert confirmed.is_drifted is True, "s38 应确认（窗 (F,F,T,T,T) 计数 3 且当前 T）"
    assert confirmed.drift_direction == "up"
    assert confirmed.drift_level == "moderate"
    assert increment * 7 < confirmed.cusum_high <= 8 * sigma0, "s38 Sₕ 区间断言（moderate 域）"


@then("degenerate 防御断言通过（全同值基线恒不判定 + sample_count 递增）")
def then_degenerate_baseline_defense(context: dict[str, Any]) -> None:
    """σ₀≈0 防线断言（detection 恒 False + 样本计数继续累积——可观测降级非异常）。"""
    degenerate = context["degenerate_assessments"]
    assert degenerate[29].baseline_std == 0.0, "全同值基线 σ₀ 应为 0"
    for index, assessment in enumerate(degenerate, start=1):
        assert assessment.is_drifted is False, f"degenerate 样本 {index} 不应判定"
        assert assessment.sample_count == index, "degenerate 下 sample_count 继续递增"


@then("入参域守卫断言通过（越界/bool/非数值抛 ValidationError 201 三段式）")
def then_input_domain_guard(context: dict[str, Any]) -> None:
    """201 三段式断言（raises + code + context 携 score）——四参数化形态。"""
    for bad_score, error in context["domain_guard_violations"]:
        assert error is not None, f"入参 {bad_score!r} 应抛 ValidationError"
        assert error.code == "EXCEPTION_201", f"入参 {bad_score!r} 异常码应为 201（实际 {error.code}）"
        assert "score" in error.context, f"入参 {bad_score!r} context 应携 score 键（实际 {error.context}）"


# ===================================================================
# AC-2: trigger_recalibration 与 DriftDetected 事件（组件级）
# ===================================================================


@when("调用 trigger_recalibration 执行事件发布")
def when_call_trigger_recalibration(context: dict[str, Any]) -> None:
    """触发重校准（确认 assessment + agent_id 显式透传 + None 默认双形态）。"""
    assessment = context["confirmed_assessment"]
    context["trigger_return"] = _run_async(
        context["_loop"], context["detector"].trigger_recalibration(assessment, agent_id="agent-x")
    )
    # None 默认透传形态（第二次调用——agent_id 缺省）
    context["trigger_return_default"] = _run_async(context["_loop"], context["detector"].trigger_recalibration(assessment))
    # 未确认 assessment（is_drifted=False）注入——零发布守卫断言锚
    from src.application.ports.agent_drift import DriftAssessment

    unconfirmed = DriftAssessment(
        is_drifted=False,
        baseline_ready=True,
        drift_direction="none",
        drift_level="none",
        cusum_high=0.0,
        cusum_low=0.0,
        baseline_mean=context["mu0"],
        baseline_std=context["sigma0"],
        observed_value=0.8,
        sample_count=40,
    )
    context["unconfirmed_return"] = _run_async(
        context["_loop"], context["detector"].trigger_recalibration(unconfirmed, agent_id="agent-x")
    )
    # 事件契约三断言材料（注册/aggregate/to_dict）
    from src.domain.events.base import DomainEvent
    from src.domain.events.drift_events import DriftDetected

    context["DriftDetected"] = DriftDetected
    context["event_registry"] = DomainEvent._registry.get("DriftDetected")


@then("发布事件字段真值断言通过（isinstance + metric_name + 逐字段相等 + agent_id 透传）")
def then_published_event_field_truth(context: dict[str, Any]) -> None:
    """事件字段逐项断言（与 assessment 逐字段相等 + agent_id 双形态透传）。"""
    from src.domain.events.drift_events import DriftDetected

    assessment = context["confirmed_assessment"]
    publisher = context["publisher"]
    events = publisher.published_events
    assert len(events) == 2, f"确认+默认两次 trigger 应各发布一次（实际 {len(events)}）"
    for event in events:
        assert isinstance(event, DriftDetected)
        assert event.metric_name == "overall_score"
        assert event.drift_direction == assessment.drift_direction
        assert event.drift_level == assessment.drift_level
        assert event.cusum_high == assessment.cusum_high
        assert event.cusum_low == assessment.cusum_low
        assert event.baseline_mean == assessment.baseline_mean
        assert event.baseline_std == assessment.baseline_std
        assert event.observed_value == assessment.observed_value
        assert event.sample_count == assessment.sample_count
        assert event.recommended_action == "manual_review"
    assert events[0].agent_id == "agent-x", "显式 agent_id 应透传"
    assert events[1].agent_id is None, "缺省 agent_id 应透传 None"
    # 未确认 assessment → 零发布（is_drifted 守卫——与调用方守卫双保险）
    assert len(publisher.published_events) == 2, "未确认 assessment 不应再发布"
    assert context["unconfirmed_return"] is None


@then("未确认 assessment 零发布断言通过（is_drifted=False 注入零捕获）")
def then_unconfirmed_assessment_zero_publish(context: dict[str, Any]) -> None:
    """未确认守卫断言（trigger 内 is_drifted 守卫与调用方守卫双保险——R1 裁定）。"""
    publisher = context["publisher"]
    assert context["unconfirmed_return"] is None, "未确认 assessment 应直接 return None"
    assert len(publisher.published_events) == 2, (
        f"未确认 assessment 不应发布（替身捕获应保持 2——实际 {len(publisher.published_events)}）"
    )


@then("事件契约断言通过（注册 + aggregate_type + to_dict 序列化含 agent_id）")
def then_event_contract_assertions(context: dict[str, Any]) -> None:
    """事件契约三断言（注册/aggregate/to_dict——test_event_contract 先例形态）。"""
    assert context["event_registry"] is context["DriftDetected"], "DomainEvent._registry 应注册 DriftDetected"
    event = context["publisher"].published_events[0]
    assert event.aggregate_type == "AgentEvaluation"
    assert event.event_type == "DriftDetected"
    payload = event.to_dict()["payload"]
    for field in (
        "agent_id",
        "metric_name",
        "drift_direction",
        "drift_level",
        "cusum_high",
        "cusum_low",
        "baseline_mean",
        "baseline_std",
        "observed_value",
        "sample_count",
        "recommended_action",
    ):
        assert field in payload, f"to_dict payload 应含 {field}（实际 {sorted(payload)}）"


@given("事件通道配置模块已加载")
def given_event_channel_modules_loaded(context: dict[str, Any]) -> None:
    """加载双登记两处配置源（yaml + DEFAULT_MAPPINGS）。"""
    import yaml as yaml_module

    from src.infrastructure.messaging.channel_router import ChannelRouter

    channels = yaml_module.safe_load((REPO_ROOT / "configs" / "event_channels.yaml").read_text(encoding="utf-8"))
    context["yaml_channels"] = channels["event_channels"]
    context["default_mappings"] = ChannelRouter.DEFAULT_MAPPINGS


@when("检查 DriftDetected 双登记条目")
def when_check_dual_registration_entries(context: dict[str, Any]) -> None:
    """双登记条目检查（yaml 条目 + ChannelMapping 条目存 context）。"""
    context["yaml_entry"] = context["yaml_channels"].get("DriftDetected")
    context["mapping_entry"] = context["default_mappings"].get("DriftDetected")


@then("event_channels.yaml 条目断言通过（rabbitmq_routing_key + delivery_mode reliable）")
def then_yaml_entry_assertions(context: dict[str, Any]) -> None:
    """yaml 侧断言（reliable 单通道 3 键形态）。"""
    entry = context["yaml_entry"]
    assert entry is not None, "event_channels.yaml 应含 DriftDetected 条目"
    assert entry["rabbitmq_routing_key"] == "sisys.events.reliable.drift_detected"
    assert entry["delivery_mode"] == "reliable"
    assert entry.get("description"), "description 应非空"


@then("ChannelRouter.DEFAULT_MAPPINGS 条目断言通过（同字段逐字一致）")
def then_default_mappings_entry_assertions(context: dict[str, Any]) -> None:
    """DEFAULT_MAPPINGS 侧断言（与 yaml 逐字段一致——双登记门禁形态）。"""
    from src.infrastructure.messaging.channel_router import DeliveryMode

    mapping = context["mapping_entry"]
    assert mapping is not None, "DEFAULT_MAPPINGS 应含 DriftDetected 条目"
    assert mapping.event_type == "DriftDetected"
    assert mapping.rabbitmq_routing_key == "sisys.events.reliable.drift_detected"
    assert mapping.delivery_mode is DeliveryMode.RELIABLE
    assert mapping.description, "description 应非空"


@given("真实 CUSUMDriftDetector 实例已装配（注入抛异常 publisher 替身）")
def given_detector_with_raising_publisher(context: dict[str, Any]) -> None:
    """装配检测器 + 恒抛异常 publisher 替身（发布失败注入面）。"""
    from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

    context["publisher"] = _RaisingEventPublisher()
    context["detector"] = CUSUMDriftDetector(event_publisher=context["publisher"])
    context["baseline"] = list(_BASELINE_SEQUENCE)
    context["mu0"], context["sigma0"] = _baseline_stats()


@then("发布失败降级断言通过（不上抛 returns None + caplog error 断言）")
def then_publish_failure_degradation(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    """发布失败降级断言（可观测附加面——事件失败不阻断检测语义）。"""

    assert context["trigger_return"] is None, "trigger_recalibration 应返回 None"
    assert context["trigger_return_default"] is None
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR and "DriftDetected" in r.message]
    assert error_records, "发布失败应有 ERROR 级日志（含 DriftDetected 事件标识）"


# ===================================================================
# AC-3: 主链接入——第七可选依赖 + 漂移检测块 + drift.detected span 填值（链级）
# ===================================================================


@given("链级全局追踪通道已启用（场景级 initialize + InMemory exporter）", target_fixture=None)
def given_chain_tracing_enabled(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """链级 OTel 通道（场景级新 provider 经 initialize 履行全局 set——5.7 SSOT）。"""
    monkeypatch.delenv("PHOENIX_TRACING_ENABLED", raising=False)
    _enable_test_tracing(context)


@given("漂移检测工作流链已装配（预填充 34 样本 + Fake LLM 幻觉分注入 + 零 IO publisher 替身）")
def given_drift_workflow_chain_assembled(context: dict[str, Any]) -> None:
    """链级装配（真实检测器 + publisher 替身 + 34 样本预填充 drift 形态）。"""
    from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

    publisher = _RecordingEventPublisher()
    context["drift_publisher"] = publisher
    detector = CUSUMDriftDetector(event_publisher=publisher)
    _assemble_drift_workflow_chain(context, drift_detector=detector, prefill="drift")


@given("降级工作流链已装配（手写零 IO FakeDriftPort——update 抛 451）")
def given_degradation_chain_assembled(context: dict[str, Any]) -> None:
    """降级链装配（FakeDriftPort update 抛 DriftDetectionError 451——验收禁 mock 红线手写替身）。"""
    from src.domain.exceptions import DriftDetectionError

    context["fake_drift_port"] = _FakeDriftPort(
        update_error=DriftDetectionError(metric_name="overall_score", reason="drift_update")
    )
    _assemble_drift_workflow_chain(context, drift_detector=context["fake_drift_port"])


@when("调用 RunAgentWorkflowUseCase.execute 执行六阶段工作流")
def when_execute_workflow(context: dict[str, Any]) -> None:
    """执行工作流（异常捕获存 context["caught"]——透传断言锚）。"""
    _run_workflow(context)


@then("agent_execution 根 span drift.detected 真值断言通过（键字符串逐字对照——OD-2 兑现锚）")
def then_root_span_drift_detected_truth(context: dict[str, Any]) -> None:
    """drift.detected span 填值断言（键字符串逐字 + 常量同值——5.7 契约兑现）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    span = _find_root_span(context)
    attributes = dict(span.attributes)
    assert "drift.detected" in attributes, "根 span 应含 drift.detected 键（逐字对照）"
    assert attributes["drift.detected"] is True, "drift.detected 应为 True"
    assert "drift.detected" == SpanAttributeKeys.DRIFT_DETECTED, "键字符串应与 SpanAttributeKeys 常量一致"


@then("DriftDetected 事件发布断言通过（替身捕获 + direction=down + agent_id 透传）")
def then_drift_detected_event_published(context: dict[str, Any]) -> None:
    """事件发布断言（预填充使链上末样本即确认——direction/agent_id 真值）。"""
    from src.domain.events.drift_events import DriftDetected

    publisher = context["drift_publisher"]
    events = [e for e in publisher.published_events if isinstance(e, DriftDetected)]
    assert len(events) == 1, f"应恰发布一次 DriftDetected（实际 {len(events)}）"
    event = events[0]
    assert event.drift_direction == "down", "预填充 4×0.4 + 链上样本应确认 down"
    assert event.agent_id == str(context["agent"].agent_id), "agent_id 应从 execute 形参透传"
    assert event.metric_name == "overall_score"


@then("主链正常返回断言通过（结果五字段 + eval 三键仍在 + drift.detected 缺席）")
def then_main_chain_normal_return(context: dict[str, Any]) -> None:
    """降级路径断言（评估先于漂移成功——三键在；漂移失败缺席不阻断）。"""
    result = context["result"]
    assert result is not None, "主链应正常返回（451 降级不阻断）"
    assert context.get("caught") is None, "451 应被评估块 catch 扩捕获不上抛"
    assert result.workflow_status == "completed"
    span = _find_root_span(context)
    attributes = dict(span.attributes)
    for key in ("eval.hallucination_score", "eval.context_relevance", "eval.confidence_accuracy"):
        assert key in attributes, f"eval 三键应仍在（{key}——评估先于漂移成功）"
    assert "drift.detected" not in attributes, "漂移失败时 drift.detected 应缺席（不写哨兵值）"


@then("降级 warning 日志断言通过（WARNING 级 + 文本含 451 异常 str）")
def then_degradation_warning_log(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    """warning 断言（451 共享评估块 catch——消息模板按 451 异常 str 锚，禁直觉断言「漂移」）。"""

    expected_fragment = str(context["fake_drift_port"]._update_error)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and expected_fragment in r.message]
    assert warnings, f"应有 WARNING 级降级日志（含 451 异常 str「{expected_fragment}」）"


@given("工作流模块已加载")
def given_workflow_module_loaded(context: dict[str, Any]) -> None:
    """模块加载（存量模块——本场景红锚在签名断言）。"""
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

    context["RunAgentWorkflowUseCase"] = RunAgentWorkflowUseCase


@when("检查构造签名七依赖清单与 None 默认路径")
def when_check_seven_dependency_signature(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """七依赖签名检查 + None 默认路径执行（六参构造——存量零破坏回归锚）。"""
    import inspect

    monkeypatch.delenv("PHOENIX_TRACING_ENABLED", raising=False)
    _enable_test_tracing(context)

    use_case_cls = context["RunAgentWorkflowUseCase"]
    signature = inspect.signature(use_case_cls.__init__)
    context["signature_params"] = list(signature.parameters)[1:]
    context["signature_default"] = signature.parameters["drift_detector"].default

    # None 默认路径：六参构造（不注入 drift_detector）——行为与 5.8 基线一致
    _assemble_drift_workflow_chain(context, drift_detector=None)
    _run_workflow(context)


@then("七依赖签名断言通过（inspect.signature 参数清单 + 第七参数默认 None）")
def then_seven_dependency_signature(context: dict[str, Any]) -> None:
    """七依赖清单断言（第七参数 drift_detector 尾部追加 None 默认）。"""
    expected = [
        "agent_repository",
        "agent_profile_use_case",
        "agent_engine",
        "agent_workflow_service",
        "isolation_guard",
        "evaluation_harness",
        "drift_detector",
    ]
    assert context["signature_params"] == expected, f"构造签名应为七依赖: {context['signature_params']}"
    assert context["signature_default"] is None, "第七参数 drift_detector 应默认 None"


@then("None 默认路径断言通过（六参构造行为与 5.8 基线一致 + 漂移块零执行）")
def then_none_default_path_baseline(context: dict[str, Any]) -> None:
    """None 路径断言（eval 三键在 + drift.detected 缺席——5.8 基线回归锚）。"""
    assert context["result"] is not None and context.get("caught") is None
    span = _find_root_span(context)
    attributes = dict(span.attributes)
    assert "eval.hallucination_score" in attributes, "None 路径 eval 三键应在（5.8 基线一致）"
    assert "drift.detected" not in attributes, "None 路径漂移块整体跳过（drift.detected 缺席）"
    assert getattr(context["use_case"], "_drift_detector", "missing") is None, "六参构造 _drift_detector 应为 None"


@then("存量断言同步 ×5 基线断言通过（5-7 验收 + 5-7 test_arch + 5-8 test_arch + 单测第六参 + 5-8 验收清单）")
def then_five_assertion_sync_baselines(context: dict[str, Any]) -> None:
    """断言同步 ×5 基线（回执字面行保留防线——①②既有行原样 + 尾部追加 drift_detector 行）。"""
    targets = {
        "tests/acceptance/test_acceptance_phoenix_tracer.py": '"drift_detector",  # Story 5.9 第七可选依赖',
        "tests/unit/architecture/test_arch_phoenix_tracer.py": '"drift_detector",  # Story 5.9 第七可选依赖',
        "tests/unit/architecture/test_arch_evaluation.py": '"drift_detector"',
        "tests/unit/application/use_cases/test_run_agent_workflow.py": '"drift_detector"',
        "tests/acceptance/test_acceptance_agent_evaluation.py": '"drift_detector"',
    }
    for relative, anchor in targets.items():
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert anchor in source, f"{relative} 应含七依赖清单行（断言同步 ×5——锚 {anchor!r}）"
        assert '"evaluation_harness"' in source, f"{relative} 既有六依赖清单行应保留（尾部追加禁改写）"
    # 回执耦合防线：5-8 验收锁死的 ①② 字面行仍在位（被断言锁死——禁改写）
    for relative in (
        "tests/acceptance/test_acceptance_phoenix_tracer.py",
        "tests/unit/architecture/test_arch_phoenix_tracer.py",
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert '"evaluation_harness",  # Story 5.8 第六可选依赖' in source, f"{relative} 5-8 回执字面行应原样保留"


# ===================================================================
# AC-4: 端口接线、架构合规与组合根注册（静态 + 接线——零 OTel 全局触碰）
# ===================================================================


@given("组合根注册模块已加载")
def given_composition_root_loaded(context: dict[str, Any]) -> None:
    """组合根加载（bootstrap 经 tests/conftest session 闩——get_resolver 复用注册态）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    context["resolver"] = resolver
    context["drift_instance"] = resolver.resolve("agent_drift")
    context["use_case_instance"] = resolver.resolve("agent_workflow_use_case")


@when("检查 agent_drift 端口注册与 use case 工厂接线")
def when_check_port_registration_and_factory_wiring(context: dict[str, Any]) -> None:
    """注册与接线检查（含 CR1-DF2 降级防护——未注册形态 resolve_optional None）。"""
    from src.composition_root import _build_agent_workflow_use_case
    from src.domain.ports.registry import _global_registry

    context["drift_spec"] = _global_registry.get("agent_drift")

    class _UnregisteredDriftResolver:
        """CR1-DF2 降级防护替身（agent_drift 未注册形态——resolve_optional 恒 None）。"""

        def resolve(self, name: str) -> Any:
            return object()

        def resolve_optional(self, name: str) -> Any:
            return None

    degraded_use_case = _build_agent_workflow_use_case(_UnregisteredDriftResolver())
    context["degraded_use_case"] = degraded_use_case


@then("组合根注册 resolve 四件断言通过（可达/isinstance/PortSpec 元数据/SINGLETON）")
def then_resolve_four_assertions(context: dict[str, Any]) -> None:
    """resolve 四件（可达 + isinstance 端口 + PortSpec 元数据 + SINGLETON——接线断言不执行 update）。"""
    from src.application.ports.agent_drift import DriftDetectionPort
    from src.domain.ports.registry import Lifetime

    instance = context["drift_instance"]
    assert instance is not None, "resolve('agent_drift') 应可达"
    assert isinstance(instance, DriftDetectionPort), f"应实现 DriftDetectionPort: {type(instance)}"
    spec = context["drift_spec"]
    assert spec is not None, "注册表应有 agent_drift 条目"
    assert spec.version == "v1.0.0"
    assert spec.module == "src.infrastructure.monitoring.cusum_detector"
    assert spec.lifetime == Lifetime.SINGLETON
    assert spec.owner == "platform"
    assert spec.tags == ("agent", "drift", "observability")


@then("use case 工厂注入断言通过（resolve 实例 _drift_detector 非 None 且 isinstance DriftDetectionPort）")
def then_factory_injection_assertions(context: dict[str, Any]) -> None:
    """接线可达性（resolve_optional 第七依赖注入）。"""
    from src.application.ports.agent_drift import DriftDetectionPort

    use_case = context["use_case_instance"]
    detector = getattr(use_case, "_drift_detector", None)
    assert detector is not None, "use case 第七依赖应注入非 None（resolve_optional 接线）"
    assert isinstance(detector, DriftDetectionPort)


@then("CR1-DF2 降级防护断言通过（未注册形态 resolve_optional None + use case 构造成功）")
def then_cr1_df2_degradation_guard(context: dict[str, Any]) -> None:
    """CR1-DF2[5.8] 处置（agent_drift 注册缺失 → _drift_detector None 不阻断构造——同窗断言）。"""
    degraded = context["degraded_use_case"]
    assert degraded is not None, "未注册形态 use case 应正常构造（接线失败降级不阻断 bootstrap）"
    assert getattr(degraded, "_drift_detector", "missing") is None, "未注册形态 _drift_detector 应为 None"
    assert getattr(degraded, "_evaluation_harness", "missing") is None, (
        "同窗断言：评估接线同为 None（resolver.resolve_optional 恒 None）"
    )


@then("端口契约 11 维度断言通过（REQUIRED_METHODS + _DummyResolver event_publisher 分支）")
def then_port_contract_dimensions(context: dict[str, Any]) -> None:
    """契约 11 维度基础（方法齐备——全量归 tests/contracts/test_port_contract_agent_drift.py）。"""
    instance = context["drift_instance"]
    for method in ("update", "trigger_recalibration"):
        assert hasattr(instance, method), f"{type(instance).__name__} 应有 {method}"
        assert callable(getattr(instance, method)), f"{method} 应 callable"


@given("交付文件存在性已确认")
def given_delivery_files_exist(context: dict[str, Any]) -> None:
    """交付文件前置检查（缺失即红——静态扫描的数据源）。"""
    targets = [
        SRC_DIR / "application" / "ports" / "agent_drift.py",
        SRC_DIR / "application" / "ports" / "__init__.py",
        SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py",
        SRC_DIR / "domain" / "events" / "drift_events.py",
        SRC_DIR / "domain" / "exceptions" / "evaluation_exceptions.py",
        SRC_DIR / "infrastructure" / "monitoring" / "cusum_detector.py",
        SRC_DIR / "composition_root.py",
    ]
    for path in targets:
        assert path.is_file(), f"交付文件缺失: {path}"


@when("执行架构静态扫描（内联轻量版——全量验证器归 tests/unit/architecture）")
def when_run_inline_static_scan(context: dict[str, Any]) -> None:
    """扫描执行（AST 解析 + 源码文本存 context——静态断言数据源）。"""
    import ast

    scan_targets = {
        "agent_drift": SRC_DIR / "application" / "ports" / "agent_drift.py",
        "ports_init": SRC_DIR / "application" / "ports" / "__init__.py",
        "run_agent_workflow": SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py",
        "drift_events": SRC_DIR / "domain" / "events" / "drift_events.py",
        "cusum_detector": SRC_DIR / "infrastructure" / "monitoring" / "cusum_detector.py",
    }
    context["scan_trees"] = {name: ast.parse(p.read_text(encoding="utf-8")) for name, p in scan_targets.items()}
    context["use_case_source"] = scan_targets["run_agent_workflow"].read_text(encoding="utf-8")
    context["cusum_source"] = scan_targets["cusum_detector"].read_text(encoding="utf-8")


@then("application 触碰文件零新增第三方断言通过")
def then_application_zero_new_third_party(context: dict[str, Any]) -> None:
    """验证器 A 轻量版（agent_drift 纯标准库 + run_agent_workflow 既有 opentelemetry 基线内）。"""
    import ast
    import sys

    allowed = {"opentelemetry"}  # run_agent_workflow 既有基线——本 Story 零新增第三方
    for name, tree in context["scan_trees"].items():
        if name not in ("agent_drift", "ports_init", "run_agent_workflow"):
            continue
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib <= allowed, f"{name} 白名单外第三方: {non_stdlib - allowed}"
    # agent_drift.py 端口文件纯标准库专项（5-8 端口文件同款断言）
    modules = {
        alias.name.split(".")[0]
        for node in ast.walk(context["scan_trees"]["agent_drift"])
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(context["scan_trees"]["agent_drift"])
        if isinstance(node, ast.ImportFrom) and node.module
    }
    import sys as sys_module

    non_stdlib = {m for m in modules if m not in sys_module.stdlib_module_names and m != "src"}
    assert non_stdlib == set(), f"agent_drift.py 应纯标准库零第三方（实际 {non_stdlib}）"


@then("domain 触碰面收窄断言通过（业务目录零命中 + events 白名单域 + 异常三件内）")
def then_domain_touch_narrowed(context: dict[str, Any]) -> None:
    """验证器 B 轻量版（业务符号零命中 + DriftDetected 允许 events + 451 仅 exceptions 三件）。"""
    import re

    story_symbols = ("CUSUMDriftDetector", "DriftDetectionPort", "DriftAssessment")
    business_dirs = [
        SRC_DIR / "domain" / "ports",
        SRC_DIR / "domain" / "services",
        SRC_DIR / "domain" / "entities",
        SRC_DIR / "domain" / "value_objects",
    ]
    for directory in business_dirs:
        for py_file in directory.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for symbol in story_symbols:
                pattern = rf"\b{re.escape(symbol)}\b"
                assert not re.search(pattern, source), f"domain 业务域零触碰红线: {py_file} 含 {symbol}"

    # events 白名单域：DriftDetected 允许且应在 domain/events/drift_events.py（本 Story 与 5.8 的差异面）
    events_hits = [
        py_file
        for py_file in (SRC_DIR / "domain" / "events").rglob("*.py")
        if "DriftDetected" in py_file.read_text(encoding="utf-8")
    ]
    assert any(p.name == "drift_events.py" for p in events_hits), "DriftDetected 应在 domain/events/drift_events.py"

    # DriftDetectionError 仅 exceptions 三件内
    exception_hits = [
        py_file
        for py_file in (SRC_DIR / "domain" / "exceptions").rglob("*.py")
        if "DriftDetectionError" in py_file.read_text(encoding="utf-8")
    ]
    allowed_exception_files = {"evaluation_exceptions.py", "_code_ranges.py", "__init__.py"}
    assert exception_hits, "DriftDetectionError 应存在于 exceptions（正向锚）"
    for hit in exception_hits:
        assert hit.name in allowed_exception_files, f"DriftDetectionError 应仅在 exceptions 三件内: {hit}"


@then("组合根外零实例化与依赖方向断言通过")
def then_composition_root_only_instantiation(context: dict[str, Any]) -> None:
    """验证器 B 轻量版（CUSUMDriftDetector 构造点仅组合根 + infrastructure→application/domain）。"""
    import ast

    violations: list[str] = []
    found = False
    for py_file in SRC_DIR.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = node.func
                name = getattr(callee, "id", None) or getattr(callee, "attr", None)
                if name == "CUSUMDriftDetector":
                    rel = str(py_file.relative_to(REPO_ROOT))
                    found = True
                    if not rel.startswith("src/composition_root.py"):
                        violations.append(f"{rel}:{node.lineno}")
    assert found, "组合根应至少一处 CUSUMDriftDetector 实例化（注册 lambda）"
    assert not violations, f"组合根外实例化点: {violations}"

    # 依赖方向：cusum_detector（infrastructure）import application/domain——合法面锚定
    modules = {
        node.module
        for node in ast.walk(context["scan_trees"]["cusum_detector"])
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert any(m.startswith("src.application") for m in modules), "cusum_detector 应 import application 端口（依赖方向锚）"
    assert any(m.startswith("src.domain") for m in modules), "cusum_detector 应 import domain 端口/事件（依赖方向锚）"
    assert not any(m.startswith("src.interfaces") or m.startswith("src.entrypoints") for m in modules), (
        "infrastructure 不得 import interfaces/entrypoints"
    )


@then("主链漂移块静态锚断言通过（update 调用 + DRIFT_DETECTED 常量 + is_drifted 分支 + trigger_recalibration）")
def then_main_chain_drift_block_static_anchor(context: dict[str, Any]) -> None:
    """验证器 C 轻量版（execute 体内四静态锚——AST Attribute/源段双形态）。"""
    import ast

    tree = context["scan_trees"]["run_agent_workflow"]
    execute_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "execute":
            execute_node = node
    assert execute_node is not None, "应存在 execute 方法"

    source_segment = ast.get_source_segment(context["use_case_source"], execute_node) or ""
    assert "_drift_detector" in source_segment, "execute 体内应有漂移检测块（None 守卫）"
    assert "await self._drift_detector.update(" in source_segment, "execute 体内应有 update 调用"
    assert "is_drifted" in source_segment, "execute 体内应有 is_drifted 分支"
    assert "trigger_recalibration" in source_segment, "execute 体内应有 trigger_recalibration 调用"

    attr_names = {node.attr for node in ast.walk(execute_node) if isinstance(node, ast.Attribute)}
    assert "DRIFT_DETECTED" in attr_names, "execute 体内应引用 SpanAttributeKeys.DRIFT_DETECTED（Attribute 形态）"
    assert "is_recording" in source_segment, "span 写入应有 is_recording 守卫"


@then(".env.example 零改动断言通过")
def then_env_example_untouched(context: dict[str, Any]) -> None:
    """配置零改动断言（CUSUM 参数是代码常量——无新环境变量）。"""
    env_content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "CUSUM" not in env_content, ".env.example 不应新增 CUSUM 配置（常量单源裁定）"
    assert "DRIFT_" not in env_content, ".env.example 不应新增 DRIFT_ 开关"


# ===================================================================
# AC-5: 性能双锚——检测延迟 P99 + 合成回测准确率（委托集成计时）
# ===================================================================


@given("集成计时委托模块已加载（_PERF_CACHE 委托采样）")
def given_perf_delegate_loaded(context: dict[str, Any]) -> None:
    """P99 委托采样（helper cache-or-compute——命中或首次采样，同 xdist_group 同 worker）。"""
    from tests.integration.test_integration_drift_detection import sample_drift_p99_perf

    context["p99_summary"] = _run_async(context["_loop"], sample_drift_p99_perf())


@when("执行 P99 委托采样（warmup 1 + 100 采样 + quantiles exclusive [98]）")
def when_read_delegated_p99(context: dict[str, Any]) -> None:
    """读取 P99 摘要（常量单源 import——验收侧禁双真源）。"""
    from tests.integration.test_integration_drift_detection import DRIFT_P99_LIMIT_SECONDS

    context["p99_seconds"] = context["p99_summary"]["p99_seconds"]
    context["p99_limit"] = DRIFT_P99_LIMIT_SECONDS
    context["update_call_count"] = context["p99_summary"]["update_call_count"]


@then("P99 小于 100ms 断言通过（DRIFT_P99_LIMIT_SECONDS 常量单源）")
def then_p99_below_100ms(context: dict[str, Any]) -> None:
    """P99<100ms（epics L1838 钦定——纯内存检测管线口径，事件发布出栈）。"""
    assert context["p99_limit"] == 0.1, "DRIFT_P99_LIMIT_SECONDS 应为 0.1（常量单源）"
    assert context["p99_seconds"] < context["p99_limit"], (
        f"检测管线 P99 应 < {context['p99_limit']}s，实际 {context['p99_seconds']}s"
    )


@then("正向锚断言通过（采样轮 update 调用计数 == warmup + 采样数 101）")
def then_p99_positive_anchor(context: dict[str, Any]) -> None:
    """正向锚（防静默跳过假绿——warmup 1 + 100 采样 == 101 次 update）。"""
    assert context["update_call_count"] == 101, (
        f"采样轮 update 调用计数应为 101（warmup 1 + 采样 100），实际 {context['update_call_count']}"
    )


@given("集成计时委托模块已加载（_PERF_CACHE 委托回测）")
def given_backtest_delegate_loaded(context: dict[str, Any]) -> None:
    """合成回测委托（_PERF_CACHE["backtest"] 命中或首次计算）。"""
    from tests.integration.test_integration_drift_detection import run_synthetic_backtest

    context["backtest_summary"] = run_synthetic_backtest()


@when("执行合成回测委托采样（固定种子 20261028 + 40 序列 × 60 样本 + RNG 调用序钉死）")
def when_read_delegated_backtest(context: dict[str, Any]) -> None:
    """读取回测摘要（TP/FP/TN 分项 + 序列签名）。"""
    summary = context["backtest_summary"]
    context["backtest_accuracy"] = summary["accuracy"]
    context["backtest_tp"] = summary["tp"]
    context["backtest_fp"] = summary["fp"]
    context["backtest_tn"] = summary["tn"]


@then("回测准确率不低于 85% 断言通过（(TP+TN)/40 ≥ 0.85 + 分项计数可观测）")
def then_backtest_accuracy(context: dict[str, Any]) -> None:
    """准确率断言（钦定种子基准 TP=20/FP=1/acc=0.975——失败消息携带分项计数可诊断）。"""
    tp, fp, tn = context["backtest_tp"], context["backtest_fp"], context["backtest_tn"]
    accuracy = context["backtest_accuracy"]
    assert accuracy >= 0.85, f"合成回测准确率应 ≥0.85（实际 {accuracy}——分项 TP={tp} FP={fp} TN={tn} FN={20 - tp}）"
    assert tp + tn + fp == 40, f"分项计数应覆盖 40 序列（TP={tp} TN={tn} FP={fp}）"


@then("确定性断言通过（同种子重跑同结果）")
def then_backtest_determinism(context: dict[str, Any]) -> None:
    """确定性断言（固定种子 20261028——两次生成完全相等，防 flaky）。"""
    from tests.integration.test_integration_drift_detection import make_backtest_sequences

    first = make_backtest_sequences(20261028)
    second = make_backtest_sequences(20261028)
    assert first == second, "同种子两次生成应完全相等（确定性锚）"
    assert len(first) == 40 and all(len(sequence) == 60 for _, sequence in first), "40 序列 × 60 样本形态"


@then("xdist 组互异断言通过（drift-detection-perf 与既有 13 组不冲突）")
def then_xdist_group_unique(context: dict[str, Any]) -> None:
    """xdist 组互异断言（全仓扫描——drift-detection-perf 仅集成/验收两文件消费）。"""
    import re

    existing_groups: set[str] = set()
    consumer_files: list[str] = []
    for py_file in (REPO_ROOT / "tests").rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        for match in re.findall(r'xdist_group\("([^"]+)"\)', source):
            existing_groups.add(match)
            if match == "drift-detection-perf":
                consumer_files.append(str(py_file.relative_to(REPO_ROOT)))
    expected_existing = {
        "agent-workflow-perf",
        "agent-isolation-perf",
        "agent-triple-isolation-perf",
        "isolation-switch-log-perf",
        "phoenix-tracer-perf",
        "agent-evaluation-perf",
        "agent-instantiation",
        "agent-profile-loading",
        "data-source-cache",
        "sandbox-daemon",
        "tool-executions-pg",
        "tool-versions-pg",
        "validation-feedback-pg",
    }
    assert expected_existing <= existing_groups, f"既有 13 组清单应全部在位（缺失 {expected_existing - existing_groups}）"
    assert "drift-detection-perf" in existing_groups, "drift-detection-perf 组应存在（集成/验收委托配对）"
    drift_consumers = {f for f in consumer_files if "drift_detection" in f}
    assert len(drift_consumers) == 2, f"drift-detection-perf 应恰有集成/验收两消费方（实际 {drift_consumers}）"


# ===================================================================
# 收尾场景（Task 6 追加——14 终态）：完成清单逐项确认
# ===================================================================


@scenario(
    "test_acceptance_drift_detection.feature",
    "收尾 - 完成清单逐项确认",
)
def test_completion_checklist_confirmation(context: dict[str, Any]) -> None:
    """收尾：src + tests 四目录完成清单逐项确认（5-8 收尾同款）。"""


@given("开发完成清单已就绪（src 七件 + tests 十件新建 + 存量触碰文本锚）")
def given_completion_checklist_ready(context: dict[str, Any]) -> None:
    """清单数据装配（相对路径清单存 context——存在性断言数据源）。"""
    context["src_new_files"] = [
        "src/application/ports/agent_drift.py",
        "src/domain/events/drift_events.py",
        "src/infrastructure/monitoring/cusum_detector.py",
    ]
    context["src_modified_files"] = [
        "src/application/use_cases/run_agent_workflow.py",
        "src/application/ports/__init__.py",
        "src/domain/events/__init__.py",
        "src/domain/exceptions/evaluation_exceptions.py",
        "src/domain/exceptions/_code_ranges.py",
        "src/domain/exceptions/__init__.py",
        "src/interfaces/api/exception_handlers.py",
        "src/infrastructure/messaging/channel_router.py",
        "src/composition_root.py",
    ]
    context["test_new_files"] = [
        "tests/unit/domain/events/test_drift_events.py",
        "tests/unit/application/test_agent_drift_model.py",
        "tests/unit/infrastructure/monitoring/test_cusum_drift_detector.py",
        "tests/contracts/test_port_contract_agent_drift.py",
        "tests/contracts/test_event_contract_drift_events.py",
        "tests/contracts/test_event_channel_mapping_drift.py",
        "tests/integration/test_integration_drift_detection.py",
        "tests/unit/architecture/test_arch_drift_detection.py",
        "tests/acceptance/test_acceptance_drift_detection.feature",
        "tests/acceptance/test_acceptance_drift_detection.py",
    ]
    context["test_modified_files"] = [
        "tests/unit/domain/exceptions/test_evaluation_exceptions.py",
        "tests/unit/application/use_cases/test_run_agent_workflow.py",
        "tests/acceptance/test_acceptance_phoenix_tracer.py",
        "tests/unit/architecture/test_arch_phoenix_tracer.py",
        "tests/unit/architecture/test_arch_evaluation.py",
        "tests/acceptance/test_acceptance_agent_evaluation.py",
        "tests/unit/interfaces/api/test_exception_handlers.py",
    ]


@when("逐项验证 src 与 tests 完成清单")
def when_verify_completion_checklist(context: dict[str, Any]) -> None:
    """存在性验证（逐文件 is_file——缺失即红）。"""
    for relative in context["src_new_files"] + context["src_modified_files"]:
        assert (REPO_ROOT / relative).is_file(), f"src 交付文件缺失: {relative}"
    for relative in context["test_new_files"] + context["test_modified_files"]:
        assert (REPO_ROOT / relative).is_file(), f"tests 交付文件缺失: {relative}"


@then("src 完成清单断言通过（检测器/端口/事件/异常/组合根/通道双登记/主链漂移块文本锚）")
def then_src_completion_anchors(context: dict[str, Any]) -> None:
    """src 文本锚（关键符号在位——主链漂移块 + 通道双登记 + 异常注册）。"""
    use_case_source = (REPO_ROOT / "src/application/use_cases/run_agent_workflow.py").read_text(encoding="utf-8")
    assert "drift_detector" in use_case_source, "run_agent_workflow.py 应含第七依赖 drift_detector"
    assert "SpanAttributeKeys.DRIFT_DETECTED" in use_case_source, "主链漂移块应有 DRIFT_DETECTED 常量引用"

    channels_source = (REPO_ROOT / "configs/event_channels.yaml").read_text(encoding="utf-8")
    assert "DriftDetected" in channels_source, "event_channels.yaml 应含 DriftDetected 条目"
    assert "sisys.events.reliable.drift_detected" in channels_source, "routing_key 应在 yaml 登记"
    router_source = (REPO_ROOT / "src/infrastructure/messaging/channel_router.py").read_text(encoding="utf-8")
    assert '"DriftDetected": ChannelMapping(' in router_source, "DEFAULT_MAPPINGS 应含 DriftDetected 条目"

    exceptions_source = (REPO_ROOT / "src/domain/exceptions/evaluation_exceptions.py").read_text(encoding="utf-8")
    assert 'code = "EXCEPTION_451"' in exceptions_source, "DriftDetectionError 应为 EXCEPTION_451"

    composition_source = (REPO_ROOT / "src/composition_root.py").read_text(encoding="utf-8")
    assert 'name="agent_drift"' in composition_source, "组合根应有 agent_drift 注册区段"
    assert 'resolve_optional("agent_drift")' in composition_source, "use case 工厂应有第七依赖接线"


@then("tests 四目录完成清单断言通过（十件新建 + 断言同步 ×5 + expected_types 伴随更新）")
def then_tests_completion_anchors(context: dict[str, Any]) -> None:
    """tests 文本锚（断言同步 ×5 更新在位 + expected_types 伴随 + 451 用例追加）。"""
    sync_targets = {
        "tests/acceptance/test_acceptance_phoenix_tracer.py": '"drift_detector",  # Story 5.9 第七可选依赖',
        "tests/unit/architecture/test_arch_phoenix_tracer.py": '"drift_detector",  # Story 5.9 第七可选依赖',
        "tests/unit/architecture/test_arch_evaluation.py": '"drift_detector"',
        "tests/unit/application/use_cases/test_run_agent_workflow.py": '"drift_detector"',
        "tests/acceptance/test_acceptance_agent_evaluation.py": '"drift_detector"',
    }
    for relative, anchor in sync_targets.items():
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert anchor in source, f"{relative} 应含七依赖清单更新（断言同步 ×5——锚 {anchor!r}）"

    handlers_test_source = (REPO_ROOT / "tests/unit/interfaces/api/test_exception_handlers.py").read_text(encoding="utf-8")
    assert "DriftDetectionError" in handlers_test_source, "expected_types 应伴随追加 DriftDetectionError"

    exceptions_test_source = (REPO_ROOT / "tests/unit/domain/exceptions/test_evaluation_exceptions.py").read_text(
        encoding="utf-8"
    )
    assert "EXCEPTION_451" in exceptions_test_source, "451 用例应已追加"

    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "CUSUM" not in env_example and "DRIFT_" not in env_example, ".env.example 零改动（常量单源裁定）"
