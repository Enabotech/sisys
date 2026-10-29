"""验收测试 Story 5.10 - CheckpointWithEvaluation 集成（FR-EV-04）。

14 场景三属性分档表（Task 0.6 定稿）：

| 场景 | 外部服务依赖 | 前置状态（Given 装配） | 断言面（Then） |
|------|-------------|----------------------|---------------|
| AC-1.1 | 无（组件级纯内存） | 真实 DTO 手工构造 | 五分数域守卫 201/agent_id 非空/frozen/三序列等长 |
| AC-1.2 | 无（组件级纯内存） | 手算锚聚合（3 条记录） | 打包四键/stage_id/手算锚逐值/MAX_HISTORY_SIZE |
| AC-1.3 | 无（组件级纯内存） | 手算锚聚合（3 条记录） | 往返逐值/recorded_at isoformat/空历史退化锚 |
| AC-2.1 | 无（Fake LLM 链 + OTel） | 链级 initialize + Recorder + 替身仓储 + drift | record 真值/predicted/命名空间/累积 |
| AC-2.2 | 无（同上 + RaisingRepo） | StorageError 注入 + drift 预填充 | 主链正常 + 三键在 + 漂移仍执行 + WARNING |
| AC-2.3 | 无（链级 OTel 通道） | 模块加载 + 多形态装配 | 漂移失败联动/评估降级联动/None 默认/八依赖签名/同步 ×7 |
| AC-3.1 | Redis（真实往返） | 场景级独立客户端 + 真实 RedisSnapshotStore | 落键两层 json/TTL 86400 |
| AC-3.2 | Redis（真实往返） | 新 Recorder 模拟重启 | 重启恢复/累积延续/快照不存在 None |
| AC-3.3 | Redis（真实往返） | 真实 Recorder + 注入序已知 | 趋势时序/自清理 exists False |
| AC-4.1 | 无（组合根 resolve） | get_resolver（conftest session 闩） | resolve 四件/工厂第八依赖/CR1-DF2 防护/契约方法 |
| AC-4.2 | 无（静态扫描） | 交付文件存在 | 零新第三方/domain 收窄/events 零触碰/静态锚/env 零改动 |
| AC-5.1 | Redis（委托集成计时） | _PERF_CACHE["save_p95"] 委托采样 | save P95<100ms + 正向锚 21 + 满窗锚 |
| AC-5.2 | Redis（委托集成计时） | _PERF_CACHE["query_p95"] 委托采样 | query P95<50ms + 正向锚 21 + 口径声明 |
| 收尾 | 无（静态存在性） | 完成清单就绪 | src 2+7/tests 7+3+6 文本锚 |

span 断言锚（5.7 SSOT 全文唯一口径）：链级场景（AC-2.*）统一通道 = 场景级新
TracerProvider + SimpleSpanProcessor + InMemorySpanExporter 经
PhoenixTracer(config=测试配置, tracer_provider=注入).initialize() → 断言 →
teardown 强制 reset_for_testing() 双复位；组件级场景（AC-1）零全局触碰。

Recorder 状态隔离（SINGLETON 有状态——5.9 检测器同款防线）：全部场景手工构造
新实例（不走 resolve——SINGLETON 累积跨场景污染防线）；「连续执行累积」场景
显式同实例两次 execute。

redis marker 显式声明（混合文件知悉）：文件名 checkpoint_evaluation 不命中
conftest 服务关键词映射，AC-3/AC-5 用真实 Redis——isolation_switch_log 先例
同处境同款显式声明；AC-1×3 与 AC-4×2 纯内存场景被文件级 marker 覆盖
（-m "not redis" 环境会连纯内存场景一并排除——分档表服务依赖列标「无」知悉）。

Run with:
    poetry run pytest tests/acceptance/test_acceptance_checkpoint_evaluation.py -v
"""

from __future__ import annotations

import asyncio
import logging
import uuid as uuid_module
from pathlib import Path
from typing import Any, Coroutine, Generator

import pytest
from pytest_bdd import given, scenario, then, when

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"

