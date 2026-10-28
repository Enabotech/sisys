"""验收测试 Story 5.8 - Agent 输出质量评估（FR-EV-02）。

12 场景三属性分档表（Task 0.6 定稿）：

| 场景 | 外部服务依赖 | 前置状态（Given 装配） | 断言面（Then） |
|------|-------------|----------------------|---------------|
| AC-1.1 | 零（组件级） | 端口模块延迟加载 | 构造/201 越界/bool 拒/frozen/权重和 |
| AC-1.2 | 零（Fake LLM + 替身） | 评估链装配（幻觉分 0.2 注入） | 调用矩阵（三要素/Schema/config）+ 450 守卫 + 异常矩阵 |
| AC-1.3 | 零（同上） | 评估链装配 | cr 四态精确值 + ca 数值矩阵 + overall 同式表达式对照 |
| AC-2.1 | 零（真实 UDMR 链 + 手写替身） | 健康替身 True + 单云端 + PIPL 注入 | cloud 匹配逐字段 + 事件发布 + 决策日志 |
| AC-2.2 | 零（同上） | 健康替身 False + 本地模型（≠ from_env 默认） | local 回退 + 双配置非硬编码矩阵 |
| AC-2.3 | 零（同上） | 漂移配置双注入（policy=B × resolver=A） | 450 携诊断 context + 事件已发布 |
| AC-3.1 | 零（Fake LLM 六分派 + OTel） | 链级 initialize 通道 + 评估链注入 | 三键真值 0.2/0.0/0.55 + 常量键串 + 零耦合 |
| AC-3.2 | 零（同上） | 幻觉分支抛 LLMAPIError | 主链正常 + 三键缺席 + warning + 十属性在位 |
| AC-3.3 | 零（同上） | 模块加载 + None 链 | 六依赖签名 + None 基线一致 + 5-7 断言更新 |
| AC-4.1 | 零（组合根 resolve——UDMR env 清理） | UDMR_CLOUD_* 全清理 | 双端口四件 + use case 注入 + REQUIRED_METHODS |
| AC-4.2 | 零（静态扫描） | 交付文件存在 | 白名单/domain 收窄/零实例化/主链静态锚/配置零改动 |
| AC-5.1 | 零（委托集成计时） | _PERF_CACHE 委托采样 | P95<0.5s + 正向锚（调用计数 == 采样总数） |
| 收尾 | 零（文件清单） | 开发完成 | src/tests 清单 + 5-7 更新 ×2 + 配置零改动 |

span 断言锚（5-7 SSOT 全文唯一口径）：装饰器/@trace 链路 span 只经全局 provider
可观测——链级场景（AC-3.*）统一通道 = 场景级新 TracerProvider + SimpleSpanProcessor
+ InMemorySpanExporter 经 PhoenixTracer(config=测试配置, tracer_provider=注入)
.initialize() → 断言 → teardown 强制 reset_for_testing() 双复位；组件级场景
（AC-1/AC-2）零全局触碰（不经装饰器，纯服务调用无 span 依赖）。

Run with:
    poetry run pytest tests/acceptance/test_acceptance_agent_evaluation.py -v
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
# 计时场景逐字同组（loadgroup 同 worker 串行是 _PERF_CACHE 委托缓存命中前提）
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.xdist_group("agent-evaluation-perf"),
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
    （test_event_monitoring::TestInitTracing）与场景间交叉污染。评估模块未交付
    （Task 0 红阶段）时零复位零阻断——场景步骤的延迟 import 承载红。
    """
    try:
        from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer
    except ImportError:
        yield  # Task 0 红阶段兼容：模块未交付时零复位零阻断（转绿后不可达分支）
        return
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


def _make_injectable_components() -> tuple[Any, Any]:
    """链级注入通道材料：新 TracerProvider + Simple + InMemory（零全局触碰）。"""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _enable_test_tracing(context: dict[str, Any]) -> None:
    """链级统一通道：注入 provider 经 initialize 履行全局 set（唯一职责——5-7 SSOT）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    provider, exporter = _make_injectable_components()
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


class _RecordingEventPublisher:
    """记录发布事件的发布器（内存替身发布面——5-7 先例同款形态）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(event.event_id) if hasattr(event, "event_id") else "",
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


class _RecordingToolExecutionService:
    """记录 ExecutionContext 的工具执行服务包装（duck-typing 委托）。"""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.captured_contexts: list[Any] = []

    async def execute(self, tool_id: Any, tool_call: Any, execution_context: Any) -> Any:
        self.captured_contexts.append(execution_context)
        return await self._inner.execute(tool_id, tool_call, execution_context)


class _StubProfileUseCase:
    """零 IO 档案用例替身（duck-typing——返回手工装配的 AgentProfileLoadResult）。"""

    def __init__(self, profile_result: Any) -> None:
        self._profile_result = profile_result

    async def execute(self, agent_id: Any) -> Any:
        return self._profile_result


class _RecordingDecisionLogRepository:
    """零 IO 路由决策日志仓储替身（duck-typing——save 调用记录，AC-2 决策日志断言锚）。"""

    def __init__(self) -> None:
        self.saved_logs: list[Any] = []

    async def save(self, log_entry: Any) -> None:
        self.saved_logs.append(log_entry)


class _StubHealthChecker:
    """健康检查替身（外部探测面豁免——True/False 可控路由方向；双方法防 isinstance 校验）。"""

    def __init__(self, healthy: bool) -> None:
        self._healthy = healthy
        self.check_calls = 0

    async def check(self) -> bool:
        self.check_calls += 1
        return self._healthy

    async def close(self) -> None:
        return None


class _StaticModelResolverStub:
    """固定基底配置解析替身（AC-1/AC-3——评估管线断言与路由方向解耦，R3-F3 钉死）。

    基底 config 的 temperature/timeout 必须与评估常量（0.1/8.0）相异——
    LLMConfig() 默认 0.7/600.0 恰满足判别力前提（实现漏 replace 时断言必红）。
    """

    def __init__(self, base_config: Any) -> None:
        self.base_config = base_config
        self.resolve_calls: list[str] = []

    async def resolve_config(self, input_text: str) -> Any:
        self.resolve_calls.append(input_text)
        return self.base_config


def _make_evaluation_resolver_stub() -> Any:
    """评估链 resolver 替身（连接字段非默认值——连接继承断言有判别力）。"""
    from src.domain.ports.llm_client import LLMConfig

    return _StaticModelResolverStub(
        LLMConfig(model="base-eval-model", endpoint="https://base-eval.example/v1", api_key=_BASE_EVAL_FAKE_KEY)
    )


