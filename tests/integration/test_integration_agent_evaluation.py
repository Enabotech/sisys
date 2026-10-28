"""Agent 输出质量评估集成测试（Story 5.8——五场景 + P95 计时委托）。

场景① 全链评估（六阶段真实链 + 真实 EvaluationHarness → span 三键真值断言
+ overall 可派生性）；
场景② UDMR in-band 全链（真实 UDMR 决策链 resolver → 幻觉检测 config.model
== 路由产物——经 Fake LLM call_args 捕获断言）；
场景③ 降级链（幻觉分支抛 LLMAPIError → 主链正常 + 三键缺席 + warning +
AgentDecided 照常发布）；
场景④ None 路径对比（五参构造 → 与 5-7 基线 span 树等价：十属性 + 零 eval.*）；
场景⑤ P95 计时（_PERF_CACHE 单槽缓存 + warmup 1 + 20 采样 + exclusive P95
[18]——验收 AC-5.1 委托消费，禁采样双跑）。

P95 口径声明（DC-8）：评估管线自身开销（幻觉检测 structured_generate 调用
编排 + 双本地计算 + overall 加权 + EvaluationResult 构造）——Fake LLM 即时返回，
LLM 网络延迟显式出栈（外部主导不可控——真实 LLM 单次调用秒级，epics 500ms
预算对真实网络不可行；5-7 AC-5「测纯进程内开销」同款口径）。生产形态下
resolver 健康检查 TTL 未命中的真实网络探测不在本口径内。

OTel 隔离（5-7 SSOT）：凡 initialize 一律文件级 autouse「前置双复位 → yield →
teardown 双复位」；链级场景统一 initialize 全局通道。

Run with:
    poetry run pytest tests/integration/test_integration_agent_evaluation.py -v
"""

from __future__ import annotations

import statistics
import time
import uuid
from pathlib import Path
from typing import Any, Generator

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("agent-evaluation-perf")]

# ===================================================================
# 常量单源（验收 AC-5.1 import 消费——禁双真源）
# ===================================================================

#: P95 上限（秒）——epics L1794 钦定 500ms
EVALUATION_P95_LIMIT_SECONDS = 0.5

#: 计时采样参数（5-7 委托模式——warmup 1 + 20 采样 + exclusive [18]）
EVALUATION_WARMUP_ROUNDS = 1
EVALUATION_SAMPLE_ROUNDS = 20

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"

#: 采样缓存（模块级单槽——集成场景⑤与验收 AC-5.1 共享同批结果，同 xdist_group
#: 同 worker 串行保证缓存命中；禁采样双跑）
_PERF_CACHE: dict[str, Any] = {}

#: 测试假密钥占位（resolver 替身基底的连接字段——非真实凭据）
_BASE_EVAL_FAKE_KEY = "base-eval-" + "key"


# ===================================================================
# OTel 全局状态隔离（5-7 SSOT——凡 initialize 一律双复位）
# ===================================================================


@pytest.fixture(autouse=True)
def _otel_global_state_isolation() -> Generator[None, None, None]:
    """OTel 全局状态 function 级双复位（前置 + teardown——变量 + Once 闩锁重建）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    PhoenixTracer.reset_for_testing()
    yield
    PhoenixTracer.reset_for_testing()


def _enable_global_tracing() -> Any:
    """链级统一通道：注入 provider 经 initialize 履行全局 set（返回 exporter）。"""
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
    return exporter


# ===================================================================
# 装配替身与 helpers（零外部服务——DC-7 豁免面：Fake LLM + 手写替身 + 真实件）
# ===================================================================


class _StubAgentRepository:
    """零 IO Agent 仓储替身（返回真实 Agent 实体——duck-typing 端口契约）。"""

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
    """手写 duck-typing 日志仓储替身（零 IO——隔离切换日志仓储正确用途）。"""

    async def save(self, log: Any) -> None:
        return None

    async def search(self, query: Any) -> Any:
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


class _RecordingDecisionLogRepository:
    """零 IO 路由决策日志仓储替身（CR1-20 清偿——语义对齐：UDMRService.log_repo
    消费的是路由决策日志非隔离切换日志，原以 _StubIsolationSwitchLogRepository
    充当属 duck-typing 合法但语义错位；验收 AC-2 同款形态）。"""

    def __init__(self) -> None:
        self.saved_logs: list[Any] = []

    async def save(self, log_entry: Any) -> None:
        self.saved_logs.append(log_entry)


class _RecordingEventPublisher:
    """记录发布事件的发布器（内存替身发布面）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(event.event_id) if hasattr(event, "event_id") else "",
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


