"""PhoenixTracer 全链路追踪验收测试（Story 5.7 — FR-EV-01 追踪面）

R6 骨架：@scenario 多行字面量显式绑定 + context dict fixture + _run_async 同循环
调度 + 延迟 import 纪律 + 禁 then-pass 占位；Gherkin 中文关键字取 PG 模板形态。

外部服务门控 = 零外部服务（span 面进程内自包含）：链级场景 Fake LLM 手工装配
（外部 LLM API 不可验收强依赖——5-3 验收先例豁免面仅 llm_client 一项，六阶段
服务/图/用例/守卫链全真实，隔离仓储以零 IO stub 注入——_StubIsolationSwitchLogRepository
同先例形态）。

14 场景三属性分档表（Task 0.6 定稿——依赖面/全局状态面/清理义务）:
- AC-1.1: 零外部服务 / initialize×2（注入 set + 自建 set）/ 双复位（autouse 兜底）
- AC-1.2: 零外部服务 / initialize 注入 set×1 + enabled=false 不 set / 双复位
- AC-1.3: 零外部服务 / 零（纯构造 + env monkeypatch）/ monkeypatch 自动复原
- AC-2.1: 零外部服务（Fake LLM）/ initialize set 全局 / 双复位 + exporter 清空
- AC-2.2: 零外部服务（Fake LLM）/ initialize set 全局 / 双复位 + exporter 清空
- AC-2.3: 零外部服务（Fake LLM）/ 不 initialize（proxy 态前提——前置双复位）/ 双复位
- AC-3.1: 零外部服务（Fake LLM）/ initialize set 全局 / 双复位 + exporter 清空
- AC-3.2: 零外部服务 / 零（组件级注入通道不 initialize）/ exporter 清空
- AC-3.3: 零外部服务（Fake LLM）/ initialize set + 中途双复位再跑 NoOp / 双复位
- AC-4.1: resolve 组合根（session 已引导）/ 直构 initialize set 全局 + 负路径不 set / 双复位 + env 复原
- AC-4.2: 静态扫描（AST）/ 零 / 无
- AC-4.3: 静态扫描（inspect）/ 零 / 无
- AC-5.1: 委托集成计时缓存 / 零（集成侧管理）/ 集成侧承担
- AC-5.2: 委托集成计时缓存 / 零（集成侧块序管理）/ 集成侧承担

OTel 全局状态隔离 SSOT（见 5-7 故事测试隔离约束节）：
- 链级场景统一通道 = 场景级新 TracerProvider + SimpleSpanProcessor +
  InMemorySpanExporter 经 PhoenixTracer(config, tracer_provider=注入).initialize()
  （initialize 履行全局 set 唯一职责——测试不直接调 trace.set_tracer_provider）；
- 文件级 function-scope autouse 双复位兜底（R3-2——纪律升级为机制，兼修同进程
  先行模块泄漏与场景间交叉污染）；
- 组件级场景（AC-1.3/AC-3.2）纯构造注入通道零全局触碰。

Run with:
    poetry run pytest tests/acceptance/test_acceptance_phoenix_tracer.py -v
"""

from __future__ import annotations

import asyncio
import inspect
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
    pytest.mark.xdist_group("phoenix-tracer-perf"),
]


@pytest.fixture(scope="module")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """模块级事件循环（13 验收文件惯例——BDD 步骤 run_until_complete 专用，禁 @pytest.mark.asyncio）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _otel_global_state_isolation() -> Generator[None, None, None]:
    """OTel 全局状态 function 级双复位兜底（R3-2——纪律升级为机制）。

    每场景前置 + teardown 双复位（变量复位 + Once 闩锁重建——锁定的 OTel 1.44.0
    单复位不恢复 re-set 能力）：兼修已知同进程泄漏源（test_event_monitoring::
    TestInitTracing 前置 reset 无 teardown）与场景间交叉污染。实现未交付（Task 0
    红阶段）时零阻断——场景步骤的延迟 import 承载红。
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
# 装配 helpers（延迟 import 纪律——本 Story 新模块一律函数体内 import）
# ===================================================================


def _make_phoenix_config(**overrides: Any) -> Any:
    """链级/组件级测试配置（enabled 全采样——endpoint 生产形态仅装配不外联）。"""
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
    """组件级注入通道材料：新 TracerProvider + Simple + InMemory（零全局触碰）。"""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _enable_test_tracing(context: dict[str, Any]) -> None:
    """链级统一通道：注入 provider 经 initialize 履行全局 set（唯一职责）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    provider, exporter = _make_injectable_components()
    tracer = PhoenixTracer(config=_make_phoenix_config(), tracer_provider=provider)
    assert tracer.initialize() is True, "注入通道 initialize 应返回 True（全局 set 成功）"
    context["_provider"] = provider
    context["_exporter"] = exporter
    context["_phoenix_tracer"] = tracer


def _reset_global_tracing() -> None:
    """双复位全局（中途态切换用——AC-1.1/AC-3.3 场景内 NoOp 转换）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    PhoenixTracer.reset_for_testing()


def _is_proxy_global() -> bool:
    """全局 provider 未 set 判据（proxy 态——OTel 1.44 公开导出类 ProxyTracerProvider）。"""
    import opentelemetry.trace as otel_trace
    from opentelemetry.trace import ProxyTracerProvider

    return isinstance(otel_trace.get_tracer_provider(), ProxyTracerProvider)


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
    """记录发布事件的发布器（内存替身发布面——5-3 集成同款形态）。"""

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
    """记录 ExecutionContext 的工具执行服务包装（duck-typing 委托——AC-3.3 贯通断言锚）。"""

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