def _make_fake_llm(
    *,
    verify_mode: str = "always_pass",
    plan_tool_names: tuple[str, ...] = (),
    hallucination_score: float = 0.2,
    hallucination_error: bool = False,
    delay_sec: float = 0.0,
) -> Any:
    """六阶段 + 幻觉检测 Fake LLM 替身（外部 SaaS 豁免面——5-7 先例 + 幻觉分支扩展）。

    分派键 = response_schema 身份（Schema 两两不同前提——幻觉 Schema 独立新类保持）；
    幻觉分派值可注入（AC-3.1 三键真值数据源）；hallucination_error=True 时幻觉
    分支抛 LLMAPIError（AC-3.2 降级注入面）。
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
    from src.domain.exceptions import LLMAPIError
    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    verify_calls = {"count": 0}
    tool_llm_calls = {"count": 0}

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        if delay_sec:
            await asyncio.sleep(delay_sec)
        if response_schema is HallucinationEvaluationSchema:
            if hallucination_error:
                raise LLMAPIError(message="模拟评估 LLM API 故障（验收注入）")
            return HallucinationEvaluationSchema(
                rationale="回答与证据材料一致，无幻觉内容",
                hallucination_score=hallucination_score,
            )
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


def _make_evaluation_input(
    *,
    tool_trace: tuple[str, ...] = (),
    artifacts_snapshot: tuple[tuple[str, str], ...] = (),
    citations: tuple[str, ...] = (),
    confidence: float = 0.85,
) -> Any:
    """评估输入真实 VO 构造（ChainOfThought + TaskEvidencePackage——242 校验通过的真实材料）。"""
    from src.application.ports.agent_workflow import AgentWorkflowResult
    from src.domain.value_objects.chain_of_thought import ChainOfThought
    from src.domain.value_objects.task_evidence import TaskEvidencePackage

    chain = ChainOfThought(
        input_summary="任务理解：分析新能源汽车行业进入战略并给出三层次建议",
        reflection="复盘：论证链条完整",
        tools_used=tool_trace,
        constraints_check="约束核对通过",
        final_answer='{"answer": "三层次进入策略：聚焦细分市场、构建生态合作、分阶段投入"}',
    )
    evidence = TaskEvidencePackage(
        input_hash="a" * 64,  # 64 位 hex 假值（VO 校验形态——5-3 存量先例 L97）
        task_breakdown=("市场分析", "进入策略制定"),
        tool_trace=tool_trace,
        artifacts_snapshot=artifacts_snapshot,
        confidence=confidence,
        confidence_rationale="结构化检查通过，置信折算 0.85",
        citations=citations,
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


def _assemble_evaluation_chain(context: dict[str, Any], *, hallucination_score: float = 0.2) -> None:
    """AC-1 组件级评估链装配（Fake LLM + resolver 替身 + 真实 EvaluationHarness）。"""
    from src.application.services.evaluation_harness import EvaluationHarness

    fake_llm = _make_fake_llm(hallucination_score=hallucination_score)
    resolver = _make_evaluation_resolver_stub()
    harness = EvaluationHarness(llm_client=fake_llm, model_resolver=resolver)
    context["fake_llm"] = fake_llm
    context["resolver"] = resolver
    context["harness"] = harness
    context["evaluation_input"] = _make_evaluation_input()
    context["evaluation_result"] = None


def _make_cloud_config(model: str) -> Any:
    """测试云端模型配置（CloudModelConfig——连接字段全非默认值，逐字段断言有判别力）。"""
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


_TEST_LOCAL_MODEL = "qwen2.5-eval-local"
_TEST_LLM_TIMEOUT = 30


def _assemble_udmr_chain(
    context: dict[str, Any],
    *,
    policy_models: tuple[str, ...],
    resolver_models: tuple[str, ...],
    health_healthy: bool,
) -> None:
    """AC-2 真实 UDMR 决策链手工装配（零外部服务——DC-7 豁免面：手写替身 + 真实件）。

    装配面：真实 UDMRService（十参数对齐组合根 L1627-1647）+ 真实 StaticUdmrPolicy
    （policy_models 注入）+ 真实 ComplianceGatewayImpl（**pipl_service 显式注入**——
    零参装配下 PIPL 正则分支被 if self._pipl_service: 门死不可达）+ 真实
    StaticTokenEstimator + 真实 build_cost_calculator（纯计算零 IO）+ 手写零 IO
    publisher/决策日志替身 + 手写健康检查替身（True/False 可控路由方向）。
    local_model 取与 from_env 默认（qwen2.5:7b）相异值——local 分支判别力前提。
    """
    from src.domain.services.udmr_service import UDMRService
    from src.infrastructure.config.udmr import build_cost_calculator
    from src.infrastructure.monitoring.static_token_estimator import StaticTokenEstimator
    from src.infrastructure.routing.udmr_evaluation_model_resolver import UdmrEvaluationModelResolver
    from src.infrastructure.routing.udmr_policy import StaticUdmrPolicy
    from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl
    from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

    publisher: Any = _RecordingEventPublisher()
    log_repo: Any = _RecordingDecisionLogRepository()
    health_checker = _StubHealthChecker(health_healthy)
    service = UDMRService(
        compliance_gateway=ComplianceGatewayImpl(pipl_service=PIPLComplianceServiceImpl()),
        policy=StaticUdmrPolicy(
            cloud_configs=[_make_cloud_config(m) for m in policy_models],
            local_model=_TEST_LOCAL_MODEL,
        ),
        health_checker=health_checker,
        log_repo=log_repo,
        publisher=publisher,
        local_first=False,
        local_model=_TEST_LOCAL_MODEL,
        llm_timeout=_TEST_LLM_TIMEOUT,
        token_estimator=StaticTokenEstimator(),
        cost_calculator=build_cost_calculator(),
    )
    resolver = UdmrEvaluationModelResolver(
        udmr_service=service,
        cloud_configs=[_make_cloud_config(m) for m in resolver_models],
        local_model=_TEST_LOCAL_MODEL,
        llm_timeout=_TEST_LLM_TIMEOUT,
    )
    context["udmr_service"] = service
    context["publisher"] = publisher
    context["log_repo"] = log_repo
    context["health_checker"] = health_checker
    context["resolver"] = resolver
    context["resolved_config"] = None
    context["caught"] = None


_EVALUATION_INPUT_TEXT = "最终回答：三层次进入策略（评估路由输入文本）"

#: 测试假密钥占位（resolver 替身基底的连接字段——非真实凭据）
_BASE_EVAL_FAKE_KEY = "base-eval-" + "key"


def _assemble_evaluation_workflow_chain(
    context: dict[str, Any],
    *,
    hallucination_score: float = 0.2,
    hallucination_error: bool = False,
    with_evaluation: bool = True,
) -> None:
    """AC-3 链级手工装配（5-7 _assemble_workflow_chain 同款 + 第六依赖注入）。

    零工具步（plan_tool_names=()）——evidence 三元组全空 → cr=0.0（R3 钦定
    精确三元组前提）；评估链 resolver 用替身（三键值与路由方向无关——真实
    UDMR 链归 AC-2 与集成场景②）。
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

    fake_llm = _make_fake_llm(
        plan_tool_names=(),
        hallucination_score=hallucination_score,
        hallucination_error=hallucination_error,
    )
    context["fake_llm"] = fake_llm
    recording_tool_service = _RecordingToolExecutionService(_build_tool_execution_service(fake_llm))

    service: Any = AgentWorkflowService(
        llm_client=fake_llm,
        tool_execution_service=recording_tool_service,
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

    evaluation_harness = None
    if with_evaluation:
        evaluation_harness = EvaluationHarness(llm_client=fake_llm, model_resolver=_make_evaluation_resolver_stub())
    context["evaluation_harness"] = evaluation_harness
    context["use_case"] = RunAgentWorkflowUseCase(
        agent_repository=stub_agent_repo,
        agent_profile_use_case=profile_use_case,
        agent_engine=context["engine"],
        agent_workflow_service=service,
        isolation_guard=guard,
        evaluation_harness=evaluation_harness,
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


def _get_spans(context: dict[str, Any]) -> list[Any]:
    """取导出器全部 span（链级场景断言锚——exporter 必在位）。"""
    exporter = context.get("_exporter")
    assert exporter is not None, "链级场景须先启用测试追踪（initialize 全局通道）"
    return list(exporter.get_finished_spans())


def _get_root_span(context: dict[str, Any]) -> Any:
    """取唯一 agent_execution 根 span。"""
    roots = [s for s in _get_spans(context) if s.name == "agent_execution"]
    assert len(roots) == 1, f"应恰有一个 agent_execution 根 span，实际 {len(roots)}"
    return roots[0]


# ===================================================================
# AC-1: EvaluationResult 模型与三维指标计算（组件级——零服务依赖）
# ===================================================================


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-1.1 - EvaluationResult 构造与分数域校验",
)
def test_ac_1_1_evaluation_result_model_and_domain_guard(context: dict[str, Any]) -> None:
    """AC-1.1: 构造/201 越界参数化/bool 拒/frozen/权重和断言。"""


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-1.2 - 幻觉检测 LLM 结构化调用",
)
def test_ac_1_2_hallucination_llm_structured_call(context: dict[str, Any]) -> None:
    """AC-1.2: prompt 三要素 + Schema 身份 + config 派生 + 450 守卫 + LLM 族异常矩阵。"""


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-1.3 - 证据支撑度与校准公式计算",
)
def test_ac_1_3_context_relevance_and_calibration_formulas(context: dict[str, Any]) -> None:
    """AC-1.3: cr 四态精确值 + ca 数值矩阵 + overall 同式表达式对照。"""


@given("评估端口模型模块已加载")
def given_evaluation_port_module_loaded(context: dict[str, Any]) -> None:
    """端口模型加载（延迟 import——Task 0 红阶段的 ModuleNotFoundError 承载者）。"""
    from src.application.ports.agent_evaluation import (
        AgentEvaluationPort,
        EvaluationModelResolverPort,
        EvaluationResult,
    )

    context["AgentEvaluationPort"] = AgentEvaluationPort
    context["EvaluationModelResolverPort"] = EvaluationModelResolverPort
    context["EvaluationResult"] = EvaluationResult


@given("评估链已装配（Fake LLM + resolver 替身）")
def given_evaluation_chain_assembled(context: dict[str, Any]) -> None:
    """组件级评估链装配（幻觉分 0.2 注入 + resolver 替身固定基底）。"""
    _assemble_evaluation_chain(context, hallucination_score=0.2)


@when("构造合法 EvaluationResult 实例并执行分数域校验")
def when_construct_valid_evaluation_result(context: dict[str, Any]) -> None:
    """合法构造 + 分数域守卫执行（合法四分数 → 实例化成功）。"""
    from src.application.ports.agent_evaluation import EvaluationResult

    context["valid_result"] = EvaluationResult(
        hallucination_score=0.2,
        context_relevance=0.4,
        confidence_accuracy=0.55,
        overall_score=0.5,
    )