# redis marker 显式声明（文件名不命中 conftest 服务关键词映射——AC-3/AC-5 真实
# Redis 场景；xdist_group 与集成计时场景逐字同组（loadgroup 同 worker 串行是
# _PERF_CACHE 委托缓存命中前提）
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.redis,
    pytest.mark.xdist_group("checkpoint-evaluation-perf"),
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
    与场景间交叉污染。
    """
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    PhoenixTracer.reset_for_testing()
    yield
    PhoenixTracer.reset_for_testing()


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """场景级共享上下文（dict 形态）+ 惰性真实 Redis 客户端（场景级独立——跨循环记忆锚）。"""
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(
        host=acceptance_env_config.redis.host,
        port=acceptance_env_config.redis.port,
        password=acceptance_env_config.redis.password,
        decode_responses=True,
    )
    ctx: dict[str, Any] = {"_loop": event_loop, "_redis_client": redis_client, "_session_ids": []}
    yield ctx
    # teardown：只清理自己创建的 snapshot 命名空间键（禁 delete/truncate 全局模式）
    for session_id in ctx["_session_ids"]:
        _run_async(event_loop, redis_client.delete(f"sisys:snapshot:{session_id}"))
    _run_async(event_loop, redis_client.close())
    exporter = ctx.pop("_exporter", None)
    if exporter is not None:
        exporter.clear()


def _run_async(event_loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, Any]) -> Any:
    """同循环调度（BDD 步骤禁 @pytest.mark.asyncio——context 数据丢失）。"""
    return event_loop.run_until_complete(coro)


def _redis_available(context: dict[str, Any]) -> bool:
    """Redis 门控（ping 失败动态 skip——禁写死 @pytest.mark.skip）。"""
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
        return True
    except Exception as exc:  # 场景门控专用——ping 失败一律 skip（isolation_switch_log L277 同款）
        pytest.skip(f"Redis not available: {exc}")
        return False


# ===================================================================
# 装配 helpers（延迟 import 纪律——本 Story 新交付模块一律函数体内 import）
# ===================================================================

#: 手算锚分数序列（一位小数——避开浮点边界，AC-1 三场景共用）
_ANCHOR_SCORES: tuple[float, float, float] = (0.1, 0.3, 0.5)

#: 手算锚 predicted 序列（一位小数——V1-EV3 锚数据）
_ANCHOR_PREDICTED: tuple[float, float, float] = (0.2, 0.4, 0.6)

#: 手算锚基线序列（drift 预填充复用——[0.7, 0.9]×15，μ₀=0.8）
_BASELINE_SEQUENCE: list[float] = [0.7, 0.9] * 15

#: 漂移注入值（下漂锚——预填充后链上任一样本即确认）
_DOWN_DRIFT_SCORE = 0.4

#: 测试假密钥占位（resolver 替身基底的连接字段——非真实凭据；5-8/5-9 验收同款）
_BASE_EVAL_FAKE_KEY = "base-eval-" + "fake-key"


def _make_checkpoint(recorded_at: Any, agent_id: str, index: int) -> Any:
    """手算锚评估记录构造（七字段——分数取 _ANCHOR_SCORES[index] 一位小数）。"""
    from src.application.ports.agent_checkpoint import EvaluationCheckpoint

    score = _ANCHOR_SCORES[index]
    return EvaluationCheckpoint(
        recorded_at=recorded_at,
        agent_id=agent_id,
        hallucination_score=score,
        context_relevance=score,
        confidence_accuracy=score,
        overall_score=score,
        predicted_confidence=_ANCHOR_PREDICTED[index],
    )


def _make_anchor_aggregate(agent_id: str = "agent-anchor-001") -> Any:
    """手算锚聚合（3 条评估记录——三序列同源一位小数）。"""
    from datetime import UTC, datetime

    from src.application.ports.agent_checkpoint import CheckpointWithEvaluation

    base_time = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)
    history = tuple(_make_checkpoint(base_time.replace(minute=10 * i), agent_id, i) for i in range(3))
    return CheckpointWithEvaluation(
        agent_id=agent_id,
        evaluation_history=history,
        hallucination_trend=tuple(c.hallucination_score for c in history),
        confidence_accuracy_trend=tuple(c.confidence_accuracy for c in history),
    )


class _RecordingSnapshotRepo:
    """手写零 IO 快照仓储替身（duck-typing 实现 SnapshotRepositoryProtocol——验收禁 mock 红线）。

    save 捕获快照列表（record 断言锚）+ load 返回最后快照（restore 委托面）+
    delete 计数（清理面）；test_integration_execute.py MockSnapshotRepo 先例形态。
    """

    def __init__(self) -> None:
        self.saved_snapshots: list[Any] = []
        self.delete_calls: list[str] = []

    async def save(self, snapshot: Any) -> None:
        self.saved_snapshots.append(snapshot)

    async def load(self, session_id: str) -> Any:
        for snapshot in reversed(self.saved_snapshots):
            if snapshot.session_id == session_id:
                return snapshot
        return None

    async def delete(self, session_id: str) -> None:
        self.delete_calls.append(session_id)


class _RaisingSnapshotRepo:
    """恒抛 StorageError 的快照仓储替身（AC-2.2 record 失败降级注入面——统一 StorageError 口径）。"""

    async def save(self, snapshot: Any) -> None:
        from src.domain.exceptions import StorageError

        raise StorageError(message="Failed to save snapshot: 模拟 Redis 故障（验收注入）")

    async def load(self, session_id: str) -> Any:
        return None

    async def delete(self, session_id: str) -> None:
        return None


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


class _FakeDriftPort:
    """手写零 IO 漂移检测替身（AC-2.3 漂移失败联动——update 抛 451 注入面）。"""

    def __init__(self) -> None:
        self.update_calls = 0

    async def update(self, score: float) -> Any:
        from src.domain.exceptions import DriftDetectionError

        self.update_calls += 1
        raise DriftDetectionError(metric_name="overall_score", reason="invalid_state")

    async def trigger_recalibration(self, assessment: Any, agent_id: str | None = None) -> None:
        return None


class _RaisingEvaluationPort:
    """手写零 IO 评估替身（AC-2.3 评估降级联动——evaluate 抛 450 注入面）。"""

    def __init__(self) -> None:
        self.evaluate_calls = 0

    async def evaluate(self, result: Any) -> Any:
        from src.domain.exceptions import AgentEvaluationError

        self.evaluate_calls += 1
        raise AgentEvaluationError(reason="llm_call")


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
    """六阶段 + 幻觉检测 Fake LLM 替身（外部 SaaS 豁免面——5-9 验收同款全文照抄）。"""
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
    """工具执行面替身边界（真实服务链 + Fake llm + 沙箱替身——5-7/5-9 先例同款）。"""
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


def _make_evaluation_resolver_stub() -> Any:
    """评估链 resolver 替身（连接字段非默认值——5-8/5-9 验收同款）。"""
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


def _prefill_drift(loop: asyncio.AbstractEventLoop, detector: Any) -> None:
    """drift 确认态预填充（30 基线 + 4×0.4——链上末样本全域任意值均确认 down）。"""
    for score in list(_BASELINE_SEQUENCE) + [_DOWN_DRIFT_SCORE] * 4:
        loop.run_until_complete(detector.update(score))


def _assemble_checkpoint_workflow_chain(
    context: dict[str, Any],
    *,
    checkpoint_recorder: Any = None,
    drift_detector: Any = None,
    drift_prefill: bool = False,
    evaluation_harness: Any | None = "default",
) -> None:
    """AC-2 链级手工装配（5-9 装配链同款 + 第八依赖注入）。

    drift_prefill=True 时对注入的真实检测器预填充 drift 确认态（场景私有实例——
    SINGLETON 隔离防线；替身形态恒 False）；evaluation_harness="default" 表示真实
    EvaluationHarness（None 与替身显式传入）。
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

    if evaluation_harness == "default":
        harness: Any = EvaluationHarness(llm_client=fake_llm, model_resolver=_make_evaluation_resolver_stub())
    else:
        harness = evaluation_harness
    context["evaluation_harness"] = harness

    injected_detector = drift_detector
    if injected_detector is not None and drift_prefill:
        _prefill_drift(loop, injected_detector)
    context["drift_detector"] = injected_detector
    context["checkpoint_recorder"] = checkpoint_recorder
    context["use_case"] = RunAgentWorkflowUseCase(
        agent_repository=stub_agent_repo,
        agent_profile_use_case=profile_use_case,
        agent_engine=context["engine"],
        agent_workflow_service=service,
        isolation_guard=guard,
        evaluation_harness=harness,
        drift_detector=injected_detector,
        checkpoint_recorder=checkpoint_recorder,
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


def _make_real_recorder(context: dict[str, Any], agent_id: str) -> Any:
    """真实 Recorder 装配（场景级独立 Redis 客户端 + 真实 RedisSnapshotStore——AC-3）。"""
    from src.application.services.evaluation_checkpoint_recorder import EvaluationCheckpointRecorder
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

    store = RedisSnapshotStore(adapter=RedisAdapter(context["_redis_client"]))
    context["snapshot_store"] = store
    context["agent_id"] = agent_id
    context["session_id"] = f"agent-evaluation-{agent_id}"
    context["_session_ids"].append(context["session_id"])
    return EvaluationCheckpointRecorder(snapshot_repository=store)


def _make_result_for_record(index: int) -> Any:
    """record 形参构造（真实 EvaluationResult + predicted——手算锚同源分数）。"""
    from src.application.ports.agent_evaluation import EvaluationResult

    score = _ANCHOR_SCORES[index]
    return EvaluationResult(
        hallucination_score=score,
        context_relevance=score,
        confidence_accuracy=score,
        overall_score=score,
    )


class EvaluationResultHelper:
    """EvaluationResult 构造 helper（AC-3.3 分数注入——全部四分数同值简化形态）。"""

    @staticmethod
    def make(score: float) -> Any:
        """四分数同值构造（时序断言只关心序列序——值域合法即可）。"""
        from src.application.ports.agent_evaluation import EvaluationResult

        return EvaluationResult(
            hallucination_score=score,
            context_relevance=score,
            confidence_accuracy=score,
            overall_score=score,
        )


# ===================================================================
# 场景绑定（14 场景全显式）
# ===================================================================


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-1.1 - EvaluationCheckpoint 域守卫与聚合等长守卫",
)
def test_ac_1_1_domain_guards_and_aggregate_consistency(context: dict[str, Any]) -> None:
    """AC-1.1: 五分数域守卫 201/agent_id 非空/frozen/三序列等长。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-1.2 - to_checkpoint_snapshot 打包（state_data 四键契约）",
)
def test_ac_1_2_snapshot_packing_four_keys(context: dict[str, Any]) -> None:
    """AC-1.2: 打包结构四键/stage_id/手算锚逐值/MAX_HISTORY_SIZE 常量。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-1.3 - from_snapshot 往返一致性与空历史退化锚",
)
def test_ac_1_3_roundtrip_and_empty_history(context: dict[str, Any]) -> None:
    """AC-1.3: 往返逐值/recorded_at isoformat 往返/空历史退化。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-2.1 - 主链 record 块执行与 predicted 持久化",
)
def test_ac_2_1_main_chain_record_and_predicted(context: dict[str, Any]) -> None:
    """AC-2.1: record 快照真值/predicted 持久化/命名空间/连续累积。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-2.2 - record 失败独立降级网（452 不阻断主链与漂移块）",
)
def test_ac_2_2_record_failure_independent_degradation(context: dict[str, Any]) -> None:
    """AC-2.2: StorageError→452 降级 + 三键仍在 + 漂移仍执行 + WARNING 452 锚。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-2.3 - 降级联动与构造签名八依赖基线",
)
def test_ac_2_3_degradation_linkage_and_signature(context: dict[str, Any]) -> None:
    """AC-2.3: 漂移失败/评估降级联动 + None 默认 + 八依赖签名 + 同步 ×7。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-3.1 - 真实 Redis 落键验证",
)
def test_ac_3_1_real_redis_key_landing(context: dict[str, Any]) -> None:
    """AC-3.1: hget latest 两层 json + 三序列逐值 + TTL 86400。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-3.2 - 重启恢复与累积延续",
)
def test_ac_3_2_restart_restore_and_continuity(context: dict[str, Any]) -> None:
    """AC-3.2: 新实例 restore 逐值 + 恢复后 record 延续 + 快照不存在 None。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-3.3 - 趋势时序与自清理",
)
def test_ac_3_3_trend_ordering_and_cleanup(context: dict[str, Any]) -> None:
    """AC-3.3: hallucination_trend 顺序 == 注入序 + teardown exists False。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-4.1 - 组合根接线与降级防护",
)
def test_ac_4_1_composition_root_wiring(context: dict[str, Any]) -> None:
    """AC-4.1: resolve 四件/工厂第八依赖/CR1-DF2 防护/契约方法。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-4.2 - 架构静态扫描",
)
def test_ac_4_2_architecture_static_scan(context: dict[str, Any]) -> None:
    """AC-4.2: 零新第三方/domain 收窄/events 零触碰/静态锚/env 零改动 + xdist 互异。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-5.1 - 快照创建 P95 小于 100ms",
)
def test_ac_5_1_save_p95_below_100ms(context: dict[str, Any]) -> None:
    """AC-5.1: 委托集成计时（save P95<100ms 常量单源 + 正向锚 21 + 满窗锚）。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "AC-5.2 - 评估历史查询 P95 小于 50ms",
)
def test_ac_5_2_query_p95_below_50ms(context: dict[str, Any]) -> None:
    """AC-5.2: 委托查询计时（query P95<50ms 常量单源 + 正向锚 21 + 口径声明）。"""


@scenario(
    "test_acceptance_checkpoint_evaluation.feature",
    "收尾 - 完成清单逐项确认",
)
def test_wrapped_up_completion_checklist(context: dict[str, Any]) -> None:
    """收尾: src 2+7/tests 7+3+6 完成清单逐项存在性与文本锚。"""


# ===================================================================
# AC-1: CheckpointWithEvaluation 聚合与快照转换（组件级——纯内存零服务依赖）
# ===================================================================


@given("真实 EvaluationCheckpoint 与 CheckpointWithEvaluation frozen DTO 已装配（手工构造——纯数据类）")
def given_real_dtos_assembled(context: dict[str, Any]) -> None:
    """手工构造真实 DTO（每场景新实例——纯数据类零外部依赖）。"""
    from datetime import UTC, datetime

    context["recorded_at"] = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)
    context["agent_id"] = "agent-guard-001"
    context["valid_checkpoint"] = _make_checkpoint(context["recorded_at"], context["agent_id"], 0)


@when("执行五分数字段越界与类型违规参数化构造与三序列等长守卫构造")
def when_execute_violating_constructions(context: dict[str, Any]) -> None:
    """违规构造执行（五分数 × 四违规值 + agent_id 空串 + 等长不齐——收集各构造面）。"""
    context["violation_cases"] = []
    base_kwargs = {
        "recorded_at": context["recorded_at"],
        "agent_id": context["agent_id"],
        "hallucination_score": 0.2,
        "context_relevance": 0.3,
        "confidence_accuracy": 0.4,
        "overall_score": 0.3,
        "predicted_confidence": 0.5,
    }
    for field in ("hallucination_score", "context_relevance", "confidence_accuracy", "overall_score", "predicted_confidence"):
        for bad_value in (-0.01, 1.01, True, "0.5"):
            kwargs = {**base_kwargs, field: bad_value}
            context["violation_cases"].append((field, bad_value, kwargs))

    context["empty_agent_id_kwargs"] = {**base_kwargs, "agent_id": ""}

    anchor = _make_anchor_aggregate("agent-mismatch-001")
    context["unequal_aggregate_kwargs"] = {
        "agent_id": "agent-mismatch-001",
        "evaluation_history": anchor.evaluation_history,
        "hallucination_trend": anchor.hallucination_trend,
        "confidence_accuracy_trend": anchor.confidence_accuracy_trend[:2],
    }