class _StubHealthChecker:
    """健康检查替身（True/False 可控路由方向；双方法防 isinstance 校验）。"""

    def __init__(self, healthy: bool) -> None:
        self._healthy = healthy

    async def check(self) -> bool:
        return self._healthy

    async def close(self) -> None:
        return None


class _StubProfileUseCase:
    """零 IO 档案用例替身（返回手工装配的 AgentProfileLoadResult）。"""

    def __init__(self, profile_result: Any) -> None:
        self._profile_result = profile_result

    async def execute(self, agent_id: Any) -> Any:
        return self._profile_result


def _make_cloud_config(model: str) -> Any:
    """测试云端模型配置（连接字段非默认值）。"""
    from src.infrastructure.config.udmr import CloudModelConfig

    return CloudModelConfig(
        api_type="openai",
        endpoint=f"https://{model}.example/v1",
        api_key=f"key-{model}",
        model=model,
        enabled=True,
        max_tokens=1024,
        temperature=0.5,
    )


def _make_fake_llm(
    *,
    hallucination_score: float = 0.2,
    hallucination_error: bool = False,
) -> Any:
    """六阶段 + 幻觉检测 Fake LLM（Schema 身份分派——零工具步默认）。"""
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
    from src.domain.exceptions import LLMAPIError
    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    verify_calls = {"count": 0}
    tool_llm_calls = {"count": 0}

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        if response_schema is HallucinationEvaluationSchema:
            if hallucination_error:
                raise LLMAPIError(message="模拟评估 LLM API 故障（集成注入）")
            return HallucinationEvaluationSchema(
                rationale="回答与证据材料一致，无幻觉内容",
                hallucination_score=hallucination_score,
            )
        if response_schema is PerceptionSchema:
            return PerceptionSchema(summary="任务摘要：新能源车进入战略分析")
        if response_schema is PlanSchema:
            return PlanSchema(
                steps=[PlanStep(description="零工具直接推理", tool_name="", arguments={})],
                selected_tools=[],
            )
        if response_schema is VerificationSchema:
            verify_calls["count"] += 1
            return VerificationSchema(passed=True, confidence=0.85, rationale="结构化检查通过")
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


def _make_tool_execution_service(fake_llm: Any) -> Any:
    """工具执行面（真实服务链 + Fake llm + 沙箱替身）。"""
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


def _build_udmr_resolver(cloud_model: str, fake_llm: Any) -> Any:
    """真实 UDMR 决策链 resolver（pipl_service 显式注入 + 手写替身豁免面）。"""
    from src.domain.services.udmr_service import UDMRService
    from src.infrastructure.config.udmr import build_cost_calculator
    from src.infrastructure.monitoring.static_token_estimator import StaticTokenEstimator
    from src.infrastructure.routing.udmr_evaluation_model_resolver import UdmrEvaluationModelResolver
    from src.infrastructure.routing.udmr_policy import StaticUdmrPolicy
    from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl
    from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

    stub_log_repo: Any = _RecordingDecisionLogRepository()
    stub_publisher: Any = _RecordingEventPublisher()
    service = UDMRService(
        compliance_gateway=ComplianceGatewayImpl(pipl_service=PIPLComplianceServiceImpl()),
        policy=StaticUdmrPolicy(cloud_configs=[_make_cloud_config(cloud_model)], local_model="qwen2.5-eval-local"),
        health_checker=_StubHealthChecker(True),
        log_repo=stub_log_repo,
        publisher=stub_publisher,
        local_first=False,
        local_model="qwen2.5-eval-local",
        llm_timeout=30,
        token_estimator=StaticTokenEstimator(),
        cost_calculator=build_cost_calculator(),
    )
    return UdmrEvaluationModelResolver(
        udmr_service=service,
        cloud_configs=[_make_cloud_config(cloud_model)],
        local_model="qwen2.5-eval-local",
        llm_timeout=30,
    )