@then("四分数字段值与权重常量断言通过")
def then_evaluation_result_fields_and_weights(context: dict[str, Any]) -> None:
    """四字段值断言 + 权重常量两组和为 1.0 元断言（防权重漂移）。"""
    from src.application.ports.agent_evaluation import (
        CONFIDENCE_ACCURACY_WEIGHT,
        CONTEXT_ARTIFACT_WEIGHT,
        CONTEXT_CITATION_WEIGHT,
        CONTEXT_RELEVANCE_WEIGHT,
        CONTEXT_TOOL_TRACE_WEIGHT,
        HALLUCINATION_WEIGHT,
    )

    result = context["valid_result"]
    assert result.hallucination_score == 0.2
    assert result.context_relevance == 0.4
    assert result.confidence_accuracy == 0.55
    assert result.overall_score == 0.5
    overall_sum = HALLUCINATION_WEIGHT + CONTEXT_RELEVANCE_WEIGHT + CONFIDENCE_ACCURACY_WEIGHT
    context_sum = CONTEXT_CITATION_WEIGHT + CONTEXT_ARTIFACT_WEIGHT + CONTEXT_TOOL_TRACE_WEIGHT
    assert overall_sum == 1.0, f"overall 三维权重和应为 1.0，实际 {overall_sum}"
    assert context_sum == 1.0, f"证据支撑度三元权重和应为 1.0，实际 {context_sum}"


@then("越界分数构造抛出 ValidationError 201")
def then_out_of_range_raises_validation_error_201(context: dict[str, Any]) -> None:
    """越界/类型错 → 201 三段式（isinstance → code → context 携字段名）。"""
    from src.domain.exceptions import ValidationError

    result_cls = context["EvaluationResult"]
    base = {
        "hallucination_score": 0.2,
        "context_relevance": 0.4,
        "confidence_accuracy": 0.55,
        "overall_score": 0.5,
    }
    bad_values = [-0.01, 1.01, 2.0]
    for field in base:
        for bad in bad_values:
            kwargs = {**base, field: bad}
            with pytest.raises(ValidationError) as exc_info:
                result_cls(**kwargs)
            caught = exc_info.value
            assert isinstance(caught, ValidationError)
            assert caught.code == "EXCEPTION_201"
            assert field in caught.context, f"context 应携越界字段名 {field}: {caught.context}"
    # bool 拒（bool 是 int 子类——显式拒绝防隐性分数）
    for field in base:
        kwargs = {**base, field: True}
        with pytest.raises(ValidationError) as exc_info:
            result_cls(**kwargs)
        assert exc_info.value.code == "EXCEPTION_201"