def _make_fake_llm(
    *,
    verify_mode: str = "always_pass",
    plan_tool_names: tuple[str, ...] = ("PESTEL 分析",),
    delay_sec: float = 0.0,
    error_schema: Any = None,
) -> Any:
    """六阶段 Fake LLM 端口替身（外部 SaaS 豁免面——5-3 验收先例照抄 + 异常注入扩展）。

    分派键 = response_schema 身份（六阶段 Schema 两两不同是前提）；verify 序列模式
    verify_mode（always_pass / fail_once）；error_schema 指定 Schema 身份时抛
    LLMAPIError（AC-2.2 注入面——LLM 族经 _structured_call 包装 444）。

    Args:
        verify_mode: always_pass / fail_once（序列 Fake——5-3 R2-F8 形态）
        plan_tool_names: 规划产出的工具步名（空 = 零工具步；须在 CEO allowed_tools 白名单内）
        delay_sec: 每调用模拟延迟（秒）
        error_schema: 注入 LLMAPIError 的 Schema 身份（None = 不注入）

    Returns:
        AsyncMock(spec=LLMClientPort) 替身
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
            raise LLMAPIError(message="模拟 LLM API 传输故障（验收注入）")
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
    """工具执行面替身边界（隔离约束①——5-3 集成同款）：真实服务链 + Fake llm + 沙箱替身。"""
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


def _assemble_workflow_chain(
    context: dict[str, Any],
    *,
    verify_mode: str = "fail_once",
    plan_tool_names: tuple[str, ...] = ("PESTEL 分析",),
    delay_sec: float = 0.0,
    error_schema: Any = None,
) -> None:
    """自包含手工装配六阶段全链（零外部服务——真实服务链 + Fake LLM 豁免面）。

    装配面：真实 Agent 实体锚点 / 真实 IsolationManagementService + IsolationGuardService
    （隔离仓储以零 IO stub 注入——5-3 验收 _Stub 同先例）/ 真实 LoadAgentProfileUseCase
    （resolve 无状态实例——本地静态档案）/ 真实 AgentWorkflowService + LangGraphEngine +
    RunAgentWorkflowUseCase（六阶段服务/图/用例全真实）/ Fake LLM（唯一豁免替身）。
    """
    from src.application.services.agent_workflow_service import AgentWorkflowService
    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
    from src.domain.entities.agent import Agent
    from src.domain.ports.resolver import resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

    loop = context["_loop"]
    import uuid as uuid_module

    from src.domain.entities.agent import AgentRole

    agent = Agent(agent_id=uuid_module.uuid4(), role=AgentRole.CEO, name="CEO Agent")
    context["agent"] = agent
    context["task"] = "分析新能源汽车行业进入战略并给出三层次建议"

    # duck-typing 替身经 Any 注入（结构满足调用面——5-6 验收 _Stub 同惯例）
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
        verify_mode=verify_mode,
        plan_tool_names=plan_tool_names,
        delay_sec=delay_sec,
        error_schema=error_schema,
    )
    context["fake_llm"] = fake_llm
    recording_tool_service = _RecordingToolExecutionService(_build_tool_execution_service(fake_llm))
    context["tool_service"] = recording_tool_service

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

    # 档案材料（无状态 loader/selector 本地静态加载——零外部服务；真实
    # LoadAgentProfileUseCase 内含 443 守卫绑定 Redis 仓储，stub Agent 过不了
    # 守卫——5-3 验收 _assemble_workflow_chain 同款手工装配形态）
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
    context["profile_use_case"] = profile_use_case
    context["profile_result"] = profile_result

    context["use_case"] = RunAgentWorkflowUseCase(
        agent_repository=stub_agent_repo,
        agent_profile_use_case=profile_use_case,
        agent_engine=context["engine"],
        agent_workflow_service=service,
        isolation_guard=guard,
    )


def _make_registry() -> Any:
    """手工组装工具注册服务（InMemoryToolRepository + register_all——5-3 验收同款）。"""
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    return registry


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
# AC-1: PhoenixTracer 实例化与配置（组件级——零服务依赖）
# ===================================================================


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-1.1 - PhoenixTracer 实例化与 project_name 映射（双路径拆分）",
)
def test_ac_1_1_phoenix_tracer_project_name_mapping(context: dict[str, Any]) -> None:
    """AC-1.1: 注入路径 initialize 挂载 + 自建路径 Resource service.name/sampler。"""


@given("PhoenixTracer 以注入路径构造（测试 provider 与内存导出器）")
def given_phoenix_tracer_injected_path(context: dict[str, Any]) -> None:
    """注入路径：注入 provider + InMemory 导出器构造（R2-1 双源解析注入通道）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    provider, exporter = _make_injectable_components()
    context["_provider"] = provider
    context["_exporter"] = exporter
    context["_phoenix_tracer"] = PhoenixTracer(config=_make_phoenix_config(), tracer_provider=provider)


@when("执行 initialize 启用追踪")
def when_initialize_tracing(context: dict[str, Any]) -> None:
    """initialize（注入路径 set 全局 / 自建路径构造 provider 后 set）。"""
    result = context["_phoenix_tracer"].initialize()
    context["initialize_result"] = result


@then("全局 provider 为注入实例且 create_span 产出真 span 到注入导出器")
def then_injected_path_global_and_span(context: dict[str, Any]) -> None:
    """注入路径断言：全局 == 注入实例 + span 可观测（initialize 挂载语义）。"""
    import opentelemetry.trace as otel_trace

    assert context["initialize_result"] is True
    assert otel_trace.get_tracer_provider() is context["_provider"]
    tracer = context["_phoenix_tracer"]
    with tracer.create_span("inject-probe") as handle:
        assert handle is not None, "注入通道 create_span 应产真 span（R2-1 双源解析）"
    spans = context["_exporter"].get_finished_spans()
    assert [s.name for s in spans] == ["inject-probe"]


@given('双复位全局后以自建路径构造 PhoenixTracer（配置 project_name 为 "sisys-agent"）')
def given_phoenix_tracer_selfbuilt_path(context: dict[str, Any]) -> None:
    """自建路径：双复位全局（注入路径已 set——中途态切换）后未注入构造。"""
    _reset_global_tracing()
    assert _is_proxy_global(), "双复位后全局应回 proxy 态"
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    context.pop("_exporter", None)
    context["_phoenix_tracer"] = PhoenixTracer(config=_make_phoenix_config())


@then('自建 provider 的 Resource 携带 service.name == "sisys-agent"')
def then_selfbuilt_resource_service_name(context: dict[str, Any]) -> None:
    """自建路径断言：全局 provider（== 自建实例）的 Resource service.name（OD-1 映射）。"""
    assert context["initialize_result"] is True
    import opentelemetry.trace as otel_trace

    provider: Any = otel_trace.get_tracer_provider()  # SDK 实现面属性（API 类型未声明）
    assert provider.resource.attributes["service.name"] == "sisys-agent"


@then("sampler 采样率与配置一致")
def then_selfbuilt_sampler_ratio(context: dict[str, Any]) -> None:
    """自建路径断言：TraceIdRatioBased 采样率 == 配置值（1.0 全采样）。"""
    import opentelemetry.trace as otel_trace
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

    provider: Any = otel_trace.get_tracer_provider()  # SDK 实现面属性（API 类型未声明）
    assert isinstance(provider.sampler, TraceIdRatioBased)
    assert provider.sampler.rate == 1.0


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-1.2 - initialize 幂等与 enabled=false 不装配",
)
def test_ac_1_2_initialize_idempotent_and_disabled(context: dict[str, Any]) -> None:
    """AC-1.2: 实例闩静默幂等 + enabled=false 不装配 + 无 tracer 来源降级 None。"""