async def _assemble_chain(
    *,
    hallucination_score: float = 0.2,
    hallucination_error: bool = False,
    with_evaluation: bool = True,
    real_udmr: bool = False,
) -> dict[str, Any]:
    """自包含手工装配六阶段全链 + 评估链（真实服务链 + Fake LLM 豁免面）。"""
    from src.application.services.agent_workflow_service import AgentWorkflowService
    from src.application.services.evaluation_harness import EvaluationHarness
    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
    from src.domain.entities.agent import Agent, AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

    agent = Agent(agent_id=uuid.uuid4(), role=AgentRole.CEO, name="CEO Agent")
    stub_repo: Any = _StubAgentRepository(agent)
    isolation_service = IsolationManagementService(
        isolation_repository=_StubIsolationRepository(),
        agent_repository=stub_repo,
        event_publisher=InMemoryEventBus(),
        agent_config_loader=resolve("agent_config_loader"),
        isolation_switch_log_repository=_StubIsolationSwitchLogRepository(),
        audit_service=None,
    )
    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=stub_repo,
        agent_config_loader=resolve("agent_config_loader"),
    )

    fake_llm = _make_fake_llm(hallucination_score=hallucination_score, hallucination_error=hallucination_error)
    service: Any = AgentWorkflowService(
        llm_client=fake_llm,
        tool_execution_service=_make_tool_execution_service(fake_llm),
        skill_loader=resolve("skill_loader"),
        tool_registry_service=resolve("tool_registry_service"),
        isolation_guard=guard,
    )
    recorder = _RecordingEventPublisher()
    engine = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=recorder,
        workflow_service=service,
    )

    profile_loader = resolve("agent_profile_loader")
    profile = await profile_loader.load(role=AgentRole.CEO, agent_id=agent.agent_id)
    skill_selector = resolve("skill_selector")
    tools_l1 = await skill_selector.list_active_skills()
    profile_result = AgentProfileLoadResult(
        agent_id=agent.agent_id,
        role=AgentRole.CEO,
        profile=profile,
        tools_l1=tools_l1,
        startup_context_tokens=0,
    )
    profile_use_case: Any = _StubProfileUseCase(profile_result)

    evaluation_harness = None
    if with_evaluation:
        if real_udmr:
            model_resolver = _build_udmr_resolver("test-model-a", fake_llm)
        else:
            from src.domain.ports.llm_client import LLMConfig

            class _StaticResolver:
                async def resolve_config(self, input_text: str) -> Any:
                    return LLMConfig(
                        model="base-eval-model",
                        endpoint="https://base-eval.example/v1",
                        api_key=_BASE_EVAL_FAKE_KEY,
                    )

            model_resolver = _StaticResolver()
        evaluation_harness = EvaluationHarness(llm_client=fake_llm, model_resolver=model_resolver)

    use_case = RunAgentWorkflowUseCase(
        agent_repository=stub_repo,
        agent_profile_use_case=profile_use_case,
        agent_engine=engine,
        agent_workflow_service=service,
        isolation_guard=guard,
        evaluation_harness=evaluation_harness,
    )
    return {
        "agent": agent,
        "task": "分析新能源汽车行业进入战略并给出三层次建议",
        "use_case": use_case,
        "fake_llm": fake_llm,
        "recorder": recorder,
        "evaluation_harness": evaluation_harness,
    }


async def _run_chain(chain: dict[str, Any]) -> tuple[Any, Any]:
    """执行工作流（异常捕获返回——降级/异常断言锚）。"""
    try:
        result = await chain["use_case"].execute(chain["agent"].agent_id, chain["task"])
        return result, None
    except Exception as exc:
        return None, exc


def _get_root(exporter: Any) -> Any:
    """取唯一 agent_execution 根 span。"""
    roots = [s for s in exporter.get_finished_spans() if s.name == "agent_execution"]
    assert len(roots) == 1
    return roots[0]


# ===================================================================
# 场景①②③④：全链评估 + UDMR in-band + 降级 + None 对比
# ===================================================================


async def test_scenario_1_full_chain_evaluation_span_truth() -> None:
    """场景①：全链评估——span 三键真值（h=0.2/cr=0.0/ca=0.55）+ overall 可派生。"""
    from src.application.ports.agent_evaluation import (
        CONFIDENCE_ACCURACY_WEIGHT,
        CONTEXT_RELEVANCE_WEIGHT,
        HALLUCINATION_WEIGHT,
    )
    from src.application.ports.agent_tracing import SpanAttributeKeys

    exporter = _enable_global_tracing()
    chain = await _assemble_chain(hallucination_score=0.2)
    result, error = await _run_chain(chain)

    assert error is None
    assert result is not None and result.workflow_status == "completed"
    root = _get_root(exporter)
    attrs = root.attributes
    assert attrs[SpanAttributeKeys.EVAL_HALLUCINATION_SCORE] == 0.2
    assert attrs[SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE] == 0.0
    assert attrs[SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY] == 0.55
    # overall 可派生性（三键经 EVALUATION_WEIGHTS 重构 == overall——同式表达式）
    expected_overall = (
        (1.0 - attrs[SpanAttributeKeys.EVAL_HALLUCINATION_SCORE]) * HALLUCINATION_WEIGHT
        + attrs[SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE] * CONTEXT_RELEVANCE_WEIGHT
        + attrs[SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY] * CONFIDENCE_ACCURACY_WEIGHT
    )
    assert expected_overall == pytest.approx(0.4575)