@then("frozen 不可变断言通过")
def then_evaluation_result_frozen(context: dict[str, Any]) -> None:
    """frozen dataclass 不可变断言（赋值 raises FrozenInstanceError）。"""
    import dataclasses

    result = context["valid_result"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.hallucination_score = 0.9


@when("调用 EvaluationHarness.evaluate 执行评估")
def when_call_harness_evaluate(context: dict[str, Any]) -> None:
    """评估执行（Fake LLM 幻觉分派 → evaluate 端到端 → EvaluationResult）。"""
    context["evaluation_result"] = _run_async(context["_loop"], context["harness"].evaluate(context["evaluation_input"]))


@then("幻觉检测 structured_generate 调用断言通过（prompt 三要素 + Schema 身份 + config 派生）")
def then_hallucination_call_assertions(context: dict[str, Any]) -> None:
    """调用矩阵断言：prompt 三要素 + response_schema 身份 + config 派生（0.1/8.0 + 连接继承）。"""
    from src.application.services.evaluation_harness import EVALUATION_TEMPERATURE, EVALUATION_TIMEOUT_SEC
    from src.application.services.evaluation_schemas import HallucinationEvaluationSchema

    fake_llm = context["fake_llm"]
    calls = [
        c
        for c in fake_llm.structured_generate.call_args_list
        if c.kwargs.get("response_schema") is HallucinationEvaluationSchema
    ]
    assert len(calls) == 1, f"幻觉检测应恰一次 structured_generate 调用，实际 {len(calls)}"
    call = calls[0]
    prompt = call.kwargs["prompt"]
    # 三要素：input_summary（任务理解参照）+ 证据摘要 + final_answer（被评估回答）
    assert "分析新能源汽车行业进入战略" in prompt, "prompt 应含 chain.input_summary"
    assert "（无引用源）" in prompt, "prompt 应含证据摘要段（零证据链的确定性占位形态——CR1-F6 内容锚）"
    assert '{"answer"' in prompt, "prompt 应含 chain.final_answer（JSON 尾段）"
    assert call.kwargs["response_schema"] is HallucinationEvaluationSchema
    assert call.kwargs.get("system_prompt"), "应传 SYSTEM_PROMPT"
    config = call.kwargs.get("config")
    assert config is not None, "应传派生 config（禁 None 走客户端默认）"
    assert config.temperature == EVALUATION_TEMPERATURE == 0.1
    assert config.timeout == EVALUATION_TIMEOUT_SEC == 8.0
    # 连接字段随路由产物继承（基底 0.7/600.0 与评估常量相异——判别力前提）
    assert config.model == "base-eval-model"
    assert config.endpoint == "https://base-eval.example/v1"
    assert config.api_key == context["resolver"].base_config.api_key


@then("幻觉分与 Fake 注入值相等")
def then_hallucination_score_matches_injection(context: dict[str, Any]) -> None:
    """evaluate 返回 hallucination_score == Fake 注入值（0.2）。"""
    result = context["evaluation_result"]
    assert result.hallucination_score == 0.2


@then("Schema 校验失败路径抛出 AgentEvaluationError 450")
def then_schema_guard_raises_450(context: dict[str, Any]) -> None:
    """Fake 返回非 Schema 实例 → isinstance 守卫 → 450 三段式。"""
    from unittest.mock import AsyncMock

    from src.application.services.evaluation_harness import EvaluationHarness
    from src.domain.exceptions import AgentEvaluationError
    from src.domain.ports.llm_client import LLMClientPort

    async def _bad_schema(prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None) -> Any:
        return {"hallucination_score": 0.1, "rationale": "非 Schema 实例（验收注入）"}

    bad_llm = AsyncMock(spec=LLMClientPort)
    bad_llm.structured_generate.side_effect = _bad_schema
    bad_harness = EvaluationHarness(llm_client=bad_llm, model_resolver=_make_evaluation_resolver_stub())
    with pytest.raises(AgentEvaluationError) as exc_info:
        _run_async(context["_loop"], bad_harness.evaluate(context["evaluation_input"]))
    caught = exc_info.value
    assert isinstance(caught, AgentEvaluationError)
    assert caught.code == "EXCEPTION_450"
    assert caught.context["phase"] == "evaluation"
    assert caught.context["reason"] == "schema_validation"


@then("LLM 族异常矩阵断言通过（450 包装与 332 透传分述）")
def then_llm_exception_matrix(context: dict[str, Any]) -> None:
    """异常矩阵：330/331/Timeout/ServiceUnavailable → 450 包装 from error；332/Cancelled 透传。"""
    import asyncio as asyncio_module
    from unittest.mock import AsyncMock

    from src.application.services.evaluation_harness import EvaluationHarness
    from src.domain.exceptions import (
        AgentEvaluationError,
        LLMAPIError,
        LLMConfigError,
        LLMResponseError,
        ServiceUnavailableError,
    )
    from src.domain.ports.llm_client import LLMClientPort

    wrapped_cases = [
        LLMAPIError(message="模拟 330"),
        LLMResponseError(message="模拟 331"),
        TimeoutError("模拟超时"),
        ServiceUnavailableError(message="模拟 503"),
    ]
    for injected in wrapped_cases:

        async def _raise_error(
            prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None, _e=injected
        ) -> Any:
            raise _e

        fake = AsyncMock(spec=LLMClientPort)
        fake.structured_generate.side_effect = _raise_error
        harness = EvaluationHarness(llm_client=fake, model_resolver=_make_evaluation_resolver_stub())
        with pytest.raises(AgentEvaluationError) as exc_info:
            _run_async(context["_loop"], harness.evaluate(context["evaluation_input"]))
        caught = exc_info.value
        assert caught.code == "EXCEPTION_450", f"{type(injected).__name__} 应包装 450"
        assert caught.context["phase"] == "evaluation"
        assert caught.context["reason"] == "llm_call"
        assert isinstance(caught.__cause__, type(injected)), "包装应 from error 保留异常链"

    # 透传两支：LLMConfigError（332）与 CancelledError（BaseException 族——变量分离防类型窄化冲突）
    passthrough_cases: list[BaseException] = [LLMConfigError(message="模拟 332"), asyncio_module.CancelledError()]
    for injected_case in passthrough_cases:

        async def _raise_passthrough(
            prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None, _e=injected_case
        ) -> Any:
            raise _e

        fake = AsyncMock(spec=LLMClientPort)
        fake.structured_generate.side_effect = _raise_passthrough
        harness = EvaluationHarness(llm_client=fake, model_resolver=_make_evaluation_resolver_stub())
        with pytest.raises(type(injected_case)) as passthrough_info:
            _run_async(context["_loop"], harness.evaluate(context["evaluation_input"]))
        assert not isinstance(passthrough_info.value, AgentEvaluationError), f"{type(injected_case).__name__} 应透传不包装"


@when("调用证据支撑度四态参数化计算与校准公式数值矩阵")
def when_compute_context_relevance_and_calibration(context: dict[str, Any]) -> None:
    """四态参数化 + 数值矩阵执行（结果存 context 供 Then 断言）。"""
    harness = context["harness"]
    four_states = {
        "all_empty": _make_evaluation_input(),
        "citations_only": _make_evaluation_input(citations=("行业白皮书-2026",)),
        "citations_and_tool_trace": _make_evaluation_input(citations=("行业白皮书-2026",), tool_trace=("pestel_analysis:1.0",)),
        "all_full": _make_evaluation_input(
            citations=("行业白皮书-2026",),
            tool_trace=("pestel_analysis:1.0",),
            artifacts_snapshot=(("pestel_report", "政策支持 经济上行"),),
        ),
    }
    context["cr_results"] = {name: harness.compute_context_relevance(inp.evidence) for name, inp in four_states.items()}
    context["ca_results"] = {
        "zero_diff": harness.compute_confidence_accuracy(0.5, 0.5),
        "point3_diff": harness.compute_confidence_accuracy(1.0, 0.7),
        "full_diff": harness.compute_confidence_accuracy(1.0, 0.0),
    }
    full_evidence_input = _make_evaluation_input(
        citations=("行业白皮书-2026",),
        tool_trace=("pestel_analysis:1.0",),
        artifacts_snapshot=(("pestel_report", "政策支持 经济上行"),),
        confidence=0.85,
    )
    context["evaluate_all_full"] = _run_async(context["_loop"], harness.evaluate(full_evidence_input))


@then("上下文相关性四态精确值断言通过（全空 0.0 / 仅引用 0.4 / 引用加轨迹 0.7 / 全满 1.0）")
def then_context_relevance_four_states(context: dict[str, Any]) -> None:
    """四态精确值断言（OD-3 证据支撑度三元加权——确定性启发式）。"""
    cr = context["cr_results"]
    assert cr["all_empty"] == 0.0, f"全空应 0.0，实际 {cr['all_empty']}"
    assert cr["citations_only"] == 0.4, f"仅 citations 应 0.4，实际 {cr['citations_only']}"
    assert cr["citations_and_tool_trace"] == 0.7, f"citations+tool_trace 应 0.7，实际 {cr['citations_and_tool_trace']}"
    assert cr["all_full"] == 1.0, f"全满应 1.0，实际 {cr['all_full']}"


@then("置信度校准数值矩阵断言通过（偏差 0 得 1.0 / 偏差 0.3 得 0.7 / 偏差不小于 1.0 得 0.0）")
def then_calibration_numeric_matrix(context: dict[str, Any]) -> None:
    """校准公式矩阵（§17.3.8 L1681 钦定：1.0 - min(|predicted-actual|, 1.0)）。"""
    ca = context["ca_results"]
    assert ca["zero_diff"] == 1.0, f"|diff|=0 应 1.0，实际 {ca['zero_diff']}"
    assert ca["point3_diff"] == 0.7, f"|diff|=0.3 应 0.7，实际 {ca['point3_diff']}"
    assert ca["full_diff"] == 0.0, f"|diff|>=1.0 应 0.0，实际 {ca['full_diff']}"


@then("overall 加权手算对照断言通过（同式表达式期望值）")
def then_overall_weighted_manual_check(context: dict[str, Any]) -> None:
    """overall 同式表达式对照（禁十进制字面量——浮点实算值非 0.6475 类字面）。

    组合链：h=0.2（Fake 注入）+ cr=1.0（全满证据）+ pred=0.85（evidence.confidence）
    → actual=(1-h)*0.5+cr*0.5 → ca=1-min(|pred-actual|,1.0) → overall 三键反转加权。
    """
    from src.application.ports.agent_evaluation import (
        CONFIDENCE_ACCURACY_WEIGHT,
        CONTEXT_RELEVANCE_WEIGHT,
        HALLUCINATION_WEIGHT,
    )

    result = context["evaluate_all_full"]
    h, cr, pred = 0.2, 1.0, 0.85
    actual_quality = (1.0 - h) * 0.5 + cr * 0.5
    expected_ca = 1.0 - min(abs(pred - actual_quality), 1.0)
    expected_overall = (
        (1.0 - h) * HALLUCINATION_WEIGHT + cr * CONTEXT_RELEVANCE_WEIGHT + expected_ca * CONFIDENCE_ACCURACY_WEIGHT
    )
    assert result.context_relevance == 1.0
    assert result.confidence_accuracy == expected_ca, f"ca 应 {expected_ca}，实际 {result.confidence_accuracy}"
    assert result.overall_score == expected_overall, f"overall 应 {expected_overall}，实际 {result.overall_score}"


# ===================================================================
# AC-2: 评估模型 UDMR in-band 动态路由（组件级——真实 UDMR 决策链手工装配）
# ===================================================================


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-2.1 - 评估模型 cloud 路由与 LLMConfig 匹配",
)
def test_ac_2_1_udmr_cloud_routing_and_config_match(context: dict[str, Any]) -> None:
    """AC-2.1: cloud 路由（健康 True + 单云端）→ 六连接字段 + timeout 逐字段匹配。"""


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-2.2 - 云端不可用 local 回退与非硬编码双配置判别",
)
def test_ac_2_2_local_fallback_and_non_hardcoded_matrix(context: dict[str, Any]) -> None:
    """AC-2.2: 健康检查 False → decide 回退 local + 双配置矩阵（模型 A/B 随注入变化）。"""


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-2.3 - 路由产物匹配失败 450 与事件发布",
)
def test_ac_2_3_drift_match_failure_450_and_event(context: dict[str, Any]) -> None:
    """AC-2.3: 漂移配置双注入（policy=B × resolver=A）→ 匹配失败 450 + 事件已发布。"""


@given("真实 UDMR 决策链已装配（健康检查替身 True + 单云端配置 + PIPL 服务显式注入）")
def given_udmr_chain_cloud(context: dict[str, Any]) -> None:
    """cloud 路向装配（健康 True + 单云端 test-model-a）。"""
    _assemble_udmr_chain(
        context,
        policy_models=("test-model-a",),
        resolver_models=("test-model-a",),
        health_healthy=True,
    )


@given("真实 UDMR 决策链已装配（健康检查替身 False + 云端配置 + 本地模型）")
def given_udmr_chain_local(context: dict[str, Any]) -> None:
    """local 路向装配（健康 False——云端不可用回退）。"""
    _assemble_udmr_chain(
        context,
        policy_models=("test-model-a",),
        resolver_models=("test-model-a",),
        health_healthy=False,
    )


@given("漂移配置双注入构造（policy 云配置模型 B 与 resolver 云配置模型 A）")
def given_udmr_chain_drift(context: dict[str, Any]) -> None:
    """漂移双注入装配（policy 看见 B、resolver 只认 A——decide 发布 B 后匹配失败）。

    零 mock 零 monkeypatch 全真实组件（R1-F6——验收禁 mock 红线下的唯一构造法）。
    """
    _assemble_udmr_chain(
        context,
        policy_models=("test-model-b",),
        resolver_models=("test-model-a",),
        health_healthy=True,
    )


@when("调用 resolver.resolve_config 解析评估模型配置")
def when_call_resolver_resolve_config(context: dict[str, Any]) -> None:
    """resolve_config 执行（真实 decide 链 → LLMConfig；异常捕获存 caught）。"""
    try:
        context["resolved_config"] = _run_async(context["_loop"], context["resolver"].resolve_config(_EVALUATION_INPUT_TEXT))
    except Exception as exc:
        context["caught"] = exc