@then('五分数域守卫断言通过（[-0.01/1.01/True/"0.5"] 抛 ValidationError 201 三段式——context 携字段名）')
def then_five_score_domain_guards(context: dict[str, Any]) -> None:
    """五分数 × 四违规值参数化 201 三段式（raises → code → context 携字段名）。"""
    import pytest as pytest_module

    from src.domain.exceptions import ValidationError

    for field, bad_value, kwargs in context["violation_cases"]:
        with pytest_module.raises(ValidationError) as exc_info:
            _construct_checkpoint(kwargs)
        assert exc_info.value.code == "EXCEPTION_201", f"{field}={bad_value!r} 应抛 201（实际 {exc_info.value.code}）"
        assert field in exc_info.value.context, f"context 应携字段名 {field}（实际 {exc_info.value.context}）"


def _construct_checkpoint(kwargs: dict[str, Any]) -> Any:
    """延迟 import 构造 EvaluationCheckpoint（红阶段 ModuleNotFoundError 逐场景承载）。"""
    from src.application.ports.agent_checkpoint import EvaluationCheckpoint

    return EvaluationCheckpoint(**kwargs)


@then("agent_id 非空守卫断言通过（空串抛 201）")
def then_agent_id_nonempty_guard(context: dict[str, Any]) -> None:
    """agent_id 空串 201 断言。"""
    import pytest as pytest_module

    from src.domain.exceptions import ValidationError

    with pytest_module.raises(ValidationError):
        _construct_checkpoint(context["empty_agent_id_kwargs"])


@then("frozen 不可变断言通过（setattr 抛 FrozenInstanceError）")
def then_frozen_immutability(context: dict[str, Any]) -> None:
    """frozen 断言（dataclasses.FrozenInstanceError——EvaluationResult/DriftAssessment 同款）。"""
    import dataclasses

    checkpoint = context["valid_checkpoint"]
    try:
        setattr(checkpoint, "agent_id", "mutated")
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("EvaluationCheckpoint 应 frozen 不可变（setattr 应抛 FrozenInstanceError）")


@then("三序列等长守卫断言通过（history 3 + trend 2 抛 201）")
def then_three_sequence_equal_length_guard(context: dict[str, Any]) -> None:
    """聚合三序列等长守卫（history 3 + trend 2 → 201）。"""
    import pytest as pytest_module

    from src.application.ports.agent_checkpoint import CheckpointWithEvaluation
    from src.domain.exceptions import ValidationError

    with pytest_module.raises(ValidationError):
        CheckpointWithEvaluation(**context["unequal_aggregate_kwargs"])


@given("手算锚聚合已构造（3 条评估记录——分数取 0.1/0.3/0.5 一位小数）")
def given_anchor_aggregate_constructed(context: dict[str, Any]) -> None:
    """手算锚聚合（3 条记录——一位小数避开浮点边界）。"""
    context["anchor_aggregate"] = _make_anchor_aggregate()
    context["anchor_agent_id"] = "agent-anchor-001"


@when("调用 to_checkpoint_snapshot(session_id, state_version=1) 打包")
def when_pack_to_snapshot(context: dict[str, Any]) -> None:
    """打包执行（session_id 形参 + state_version=1——聚合纯转换默认值锚）。"""
    context["packed_snapshot"] = context["anchor_aggregate"].to_checkpoint_snapshot(
        session_id="agent-evaluation-agent-anchor-001", state_version=1
    )


@then(
    '打包结构断言通过（stage_id=="evaluation" + state_data 四键存在 + snapshot_id 非空 UUID'
    " + ttl_seconds==86400 + state_version==1 默认值）"
)
def then_packing_structure(context: dict[str, Any]) -> None:
    """打包结构断言（四键契约 + 实体字段默认值——OD-3 键契约锚）。"""
    from uuid import UUID

    snapshot = context["packed_snapshot"]
    assert snapshot.stage_id == "evaluation"
    assert snapshot.state_version == 1, "state_version 默认 1（递增语义归 Recorder 计数器）"
    assert snapshot.ttl_seconds == 86400, "ttl_seconds 应为实体默认 86400"
    assert isinstance(snapshot.snapshot_id, UUID) and snapshot.snapshot_id is not None
    for key in ("agent_id", "evaluation_history", "hallucination_trend", "confidence_accuracy_trend"):
        assert key in snapshot.state_data, f"state_data 应含四键之 {key}（实际键 {list(snapshot.state_data)}）"
    assert snapshot.state_data["agent_id"] == "agent-anchor-001"
    assert isinstance(snapshot.state_data["evaluation_history"], list), "evaluation_history 应为记录 dict 列表"


@then("手算锚逐值断言通过（三序列长度 == 3 + 逐值精确相等）")
def then_anchor_values_exact(context: dict[str, Any]) -> None:
    """手算锚三序列逐值（0.1/0.3/0.5——精确等式禁 approx）。"""
    state_data = context["packed_snapshot"].state_data
    assert state_data["hallucination_trend"] == list(_ANCHOR_SCORES)
    assert state_data["confidence_accuracy_trend"] == list(_ANCHOR_SCORES)
    assert len(state_data["evaluation_history"]) == 3
    for i, record in enumerate(state_data["evaluation_history"]):
        assert record["hallucination_score"] == _ANCHOR_SCORES[i]
        assert record["context_relevance"] == _ANCHOR_SCORES[i]
        assert record["confidence_accuracy"] == _ANCHOR_SCORES[i]
        assert record["overall_score"] == _ANCHOR_SCORES[i]
        assert record["predicted_confidence"] == _ANCHOR_PREDICTED[i]
        assert record["agent_id"] == "agent-anchor-001"


@then("MAX_HISTORY_SIZE 常量单源断言通过（== 100 模块常量）")
def then_max_history_size_constant(context: dict[str, Any]) -> None:
    """MAX_HISTORY_SIZE 模块常量单源（OD-8 窗口上限锚——防参数漂移）。"""
    from src.application.ports import agent_checkpoint

    assert agent_checkpoint.MAX_HISTORY_SIZE == 100


@when("执行打包后 from_snapshot 解包往返")
def when_roundtrip_unpack(context: dict[str, Any]) -> None:
    """纯内存往返（to → from——json 双程验证由 AC-3 真实 Redis 场景承载）。"""
    from src.application.ports.agent_checkpoint import CheckpointWithEvaluation

    snapshot = context["anchor_aggregate"].to_checkpoint_snapshot(session_id="agent-evaluation-agent-anchor-001")
    context["restored_aggregate"] = CheckpointWithEvaluation.from_snapshot(snapshot)


@then("往返一致性断言通过（三序列逐值精确相等 + recorded_at isoformat 往返相等 + agent_id 相等）")
def then_roundtrip_consistency(context: dict[str, Any]) -> None:
    """往返一致性（三序列逐值 + recorded_at datetime 相等 + agent_id）。"""
    original = context["anchor_aggregate"]
    restored = context["restored_aggregate"]
    assert restored.evaluation_history == original.evaluation_history, "history 应逐值精确相等"
    assert restored.hallucination_trend == original.hallucination_trend
    assert restored.confidence_accuracy_trend == original.confidence_accuracy_trend
    for orig, rest in zip(original.evaluation_history, restored.evaluation_history):
        assert rest.recorded_at == orig.recorded_at, "recorded_at isoformat 往返应相等"
    assert restored.agent_id == original.agent_id


@then("空历史退化锚断言通过（零记录聚合打包三序列空列表 + 恢复空聚合）")
def then_empty_history_degenerate_anchor(context: dict[str, Any]) -> None:
    """空历史退化锚（restore 边界态——首次评估前无历史是正常态）。"""
    from src.application.ports.agent_checkpoint import CheckpointWithEvaluation

    empty = CheckpointWithEvaluation(
        agent_id="agent-empty-001",
        evaluation_history=(),
        hallucination_trend=(),
        confidence_accuracy_trend=(),
    )
    snapshot = empty.to_checkpoint_snapshot(session_id="agent-evaluation-agent-empty-001")
    assert snapshot.state_data["evaluation_history"] == []
    assert snapshot.state_data["hallucination_trend"] == []
    assert snapshot.state_data["confidence_accuracy_trend"] == []
    restored = CheckpointWithEvaluation.from_snapshot(snapshot)
    assert restored.evaluation_history == ()
    assert restored.agent_id == "agent-empty-001"


# ===================================================================
# AC-2: 主链接入——第八可选依赖 + record 块 + 独立降级网（链级——OTel 通道）
# ===================================================================