async def test_scenario_2_udmr_inband_full_chain() -> None:
    """场景②：UDMR in-band 全链——幻觉检测 config.model == 路由产物（真值匹配）。"""
    from src.application.services.evaluation_schemas import HallucinationEvaluationSchema

    exporter = _enable_global_tracing()
    chain = await _assemble_chain(hallucination_score=0.2, real_udmr=True)
    result, error = await _run_chain(chain)

    assert error is None
    assert result is not None and result.workflow_status == "completed"
    calls = [
        c
        for c in chain["fake_llm"].structured_generate.call_args_list
        if c.kwargs.get("response_schema") is HallucinationEvaluationSchema
    ]
    assert len(calls) == 1
    config = calls[0].kwargs.get("config")
    assert config is not None
    assert config.model == "test-model-a", "幻觉检测 config.model 应等于 UDMR 路由产物"
    assert config.temperature == 0.1
    assert config.timeout == 8.0
    assert config.endpoint == "https://test-model-a.example/v1"
    # 评估仍成功（三键在位）
    from src.application.ports.agent_tracing import SpanAttributeKeys

    attrs = _get_root(exporter).attributes
    assert attrs[SpanAttributeKeys.EVAL_HALLUCINATION_SCORE] == 0.2


async def test_scenario_3_degradation_chain_not_blocking() -> None:
    """场景③：降级链——幻觉分支 LLMAPIError → 主链正常 + 三键缺席 + AgentDecided 照常发布。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys
    from src.domain.events.agent_events import AgentDecided

    exporter = _enable_global_tracing()
    chain = await _assemble_chain(hallucination_error=True)
    result, error = await _run_chain(chain)

    assert error is None, "评估失败应降级不阻断主链"
    assert result is not None and result.workflow_status == "completed"
    attrs = _get_root(exporter).attributes
    for key in (
        SpanAttributeKeys.EVAL_HALLUCINATION_SCORE,
        SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE,
        SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY,
    ):
        assert key not in attrs
    # MVP 十属性仍在（降级不伤既有属性块）
    assert SpanAttributeKeys.AGENT_ID in attrs
    assert SpanAttributeKeys.WORKFLOW_STATUS in attrs
    assert SpanAttributeKeys.EVAL_CONFIDENCE in attrs
    # AgentDecided 照常发布（工作流既有事件——评估降级不影响事件面）
    decided = [e for e in chain["recorder"].published_events if isinstance(e, AgentDecided)]
    assert len(decided) >= 1


async def test_scenario_4_none_path_matches_5_7_baseline() -> None:
    """场景④：None 路径对比——五参构造 execute 与 5-7 基线 span 树等价（十属性 + 零 eval.*）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    exporter = _enable_global_tracing()
    chain = await _assemble_chain(with_evaluation=False)
    assert chain["evaluation_harness"] is None
    result, error = await _run_chain(chain)

    assert error is None
    assert result is not None and result.workflow_status == "completed"
    attrs = _get_root(exporter).attributes
    for key in (
        SpanAttributeKeys.EVAL_HALLUCINATION_SCORE,
        SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE,
        SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY,
    ):
        assert key not in attrs, f"None 路径零 eval.* 键: {key}"
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
        assert key in attrs, f"None 路径十属性应在位: {key}"


# ===================================================================
# 场景⑤：P95 计时（委托——验收 AC-5.1 消费 _PERF_CACHE）
# ===================================================================