@then("config 匹配云端模型（model 与 endpoint 与 api_key 与 timeout 逐字段相等）")
def then_config_matches_cloud_model(context: dict[str, Any]) -> None:
    """cloud 匹配六连接字段 + timeout ← llm_timeout（build_default_llm_config 同款先例）。"""
    expected_cloud = _make_cloud_config("test-model-a")
    config = context["resolved_config"]
    assert config is not None, "cloud 路由应返回 config"
    assert config.model == expected_cloud.model
    assert config.endpoint == expected_cloud.endpoint
    assert config.api_key == expected_cloud.api_key
    assert config.timeout == _TEST_LLM_TIMEOUT
    assert config.api_type == expected_cloud.api_type
    assert config.max_tokens == expected_cloud.max_tokens


@then("RoutingDecided 事件经替身捕获发布断言通过")
def then_routing_decided_event_published(context: dict[str, Any]) -> None:
    """事件发布断言（isinstance + route_type/selected_model 与 config 对应）。"""
    from src.domain.events.routing_events import RoutingDecided

    config = context["resolved_config"]
    events = [e for e in context["publisher"].published_events if isinstance(e, RoutingDecided)]
    assert len(events) >= 1, "decide() 应发布 RoutingDecided 事件"
    event = events[-1]
    assert event.route_type == "cloud"
    assert event.selected_model == config.model


@then("决策日志持久化断言通过")
def then_decision_log_persisted(context: dict[str, Any]) -> None:
    """决策日志持久化调用断言（零 IO 替身捕获——R1-F7：input 不可断言，以日志/事件一致性替代）。"""
    saved = context["log_repo"].saved_logs
    assert len(saved) >= 1, "decide() 应持久化决策日志"
    log_entry = saved[-1]
    assert log_entry.route_type == "cloud"
    assert log_entry.selected_model == context["resolved_config"].model


@then("local 分支断言通过（config.model 等于 selected_model 等于 local_model）")
def then_local_branch_assertions(context: dict[str, Any]) -> None:
    """local 回退断言（健康 False → decide 内部回退 → resolver 消费 local 分支）。"""
    from src.domain.ports.llm_client import LLMConfig

    config = context["resolved_config"]
    assert config is not None, "local 路由应返回 config"
    assert config.model == _TEST_LOCAL_MODEL, f"local 分支 model 应对齐路由产物，实际 {config.model}"
    # 连接字段来自 from_env 形态（local_model ≠ from_env 默认 qwen2.5:7b 的判别力前提
    # 由单测 resolver L225 前提断言承载——验收侧此断言由上行 ==_TEST_LOCAL_MODEL 蕴含，
    # CR1-F12 删除自证冗余行）
    from_env_defaults = LLMConfig.from_env()
    assert config.endpoint == from_env_defaults.endpoint
    assert config.api_key == from_env_defaults.api_key


@then("双配置矩阵非硬编码判别通过（模型 A 与模型 B 随注入变化）")
def then_non_hardcoded_dual_config_matrix(context: dict[str, Any]) -> None:
    """双配置矩阵（同一 resolver 代码不同注入 → config.model 随路由决策变化）。"""
    # 本场景已验 local 分支；此处构造 cloud 双配置对照（模型 A → A；模型 B → B）
    cloud_ctx: dict[str, Any] = {"_loop": context["_loop"]}
    _assemble_udmr_chain(cloud_ctx, policy_models=("test-model-a",), resolver_models=("test-model-a",), health_healthy=True)
    config_a = _run_async(cloud_ctx["_loop"], cloud_ctx["resolver"].resolve_config(_EVALUATION_INPUT_TEXT))
    assert config_a.model == "test-model-a"

    drift_ctx: dict[str, Any] = {"_loop": context["_loop"]}
    _assemble_udmr_chain(drift_ctx, policy_models=("test-model-b",), resolver_models=("test-model-b",), health_healthy=True)
    config_b = _run_async(drift_ctx["_loop"], drift_ctx["resolver"].resolve_config(_EVALUATION_INPUT_TEXT))
    assert config_b.model == "test-model-b", "同一 resolver 代码不同注入应产出不同模型（硬编码实现则不变）"


@then("匹配失败抛出 AgentEvaluationError 450（context 含 selected_model 与可用清单）")
def then_match_failure_raises_450(context: dict[str, Any]) -> None:
    """漂移匹配失败 → 450 三段式 + 诊断 context（禁静默回退）。"""
    from src.domain.exceptions import AgentEvaluationError

    caught = context.get("caught")
    assert caught is not None, "漂移配置应抛 AgentEvaluationError"
    assert isinstance(caught, AgentEvaluationError)
    assert caught.code == "EXCEPTION_450"
    assert caught.context["phase"] == "evaluation"
    assert caught.context["reason"] == "model_resolution"
    assert caught.context.get("selected_model") == "test-model-b"
    available = caught.context.get("available_models")
    assert available is not None and "test-model-a" in str(available), f"context 应含可用清单: {caught.context}"


@then("RoutingDecided 事件已发布断言通过（selected_model 与配置对应）")
def then_routing_event_published_on_drift(context: dict[str, Any]) -> None:
    """漂移场景事件先于 450 发布（decide 真实链——事件发布在匹配失败前完成）。"""
    from src.domain.events.routing_events import RoutingDecided

    events = [e for e in context["publisher"].published_events if isinstance(e, RoutingDecided)]
    assert len(events) >= 1, "匹配失败前 decide() 应已发布 RoutingDecided"
    assert events[-1].selected_model == "test-model-b"


# ===================================================================
# AC-3: 主链接入——评估执行 + eval.* 三键写根 span + 降级（链级）
# ===================================================================


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-3.1 - 主链评估执行与 eval.* 三键写根 span",
)
def test_ac_3_1_main_chain_evaluation_and_span_keys(context: dict[str, Any]) -> None:
    """AC-3.1: execute 末尾评估块 → 三键真值（0.2/0.0/0.55）+ 常量键串 + 零耦合。"""


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-3.2 - 评估降级不阻断主链",
)
def test_ac_3_2_evaluation_degradation_not_blocking(context: dict[str, Any]) -> None:
    """AC-3.2: 幻觉分支 LLMAPIError → 主链正常 + 三键缺席 + warning + 十属性在位。"""


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-3.3 - 构造签名扩展与存量回归基线",
)
def test_ac_3_3_signature_extension_and_baseline_regression(context: dict[str, Any]) -> None:
    """AC-3.3: 六依赖签名 + None 默认路径 5-7 基线一致 + 5-7 断言更新两处在位。"""


@given("工作流链已装配（Fake LLM 五 Schema 分派 + 评估链注入 + OTel 链级全局通道）")
def given_workflow_chain_with_evaluation(context: dict[str, Any]) -> None:
    """链级装配（零工具步 + 幻觉分 0.2 + initialize 全局通道）。"""
    _enable_test_tracing(context)
    _assemble_evaluation_workflow_chain(context, hallucination_score=0.2, with_evaluation=True)