@given("链级全局追踪通道已启用（场景级 initialize + InMemory exporter）", target_fixture=None)
def given_chain_tracing_enabled(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """链级 OTel 通道（场景级新 provider 经 initialize 履行全局 set——5-7 SSOT）。"""
    monkeypatch.delenv("PHOENIX_TRACING_ENABLED", raising=False)
    _enable_test_tracing(context)


@given(
    "checkpoint 工作流链已装配（Fake LLM 幻觉分注入 + 真实 Recorder"
    " + 手写零 IO _RecordingSnapshotRepo 替身 + drift_detector 注入）"
)
def given_checkpoint_chain_assembled(context: dict[str, Any]) -> None:
    """链级装配（真实 Recorder + 替身仓储 + 真实 drift 检测器场景私有实例——AC-2.2 断言面）。"""
    from src.application.services.evaluation_checkpoint_recorder import EvaluationCheckpointRecorder
    from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

    repo = _RecordingSnapshotRepo()
    context["snapshot_repo"] = repo
    recorder = EvaluationCheckpointRecorder(snapshot_repository=repo)
    context["real_recorder"] = recorder
    detector = CUSUMDriftDetector(event_publisher=_RecordingEventPublisher())
    _assemble_checkpoint_workflow_chain(context, checkpoint_recorder=recorder, drift_detector=detector, drift_prefill=True)


@given("降级工作流链已装配（_RaisingSnapshotRepo——save 抛 StorageError + drift 预填充场景）")
def given_degradation_chain_assembled(context: dict[str, Any]) -> None:
    """降级链装配（save 抛 StorageError——Recorder 包装 452 完整真实路径 + drift 确认态预填充）。"""
    from src.application.services.evaluation_checkpoint_recorder import EvaluationCheckpointRecorder
    from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

    repo = _RaisingSnapshotRepo()
    context["raising_repo"] = repo
    recorder = EvaluationCheckpointRecorder(snapshot_repository=repo)
    context["real_recorder"] = recorder
    detector = CUSUMDriftDetector(event_publisher=_RecordingEventPublisher())
    _assemble_checkpoint_workflow_chain(context, checkpoint_recorder=recorder, drift_detector=detector, drift_prefill=True)


@when("调用 RunAgentWorkflowUseCase.execute 执行六阶段工作流")
def when_execute_workflow(context: dict[str, Any]) -> None:
    """执行工作流（异常捕获存 context["caught"]——透传断言锚）。"""
    _run_workflow(context)


@then(
    "record 调用断言通过（替身捕获 1 个 CheckpointSnapshot + state_data 四键"
    " + 末条五分数字段逐值相等 + agent_id 相等 + recorded_at 近期时刻）"
)
def then_record_invocation_truth(context: dict[str, Any]) -> None:
    """record 快照真值断言（末条记录与 Fake LLM 注入评估分逐值——手算锚同源断言）。"""
    from datetime import UTC, datetime

    repo = context["snapshot_repo"]
    assert len(repo.saved_snapshots) == 1, f"应恰捕获 1 个快照（实际 {len(repo.saved_snapshots)}）"
    snapshot = repo.saved_snapshots[0]
    for key in ("agent_id", "evaluation_history", "hallucination_trend", "confidence_accuracy_trend"):
        assert key in snapshot.state_data, f"state_data 应含 {key}"
    last_record = snapshot.state_data["evaluation_history"][-1]
    # Fake LLM 幻觉分 0.2 + 零工具链 cr=0.0 → actual=(1-0.2)*0.5+0*0.5=0.4，
    # ca=1-|predicted 0.85 - actual 0.4|=0.55（5-8 compute_confidence_accuracy 同款链式手算锚）
    assert last_record["hallucination_score"] == 0.2
    assert last_record["context_relevance"] == 0.0
    assert last_record["confidence_accuracy"] == 0.55
    assert last_record["agent_id"] == str(context["agent"].agent_id)
    recorded_at = datetime.fromisoformat(last_record["recorded_at"])
    now = datetime.now(UTC)
    assert abs((now - recorded_at).total_seconds()) < 300, "recorded_at 应为近期时刻"


@then("predicted 持久化断言通过（predicted_confidence == result.evidence.confidence——V1-EV3 兑现锚）")
def then_predicted_persisted(context: dict[str, Any]) -> None:
    """predicted 持久化（V1-EV3 钦定——只存 EvaluationResult 会丢 predicted 的兑现）。"""
    snapshot = context["snapshot_repo"].saved_snapshots[0]
    last_record = snapshot.state_data["evaluation_history"][-1]
    assert last_record["predicted_confidence"] == context["result"].evidence.confidence, (
        "predicted_confidence 应 == result.evidence.confidence（V1-EV3 兑现锚）"
    )


@then('命名空间与顺序断言通过（session_id=="agent-evaluation-{agent_id}" + stage_id=="evaluation" + record 块在三键后漂移前）')
def then_namespace_and_ordering(context: dict[str, Any]) -> None:
    """命名空间锚（DC-6 per-agent 聚合键）+ 顺序锚（静态面归 AC-4.2 AST 锚）。"""
    snapshot = context["snapshot_repo"].saved_snapshots[0]
    assert snapshot.session_id == f"agent-evaluation-{context['agent'].agent_id}", (
        f"session_id 应为 agent-evaluation-{{agent_id}} 命名空间（实际 {snapshot.session_id}）"
    )
    assert snapshot.stage_id == "evaluation"
    # 顺序锚（三键后漂移前）：本场景 eval 三键与 record 快照并存即结构性证明
    span = _find_root_span(context)
    attributes = dict(span.attributes)
    for key in ("eval.hallucination_score", "eval.context_relevance", "eval.confidence_accuracy"):
        assert key in attributes, "eval 三键应在（record 前已写——顺序锚）"


@then("连续执行累积断言通过（同 agent 连续 2 次 execute → 第二次快照历史长度 == 2 + trend 长度 == 2）")
def then_consecutive_accumulation(context: dict[str, Any]) -> None:
    """连续累积（Recorder 内存累积跨 run 保持——SINGLETON 语义同实例）。"""
    _run_workflow(context)
    repo = context["snapshot_repo"]
    assert len(repo.saved_snapshots) == 2, "同实例两次 execute 应产生两快照"
    second = repo.saved_snapshots[1]
    assert len(second.state_data["evaluation_history"]) == 2, (
        f"第二次快照历史长度应为 2（实际 {len(second.state_data['evaluation_history'])}）"
    )
    assert len(second.state_data["hallucination_trend"]) == 2


@then("record 失败降级断言通过（主链正常返回 + eval 三键仍在 + 漂移块仍执行 drift.detected==True）")
def then_record_failure_degradation(context: dict[str, Any]) -> None:
    """record 失败独立降级（452 内层 catch——漂移检测不受牵连）。"""
    result = context["result"]
    assert result is not None, "主链应正常返回（452 降级不阻断）"
    assert context.get("caught") is None, "452 应被 record 块专属内层 catch 捕获不上抛"
    assert result.workflow_status == "completed"
    span = _find_root_span(context)
    attributes = dict(span.attributes)
    for key in ("eval.hallucination_score", "eval.context_relevance", "eval.confidence_accuracy"):
        assert key in attributes, "eval 三键应仍在（record 前已写）"
    assert attributes.get("drift.detected") is True, "漂移块仍执行（drift 预填充场景应确认 down）"


@then('WARNING 日志断言通过（WARNING 级 + 文本含 452 静态 message "评估历史持久化失败"）')
def then_warning_log_452_static_message(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    """WARNING 断言（452 静态 message 锚——str(领域异常) 恒等于 message）。"""
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "评估历史持久化失败" in r.message]
    assert warnings, "应有 WARNING 级降级日志（含 452 静态 message「评估历史持久化失败」）"
    injected_fragment = "模拟 Redis 故障"
    assert all(injected_fragment not in r.message for r in warnings), (
        "注入 StorageError 的动态文案不应出现在 warning 文本（str≡message 机制锚）"
    )


@given("工作流模块已加载")
def given_workflow_module_loaded(context: dict[str, Any]) -> None:
    """模块加载（存量模块——本场景红锚在签名断言）。"""
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

    context["RunAgentWorkflowUseCase"] = RunAgentWorkflowUseCase


@when("检查漂移失败联动与评估降级联动与 None 默认路径与构造签名")
def when_check_linkages_and_signature(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """联动三态 + None 默认 + 八依赖签名（多形态装配依次执行——仅形态③需 OTel 通道）。"""
    import inspect

    monkeypatch.delenv("PHOENIX_TRACING_ENABLED", raising=False)

    use_case_cls = context["RunAgentWorkflowUseCase"]
    signature = inspect.signature(use_case_cls.__init__)
    context["signature_params"] = list(signature.parameters)[1:]
    context["signature_default"] = signature.parameters["checkpoint_recorder"].default

    # 形态①漂移失败联动：drift 抛 451 → record 已完成（替身捕获非空）——span 断言无需求，零全局触碰
    drift_repo = _RecordingSnapshotRepo()
    drift_recorder = _make_recorder_with(drift_repo)
    _assemble_checkpoint_workflow_chain(context, checkpoint_recorder=drift_recorder, drift_detector=_FakeDriftPort())
    context["drift_failure_repo"] = drift_repo
    _run_workflow(context)
    context["drift_failure_result"] = context.get("result")
    context["drift_failure_caught"] = context.get("caught")

    # 形态②评估降级联动：evaluate 抛 450 → record 零调用（替身零捕获）
    eval_repo = _RecordingSnapshotRepo()
    eval_recorder = _make_recorder_with(eval_repo)
    _assemble_checkpoint_workflow_chain(context, checkpoint_recorder=eval_recorder, evaluation_harness=_RaisingEvaluationPort())
    context["eval_failure_repo"] = eval_repo
    _run_workflow(context)
    context["eval_failure_result"] = context.get("result")
    context["eval_failure_caught"] = context.get("caught")

    # 形态③None 默认路径：七参构造（不注入 checkpoint_recorder）——行为与 5.9 基线一致（eval 三键断言需 OTel 通道）
    _enable_test_tracing(context)
    _assemble_checkpoint_workflow_chain(context, checkpoint_recorder=None)
    _run_workflow(context)
    context["none_default_result"] = context.get("result")
    context["none_default_caught"] = context.get("caught")


def _make_recorder_with(repo: Any) -> Any:
    """Recorder 构造 helper（延迟 import——红阶段 ModuleNotFoundError 承载）。"""
    from src.application.services.evaluation_checkpoint_recorder import EvaluationCheckpointRecorder

    return EvaluationCheckpointRecorder(snapshot_repository=repo)


@then("漂移失败联动断言通过（漂移块抛 451 → record 已完成替身捕获非空 + 主链正常返回）")
def then_drift_failure_linkage(context: dict[str, Any]) -> None:
    """漂移失败联动（record 在漂移块前——漂移失败不丢评估历史）。"""
    assert context["drift_failure_result"] is not None, "漂移失败下主链应正常返回（451 共享 catch 降级）"
    assert context["drift_failure_caught"] is None
    repo = context["drift_failure_repo"]
    assert len(repo.saved_snapshots) == 1, f"漂移失败时 record 应已完成（实际捕获 {len(repo.saved_snapshots)}）"


@then("评估降级联动断言通过（evaluate 抛 450 → record 零调用 + 主链正常返回）")
def then_evaluation_failure_linkage(context: dict[str, Any]) -> None:
    """评估降级联动（record 块在 evaluate 后同一 try 体内——evaluate 抛出直接跳外层 catch）。"""
    assert context["eval_failure_result"] is not None, "评估失败下主链应正常返回（450 共享 catch 降级）"
    assert context["eval_failure_caught"] is None
    repo = context["eval_failure_repo"]
    assert len(repo.saved_snapshots) == 0, f"evaluate 失败时 record 应零调用（实际捕获 {len(repo.saved_snapshots)}）"


@then("None 默认路径断言通过（七参构造行为与 5.9 基线一致 + record 块零执行）")
def then_none_default_path_baseline(context: dict[str, Any]) -> None:
    """None 默认路径（八参默认——存量七参构造零破坏回归锚）。"""
    assert context["none_default_result"] is not None and context["none_default_caught"] is None
    span = _find_root_span(context)
    attributes = dict(span.attributes)
    assert "eval.hallucination_score" in attributes, "None 路径 eval 三键应在（5.9 基线一致）"
    assert getattr(context["use_case"], "_checkpoint_recorder", "missing") is None, (
        "七参构造 _checkpoint_recorder 应为 None（默认值向后兼容）"
    )


@then("八依赖签名断言通过（inspect.signature 参数清单尾部 checkpoint_recorder + 默认 None + 外层共享 catch 三元组不变）")
def then_eight_dependency_signature(context: dict[str, Any]) -> None:
    """八依赖签名（尾部追加形态）+ 共享 catch 三元组不变（源码文本锚）。"""
    expected = [
        "agent_repository",
        "agent_profile_use_case",
        "agent_engine",
        "agent_workflow_service",
        "isolation_guard",
        "evaluation_harness",
        "drift_detector",
        "checkpoint_recorder",
    ]
    assert context["signature_params"] == expected, f"构造签名应为八依赖: {context['signature_params']}"
    assert context["signature_default"] is None, "第八参数 checkpoint_recorder 应默认 None"

    source = (SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py").read_text(encoding="utf-8")
    assert "except (AgentEvaluationError, LLMConfigError, DriftDetectionError)" in source, (
        "外层共享 catch 三元组应零改动（450/332/451）"
    )
    assert "except EvaluationHistoryError" in source, "record 块应有内层 452 独立降级 catch"


@then("存量断言同步 ×7 基线断言通过（5-3/5-7/5-8/5-9 存量全家回归绿）")
def then_seven_assertion_sync_baselines(context: dict[str, Any]) -> None:
    """断言同步 ×7 基线（尾部追加防线——既有行原样保留 + checkpoint_recorder 行在位）。"""
    targets = {
        "tests/acceptance/test_acceptance_phoenix_tracer.py": '"checkpoint_recorder",  # Story 5.10 第八可选依赖',
        "tests/unit/architecture/test_arch_phoenix_tracer.py": '"checkpoint_recorder",  # Story 5.10 第八可选依赖',
        "tests/unit/architecture/test_arch_evaluation.py": '"checkpoint_recorder"',
        "tests/unit/architecture/test_arch_drift_detection.py": '"checkpoint_recorder"',
        "tests/unit/application/use_cases/test_run_agent_workflow.py": '"checkpoint_recorder"',
        "tests/acceptance/test_acceptance_agent_evaluation.py": '"checkpoint_recorder"',
        "tests/acceptance/test_acceptance_drift_detection.py": '"checkpoint_recorder"',
    }
    for relative, anchor in targets.items():
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert anchor in source, f"{relative} 应含八依赖清单行（断言同步 ×7——锚 {anchor!r}）"
        assert '"drift_detector"' in source, f"{relative} 既有七依赖清单行应保留（尾部追加禁改写）"
    # 回执耦合防线：5-9 验收锁死的 ①② 字面行仍在位（被断言锁死——禁改写）
    for relative in (
        "tests/acceptance/test_acceptance_phoenix_tracer.py",
        "tests/unit/architecture/test_arch_phoenix_tracer.py",
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert '"drift_detector",  # Story 5.9 第七可选依赖' in source, f"{relative} 5-9 回执字面行应原样保留"


# ===================================================================
# AC-3: 持久化与恢复——真实 Redis 往返（真实服务）
# ===================================================================


@given("真实 Redis 服务可用（场景级独立客户端 + TestTenant UUID 前缀隔离——不可用则动态跳过）")
def given_real_redis_available(context: dict[str, Any]) -> None:
    """Redis 门控（ping 失败动态 skip——AC-3.1 场景）。"""
    _redis_available(context)
    context["redis_agent_id"] = uuid_module.uuid4().hex


@given("真实 Recorder 已装配（组合注入真实 RedisSnapshotStore）")
def given_real_recorder_assembled(context: dict[str, Any]) -> None:
    """真实 Recorder 装配（AC-3.1——record ≥3 次的数据源）。"""
    context["real_recorder"] = _make_real_recorder(context, context["redis_agent_id"])


@when("record 多次（≥3 次——累积后持久化）")
def when_record_multiple_times(context: dict[str, Any]) -> None:
    """record ×3（手算锚同源分数——注入序已知）。"""
    recorder = context["real_recorder"]
    for i in range(3):
        snapshot = _run_async(
            context["_loop"],
            recorder.record(
                agent_id=context["redis_agent_id"],
                evaluation_result=_make_result_for_record(i),
                predicted=_ANCHOR_PREDICTED[i],
            ),
        )
    context["last_snapshot"] = snapshot
    context["recorded_scores"] = list(_ANCHOR_SCORES)
    context["recorded_predicted"] = list(_ANCHOR_PREDICTED)


@then(
    '落键验证断言通过（hget build_key("snapshot", session_id) "latest" 非空'
    " + 两层 json_loads 解析 + 三序列与 record 传入逐值相等）"
)
def then_real_redis_key_landing(context: dict[str, Any]) -> None:
    """真实落键（latest field 两层 json_loads——外层 7 字段 dict + 内层 state_data JSON 串）。"""
    import json

    raw = _run_async(context["_loop"], context["_redis_client"].hget(f"sisys:snapshot:{context['session_id']}", "latest"))
    assert raw is not None, "hget latest 应非空（真实 Redis 落键锚）"
    outer = json.loads(raw)
    assert outer["stage_id"] == "evaluation"
    state_data = outer["state_data"]
    state_data = json.loads(state_data) if isinstance(state_data, str) else state_data
    assert state_data["hallucination_trend"] == context["recorded_scores"], "三序列应与 record 传入逐值相等"
    assert state_data["confidence_accuracy_trend"] == context["recorded_scores"]
    assert len(state_data["evaluation_history"]) == 3
    assert state_data["evaluation_history"][0]["predicted_confidence"] == context["recorded_predicted"][0]


@then("TTL 语义断言通过（快照 ttl_seconds == 86400 实体默认）")
def then_ttl_entity_default(context: dict[str, Any]) -> None:
    """TTL 86400 断言（24h——评估历史 MVP 生命周期，实体默认不动）。"""
    assert context["last_snapshot"].ttl_seconds == 86400


@given("真实 Redis 服务可用（前一场景已落键——session 独立键）")
def given_real_redis_available_with_prior_keys(context: dict[str, Any]) -> None:
    """Redis 门控（AC-3.2 场景——独立 session 键空间）。"""
    _redis_available(context)
    context["redis_agent_id"] = uuid_module.uuid4().hex
    recorder = _make_real_recorder(context, context["redis_agent_id"])
    for i in range(3):
        _run_async(
            context["_loop"],
            recorder.record(
                agent_id=context["redis_agent_id"],
                evaluation_result=_make_result_for_record(i),
                predicted=_ANCHOR_PREDICTED[i],
            ),
        )
    context["prior_recorded_scores"] = list(_ANCHOR_SCORES)


@given("新构造 Recorder 实例已装配（模拟重启——内存累积清零）")
def given_new_recorder_simulating_restart(context: dict[str, Any]) -> None:
    """新实例模拟重启（同 session_id——内存累积清零，Redis 落键仍在）。"""
    context["restarted_recorder"] = _make_real_recorder(context, context["redis_agent_id"])


@when("调用 restore(session_id) 从快照恢复后继续 record 1 次")
def when_restore_then_record(context: dict[str, Any]) -> None:
    """restore（恢复式语义）+ record 1 次（累积延续验证）。"""
    recorder = context["restarted_recorder"]
    context["restored"] = _run_async(context["_loop"], recorder.restore(context["session_id"]))
    context["post_restore_snapshot"] = _run_async(
        context["_loop"],
        recorder.record(
            agent_id=context["redis_agent_id"],
            evaluation_result=_make_result_for_record(2),
            predicted=_ANCHOR_PREDICTED[2],
        ),
    )
    context["missing_restore"] = _run_async(context["_loop"], recorder.restore(f"agent-evaluation-{uuid_module.uuid4().hex}"))


@then("重启恢复断言通过（restore 返回聚合非空 + 历史长度 == 最后快照 + 逐值精确相等——重启存活锚）")
def then_restart_restore_truth(context: dict[str, Any]) -> None:
    """重启恢复（内存清零后历史完整恢复）。"""
    restored = context["restored"]
    assert restored is not None, "restore 应返回非空聚合（快照在位）"
    assert len(restored.evaluation_history) == 3
    assert list(restored.hallucination_trend) == context["prior_recorded_scores"], "恢复历史应逐值精确相等"


@then("累积延续断言通过（新快照历史 == 恢复历史 + 1 + 首条 == 恢复首条——恢复式语义灌回三 deque）")
def then_accumulation_continuity(context: dict[str, Any]) -> None:
    """累积延续（restore 是恢复不是只读查询——防纯查询式假绿锚）。"""
    snapshot = context["post_restore_snapshot"]
    history = snapshot.state_data["evaluation_history"]
    restored = context["restored"]
    assert len(history) == len(restored.evaluation_history) + 1, (
        f"恢复后 record 应使历史 == 恢复历史 + 1（实际 {len(history)}）"
    )
    assert history[0]["hallucination_score"] == restored.evaluation_history[0].hallucination_score, (
        "首条应 == 恢复首条（灌回三 deque 后追加）"
    )
    assert snapshot.state_version == 4, f"state_version 应续接（3 次 record 后 restore 续接 4，实际 {snapshot.state_version}）"


@then("快照不存在断言通过（restore 未 record 过的 UUID session_id → None 正常态）")
def then_snapshot_missing_returns_none(context: dict[str, Any]) -> None:
    """快照不存在 None（AutoExecuteService.load 同款 None 语义——首次评估前正常态）。"""
    assert context["missing_restore"] is None


@given("真实 Redis 服务可用（场景级独立客户端）")
def given_real_redis_available_scoped(context: dict[str, Any]) -> None:
    """Redis 门控（AC-3.3 场景——趋势时序独立键空间）。"""
    _redis_available(context)
    context["redis_agent_id"] = uuid_module.uuid4().hex
    context["real_recorder"] = _make_real_recorder(context, context["redis_agent_id"])


@given("真实 Recorder 已装配（record 注入序已知）")
def given_real_recorder_injection_order(context: dict[str, Any]) -> None:
    """注入序数据（AC-3.3——record 注入序即趋势时序断言的期望序）。"""
    context["trend_expected_order"] = [0.5, 0.1, 0.3, 0.5]


@when("执行多次 record 后验证趋势序列顺序与 teardown 清理")
def when_record_then_verify_order_and_cleanup(context: dict[str, Any]) -> None:
    """多次 record（非单调注入序——值序断言防排序假象）+ teardown 清理。"""
    recorder = context["real_recorder"]
    for score in context["trend_expected_order"]:
        _run_async(
            context["_loop"],
            recorder.record(
                agent_id=context["redis_agent_id"],
                evaluation_result=EvaluationResultHelper.make(score),
                predicted=0.5,
            ),
        )
    context["store"] = context["snapshot_store"]


@then("趋势时序断言通过（hallucination_trend 顺序 == record 注入顺序——值序非单调性）")
def then_trend_ordering(context: dict[str, Any]) -> None:
    """趋势时序（deque 追加序即时间序——顺序保持断言，经 store.load 取最后快照）。"""
    snapshot = _run_async(context["_loop"], context["store"].load(context["session_id"]))
    assert snapshot is not None
    assert snapshot.state_data["hallucination_trend"] == context["trend_expected_order"], (
        "hallucination_trend 顺序应 == record 注入顺序（deque 追加序即时间序）"
    )


@then("自清理断言通过（teardown delete 后 RedisSnapshotStore.exists(session_id) is False——只清自己创建的键）")
def then_self_cleanup(context: dict[str, Any]) -> None:
    """自清理（delete 只清自己创建的键——snapshot namespace 键级隔离）。"""
    store = context["store"]
    _run_async(context["_loop"], store.delete(context["session_id"]))
    assert _run_async(context["_loop"], store.exists(context["session_id"])) is False, (
        "teardown delete 后 exists 应为 False（自清理锚）"
    )


# ===================================================================
# AC-4: 端口接线、架构合规与组合根注册（静态 + 接线——零 OTel 全局触碰）
# ===================================================================


@given("组合根注册模块已加载")
def given_composition_root_loaded(context: dict[str, Any]) -> None:
    """组合根加载（bootstrap 经 tests/conftest session 闩——get_resolver 复用注册态）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    context["resolver"] = resolver
    context["checkpoint_instance"] = resolver.resolve("agent_checkpoint")
    context["use_case_instance"] = resolver.resolve("agent_workflow_use_case")


@when("检查 agent_checkpoint 端口注册与 use case 工厂第八依赖接线")
def when_check_port_registration_and_factory_wiring(context: dict[str, Any]) -> None:
    """注册与接线检查（含 CR1-DF2 降级防护——未注册形态 resolve_optional None）。"""
    from src.composition_root import _build_agent_workflow_use_case
    from src.domain.ports.registry import _global_registry

    context["checkpoint_spec"] = _global_registry.get("agent_checkpoint")

    class _UnregisteredCheckpointResolver:
        """CR1-DF2 降级防护替身（agent_checkpoint 未注册形态——resolve_optional 恒 None）。"""

        def resolve(self, name: str) -> Any:
            return object()

        def resolve_optional(self, name: str) -> Any:
            return None

    degraded_use_case = _build_agent_workflow_use_case(_UnregisteredCheckpointResolver())
    context["degraded_use_case"] = degraded_use_case


@then("组合根注册 resolve 四件断言通过（可达/isinstance/PortSpec 元数据/SINGLETON）")
def then_resolve_four_assertions(context: dict[str, Any]) -> None:
    """resolve 四件（可达 + isinstance 端口 + PortSpec 元数据 + SINGLETON——跨 run 累积论证）。"""
    from src.application.ports.agent_checkpoint import AgentCheckpointPort
    from src.domain.ports.registry import Lifetime

    instance = context["checkpoint_instance"]
    assert instance is not None, "resolve('agent_checkpoint') 应可达"
    assert isinstance(instance, AgentCheckpointPort), f"应实现 AgentCheckpointPort: {type(instance)}"
    spec = context["checkpoint_spec"]
    assert spec is not None, "注册表应有 agent_checkpoint 条目"
    assert spec.version == "v1.0.0"
    assert spec.module == "src.application.services.evaluation_checkpoint_recorder"
    assert spec.lifetime == Lifetime.SINGLETON
    assert spec.owner == "platform"
    assert spec.tags == ("agent", "checkpoint", "observability")


@then("use case 工厂注入断言通过（resolve 实例 _checkpoint_recorder 非 None 且 isinstance AgentCheckpointPort）")
def then_factory_injection_assertions(context: dict[str, Any]) -> None:
    """接线可达性（resolve_optional 第八依赖注入）。"""
    from src.application.ports.agent_checkpoint import AgentCheckpointPort

    use_case = context["use_case_instance"]
    recorder = getattr(use_case, "_checkpoint_recorder", None)
    assert recorder is not None, "use case 第八依赖应注入非 None（resolve_optional 接线）"
    assert isinstance(recorder, AgentCheckpointPort)


@then("CR1-DF2 降级防护断言通过（未注册形态 resolve_optional None + use case 构造成功）")
def then_cr1_df2_degradation_guard(context: dict[str, Any]) -> None:
    """CR1-DF2[5.8] 家族延续（agent_checkpoint 注册缺失 → _checkpoint_recorder None 不阻断构造）。"""
    degraded = context["degraded_use_case"]
    assert degraded is not None, "未注册形态 use case 应正常构造（接线失败降级不阻断 bootstrap）"
    assert getattr(degraded, "_checkpoint_recorder", "missing") is None, "未注册形态 _checkpoint_recorder 应为 None"


@then('端口契约 11 维度断言通过（REQUIRED_METHODS ["record","restore"] + _DummyResolver snapshot_repository 分支）')
def then_port_contract_dimensions(context: dict[str, Any]) -> None:
    """契约 11 维度基础（方法齐备——全量归 tests/contracts/test_port_contract_agent_checkpoint.py）。"""
    instance = context["checkpoint_instance"]
    for method in ("record", "restore"):
        assert hasattr(instance, method), f"{type(instance).__name__} 应有 {method}"
        assert callable(getattr(instance, method)), f"{method} 应 callable"


@given("交付文件存在性已确认")
def given_delivery_files_exist(context: dict[str, Any]) -> None:
    """交付文件前置检查（缺失即红——静态扫描的数据源）。"""
    targets = [
        SRC_DIR / "application" / "ports" / "agent_checkpoint.py",
        SRC_DIR / "application" / "ports" / "__init__.py",
        SRC_DIR / "application" / "services" / "evaluation_checkpoint_recorder.py",
        SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py",
        SRC_DIR / "domain" / "exceptions" / "evaluation_exceptions.py",
        SRC_DIR / "composition_root.py",
    ]
    for path in targets:
        assert path.is_file(), f"交付文件缺失: {path}"


@when("执行架构静态扫描（内联轻量版——全量验证器归 tests/unit/architecture）")
def when_run_inline_static_scan(context: dict[str, Any]) -> None:
    """扫描执行（AST 解析 + 源码文本存 context——静态断言数据源）。"""
    import ast

    scan_targets = {
        "agent_checkpoint": SRC_DIR / "application" / "ports" / "agent_checkpoint.py",
        "ports_init": SRC_DIR / "application" / "ports" / "__init__.py",
        "recorder": SRC_DIR / "application" / "services" / "evaluation_checkpoint_recorder.py",
        "run_agent_workflow": SRC_DIR / "application" / "use_cases" / "run_agent_workflow.py",
    }
    context["scan_trees"] = {name: ast.parse(p.read_text(encoding="utf-8")) for name, p in scan_targets.items()}
    context["use_case_source"] = scan_targets["run_agent_workflow"].read_text(encoding="utf-8")


@then("application 触碰文件零新增第三方断言通过")
def then_application_zero_new_third_party(context: dict[str, Any]) -> None:
    """验证器 A 轻量版（agent_checkpoint/recorder 纯标准库 + run_agent_workflow 既有基线内）。"""
    import sys

    allowed = {"opentelemetry"}  # run_agent_workflow 既有基线——本 Story 零新增第三方
    for name, tree in context["scan_trees"].items():
        if name not in ("agent_checkpoint", "ports_init", "recorder", "run_agent_workflow"):
            continue
        modules: set[str] = set()
        for node in ast_walk_imports(tree):
            modules.add(node)
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib <= allowed, f"{name} 白名单外第三方: {non_stdlib - allowed}"
    # 两新文件纯标准库专项
    for name in ("agent_checkpoint", "recorder"):
        modules = set(ast_walk_imports(context["scan_trees"][name]))
        non_stdlib = {m for m in modules if m not in sys.stdlib_module_names and m != "src"}
        assert non_stdlib == set(), f"{name}.py 应纯标准库零第三方（实际 {non_stdlib}）"


def ast_walk_imports(tree: Any) -> list[str]:
    """AST 遍历取顶层 import 模块名（首段）。"""
    import ast

    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module.split(".")[0])
    return names


@then("domain 触碰面收窄断言通过（EvaluationHistoryError 仅异常三件内 + events 零触碰——OD-6 契约）")
def then_domain_touch_narrowed(context: dict[str, Any]) -> None:
    """验证器 B 轻量版（业务目录零命中 + events 零触碰 + 452 仅 exceptions 三件）。"""
    import re

    story_symbols = ("CheckpointWithEvaluation", "AgentCheckpointPort", "EvaluationCheckpointRecorder", "EvaluationCheckpoint")
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

    # events 零触碰（OD-6——本 Story 与 5.9 的差异面：CheckpointReached 不发布，事件零改动）
    events_hits = [
        py_file
        for py_file in (SRC_DIR / "domain" / "events").rglob("*.py")
        if "CheckpointWithEvaluation" in py_file.read_text(encoding="utf-8")
        or "EvaluationHistory" in py_file.read_text(encoding="utf-8")
    ]
    assert not events_hits, f"events 目录应零触碰（OD-6 契约——实际命中 {events_hits}）"

    # EvaluationHistoryError 仅 exceptions 三件内
    exception_hits = [
        py_file
        for py_file in (SRC_DIR / "domain" / "exceptions").rglob("*.py")
        if "EvaluationHistoryError" in py_file.read_text(encoding="utf-8")
    ]
    allowed_exception_files = {"evaluation_exceptions.py", "_code_ranges.py", "__init__.py"}
    assert exception_hits, "EvaluationHistoryError 应存在于 exceptions（正向锚）"
    for hit in exception_hits:
        assert hit.name in allowed_exception_files, f"EvaluationHistoryError 应仅在 exceptions 三件内: {hit}"


@then("组合根外零实例化与依赖方向断言通过")
def then_composition_root_only_instantiation(context: dict[str, Any]) -> None:
    """验证器 B 轻量版（Recorder 构造点仅组合根 + tests；application→domain 合法面锚定）。"""
    import ast

    violations: list[str] = []
    found = False
    for py_file in SRC_DIR.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = node.func
                name = getattr(callee, "id", None) or getattr(callee, "attr", None)
                if name == "EvaluationCheckpointRecorder":
                    rel = str(py_file.relative_to(REPO_ROOT))
                    found = True
                    if not rel.startswith("src/composition_root.py"):
                        violations.append(f"{rel}:{node.lineno}")
    assert found, "组合根应至少一处 EvaluationCheckpointRecorder 实例化（注册 lambda）"
    assert not violations, f"组合根外实例化点: {violations}"

    # 依赖方向：recorder（application）import application 端口 + domain 端口/实体——合法面锚定
    import ast as ast_module

    recorder_path = SRC_DIR / "application" / "services" / "evaluation_checkpoint_recorder.py"
    tree = ast_module.parse(recorder_path.read_text(encoding="utf-8"))
    modules = {node.module for node in ast_module.walk(tree) if isinstance(node, ast_module.ImportFrom) and node.module}
    assert any(m.startswith("src.application") for m in modules), "recorder 应 import application 端口（依赖方向锚）"
    assert any(m.startswith("src.domain") for m in modules), "recorder 应 import domain 端口/实体（application→domain 合法面）"
    assert not any(m.startswith("src.infrastructure") or m.startswith("src.interfaces") for m in modules), (
        "application 不得 import infrastructure/interfaces"
    )


@then(
    "主链 record 块静态锚断言通过（record 调用 + predicted=result.evidence.confidence"
    " + 内层 except EvaluationHistoryError + 漂移块前序）"
)
def then_main_chain_record_block_static_anchor(context: dict[str, Any]) -> None:
    """验证器 C 轻量版（execute 体内四静态锚——AST/源段双形态 + 兄弟节点序）。"""
    import ast

    tree = context["scan_trees"]["run_agent_workflow"]
    execute_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "execute":
            execute_node = node
    assert execute_node is not None, "应存在 execute 方法"

    source_segment = ast.get_source_segment(context["use_case_source"], execute_node) or ""
    assert "_checkpoint_recorder" in source_segment, "execute 体内应有 record 块（None 守卫）"
    assert "await self._checkpoint_recorder.record(" in source_segment, "execute 体内应有 record 调用"
    assert "result.evidence.confidence" in source_segment, "execute 体内应有 predicted=result.evidence.confidence 引用"
    assert "except EvaluationHistoryError" in source_segment, "execute 体内应有内层 452 独立降级 catch"

    # 顺序锚：record 调用索引 < 漂移 update 调用索引（AST 行号序——漂移块之前）
    record_lineno = None
    drift_lineno = None
    for node in ast.walk(execute_node):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            func = node.value.func
            func_name = getattr(func, "attr", None) or getattr(func, "id", None)
            if func_name == "record":
                record_lineno = node.lineno
            if func_name == "update":
                drift_lineno = node.lineno
    assert record_lineno is not None, "应找到 record 调用节点"
    assert drift_lineno is not None, "应找到漂移 update 调用节点"
    assert record_lineno < drift_lineno, f"record 块应在漂移块之前（record {record_lineno} < drift {drift_lineno}）"


@then(".env.example 零改动断言通过 + xdist 组互异断言通过（checkpoint-evaluation-perf 与既有 14 组不冲突）")
def then_env_untouched_and_xdist_unique(context: dict[str, Any]) -> None:
    """配置零改动 + xdist 组互异（新组与既有 14 组不冲突——全仓扫描）。"""
    import re

    env_content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "MAX_HISTORY_SIZE" not in env_content, ".env.example 不应新增 MAX_HISTORY_SIZE（代码常量单源裁定）"
    assert "EVALUATION_HISTORY" not in env_content, ".env.example 不应新增评估历史配置（窗口上限是代码常量）"

    existing_groups: set[str] = set()
    for py_file in (REPO_ROOT / "tests").rglob("*.py"):
        existing_groups.update(re.findall(r'xdist_group\("([^"]+)"\)', py_file.read_text(encoding="utf-8")))
    expected_existing = {
        "agent-workflow-perf",
        "agent-isolation-perf",
        "agent-triple-isolation-perf",
        "isolation-switch-log-perf",
        "phoenix-tracer-perf",
        "agent-evaluation-perf",
        "drift-detection-perf",
        "agent-instantiation",
        "agent-profile-loading",
        "data-source-cache",
        "sandbox-daemon",
        "tool-executions-pg",
        "tool-versions-pg",
        "validation-feedback-pg",
    }
    assert expected_existing <= existing_groups, f"既有 14 组清单应全部在位（缺失 {expected_existing - existing_groups}）"
    assert "checkpoint-evaluation-perf" in existing_groups, "checkpoint-evaluation-perf 组应存在（集成/验收委托配对）"


# ===================================================================
# AC-5: 性能双锚——快照创建 P95 + 评估历史查询 P95（委托集成计时）
# ===================================================================


@given("集成计时委托模块已加载（_PERF_CACHE 委托采样——满窗锚预填充 100 条）")
def given_perf_delegate_loaded(context: dict[str, Any]) -> None:
    """save P95 委托采样（helper cache-or-compute——命中或首次采样，同 xdist_group 同 worker）。"""
    from tests.integration.test_integration_checkpoint_evaluation import sample_checkpoint_perf

    context["perf_summary"] = _run_async(context["_loop"], sample_checkpoint_perf())


@when("执行 P95 委托采样（warmup 1 + 20 采样 + quantiles exclusive [18]）")
def when_read_delegated_save_p95(context: dict[str, Any]) -> None:
    """读取 save P95 摘要（常量单源 import——验收侧禁双真源）。"""
    from tests.integration.test_integration_checkpoint_evaluation import CHECKPOINT_SAVE_P95_LIMIT_SECONDS

    context["save_p95_seconds"] = context["perf_summary"]["save_p95_seconds"]
    context["save_p95_limit"] = CHECKPOINT_SAVE_P95_LIMIT_SECONDS
    context["save_call_count"] = context["perf_summary"]["save_call_count"]
    context["prefill_count"] = context["perf_summary"]["prefill_count"]


@then("save P95 小于 100ms 断言通过（CHECKPOINT_SAVE_P95_LIMIT_SECONDS 常量单源）")
def then_save_p95_below_limit(context: dict[str, Any]) -> None:
    """save P95<100ms（epics L1883 钦定——record 全路径含真实 Redis 写）。"""
    assert context["save_p95_limit"] == 0.1, "CHECKPOINT_SAVE_P95_LIMIT_SECONDS 应为 0.1（常量单源）"
    assert context["save_p95_seconds"] < context["save_p95_limit"], (
        f"快照创建 P95 应 < {context['save_p95_limit']}s，实际 {context['save_p95_seconds']}s"
    )


@then("正向锚断言通过（采样批次 save 调用计数 == warmup + 采样数 21）")
def then_save_positive_anchor(context: dict[str, Any]) -> None:
    """正向锚（防静默跳过假绿——warmup 1 + 20 采样 == 21 次 save）。"""
    assert context["save_call_count"] == 21, (
        f"采样批次 save 调用计数应为 21（warmup 1 + 采样 20），实际 {context['save_call_count']}"
    )


@then("满窗锚断言通过（预填充 100 条历史经 record 公共路径——最大体积形态下双锚成立）")
def then_full_window_anchor(context: dict[str, Any]) -> None:
    """满窗锚（OD-8 窗口与性能耦合——100 条预填充经 record 公共路径不计时不计数）。"""
    assert context["prefill_count"] == 100, f"预填充应为 100 条（MAX_HISTORY_SIZE 满窗），实际 {context['prefill_count']}"


@given("集成计时委托模块已加载（_PERF_CACHE 委托采样——同批 20 采样）")
def given_query_delegate_loaded(context: dict[str, Any]) -> None:
    """query P95 委托（_PERF_CACHE["query_p95"] 同批命中或首次计算）。"""
    from tests.integration.test_integration_checkpoint_evaluation import sample_checkpoint_perf

    context["perf_summary"] = _run_async(context["_loop"], sample_checkpoint_perf())


@when("执行查询 P95 委托采样（完整 restore 调用——load + 解包）")
def when_read_delegated_query_p95(context: dict[str, Any]) -> None:
    """读取 query P95 摘要（常量单源 import）。"""
    from tests.integration.test_integration_checkpoint_evaluation import CHECKPOINT_QUERY_P95_LIMIT_SECONDS

    context["query_p95_seconds"] = context["perf_summary"]["query_p95_seconds"]
    context["query_p95_limit"] = CHECKPOINT_QUERY_P95_LIMIT_SECONDS
    context["load_call_count"] = context["perf_summary"]["load_call_count"]


@then("query P95 小于 50ms 断言通过（CHECKPOINT_QUERY_P95_LIMIT_SECONDS 常量单源）")
def then_query_p95_below_limit(context: dict[str, Any]) -> None:
    """query P95<50ms（epics L1884 钦定——restore 全路径 load+解包）。"""
    assert context["query_p95_limit"] == 0.05, "CHECKPOINT_QUERY_P95_LIMIT_SECONDS 应为 0.05（常量单源）"
    assert context["query_p95_seconds"] < context["query_p95_limit"], (
        f"评估历史查询 P95 应 < {context['query_p95_limit']}s，实际 {context['query_p95_seconds']}s"
    )


@then("正向锚断言通过（采样批次 load 调用计数 == warmup + 采样数 21）")
def then_query_positive_anchor(context: dict[str, Any]) -> None:
    """正向锚（warmup 复合构成——一轮 record+restore 双计数，warmup 后双锚各 21）。"""
    assert context["load_call_count"] == 21, (
        f"采样批次 load 调用计数应为 21（warmup 1 + 采样 20），实际 {context['load_call_count']}"
    )


@then("口径声明断言通过（save 含 Redis RTT / 满窗口径 / 本地 Redis 前提 / 门=回归绊线 / 20 样本方差五注记落 docstring）")
def then_caliber_declaration_docstring(context: dict[str, Any]) -> None:
    """口径声明五注记（集成模块 docstring——防后续误读）。"""
    import inspect

    from tests.integration import test_integration_checkpoint_evaluation as integration_module

    docstring = inspect.getdoc(integration_module) or ""
    for fragment in ("RTT", "满窗", "本地 Redis", "绊线", "20"):
        assert fragment in docstring, f"集成模块 docstring 应含口径注记「{fragment}」（实际缺）"


# ===================================================================
# 收尾: 完成清单逐项确认（Task 6 追加——14 终态）
# ===================================================================


@given("开发完成清单已就绪（src 2 新建 + 7 修改 + tests 7 新建 + 3 追加 + 6 存量签名同步）")
def given_completion_checklist_ready(context: dict[str, Any]) -> None:
    """完成清单登记（src/tests 交付面全枚举——存在性 + 文本锚双面）。"""
    context["src_new_files"] = [
        "src/application/ports/agent_checkpoint.py",
        "src/application/services/evaluation_checkpoint_recorder.py",
    ]
    context["src_modified_files"] = [
        "src/domain/exceptions/evaluation_exceptions.py",
        "src/domain/exceptions/_code_ranges.py",
        "src/domain/exceptions/__init__.py",
        "src/interfaces/api/exception_handlers.py",
        "src/application/use_cases/run_agent_workflow.py",
        "src/composition_root.py",
        "src/application/ports/__init__.py",
    ]
    context["test_new_files"] = [
        "tests/unit/application/test_agent_checkpoint_model.py",
        "tests/unit/application/services/test_evaluation_checkpoint_recorder.py",
        "tests/contracts/test_port_contract_agent_checkpoint.py",
        "tests/integration/test_integration_checkpoint_evaluation.py",
        "tests/unit/architecture/test_arch_checkpoint_evaluation.py",
        "tests/acceptance/test_acceptance_checkpoint_evaluation.feature",
        "tests/acceptance/test_acceptance_checkpoint_evaluation.py",
    ]
    context["test_modified_files"] = [
        "tests/unit/domain/exceptions/test_evaluation_exceptions.py",
        "tests/unit/application/use_cases/test_run_agent_workflow.py",
        "tests/unit/interfaces/api/test_exception_handlers.py",
        "tests/acceptance/test_acceptance_phoenix_tracer.py",
        "tests/unit/architecture/test_arch_phoenix_tracer.py",
        "tests/unit/architecture/test_arch_evaluation.py",
        "tests/unit/architecture/test_arch_drift_detection.py",
        "tests/acceptance/test_acceptance_agent_evaluation.py",
        "tests/acceptance/test_acceptance_drift_detection.py",
    ]


@when("逐项验证 src 与 tests 完成清单")
def when_verify_completion_checklist(context: dict[str, Any]) -> None:
    """存在性验证（逐文件 is_file——缺失即红）。"""
    for relative in context["src_new_files"] + context["src_modified_files"]:
        assert (REPO_ROOT / relative).is_file(), f"src 交付文件缺失: {relative}"
    for relative in context["test_new_files"] + context["test_modified_files"]:
        assert (REPO_ROOT / relative).is_file(), f"tests 交付文件缺失: {relative}"


@then("src 完成清单断言通过（agent_checkpoint 端口/Recorder 实现/452 四件套/主链第八依赖/组合根区段/ports 导出）")
def then_src_completion_anchors(context: dict[str, Any]) -> None:
    """src 文本锚（关键符号在位——主链 record 块 + 452 注册 + 组合根区段）。"""
    use_case_source = (REPO_ROOT / "src/application/use_cases/run_agent_workflow.py").read_text(encoding="utf-8")
    assert "checkpoint_recorder" in use_case_source, "run_agent_workflow.py 应含第八依赖 checkpoint_recorder"
    assert "result.evidence.confidence" in use_case_source, "record 块应有 predicted=result.evidence.confidence 引用"
    assert "EvaluationHistoryError" in use_case_source, "record 块应有内层 452 catch"

    exceptions_source = (REPO_ROOT / "src/domain/exceptions/evaluation_exceptions.py").read_text(encoding="utf-8")
    assert 'code = "EXCEPTION_452"' in exceptions_source, "EvaluationHistoryError 应为 EXCEPTION_452"

    composition_source = (REPO_ROOT / "src/composition_root.py").read_text(encoding="utf-8")
    assert 'name="agent_checkpoint"' in composition_source, "组合根应有 agent_checkpoint 注册区段"
    assert 'resolve_optional("agent_checkpoint")' in composition_source, "use case 工厂应有第八依赖接线"

    ports_init_source = (REPO_ROOT / "src/application/ports/__init__.py").read_text(encoding="utf-8")
    assert "AgentCheckpointPort" in ports_init_source, "ports __init__ 应导出 AgentCheckpointPort"
    assert "CheckpointWithEvaluation" in ports_init_source, "ports __init__ 应导出 CheckpointWithEvaluation"

    handlers_source = (REPO_ROOT / "src/interfaces/api/exception_handlers.py").read_text(encoding="utf-8")
    assert "EvaluationHistoryError" in handlers_source, "EXCEPTION_HTTP_MAP 应含 452 映射"


@then("tests 四目录完成清单断言通过（七件新建 + test_run_agent_workflow 追加块 + 452 异常用例 + expected_types + 存量同步 ×7）")
def then_tests_completion_anchors(context: dict[str, Any]) -> None:
    """tests 文本锚（断言同步 ×7 更新在位 + 452 用例 + expected_types 伴随）。"""
    sync_targets = {
        "tests/acceptance/test_acceptance_phoenix_tracer.py": '"checkpoint_recorder",  # Story 5.10 第八可选依赖',
        "tests/unit/architecture/test_arch_phoenix_tracer.py": '"checkpoint_recorder",  # Story 5.10 第八可选依赖',
        "tests/unit/architecture/test_arch_evaluation.py": '"checkpoint_recorder"',
        "tests/unit/architecture/test_arch_drift_detection.py": '"checkpoint_recorder"',
        "tests/unit/application/use_cases/test_run_agent_workflow.py": '"checkpoint_recorder"',
        "tests/acceptance/test_acceptance_agent_evaluation.py": '"checkpoint_recorder"',
        "tests/acceptance/test_acceptance_drift_detection.py": '"checkpoint_recorder"',
    }
    for relative, anchor in sync_targets.items():
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert anchor in source, f"{relative} 应含八依赖清单更新（断言同步 ×7——锚 {anchor!r}）"

    handlers_test_source = (REPO_ROOT / "tests/unit/interfaces/api/test_exception_handlers.py").read_text(encoding="utf-8")
    assert "EvaluationHistoryError" in handlers_test_source, "expected_types 应伴随追加 EvaluationHistoryError"

    exceptions_test_source = (REPO_ROOT / "tests/unit/domain/exceptions/test_evaluation_exceptions.py").read_text(
        encoding="utf-8"
    )
    assert "EXCEPTION_452" in exceptions_test_source, "452 用例应已追加"

    unit_test_source = (REPO_ROOT / "tests/unit/application/use_cases/test_run_agent_workflow.py").read_text(encoding="utf-8")
    assert "TestExecuteCheckpointBlock" in unit_test_source, "主链 record 块单测应已追加"

    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "MAX_HISTORY_SIZE" not in env_example, ".env.example 零改动（常量单源裁定）"