def _make_p95_input() -> Any:
    """计时输入（固定构造 AgentWorkflowResult——每采样同输入）。"""
    from src.application.ports.agent_workflow import AgentWorkflowResult
    from src.domain.value_objects.chain_of_thought import ChainOfThought
    from src.domain.value_objects.task_evidence import TaskEvidencePackage

    chain = ChainOfThought(
        input_summary="任务理解：分析新能源汽车行业进入战略并给出三层次建议",
        reflection="复盘：论证链条完整",
        tools_used=("pestel_analysis:1.0",),
        constraints_check="约束核对通过",
        final_answer='{"answer": "三层次进入策略：聚焦细分市场、构建生态合作、分阶段投入"}',
    )
    evidence = TaskEvidencePackage(
        input_hash="a" * 64,  # 64 位 hex 假值（VO 校验形态——5-3 存量先例 L97）
        task_breakdown=("市场分析", "进入策略制定"),
        tool_trace=("pestel_analysis:1.0",),
        artifacts_snapshot=(("pestel_report", "政策支持 经济上行"),),
        confidence=0.85,
        confidence_rationale="结构化检查通过",
        citations=("行业白皮书-2026",),
        status="completed",
        failure_reason="",
    )
    return AgentWorkflowResult(
        chain=chain,
        evidence=evidence,
        workflow_status="completed",
        retry_count=0,
        executed_phases=("perceive", "plan", "verify", "package"),
    )


def _make_evaluating_harness(llm_call_counter: dict[str, int]) -> Any:
    """计时 harness（Fake LLM 即时返回——采样轮共享单 Fake，计数经闭包聚合）。"""
    from src.application.services.evaluation_harness import EvaluationHarness
    from src.domain.ports.llm_client import LLMConfig

    fake = _make_fake_llm(hallucination_score=0.2)
    original_side_effect = fake.structured_generate.side_effect

    async def _counting_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        llm_call_counter["count"] += 1
        return await original_side_effect(
            prompt=prompt, response_schema=response_schema, config=config, system_prompt=system_prompt
        )

    fake.structured_generate.side_effect = _counting_generate

    class _StaticResolver:
        async def resolve_config(self, input_text: str) -> Any:
            return LLMConfig(
                model="base-eval-model",
                endpoint="https://base-eval.example/v1",
                api_key=_BASE_EVAL_FAKE_KEY,
            )

    return EvaluationHarness(llm_client=fake, model_resolver=_StaticResolver())


async def sample_evaluation_pipeline_perf() -> dict[str, Any]:
    """评估管线 P95 采样（幂等——_PERF_CACHE 命中早退；warmup 1 + 20 采样 exclusive [18]）。

    集成场景⑤ await 直调；验收 AC-5.1 BDD 步骤经 _run_async(loop, coro) 同循环调度
    （async 协程形态使两侧共享同一 _PERF_CACHE 批次——禁采样双跑）。

    Returns:
        dict[str, Any]: 采样摘要（p95_seconds/sample_count/llm_call_count）。
    """
    if _PERF_CACHE:
        cached: dict[str, Any] = _PERF_CACHE["summary"]
        return cached
    llm_call_counter = {"count": 0}
    harness = _make_evaluating_harness(llm_call_counter)
    evaluation_input = _make_p95_input()

    for _ in range(EVALUATION_WARMUP_ROUNDS):
        await harness.evaluate(evaluation_input)  # warmup 不计入
    latencies: list[float] = []
    for _ in range(EVALUATION_SAMPLE_ROUNDS):
        start = time.perf_counter()
        await harness.evaluate(evaluation_input)
        latencies.append(time.perf_counter() - start)

    summary: dict[str, Any] = {
        "p95_seconds": statistics.quantiles(latencies, n=EVALUATION_SAMPLE_ROUNDS)[18],
        "sample_count": EVALUATION_WARMUP_ROUNDS + EVALUATION_SAMPLE_ROUNDS,
        "llm_call_count": llm_call_counter["count"],
        "latencies_max": max(latencies),
    }
    _PERF_CACHE["summary"] = summary
    return summary


@pytest.mark.benchmark
async def test_scenario_5_evaluation_pipeline_p95_below_500ms() -> None:
    """场景⑤：评估管线 P95 < 500ms（Fake LLM 管线口径——常量单源 + 正向锚）。"""
    summary = await sample_evaluation_pipeline_perf()
    assert summary["p95_seconds"] < EVALUATION_P95_LIMIT_SECONDS, (
        f"评估管线 P95 应 < {EVALUATION_P95_LIMIT_SECONDS}s，实际 {summary['p95_seconds']}s"
    )
    # 正向锚：采样轮 structured_generate 调用计数 == warmup + 采样数（防静默降级假绿）
    assert summary["llm_call_count"] == summary["sample_count"] == (EVALUATION_WARMUP_ROUNDS + EVALUATION_SAMPLE_ROUNDS)