@given("PhoenixTracer 以注入测试 provider 构造且已 initialize")
def given_phoenix_tracer_initialized_injected(context: dict[str, Any]) -> None:
    """幂等前提：注入构造 + 首次 initialize（autouse 前置已双复位）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    provider, exporter = _make_injectable_components()
    context["_provider"] = provider
    context["_exporter"] = exporter
    tracer = PhoenixTracer(config=_make_phoenix_config(), tracer_provider=provider)
    assert tracer.initialize() is True
    context["_phoenix_tracer"] = tracer


@when("同实例再次调用 initialize")
def when_initialize_again_same_instance(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    """同实例二次 initialize（实例闩——R2-9 静默语义）。"""
    with caplog.at_level(logging.WARNING):
        context["initialize_result"] = context["_phoenix_tracer"].initialize()
    context["second_init_warnings"] = [r for r in caplog.records if r.levelno >= logging.WARNING]


@then("返回 True 且单次 create_span 后导出器恰收 1 个 span（无重复装配）")
def then_idempotent_single_span(context: dict[str, Any]) -> None:
    """幂等行为断言：两次 initialize → 1 span → exporter 恰收 1（重复装配会收 2）。"""
    assert context["initialize_result"] is True
    tracer = context["_phoenix_tracer"]
    with tracer.create_span("idempotent-probe") as handle:
        assert handle is not None
    spans = context["_exporter"].get_finished_spans()
    assert [s.name for s in spans] == ["idempotent-probe"], f"应恰收 1 span，实际 {len(spans)}"


@then("同实例再入不产生告警日志（实例闩静默语义）")
def then_same_instance_no_warning(context: dict[str, Any]) -> None:
    """实例闩判据：同实例再入静默（无 warning——外来 set 检测不触发）。"""
    assert context["second_init_warnings"] == [], f"同实例再入应静默，实际告警: {context['second_init_warnings']}"


@given("enabled 为 false 的 PhoenixTracer 构造（未注入）")
def given_phoenix_tracer_disabled(context: dict[str, Any]) -> None:
    """enabled=false 构造（未注入——NoOp 天然降级形态）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    _reset_global_tracing()
    context["_phoenix_tracer"] = PhoenixTracer(config=_make_phoenix_config(enabled=False))


@when("调用 initialize")
def when_call_initialize(context: dict[str, Any]) -> None:
    """enabled=false 形态 initialize（应返回 False 不装配）。"""
    context["initialize_result"] = context["_phoenix_tracer"].initialize()


@then("返回 False 且全局 provider 保持未装配")
def then_disabled_no_assembly(context: dict[str, Any]) -> None:
    """enabled=false 断言：返回 False + 全局保持 proxy 态（不设全局）。"""

    assert context["initialize_result"] is False
    assert _is_proxy_global()


@then("未注入未 initialize 的实例 create_span 降级 yield None")
def then_no_source_yield_none(context: dict[str, Any]) -> None:
    """降级双态断言：无可用 tracer 来源（未注入且未 initialize）→ yield None。"""
    tracer = context["_phoenix_tracer"]
    with tracer.create_span("noop-probe") as handle:
        assert handle is None, "无 tracer 来源应 yield None（R2-1 双源解析降级判据）"


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-1.3 - PhoenixConfig 101 守卫五场景与 from_env 四变量",
)
def test_ac_1_3_phoenix_config_guards_and_from_env(context: dict[str, Any]) -> None:
    """AC-1.3: 101 守卫五场景三段式 + from_env 四变量矩阵 + fallback 链。"""


@given("PhoenixConfig 构造通道已就绪")
def given_phoenix_config_ready(context: dict[str, Any]) -> None:
    """构造通道就绪（延迟 import 校验模块在位——红阶段 ModuleNotFoundError）。"""
    from src.infrastructure.config.phoenix import PhoenixConfig

    assert PhoenixConfig is not None  # 构造通道锚（红阶段 ModuleNotFoundError 承载红）


@when("分别注入五类非法输入构造配置")
def when_five_invalid_config_inputs(context: dict[str, Any]) -> None:
    """101 守卫五场景：enabled 非 bool / project_name 空白 / endpoint 非法前缀 /
    sampling_ratio 非数值 / sampling_ratio 越界（0 与 1.5）。"""
    from src.infrastructure.config.phoenix import PhoenixConfig

    cases: list[tuple[str, dict[str, Any]]] = [
        ("enabled", {"enabled": "true"}),
        ("project_name", {"project_name": "   "}),
        ("endpoint", {"endpoint": "ftp://collector:4317"}),
        ("sampling_ratio", {"sampling_ratio": "high"}),
        ("sampling_ratio", {"sampling_ratio": 1.5}),
    ]
    context["guard_cases"] = [(field, overrides) for field, overrides in cases]
    # 零界合法性自证（守卫不误伤）：1.0 全采样合法
    PhoenixConfig(sampling_ratio=1.0)


@then("每类抛 ConfigurationError 101 且 context 携带字段名与实际值")
def then_guard_cases_raise_101(context: dict[str, Any]) -> None:
    """三段式断言：isinstance → code == EXCEPTION_101 → context 含字段名。"""
    from src.domain.exceptions import ConfigurationError

    for field, overrides in context["guard_cases"]:
        try:
            _make_phoenix_config(**overrides)
        except ConfigurationError as error:
            assert error.code == "EXCEPTION_101", f"{field} 守卫应 101，实际 {error.code}"
            assert field in error.context, f"{field} 守卫 context 应携带字段名，实际 {error.context}"
        else:
            pytest.fail(f"非法输入 {field}={overrides} 应抛 ConfigurationError 101")


@when("解析环境四变量（含 OTEL_EXPORTER_OTLP_ENDPOINT fallback 链与空串视为未设）")
def when_from_env_matrix(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """from_env 矩阵采样：默认值 / 全覆盖 / OTEL fallback / 空串视为未设 / bool 三态。"""
    from src.infrastructure.config.phoenix import PhoenixConfig

    for var in ("PHOENIX_TRACING_ENABLED", "PHOENIX_OTLP_ENDPOINT", "PHOENIX_PROJECT_NAME", "PHOENIX_TRACES_SAMPLER_ARG"):
        monkeypatch.delenv(var, raising=False)

    default_config = PhoenixConfig.from_env()
    assert default_config.enabled is False
    assert default_config.endpoint == "http://localhost:4317"
    assert default_config.project_name == "sisys-agent"
    assert default_config.sampling_ratio == 1.0

    monkeypatch.setenv("PHOENIX_TRACING_ENABLED", "true")
    monkeypatch.setenv("PHOENIX_OTLP_ENDPOINT", "http://phx.example:4317")
    monkeypatch.setenv("PHOENIX_PROJECT_NAME", "proj-x")
    monkeypatch.setenv("PHOENIX_TRACES_SAMPLER_ARG", "0.5")
    override_config = PhoenixConfig.from_env()

    monkeypatch.setenv("PHOENIX_TRACING_ENABLED", "1")
    assert PhoenixConfig.from_env().enabled is True, "bool 三态：'1' 应解析为 True"
    monkeypatch.setenv("PHOENIX_TRACING_ENABLED", "yes")
    assert PhoenixConfig.from_env().enabled is True, "bool 三态：'yes' 应解析为 True"
    monkeypatch.setenv("PHOENIX_TRACING_ENABLED", "false")
    assert PhoenixConfig.from_env().enabled is False

    monkeypatch.delenv("PHOENIX_OTLP_ENDPOINT")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-fallback:4317")
    fallback_config = PhoenixConfig.from_env()

    monkeypatch.setenv("PHOENIX_OTLP_ENDPOINT", "")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    empty_config = PhoenixConfig.from_env()

    context["from_env_matrix"] = {
        "override": override_config,
        "fallback": fallback_config,
        "empty": empty_config,
    }


@then("四变量与默认值矩阵及覆盖矩阵逐项一致")
def then_from_env_matrix_values(context: dict[str, Any]) -> None:
    """矩阵断言：覆盖矩阵四值 + fallback 链 + 空串视为未设（不落 101）。"""
    matrix = context["from_env_matrix"]
    assert matrix["override"].enabled is True
    assert matrix["override"].endpoint == "http://phx.example:4317"
    assert matrix["override"].project_name == "proj-x"
    assert matrix["override"].sampling_ratio == 0.5
    assert matrix["fallback"].endpoint == "http://otel-fallback:4317", "未设 PHOENIX_OTLP_ENDPOINT 应 fallback OTEL 变量"
    assert matrix["empty"].endpoint == "http://localhost:4317", "空串视为未设应回默认值（不落 101）"


# ===================================================================
# AC-2: @trace 装饰器自动 span（链级——经 initialize 全局通道）
# ===================================================================


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-2.1 - agent_execution 根 span 与六阶段子 span 树自动创建",
)
def test_ac_2_1_root_span_and_phase_tree(context: dict[str, Any]) -> None:
    """AC-2.1: 根 span + 六阶段子 span 树（fail-once 链九阶段）+ parent 链 + 同源一致。"""


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-2.2 - 异常路径 span ERROR 与 444 包装异常透传",
)
def test_ac_2_2_exception_span_error_and_444(context: dict[str, Any]) -> None:
    """AC-2.2: LLMAPIError → span ERROR + exception 事件 + 444 包装异常透传（零吞异常）。"""


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-2.3 - NoOp 降级零 span 且主链行为等价（观察哨形态）",
)
def test_ac_2_3_noop_zero_span_and_equivalence(context: dict[str, Any]) -> None:
    """AC-2.3: 全局未启用零 span + 观察哨无旁路泄漏 + 主链与 5-3 基线一致（读法丙）。"""