@given("工作流链已装配（Fake LLM 幻觉分支抛 LLMAPIError + 评估链注入 + OTel 链级全局通道）")
def given_workflow_chain_with_evaluation_error(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    """链级装配（幻觉分支抛 LLMAPIError——降级注入面 + caplog 捕获 warning）。"""
    caplog.set_level(logging.WARNING, logger="src.application.use_cases.run_agent_workflow")
    _enable_test_tracing(context)
    _assemble_evaluation_workflow_chain(context, hallucination_error=True, with_evaluation=True)


@given("use case 模块与 5-7 基线资产已加载")
def given_use_case_module_and_baseline_assets(context: dict[str, Any]) -> None:
    """模块加载 + 5-7 基线文件文本读取（断言更新检查的数据源）。"""
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

    context["RunAgentWorkflowUseCase"] = RunAgentWorkflowUseCase
    context["baseline_acceptance_text"] = (REPO_ROOT / "tests" / "acceptance" / "test_acceptance_phoenix_tracer.py").read_text(
        encoding="utf-8"
    )
    context["baseline_arch_text"] = (REPO_ROOT / "tests" / "unit" / "architecture" / "test_arch_phoenix_tracer.py").read_text(
        encoding="utf-8"
    )


@when("调用 RunAgentWorkflowUseCase.execute 执行六阶段工作流")
def when_execute_six_phase_workflow(context: dict[str, Any]) -> None:
    """工作流执行（评估块在 execute 末尾触发——异常捕获存 caught）。"""
    _run_workflow(context)


@then("agent_execution 根 span 三键真值断言通过（幻觉 0.2 / 相关性 0.0 / 校准 0.55）")
def then_root_span_three_keys_truth_values(context: dict[str, Any]) -> None:
    """三键真值断言（R3 钦定精确三元组：h=0.2/cr=0.0/pred=0.85 → actual=0.4/ca=0.55）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    root = _get_root_span(context)
    attrs = root.attributes
    assert attrs[SpanAttributeKeys.EVAL_HALLUCINATION_SCORE] == 0.2
    assert attrs[SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE] == 0.0
    assert attrs[SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY] == 0.55
    # overall 可派生性（同式表达式——浮点实算非字面量）
    from src.application.ports.agent_evaluation import (
        CONFIDENCE_ACCURACY_WEIGHT,
        CONTEXT_RELEVANCE_WEIGHT,
        HALLUCINATION_WEIGHT,
    )

    expected_overall = (
        (1.0 - attrs[SpanAttributeKeys.EVAL_HALLUCINATION_SCORE]) * HALLUCINATION_WEIGHT
        + attrs[SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE] * CONTEXT_RELEVANCE_WEIGHT
        + attrs[SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY] * CONFIDENCE_ACCURACY_WEIGHT
    )
    actual_quality = (1.0 - 0.2) * 0.5 + 0.0 * 0.5
    expected_ca = 1.0 - min(abs(0.85 - actual_quality), 1.0)
    assert attrs[SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY] == expected_ca
    assert expected_overall == pytest.approx(0.4575)


@then("三键经 SpanAttributeKeys 常量写入（键字符串逐字对照）")
def then_three_keys_written_via_constants(context: dict[str, Any]) -> None:
    """键字符串逐字断言（5.7 契约兑现锚——零改动键表）。"""
    root = _get_root_span(context)
    attrs = root.attributes
    assert "eval.hallucination_score" in attrs
    assert "eval.context_relevance" in attrs
    assert "eval.confidence_accuracy" in attrs
    # overall 不写 span（三键可派生——YAGNI 契约）
    overall_like = [k for k in attrs if "overall" in k.lower()]
    assert not overall_like, f"overall 不应写 span: {overall_like}"


@then("工作流返回值与评估块零耦合")
def then_workflow_result_zero_coupling(context: dict[str, Any]) -> None:
    """返回值零耦合断言（result 原样返回——评估不改写工作流结果）。"""
    result = context.get("result")
    assert context.get("caught") is None, f"主链不应因评估失败中断: {context.get('caught')}"
    assert result is not None
    assert result.workflow_status == "completed"
    assert result.evidence.confidence == 0.85


@then("主链正常返回 result（工作流断言全绿）")
def then_main_chain_returns_normally(context: dict[str, Any]) -> None:
    """降级路径主链正常（AgentEvaluationError 被降级 catch——可观测附加面哲学）。"""
    result = context.get("result")
    assert context.get("caught") is None, f"评估失败应降级不阻断主链: {context.get('caught')}"
    assert result is not None
    assert result.workflow_status == "completed"
    assert result.evidence.confidence == 0.85


@then("span 三键缺席断言通过")
def then_span_three_keys_absent(context: dict[str, Any]) -> None:
    """降级时三键缺席（不写哨兵值——0.0 可能是合法幻觉分，OD-2[5.7] 同款论证）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    root = _get_root_span(context)
    attrs = root.attributes
    assert SpanAttributeKeys.EVAL_HALLUCINATION_SCORE not in attrs
    assert SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE not in attrs
    assert SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY not in attrs


@then("评估降级 warning 日志已记录")
def then_degradation_warning_logged(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    """降级 warning 断言（caplog——评估降级可见性 MVP 面）。"""
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "评估降级" in r.getMessage()]
    assert warnings, f"应记录评估降级 warning 日志，实际: {[r.getMessage() for r in caplog.records]}"


@then("MVP 十属性不受影响")
def then_mvp_ten_attributes_intact(context: dict[str, Any]) -> None:
    """降级不伤既有属性块（十属性全在位——回归锚）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    root = _get_root_span(context)
    attrs = root.attributes
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
        assert key in attrs, f"降级不应伤 MVP 属性: {key}"


@when("检查构造签名六依赖清单与 None 默认路径")
def when_check_signature_and_none_path(context: dict[str, Any]) -> None:
    """六依赖签名检查 + None 默认路径链装配执行（五参构造——向后兼容）。"""
    import inspect

    use_case_cls = context["RunAgentWorkflowUseCase"]
    params = list(inspect.signature(use_case_cls.__init__).parameters)[1:]
    context["signature_params"] = params
    context["signature_default"] = inspect.signature(use_case_cls.__init__).parameters["evaluation_harness"].default

    _enable_test_tracing(context)
    _assemble_evaluation_workflow_chain(context, with_evaluation=False)
    _run_workflow(context)


@then("第六参数 evaluation_harness 默认 None 且签名清单断言通过")
def then_sixth_param_default_none(context: dict[str, Any]) -> None:
    """签名断言（六依赖清单 + 第六参数默认 None——存量五参调用零破坏）。"""
    assert context["signature_params"] == [
        "agent_repository",
        "agent_profile_use_case",
        "agent_engine",
        "agent_workflow_service",
        "isolation_guard",
        "evaluation_harness",
    ], f"构造签名应为六依赖: {context['signature_params']}"
    assert context["signature_default"] is None


@then("None 默认路径行为与 5-7 基线一致（三键缺席 + 十属性在位）")
def then_none_path_matches_baseline(context: dict[str, Any]) -> None:
    """None 路径回归锚（评估块整体跳过——行为与 5-3/5-7 完全一致）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    assert context.get("caught") is None
    result = context.get("result")
    assert result is not None and result.workflow_status == "completed"
    root = _get_root_span(context)
    attrs = root.attributes
    for key in (
        SpanAttributeKeys.EVAL_HALLUCINATION_SCORE,
        SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE,
        SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY,
    ):
        assert key not in attrs, f"None 默认路径三键应缺席: {key}"
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
        assert key in attrs, f"None 路径 MVP 十属性应在位: {key}"


@then("5-7 断言更新后基线断言通过（六依赖基线对照）")
def then_baseline_assets_updated(context: dict[str, Any]) -> None:
    """5-7 资产同步 ×2 在位断言（AC-4.3 构造签名基线 + _USE_CASE_INIT_PARAMS 常量）。"""
    acceptance_text = context["baseline_acceptance_text"]
    arch_text = context["baseline_arch_text"]
    # ① 5-7 验收 AC-4.3 use_case_params 基线更新（五依赖 → 六依赖）——CR1-F13 清单行锚
    assert '"evaluation_harness",  # Story 5.8 第六可选依赖' in acceptance_text, "5-7 验收基线应含六依赖清单行"
    # ② 5-7 架构验证器 _USE_CASE_INIT_PARAMS 常量更新（五依赖 → 六依赖）——CR1-F13 清单行锚
    assert '"evaluation_harness",  # Story 5.8 第六可选依赖' in arch_text, "_USE_CASE_INIT_PARAMS 应含六依赖清单行"


# ===================================================================
# AC-4: 端口接线、架构合规与组合根注册（静态 + 接线）
# ===================================================================


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-4.1 - 组合根双端口接线与 use case 注入",
)
def test_ac_4_1_composition_root_wiring_and_use_case_injection(context: dict[str, Any]) -> None:
    """AC-4.1: 双端口 resolve 四件 + use case lambda 第六依赖注入 + REQUIRED_METHODS。"""


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-4.2 - 架构静态扫描（白名单/domain 收窄/主链静态锚）",
)
def test_ac_4_2_architecture_static_scan(context: dict[str, Any]) -> None:
    """AC-4.2: 轻量 AST 扫描与符号 grep（白名单/收窄/零实例化/静态锚/配置零改动）。"""