@given("Phoenix 追踪已启用（测试内存导出器）")
def given_phoenix_tracing_enabled(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """链级统一通道：注入 provider 经 initialize 全局 set（R2-10 环境前提钉死）。"""
    monkeypatch.delenv("PHOENIX_TRACING_ENABLED", raising=False)
    _enable_test_tracing(context)


@given("六阶段工作流链已装配（Fake LLM 首轮验证失败）")
def given_workflow_chain_fail_once(context: dict[str, Any]) -> None:
    """fail-once 链装配（九阶段——六名集合可满足前提，R3-9）。"""
    _assemble_workflow_chain(context, verify_mode="fail_once")


@given("六阶段工作流链已装配（Fake LLM 注入 LLMAPIError）")
def given_workflow_chain_llm_error(context: dict[str, Any]) -> None:
    """异常链装配：perceive 阶段 LLM 调用抛 LLMAPIError（LLM 族 → 444 包装）。"""
    from src.application.services.agent_workflow_schemas import PerceptionSchema

    _assemble_workflow_chain(context, verify_mode="always_pass", error_schema=PerceptionSchema)


@given("六阶段工作流链已装配（Fake LLM 规划含工具步）")
def given_workflow_chain_with_tool_step(context: dict[str, Any]) -> None:
    """工具步链装配（plan 产出 PESTEL 工具步——ExecutionContext 构造点前提）。"""
    _assemble_workflow_chain(context, verify_mode="always_pass", plan_tool_names=("PESTEL 分析",))


@given("全局追踪未启用（proxy 态前提断言）且观察哨 provider 经注入通道待命")
def given_global_noop_with_sentinel(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """NoOp 前提（读法丙——R2-4）：双复位 proxy 态断言 + 注入通道观察哨不 initialize。"""

    monkeypatch.delenv("PHOENIX_TRACING_ENABLED", raising=False)
    _reset_global_tracing()
    assert _is_proxy_global(), "NoOp 前提：全局应 proxy 态"
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    sentinel_provider, sentinel_exporter = _make_injectable_components()
    context["_sentinel_exporter"] = sentinel_exporter
    context["_sentinel_tracer"] = PhoenixTracer(config=_make_phoenix_config(), tracer_provider=sentinel_provider)


@when("执行 run-task 工作流")
def when_run_task_workflow(context: dict[str, Any]) -> None:
    """执行 use case execute（异常捕获存 context——透传断言锚）。"""
    _run_workflow(context)


@then("根 span 名为 agent_execution")
def then_root_span_named(context: dict[str, Any]) -> None:
    """根 span 名断言（epics 钦定名）。"""
    root = _get_root_span(context)
    assert root.name == "agent_execution"


@then("六阶段子 span 名集合完整（agent.perceive/plan/execute/verify/reflect/package）")
def then_six_phase_span_names(context: dict[str, Any]) -> None:
    """六名集合断言（span 名末段对齐 executed_phases 枚举——package 非 package_evidence）。"""
    from src.application.ports.agent_tracing import SpanNames

    phase_spans = [s for s in _get_spans(context) if s.name != "agent_execution"]
    expected = {f"{SpanNames.PHASE_PREFIX}{phase}" for phase in ("perceive", "plan", "execute", "verify", "reflect", "package")}
    assert {s.name for s in phase_spans} == expected


@then("九阶段执行序为 perceive→plan→execute→verify→reflect→plan→execute→verify→package")
def then_nine_phase_execution_order(context: dict[str, Any]) -> None:
    """执行序断言（start_time 排序——重试轮四方法再入的线性序列）。"""
    phase_spans = sorted(
        (s for s in _get_spans(context) if s.name != "agent_execution"),
        key=lambda s: s.start_time,
    )
    expected_order = [
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
    assert [s.name for s in phase_spans] == expected_order, f"九阶段执行序不符，实际 {[s.name for s in phase_spans]}"
    assert len(_get_spans(context)) == 10, "fail-once 链应根+9 阶段恰 10 span"


@then("每个子 span 的 parent 均为根 span（同 trace 上下文传播）")
def then_phase_parents_are_root(context: dict[str, Any]) -> None:
    """parent 链断言（OTel contextvars 同进程 async 传播——ReadableSpan 自身 id 在 .context）。"""
    root = _get_root_span(context)
    for span in _get_spans(context):
        if span.name == "agent_execution":
            assert span.parent is None, "根 span 的 parent 应为空"
            continue
        assert span.parent is not None, f"子 span {span.name} 应有 parent"
        assert span.parent.span_id == root.context.span_id, f"子 span {span.name} 的 parent 应为根"


@then("span 阶段序列与 executed_phases 终态一致（同源断言）")
def then_span_sequence_matches_executed_phases(context: dict[str, Any]) -> None:
    """同源一致断言：span 末段序列 == result.executed_phases。"""
    result = context["result"]
    phase_spans = sorted(
        (s for s in _get_spans(context) if s.name != "agent_execution"),
        key=lambda s: s.start_time,
    )
    assert tuple(s.name.split(".", 1)[1] for s in phase_spans) == tuple(result.executed_phases)


@then("抛出 AgentWorkflowError 且 code 为 444")
def then_agent_workflow_error_444(context: dict[str, Any]) -> None:
    """444 包装异常断言（LLM 族经 _structured_call 包装——装饰器零吞异常透传）。"""
    from src.domain.exceptions.agent_exceptions import AgentWorkflowError

    caught = context.get("caught")
    assert isinstance(caught, AgentWorkflowError), f"应抛 AgentWorkflowError，实际 {type(caught).__name__}"
    assert caught.code == "EXCEPTION_444"


@then("异常所在子 span 状态为 ERROR 且事件含 exception")
def then_error_span_status_and_event(context: dict[str, Any]) -> None:
    """异常 span 断言：status ERROR + record_exception 事件（status 置位在 @trace wrapper）。"""
    from opentelemetry.trace import StatusCode

    error_spans = [s for s in _get_spans(context) if s.name != "agent_execution" and s.status.status_code == StatusCode.ERROR]
    assert error_spans, "异常所在子 span 应标记 ERROR"
    for span in error_spans:
        assert any(event.name == "exception" for event in span.events), f"span {span.name} 应含 exception 事件"


@then("根 span 同样标记 ERROR 且零吞异常（原样上抛）")
def then_root_span_error_and_reraise(context: dict[str, Any]) -> None:
    """根 span ERROR 断言 + 异常已透传到调用方（context["caught"] 在位即上抛证明）。"""
    from opentelemetry.trace import StatusCode

    root = _get_root_span(context)
    assert root.status.status_code == StatusCode.ERROR
    assert "caught" in context, "异常应原样上抛（装饰器零吞异常）"


@then("观察哨导出器计数保持为零（无旁路泄漏）")
def then_sentinel_zero_spans(context: dict[str, Any]) -> None:
    """观察哨断言（读法丙）：不经全局的旁路零泄漏。"""
    assert len(context["_sentinel_exporter"].get_finished_spans()) == 0


@then("工作流终态与 5-3 基线一致（executed_phases 九阶段 + retry_count 为 1）")
def then_noop_workflow_baseline(context: dict[str, Any]) -> None:
    """主链等价断言：NoOp 下返回值与 5-3 基线一致（fail-once 链九阶段 + 一次重试）。"""
    result = context["result"]
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
    assert result.retry_count == 1
    assert result.workflow_status == "completed"


@then("全局 provider 保持未装配（NoOp 判据是全局 provider 状态）")
def then_global_still_proxy(context: dict[str, Any]) -> None:
    """NoOp 判据断言：全程零全局 set（provider 状态而非 enabled 配置）。"""

    assert _is_proxy_global()


# ===================================================================
# AC-3: span 属性契约与 trace_id 贯通
# ===================================================================


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-3.1 - 根 span MVP 十项业务属性逐键断言",
)
def test_ac_3_1_mvp_attributes(context: dict[str, Any]) -> None:
    """AC-3.1: 十项属性与装配材料及返回结果逐项相等。"""


@then("agent_execution span 十项属性与装配材料及返回结果逐项相等")
def then_ten_mvp_attributes(context: dict[str, Any]) -> None:
    """十项属性逐键断言（数据源：agent 实体 / profile_result / result.evidence——AC-3 钉死）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    root = _get_root_span(context)
    agent = context["agent"]
    profile_result = context["profile_result"]
    result = context["result"]
    expected = {
        SpanAttributeKeys.AGENT_ID: str(agent.agent_id),
        SpanAttributeKeys.AGENT_ROLE: agent.role.value,
        SpanAttributeKeys.AGENT_NAME: agent.name,
        SpanAttributeKeys.AGENT_STARTUP_CONTEXT_TOKENS: profile_result.startup_context_tokens,
        SpanAttributeKeys.AGENT_ACTIVE_SKILL_COUNT: len(profile_result.tools_l1),
        SpanAttributeKeys.WORKFLOW_STATUS: result.workflow_status,
        SpanAttributeKeys.WORKFLOW_RETRY_COUNT: result.retry_count,
        SpanAttributeKeys.WORKFLOW_EXECUTED_PHASES: tuple(result.executed_phases),
        SpanAttributeKeys.EVAL_CONFIDENCE: result.evidence.confidence,
        SpanAttributeKeys.EVIDENCE_INPUT_HASH: result.evidence.input_hash,
    }
    for key, value in expected.items():
        assert root.attributes.get(key) == value, f"属性 {key} 应为 {value!r}，实际 {root.attributes.get(key)!r}"
    assert len(expected) == 10


@then("active_skill_count 等于 len(tools_l1) 派生口径")
def then_active_skill_count_derived(context: dict[str, Any]) -> None:
    """派生口径断言（agent_events.py L83 同源——len(tools_l1)）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    root = _get_root_span(context)
    assert root.attributes[SpanAttributeKeys.AGENT_ACTIVE_SKILL_COUNT] == len(context["profile_result"].tools_l1)


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-3.2 - eval-drift 四键常量注册与写入通道能力（组件级注入通道）",
)
def test_ac_3_2_eval_drift_keys_and_channel(context: dict[str, Any]) -> None:
    """AC-3.2: 四键常量逐字断言 + 子集式元断言 + 注入通道写入能力（OD-2 口径）。"""


@given("PhoenixTracer 以注入测试 provider 与内存导出器构造（未 initialize）")
def given_phoenix_tracer_injected_not_initialized(context: dict[str, Any]) -> None:
    """组件级注入通道（零全局触碰——R2-1 双源解析注入通道可观测性）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    provider, exporter = _make_injectable_components()
    context["_provider"] = provider
    context["_exporter"] = exporter
    context["_phoenix_tracer"] = PhoenixTracer(config=_make_phoenix_config(), tracer_provider=provider)


@then("SpanAttributeKeys 四键常量与规划钦定字符串逐字一致")
def then_four_key_constants(context: dict[str, Any]) -> None:
    """四键逐字断言（epics 三键 + §17.3.8 L1700 confidence_accuracy 键形增设）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    assert SpanAttributeKeys.EVAL_HALLUCINATION_SCORE == "eval.hallucination_score"
    assert SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE == "eval.context_relevance"
    assert SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY == "eval.confidence_accuracy"
    assert SpanAttributeKeys.DRIFT_DETECTED == "drift.detected"


@then("epics 三键是常量注册表的子集（子集式元断言）")
def then_epics_subset_meta(context: dict[str, Any]) -> None:
    """子集式元断言（R1-4：epics L1726-1728 三键 ⊆ SpanAttributeKeys 且逐字相等）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    epics_keys = {"eval.hallucination_score", "eval.context_relevance", "drift.detected"}
    registered = {
        value for name, value in vars(SpanAttributeKeys).items() if not name.startswith("_") and isinstance(value, str)
    }
    assert epics_keys <= registered, f"epics 三键应为注册表子集，缺失 {epics_keys - registered}"


@when("经 create_span 写入 eval-drift 四键测试值")
def when_write_eval_drift_keys(context: dict[str, Any]) -> None:
    """四键写入（attributes 批量通道——生产填值归 5.8/5.9，本 Story 验证通道能力）。"""
    from src.application.ports.agent_tracing import SpanAttributeKeys

    tracer = context["_phoenix_tracer"]
    payload = {
        SpanAttributeKeys.EVAL_HALLUCINATION_SCORE: 0.12,
        SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE: 0.87,
        SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY: 0.95,
        SpanAttributeKeys.DRIFT_DETECTED: True,
    }
    with tracer.create_span("eval-drift-channel-probe", attributes=payload) as handle:
        assert handle is not None, "注入通道 create_span 应产真 span"
    context["written_payload"] = payload


@then("导出 span 属性含全部四键且值相等（5.8/5.9 填值通道可用）")
def then_eval_drift_channel_roundtrip(context: dict[str, Any]) -> None:
    """写入→导出→断言全链（通道能力——OD-2 口径）。"""
    spans = context["_exporter"].get_finished_spans()
    assert [s.name for s in spans] == ["eval-drift-channel-probe"]
    for key, value in context["written_payload"].items():
        assert spans[0].attributes.get(key) == value, f"通道键 {key} 应为 {value!r}"


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-3.3 - trace_id run 级贯通（span hex 等于工具层 ExecutionContext.trace_id）",
)
def test_ac_3_3_trace_id_propagation(context: dict[str, Any]) -> None:
    """AC-3.3: span trace_id hex == ExecutionContext.trace_id + NoOp 全零形态（5-3 预留位核销）。"""


@when("执行 run-task 工作流并捕获工具层 ExecutionContext")
def when_run_workflow_capture_context(context: dict[str, Any]) -> None:
    """执行 + 捕获（_RecordingToolExecutionService 记录锚——工具步在 plan 内前提）。"""
    _run_workflow(context)
    captured = context["tool_service"].captured_contexts
    assert captured, "链应含 ≥1 工具步（ExecutionContext 构造点前提）"
    context["captured_trace_ids"] = [ctx.trace_id for ctx in captured]


@then("根 span 的 trace_id hex 与 ExecutionContext.trace_id 一致（32 位小写十六进制）")
def then_trace_id_hex_consistent(context: dict[str, Any]) -> None:
    """贯通断言：execute 阶段在 agent.execute 子 span 上下文内派生——与根同 trace。"""
    root = _get_root_span(context)
    expected_hex = format(root.context.trace_id, "032x")
    assert len(expected_hex) == 32 and expected_hex == expected_hex.lower()
    assert set(context["captured_trace_ids"]) == {expected_hex}, (
        f"ExecutionContext.trace_id 应为 {expected_hex}，实际 {context['captured_trace_ids']}"
    )


@when("双复位全局后同链再执行（NoOp 态）")
def when_reset_and_rerun_noop(context: dict[str, Any]) -> None:
    """NoOp 再跑（前置双复位——INVALID_SPAN trace_id==0 的格式化形态）。"""
    _reset_global_tracing()
    context["tool_service"].captured_contexts.clear()
    _run_workflow(context)
    context["noop_trace_ids"] = [ctx.trace_id for ctx in context["tool_service"].captured_contexts]
    assert context["noop_trace_ids"], "NoOp 链也应含工具步（ExecutionContext 构造点）"


@then("工具层捕获的 trace_id 为全零 32 位 hex（降级语义钉死）")
def then_noop_trace_id_all_zero(context: dict[str, Any]) -> None:
    """NoOp 降级断言：INVALID_SPAN 的 trace_id==0 → 32 位全零 hex。"""
    assert set(context["noop_trace_ids"]) == {"0" * 32}, f"NoOp trace_id 应为全零 32 位 hex，实际 {context['noop_trace_ids']}"


# ===================================================================
# AC-4: 端口接线、架构合规与回归零破坏
# ===================================================================


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-4.1 - 组合根接线与 initialize 传导（含配置错误降级负路径）",
)
def test_ac_4_1_composition_root_wiring(context: dict[str, Any]) -> None:
    """AC-4.1: resolve 四件 + 无全局副作用 + enabled 传导直构口径 + 负路径 warning 降级。"""


@given("组合根已引导装配")
def given_composition_root_bootstrapped(context: dict[str, Any]) -> None:
    """组合根已引导（session 级 _bootstrap_once——Story 5.7 区段已注册）。"""
    from src.domain.ports.registry import _global_registry

    assert _global_registry.get("agent_tracing") is not None, "agent_tracing 端口应已注册"


@then("agent_tracing 端口 resolve 可达且 PortSpec 元数据完整（SINGLETON）")
def then_agent_tracing_port_spec(context: dict[str, Any]) -> None:
    """PortSpec 四件 + 元数据（5-6 AC-6.1 同款形态）。"""
    from src.domain.ports.registry import Lifetime, _global_registry
    from src.domain.ports.resolver import get_resolver

    spec = _global_registry.get("agent_tracing")
    assert spec is not None, "agent_tracing 端口应已注册（resolve 可达）"
    assert spec.name == "agent_tracing"
    assert spec.version == "v1.0.0"
    assert spec.lifetime == Lifetime.SINGLETON, f"lifetime 应 SINGLETON，实际 {spec.lifetime}"
    assert spec.owner == "platform"
    assert spec.tags == ("agent", "observability", "tracing")
    assert spec.module == "src.infrastructure.monitoring.phoenix_tracer"
    from src.application.ports.agent_tracing import AgentTracingPort

    assert spec.interface is AgentTracingPort
    instance = get_resolver().resolve("agent_tracing")
    assert isinstance(instance, AgentTracingPort)
    assert type(instance).__name__ == "PhoenixTracer"


@then("resolve 实例 isinstance AgentTracingPort 且 resolve 无全局副作用")
def then_resolve_no_global_side_effect(context: dict[str, Any]) -> None:
    """resolve 无全局副作用断言（默认 enabled=false——构造器纯赋值零全局动作，R3-13）。"""

    assert _is_proxy_global(), "默认配置下 resolve 不应 set 全局（enabled=false NoOp 零开销）"


@when("场景内直构 PhoenixTracer（monkeypatch 环境启用追踪）并 initialize")
def when_direct_construct_and_initialize(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """enabled 传导直构口径（R2-3：SINGLETON 实例 config 在 bootstrap 构造期定格——
    场景 env 注入不可经 resolve 传导[设计事实]，直构验证 lambda 同构语义）。"""
    from src.infrastructure.config.phoenix import PhoenixConfig
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    monkeypatch.delenv("PHOENIX_TRACING_ENABLED", raising=False)
    monkeypatch.setenv("PHOENIX_TRACING_ENABLED", "true")
    tracer = PhoenixTracer(config=PhoenixConfig.from_env())
    context["_direct_tracer"] = tracer
    context["direct_initialize_result"] = tracer.initialize()


@then("initialize 返回 True（lambda 同构语义传导）")
def then_direct_initialize_true(context: dict[str, Any]) -> None:
    """直构 initialize 断言（lambda 内 from_env 同构——enabled=true 传导装配）。"""

    assert context["direct_initialize_result"] is True
    assert not _is_proxy_global(), "initialize 应 set 全局"


@when("直调 _wire_agent_tracing 接线单元且采样配置非法（PHOENIX_TRACES_SAMPLER_ARG 为 0）")
def when_wire_unit_with_bad_config(
    context: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """负路径直调（R3-3：接线提取为独立可调用单元——直调真实函数 + 坏 env 断言
    warning 降级不抛；新 Resolver 经 monkeypatch 注入绕 SINGLETON 缓存使 lambda 真跑）。"""
    import src.domain.ports.resolver as resolver_module
    from src.composition_root import _wire_agent_tracing

    _reset_global_tracing()  # 负路径前提（场景序中直构步骤已 set 全局——前置复位）
    monkeypatch.delenv("PHOENIX_TRACING_ENABLED", raising=False)
    monkeypatch.setenv("PHOENIX_TRACING_ENABLED", "true")
    monkeypatch.setenv("PHOENIX_TRACES_SAMPLER_ARG", "0")  # ∉ (0, 1] → 构造期 101
    fresh_resolver = resolver_module.Resolver()
    monkeypatch.setattr(resolver_module, "get_resolver", lambda: fresh_resolver)
    with caplog.at_level(logging.WARNING):
        _wire_agent_tracing()  # 不抛（DC-7 旁路哲学——try 罩住 resolve + isinstance + initialize）
    context["wire_warning_records"] = [r for r in caplog.records if r.levelno >= logging.WARNING]


@then("记录 warning 降级跳过且不抛出（DC-7 旁路哲学）")
def then_wire_warning_degraded(context: dict[str, Any]) -> None:
    """负路径断言：warning 有记录 + 全局未 set（配置 typo 只损失观测面）。"""

    assert context["wire_warning_records"], "_wire_agent_tracing 应 logger.warning 降级（不静默）"
    assert _is_proxy_global(), "负路径不应 set 全局"


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-4.2 - 架构静态扫描（AST 三验证器与 domain 零触碰）",
)
def test_ac_4_2_architecture_static_scan(context: dict[str, Any]) -> None:
    """AC-4.2: application 白名单 / domain 零触碰 / 组合根外零实例化 / .env.example 三变量。"""


@then("application 触碰文件第三方 import 白名单合规（允许 opentelemetry）")
def then_application_whitelist(context: dict[str, Any]) -> None:
    """验证器 A 轻量版：本 Story 触碰的 application 文件 import 顶层模块白名单。

    判据：非标准库第三方仅允许 opentelemetry（application 只碰 OTel API 包——
    DC-3 分界纪律）；标准库经 sys.stdlib_module_names 精确判定（存量文件合法
    标准库 import 不误伤）。
    """
    import ast
    import sys

    targets = [
        SRC_DIR / "application" / "tracing.py",
        SRC_DIR / "application" / "ports" / "agent_tracing.py",
        SRC_DIR / "application" / "ports" / "__init__.py",
        SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py",
        SRC_DIR / "application" / "services" / "agent_workflow_service.py",
    ]
    allowed_third_party = {"opentelemetry"}
    forbidden = {
        "pydantic",
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
    }
    for path in targets:
        assert path.is_file(), f"application 触碰文件缺失: {path}"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        assert modules & forbidden == set(), f"{path.name} 禁入第三方: {modules & forbidden}"
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib <= allowed_third_party, f"{path.name} 白名单外第三方: {non_stdlib - allowed_third_party}"


@then("domain 目录零本 Story 触碰（零新增符号且零 opentelemetry import）")
def then_domain_zero_touch(context: dict[str, Any]) -> None:
    """domain 零触碰断言（本 Story 无 domain 改动——grep 新增符号零命中）。"""
    story_symbols = ("PhoenixTracer", "PhoenixConfig", "AgentTracingPort", "SpanAttributeKeys", "SpanNames", "@trace")
    for py_file in (SRC_DIR / "domain").rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        for symbol in story_symbols:
            assert symbol not in source, f"domain 零触碰红线: {py_file} 含 {symbol}"
        assert "import opentelemetry" not in source, f"domain 禁 import opentelemetry: {py_file}"


@then("PhoenixTracer 实例化点仅组合根与测试（组合根外零实例化）")
def then_composition_root_only_instantiation(context: dict[str, Any]) -> None:
    """验证器 B 轻量版：src/ 全目录扫描 PhoenixTracer( 构造点。"""
    import ast

    violations: list[str] = []
    for py_file in SRC_DIR.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = node.func
                name = getattr(callee, "id", None) or getattr(callee, "attr", None)
                if name == "PhoenixTracer":
                    violations.append(f"{py_file.relative_to(REPO_ROOT)}:{node.lineno}")
    assert violations, "组合根应至少一处 PhoenixTracer 实例化（Story 5.7 注册 lambda）"
    assert all(v.startswith("src/composition_root.py") for v in violations), f"组合根外实例化点: {violations}"


@then(".env.example 三变量在位（PHOENIX_TRACING_ENABLED/PHOENIX_OTLP_ENDPOINT/PHOENIX_PROJECT_NAME）")
def then_env_example_three_vars(context: dict[str, Any]) -> None:
    """环境契约断言（sampling 专属变量不设样例行——注释说明）。"""
    content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for var in ("PHOENIX_TRACING_ENABLED", "PHOENIX_OTLP_ENDPOINT", "PHOENIX_PROJECT_NAME"):
        assert f"{var}=" in content, f".env.example 应含 {var}"
    assert "PHOENIX_TRACES_SAMPLER_ARG" in content, "采样变量应以注释说明（不设样例行）"


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-4.3 - 5-3 存量回归资产在位与装饰器纯附加",
)
def test_ac_4_3_regression_assets_and_pure_additive(context: dict[str, Any]) -> None:
    """AC-4.3: 5-3 测试资产在位 + 构造签名不变（纯附加装饰零签名变化）+ __wrapped__ 静态锚。"""


@then("5-3 回归测试资产文件全部在位（unit 三文件族 + 契约三件 + integration + acceptance）")
def then_5_3_assets_present(context: dict[str, Any]) -> None:
    """5-3 全家回归清单（Task 3 循环 C 同源——全量回归绿在 Task 6 收尾跑）。"""
    assets = [
        "tests/unit/application/services/test_agent_workflow_service.py",
        "tests/unit/infrastructure/agent_orch/test_single_agent_workflow_graph.py",
        "tests/unit/infrastructure/agent_orch/test_langgraph_engine.py",
        "tests/unit/application/use_cases/test_run_agent_workflow.py",
        "tests/contracts/test_port_contract_agent_workflow_service.py",
        "tests/contracts/test_port_contract_agent_workflow_use_case.py",
        "tests/contracts/test_port_contract_agent_engine.py",
        "tests/integration/test_integration_agent_workflow.py",
        "tests/acceptance/test_acceptance_agent_workflow.py",
    ]
    for relative in assets:
        assert (REPO_ROOT / relative).is_file(), f"5-3 回归资产缺失: {relative}"


@then("六阶段方法与 execute 用例构造签名与 5-3 基线一致（纯附加装饰零签名变化）")
def then_signatures_unchanged(context: dict[str, Any]) -> None:
    """构造签名不变断言（R3-14：inspect.signature 对照 5-3 基线——零构造点回归面前提）。"""
    from src.application.services.agent_workflow_service import AgentWorkflowService
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

    service_params = list(inspect.signature(AgentWorkflowService.__init__).parameters)[1:]
    assert service_params == [
        "llm_client",
        "tool_execution_service",
        "skill_loader",
        "tool_registry_service",
        "isolation_guard",
        "per_call_timeout_sec",
        "base_config",
    ]
    use_case_params = list(inspect.signature(RunAgentWorkflowUseCase.__init__).parameters)[1:]
    assert use_case_params == [
        "agent_repository",
        "agent_profile_use_case",
        "agent_engine",
        "agent_workflow_service",
        "isolation_guard",
    ]
    execute_params = list(inspect.signature(RunAgentWorkflowUseCase.execute).parameters)[1:]
    assert execute_params == ["agent_id", "task"]


@then("六阶段方法与 execute 用例的 __wrapped__ 在位（装饰器静态锚）")
def then_wrapped_in_place(context: dict[str, Any]) -> None:
    """装饰器静态锚（functools.wraps 保签名——__wrapped__ 存在 + __name__ 不变）。"""
    from src.application.services.agent_workflow_service import AgentWorkflowService
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

    for phase in ("perceive", "plan", "execute", "verify", "reflect", "package_evidence"):
        method = getattr(AgentWorkflowService, phase)
        assert hasattr(method, "__wrapped__"), f"六阶段方法 {phase} 应有装饰器（__wrapped__）"
        assert method.__name__ == phase
    assert hasattr(RunAgentWorkflowUseCase.execute, "__wrapped__"), "execute 用例方法应有装饰器"
    assert RunAgentWorkflowUseCase.execute.__name__ == "execute"


# ===================================================================
# AC-5: 性能（委托集成计时——_PERF_CACHE 单槽缓存 + xdist_group 同 worker 串行）
# ===================================================================


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-5.1 - span 记录延迟 P95 小于 5ms",
)
def test_ac_5_1_span_record_p95(context: dict[str, Any]) -> None:
    """AC-5.1: create_span 全周期 P95<5ms（常量单源集成定义——验收 import）。"""


@when("执行 span 记录计时采样（委托集成缓存——禁双跑）")
def when_span_record_sampling(context: dict[str, Any]) -> None:
    """委托集成计时（warmup 1 + 20 采样 × create_span 全周期 10 属性）。"""
    from tests.integration.test_integration_phoenix_tracer import sample_span_record_perf

    context["span_perf"] = _run_async(context["_loop"], sample_span_record_perf())


@then("P95 延迟小于 5ms（create_span 全周期 × 10 属性）")
def then_p95_below_5ms(context: dict[str, Any]) -> None:
    """P95 断言（常量单源 import——禁双真源）。"""
    from tests.integration.test_integration_phoenix_tracer import SPAN_RECORD_P95_LIMIT_SECONDS

    p95 = context["span_perf"]["p95_seconds"]
    assert p95 < SPAN_RECORD_P95_LIMIT_SECONDS, f"span 记录 P95={p95}s 应 < {SPAN_RECORD_P95_LIMIT_SECONDS}s"


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "AC-5.2 - 追踪开销小于 1%（k 轮双跑中位数对比）",
)
def test_ac_5_2_tracing_overhead(context: dict[str, Any]) -> None:
    """AC-5.2: fail-once 链 5+5 轮双跑中位数开销 <1% + traced 正向锚 50 span。"""


@when("执行追踪开销双跑采样（委托集成缓存——fail-once 链 5+5 轮）")
def when_overhead_sampling(context: dict[str, Any]) -> None:
    """委托集成计时（块序钉死：先 t_untraced×5 → 一次性 initialize → t_traced×5）。"""
    from tests.integration.test_integration_phoenix_tracer import sample_tracing_overhead

    context["overhead_perf"] = _run_async(context["_loop"], sample_tracing_overhead())


@then("开销比例小于 1%（中位数公式）")
def then_overhead_below_1_percent(context: dict[str, Any]) -> None:
    """开销公式断言：(median(t_traced) - median(t_untraced)) / median(t_untraced) < 0.01。"""
    ratio = context["overhead_perf"]["overhead_ratio"]
    assert ratio < 0.01, f"追踪开销比例 {ratio:.4f} 应 < 1%"


@then("traced 块导出器 span 计数恰为 50（正向锚——防静默降级假绿）")
def then_traced_span_count_50(context: dict[str, Any]) -> None:
    """正向锚断言（10 span × 5 轮 == 50——防 traced 轮静默降级）。"""
    assert context["overhead_perf"]["traced_span_count"] == 50, (
        f"traced 块 span 计数应恰 50，实际 {context['overhead_perf']['traced_span_count']}"
    )


# ===================================================================
# 收尾: 交付完成清单（Task 6 追加——15 场景终态）
# ===================================================================


@scenario(
    "test_acceptance_phoenix_tracer.feature",
    "收尾 - 交付完成清单",
)
def test_completion_checklist(context: dict[str, Any]) -> None:
    """收尾：src 八文件 + tests 四目录交付清单逐项在位（missing 断言）."""


@then("src 交付八文件全部在位（配置/Tracer/端口/装饰器/接入两文件/组合根/monitoring 导出/env）")
def then_src_deliverables_present(context: dict[str, Any]) -> None:
    """src 完成清单（新建四 + 接入两 + 组合根 + monitoring 导出 + .env.example）。"""
    src_files = [
        "src/infrastructure/config/phoenix.py",
        "src/infrastructure/monitoring/phoenix_tracer.py",
        "src/application/ports/agent_tracing.py",
        "src/application/tracing.py",
        "src/application/use_cases/run_agent_workflow.py",
        "src/application/services/agent_workflow_service.py",
        "src/composition_root.py",
        "src/infrastructure/monitoring/__init__.py",
    ]
    for relative in src_files:
        assert (REPO_ROOT / relative).is_file(), f"src 交付文件缺失: {relative}"
    env_content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for var in ("PHOENIX_TRACING_ENABLED", "PHOENIX_OTLP_ENDPOINT", "PHOENIX_PROJECT_NAME"):
        assert f"{var}=" in env_content, f".env.example 缺 {var}"


@then("tests 四目录交付文件全部在位（unit 三件 + 契约 + integration + acceptance 两件）")
def then_tests_deliverables_present(context: dict[str, Any]) -> None:
    """tests 完成清单（unit×3 + 契约 + 集成 + 验收×2 + 架构验证器）。"""
    test_files = [
        "tests/unit/infrastructure/config/test_phoenix_config.py",
        "tests/unit/infrastructure/monitoring/test_phoenix_tracer.py",
        "tests/unit/application/test_tracing_decorator.py",
        "tests/unit/architecture/test_arch_phoenix_tracer.py",
        "tests/contracts/test_port_contract_agent_tracing.py",
        "tests/integration/test_integration_phoenix_tracer.py",
        "tests/acceptance/test_acceptance_phoenix_tracer.feature",
        "tests/acceptance/test_acceptance_phoenix_tracer.py",
    ]
    for relative in test_files:
        assert (REPO_ROOT / relative).is_file(), f"tests 交付文件缺失: {relative}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