@given("UDMR 云端环境变量已清理")
def given_udmr_cloud_env_cleaned(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """UDMR_CLOUD_* 全段清理（R2-F1：glob 写法无效——按前缀循环逐名 delenv）。

    UDMR 云端 env 半配置态（MODEL 已设且 API_TYPE=anthropic 且缺 MAX_TOKENS 等）
    会使 UDMRConfig.from_env() 抛 101 → 注册工厂降级 → 接线断言环境依赖性红。
    """
    import os

    for key in [k for k in os.environ if k.startswith("UDMR_CLOUD_")]:
        monkeypatch.delenv(key, raising=False)


@when("resolve 双端口与 use case 实例")
def when_resolve_ports_and_use_case(context: dict[str, Any]) -> None:
    """组合根 resolve（双端口 + use case——bootstrap 经 tests/conftest session 闩）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    context["resolver_registry"] = resolver
    context["agent_evaluation_instance"] = resolver.resolve("agent_evaluation")
    context["model_resolver_instance"] = resolver.resolve("evaluation_model_resolver")
    context["use_case_instance"] = resolver.resolve("agent_workflow_use_case")


@then("agent_evaluation 四件断言通过（可达与 isinstance 与 PortSpec 元数据与 SINGLETON）")
def then_agent_evaluation_four_assertions(context: dict[str, Any]) -> None:
    """四件断言：可达 + isinstance 端口 + PortSpec 元数据 + SINGLETON。"""
    from src.application.ports.agent_evaluation import AgentEvaluationPort
    from src.domain.ports.registry import Lifetime, _global_registry

    instance = context["agent_evaluation_instance"]
    assert instance is not None, "resolve('agent_evaluation') 应可达"
    assert isinstance(instance, AgentEvaluationPort), f"应实现 AgentEvaluationPort: {type(instance)}"
    spec = _global_registry.get("agent_evaluation")
    assert spec is not None, "注册表应有 agent_evaluation 条目"
    assert spec.version == "v1.0.0"
    assert spec.module == "src.application.services.evaluation_harness"
    assert spec.lifetime == Lifetime.SINGLETON
    assert spec.owner == "platform"
    assert spec.tags == ("agent", "evaluation", "observability")


@then("evaluation_model_resolver 四件断言通过")
def then_model_resolver_four_assertions(context: dict[str, Any]) -> None:
    """四件断言：可达 + isinstance 端口 + PortSpec 元数据 + SINGLETON。"""
    from src.application.ports.agent_evaluation import EvaluationModelResolverPort
    from src.domain.ports.registry import Lifetime, _global_registry

    instance = context["model_resolver_instance"]
    assert instance is not None, "resolve('evaluation_model_resolver') 应可达"
    assert isinstance(instance, EvaluationModelResolverPort), f"应实现端口: {type(instance)}"
    spec = _global_registry.get("evaluation_model_resolver")
    assert spec is not None
    assert spec.version == "v1.0.0"
    assert spec.module == "src.infrastructure.routing.udmr_evaluation_model_resolver"
    assert spec.lifetime == Lifetime.SINGLETON
    assert spec.owner == "platform"
    assert spec.tags == ("agent", "evaluation", "udmr")


@then("use case 第六依赖注入可达（_evaluation_harness 非 None 且 isinstance 端口）")
def then_use_case_sixth_dependency_wired(context: dict[str, Any]) -> None:
    """接线可达性（resolve_optional 注入——lambda 更新随 Task 3 循环 B 落地）。"""
    from src.application.ports.agent_evaluation import AgentEvaluationPort

    use_case = context["use_case_instance"]
    harness = getattr(use_case, "_evaluation_harness", None)
    assert harness is not None, "use case 第六依赖应注入非 None（resolve_optional 接线）"
    assert isinstance(harness, AgentEvaluationPort)


@then("契约测试 11 维度断言基础齐备（REQUIRED_METHODS callable）")
def then_required_methods_callable(context: dict[str, Any]) -> None:
    """端口方法 callable 断言（11 维度全量归 tests/contracts 双文件承载）。"""
    for instance, methods in (
        (context["agent_evaluation_instance"], ("evaluate",)),
        (context["model_resolver_instance"], ("resolve_config",)),
    ):
        for method in methods:
            assert hasattr(instance, method), f"{type(instance).__name__} 应有 {method}"
            assert callable(getattr(instance, method)), f"{method} 应 callable"


@given("Story 5.8 交付文件已存在")
def given_story_delivery_files_exist(context: dict[str, Any]) -> None:
    """交付文件前置检查（缺失即红——静态扫描的数据源）。"""
    targets = [
        SRC_DIR / "application" / "ports" / "agent_evaluation.py",
        SRC_DIR / "application" / "services" / "evaluation_harness.py",
        SRC_DIR / "application" / "services" / "evaluation_schemas.py",
        SRC_DIR / "application" / "services" / "evaluation_prompts.py",
        SRC_DIR / "infrastructure" / "routing" / "udmr_evaluation_model_resolver.py",
        SRC_DIR / "domain" / "exceptions" / "evaluation_exceptions.py",
    ]
    for path in targets:
        assert path.is_file(), f"交付文件缺失: {path}"


@when("执行轻量 AST 扫描与符号 grep")
def when_run_static_scan(context: dict[str, Any]) -> None:
    """扫描执行（结果存 context——AST 解析 + 符号收集）。"""
    import ast

    scan_targets = {
        "agent_evaluation": SRC_DIR / "application" / "ports" / "agent_evaluation.py",
        "evaluation_harness": SRC_DIR / "application" / "services" / "evaluation_harness.py",
        "evaluation_schemas": SRC_DIR / "application" / "services" / "evaluation_schemas.py",
        "evaluation_prompts": SRC_DIR / "application" / "services" / "evaluation_prompts.py",
        "run_agent_workflow": SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py",
        "ports_init": SRC_DIR / "application" / "ports" / "__init__.py",
    }
    context["scan_trees"] = {name: ast.parse(p.read_text(encoding="utf-8")) for name, p in scan_targets.items()}
    context["use_case_source"] = scan_targets["run_agent_workflow"].read_text(encoding="utf-8")


@then("application 触碰文件第三方白名单断言通过（仅 pydantic 与 opentelemetry）")
def then_application_whitelist(context: dict[str, Any]) -> None:
    """验证器 A 轻量版：触碰文件第三方 import 白名单（pydantic/opentelemetry 允许）。"""
    import ast
    import sys

    allowed_third_party = {"pydantic", "opentelemetry"}
    forbidden = {
        "fastapi",
        "sqlalchemy",
        "redis",
        "typer",
        "langgraph",
        "prefect",
        "yaml",
        "minio",
        "qdrant",
        "neo4j",
        "litellm",
    }
    for name, tree in context["scan_trees"].items():
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        assert modules & forbidden == set(), f"{name} 禁入第三方: {modules & forbidden}"
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib <= allowed_third_party, f"{name} 白名单外第三方: {non_stdlib - allowed_third_party}"


@then("domain 业务域零触碰断言通过（评估符号仅 exceptions 三件）")
def then_domain_zero_touch(context: dict[str, Any]) -> None:
    """验证器 B 轻量版：业务域符号零命中（词边界——RelevanceEvaluationResult 撞名不误伤）
    + AgentEvaluationError 仅 exceptions/ 三件。"""
    import re

    story_symbols = (
        "EvaluationHarness",
        "AgentEvaluationPort",
        "EvaluationModelResolverPort",
        "EvaluationResult",
        "HallucinationEvaluationSchema",
        "EVALUATION_WEIGHTS",
    )
    business_dirs = [
        SRC_DIR / "domain" / "ports",
        SRC_DIR / "domain" / "services",
        SRC_DIR / "domain" / "entities",
        SRC_DIR / "domain" / "value_objects",
        SRC_DIR / "domain" / "events",
    ]
    for directory in business_dirs:
        for py_file in directory.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for symbol in story_symbols:
                pattern = rf"\b{re.escape(symbol)}\b"
                assert not re.search(pattern, source), f"domain 业务域零触碰红线: {py_file} 含 {symbol}"

    exception_hits: list[Path] = []
    for py_file in (SRC_DIR / "domain" / "exceptions").rglob("*.py"):
        if "AgentEvaluationError" in py_file.read_text(encoding="utf-8"):
            exception_hits.append(py_file)
    allowed_exception_files = {
        "evaluation_exceptions.py",
        "_code_ranges.py",
        "__init__.py",
    }
    for hit in exception_hits:
        assert hit.name in allowed_exception_files, f"AgentEvaluationError 应仅在 exceptions 三件内: {hit}"


@then("组合根外零实例化断言通过")
def then_composition_root_only_instantiation(context: dict[str, Any]) -> None:
    """验证器 B 轻量版：src/ 构造点扫描（EvaluationHarness/UdmrEvaluationModelResolver 仅组合根）。"""
    import ast

    for target_class in ("EvaluationHarness", "UdmrEvaluationModelResolver"):
        violations: list[str] = []
        found = False
        for py_file in SRC_DIR.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    callee = node.func
                    name = getattr(callee, "id", None) or getattr(callee, "attr", None)
                    if name == target_class:
                        rel = str(py_file.relative_to(REPO_ROOT))
                        found = True
                        if not rel.startswith("src/composition_root.py"):
                            violations.append(f"{rel}:{node.lineno}")
        assert found, f"组合根应至少一处 {target_class} 实例化（注册 lambda）"
        assert not violations, f"组合根外实例化点: {violations}"


@then("主链评估块静态锚断言通过（evaluate 调用 + 三常量引用 + is_recording 守卫）")
def then_main_chain_static_anchor(context: dict[str, Any]) -> None:
    """验证器 C 轻量版：execute 体内 evaluate 调用 + 三常量 Attribute 引用 + is_recording。"""
    import ast

    tree = context["scan_trees"]["run_agent_workflow"]
    execute_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "execute":
            execute_node = node
    assert execute_node is not None, "应存在 execute 方法"

    source_segment = ast.get_source_segment(context["use_case_source"], execute_node) or ""
    assert ".evaluate(" in source_segment, "execute 体内应有 evaluate 调用"
    assert "is_recording" in source_segment, "评估块应有 is_recording 守卫"

    attr_names = {node.attr for node in ast.walk(execute_node) if isinstance(node, ast.Attribute)}
    for constant in ("EVAL_HALLUCINATION_SCORE", "EVAL_CONTEXT_RELEVANCE", "EVAL_CONFIDENCE_ACCURACY"):
        assert constant in attr_names, f"execute 体内应引用 SpanAttributeKeys.{constant}"


@then(".env.example 与 event_channels.yaml 零改动")
def then_env_and_event_channels_untouched(context: dict[str, Any]) -> None:
    """配置零改动断言（评估无新环境变量、无新事件映射——YAGNI 裁定）。"""
    env_content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "AGENT_EVALUATION" not in env_content, ".env.example 不应新增评估开关（YAGNI 裁定）"
    assert "EVALUATION_P95" not in env_content and "EVALUATION_MODEL" not in env_content, "评估常量不应环境变量化"
    channels_content = (REPO_ROOT / "configs" / "event_channels.yaml").read_text(encoding="utf-8")
    # CR1-F14 锚收窄：原 "evaluation" 全文子串对检索域等未来含 evaluation 字样的
    # 事件名会假红——收窄为本 Story 评估面专属符号（agent_evaluation 端口族/
    # 幻觉检测事件化）零新增
    assert "agent_evaluation" not in channels_content.lower(), "评估不经事件总线（本 Story 零新增评估事件）"
    assert "hallucination" not in channels_content.lower(), "幻觉检测不经事件总线（评估是进程内同步面）"


# ===================================================================
# AC-5: 评估延迟 P95<500ms（委托集成计时）
# ===================================================================


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "AC-5.1 - 评估管线 P95 延迟达标",
)
def test_ac_5_1_evaluation_pipeline_p95(context: dict[str, Any]) -> None:
    """AC-5.1: 委托集成计时（P95<0.5s 常量单源 + 正向锚调用计数）。"""


@given("集成计时委托已缓存采样结果")
def given_perf_cache_populated(context: dict[str, Any]) -> None:
    """委托采样（_PERF_CACHE 命中或首次采样——同 xdist_group 同 worker 串行保证）。"""
    from tests.integration.test_integration_agent_evaluation import (
        sample_evaluation_pipeline_perf,
    )

    context["perf_summary"] = _run_async(context["_loop"], sample_evaluation_pipeline_perf())


@when("读取委托缓存的评估管线 P95 值")
def when_read_cached_p95(context: dict[str, Any]) -> None:
    """读取 P95（常量单源 import——验收侧禁双真源）。"""
    from tests.integration.test_integration_agent_evaluation import EVALUATION_P95_LIMIT_SECONDS

    context["p95_seconds"] = context["perf_summary"]["p95_seconds"]
    context["p95_limit"] = EVALUATION_P95_LIMIT_SECONDS
    context["sample_count"] = context["perf_summary"]["sample_count"]
    context["llm_call_count"] = context["perf_summary"]["llm_call_count"]


@then("P95 小于 0.5 秒（常量单源 EVALUATION_P95_LIMIT_SECONDS）")
def then_p95_below_limit(context: dict[str, Any]) -> None:
    """P95 < 0.5s（epics L1794 钦定——Fake LLM 管线口径，网络延迟出栈）。"""
    assert context["p95_limit"] == 0.5
    assert context["p95_seconds"] < context["p95_limit"], (
        f"评估管线 P95 应 < {context['p95_limit']}s，实际 {context['p95_seconds']}s"
    )


@then("正向锚断言通过（structured_generate 调用计数等于采样总数）")
def then_positive_anchor_call_count(context: dict[str, Any]) -> None:
    """正向锚（防静默降级假绿——评估调用真实发生）。"""
    warmup_and_samples = context["sample_count"]
    assert context["llm_call_count"] == warmup_and_samples, (
        f"structured_generate 调用计数 {context['llm_call_count']} 应 == 采样总数 {warmup_and_samples}"
    )


# ===================================================================
# 收尾: 完成清单逐项确认
# ===================================================================


@scenario(
    "test_acceptance_agent_evaluation.feature",
    "收尾 - 完成清单逐项确认",
)
def test_completion_checklist(context: dict[str, Any]) -> None:
    """收尾：src 新建六 + 修改六 + tests 四目录 + 5-7 更新 ×2 + 配置零改动。"""


@given("Story 5.8 开发已完成")
def given_story_development_complete(context: dict[str, Any]) -> None:
    """开发完成前置（清单数据源装配）。"""
    context["checklist_root"] = REPO_ROOT


@when("检查 src 与 tests 完成清单")
def when_check_completion_lists(context: dict[str, Any]) -> None:
    """清单检查执行（文件存在性 + 5-7 更新内容 + 配置零改动）。"""
    context["src_new_files"] = [
        "src/application/ports/agent_evaluation.py",
        "src/application/services/evaluation_harness.py",
        "src/application/services/evaluation_schemas.py",
        "src/application/services/evaluation_prompts.py",
        "src/infrastructure/routing/udmr_evaluation_model_resolver.py",
        "src/domain/exceptions/evaluation_exceptions.py",
    ]
    context["src_modified_files"] = [
        "src/application/use_cases/run_agent_workflow.py",
        "src/application/ports/__init__.py",
        "src/domain/exceptions/_code_ranges.py",
        "src/domain/exceptions/__init__.py",
        "src/interfaces/api/exception_handlers.py",
        "src/composition_root.py",
    ]
    context["test_files"] = [
        "tests/unit/domain/exceptions/test_evaluation_exceptions.py",
        "tests/unit/application/test_agent_evaluation_model.py",
        "tests/unit/application/services/test_evaluation_harness.py",
        "tests/unit/infrastructure/routing/test_udmr_evaluation_model_resolver.py",
        "tests/unit/architecture/test_arch_evaluation.py",
        "tests/contracts/test_port_contract_agent_evaluation.py",
        "tests/contracts/test_port_contract_evaluation_model_resolver.py",
        "tests/integration/test_integration_agent_evaluation.py",
        "tests/acceptance/test_acceptance_agent_evaluation.feature",
        "tests/acceptance/test_acceptance_agent_evaluation.py",
    ]


@then("src 新建六文件与修改六文件逐项存在")
def then_src_files_present(context: dict[str, Any]) -> None:
    """src 清单断言（missing 断言形态）。"""
    for relative in context["src_new_files"] + context["src_modified_files"]:
        assert (REPO_ROOT / relative).is_file(), f"src 交付文件缺失: {relative}"


@then("tests 四目录清单逐项存在")
def then_test_files_present(context: dict[str, Any]) -> None:
    """tests 清单断言（unit/contracts/integration/acceptance 四目录 + use case 追加面）。"""
    for relative in context["test_files"]:
        assert (REPO_ROOT / relative).is_file(), f"tests 交付文件缺失: {relative}"
    # 主链评估块单测（追加于 5-3 存量文件）
    use_case_test_path = REPO_ROOT / "tests" / "unit" / "application" / "use_cases" / "test_run_agent_workflow.py"
    use_case_tests = use_case_test_path.read_text(encoding="utf-8")
    assert "evaluation_harness" in use_case_tests, "test_run_agent_workflow.py 应含评估块追加用例"


@then("5-7 断言更新文件两处已更新")
def then_5_7_assets_updated(context: dict[str, Any]) -> None:
    """5-7 资产同步 ×2 断言（验收 AC-4.3 + 架构 _USE_CASE_INIT_PARAMS）。

    CR1-F13 锚升级：裸 "evaluation_harness" 全文子串弱锚（注释提及即绿）——
    改锚参数清单行片段（含资产同步注释的六依赖清单行）；主防线是 5-7 自身
    的 inspect.signature 断言与验证器 C 基线（本断言是跨文件回执级注记）。
    """
    acceptance_text = (REPO_ROOT / "tests" / "acceptance" / "test_acceptance_phoenix_tracer.py").read_text(encoding="utf-8")
    arch_text = (REPO_ROOT / "tests" / "unit" / "architecture" / "test_arch_phoenix_tracer.py").read_text(encoding="utf-8")
    assert '"evaluation_harness",  # Story 5.8 第六可选依赖' in acceptance_text, "5-7 验收 AC-4.3 基线应含六依赖清单行"
    assert '"evaluation_harness",  # Story 5.8 第六可选依赖' in arch_text, "5-7 架构 _USE_CASE_INIT_PARAMS 应含六依赖清单行"
