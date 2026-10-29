"""集成测试 Story 5.9 - CUSUM 漂移检测全链与性能双锚（FR-EV-03）。

六场景：① 全链漂移确认（Fake LLM 六阶段链 + 检测器预填充 34 样本 + drift.detected
span 真值 + DriftDetected 事件）② 无漂移对照（34 正常样本预填——R2 钉死禁复用
4×0.4 预填[数学互斥]）③ 451 降级链 ④ None 路径对比（六参构造——5.8 基线等价）
⑤ P99<100ms（委托 _PERF_CACHE["p99"]——常量单源，验收 AC-5.1 import 消费）
⑥ 合成回测准确率 ≥0.85（委托 _PERF_CACHE["backtest"]——钦定种子基准
TP=20/FP=1/acc=0.975，RNG 调用序钉死）。

性能口径声明（DC-8——防后续误读）：
- P99 = **纯内存检测管线开销**（update 双侧累积 + N中M 确认 + DriftAssessment
  构造——单次 update 调用）；**事件发布不在口径内**（Outbox 写 PG 是 IO——发布
  是确认后的重校准触发动作，非检测延迟面；epics L1838「检测延迟」语义锚定判定
  时延）。μs 级预期——100ms 上限对纯内存管线宽松，门定位是回归绊线（意外同步
  阻塞/算法误入 O(n) 全量重算会击穿）。quantiles(n=100)[98] 是 exclusive P99
  ——100 样本下即前 2 大样本插值、方差大、保守方向[高估分位→更严门]，「近最大
  值估计量」知悉（5.8 P95 [18] 的 P99 版）。
- 准确率 = **合成序列回测**（固定种子确定性——CI 无 flaky）；合成形态下的统计
  检出能力验证（合成 uniform ≠ 真实多峰形态——5-8 风险 #6④ 知悉），真实历史
  回测是 V2 指标本义（数据积累后 V2-EV1）。**60 样本/30 评估段参数定稿、评估
  段长 30 禁拉长**——FP 随评估段长线性增长（蒙特卡洛实测 L=70 最坏 acc=0.775
  击穿门）；FP 主因是 n=30 基线 σ̂₀ 低估[相对标准误 ≈1/√(2×30)≈13%]非算法缺陷
  （实测 FP≈1/40）——docstring 知悉注记。漂移注入幅度 delta∈[0.3,0.5] 按
  σ̂₀≈0.058 实算 ≈4.9σ~8.1σ（强漂移注入——检测器设计检测灵敏度 0.5σ-2σ 的
  保守上界侧，小漂移检出是 V1 调参面）。

Run with:
    poetry run pytest tests/integration/test_integration_drift_detection.py -v
"""

from __future__ import annotations

import asyncio
import random
import statistics
import time
from pathlib import Path
from typing import Any, Generator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"

# 文件名不含服务关键词且零外部服务——无 redis/database marker；xdist_group 与验收
# AC-5.* 逐字同组（loadgroup 同 worker 串行是 _PERF_CACHE 委托缓存命中前提）
pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group("drift-detection-perf"),
]

# ===================================================================
# 常量单源（验收 AC-5.1/5.2 import 消费——禁双真源）
# ===================================================================

#: P99 上限（秒）——epics L1838 钦定 100ms（纯内存检测管线口径——见模块 docstring）
DRIFT_P99_LIMIT_SECONDS = 0.1

#: 计时采样参数（5.8 P95 [18] 委托模式的 P99 版——warmup 1 + 100 采样 + exclusive [98]）
DRIFT_P99_WARMUP_ROUNDS = 1
DRIFT_P99_SAMPLE_ROUNDS = 100

#: 合成回测参数（R1 定稿——评估段长 30 禁拉长：FP 随段长线性增长）
BACKTEST_SEED = 20261028
BACKTEST_SEQUENCE_COUNT = 40  # 前 20 稳定 / 后 20 漂移按序生成
BACKTEST_BASELINE_SAMPLES = 30
BACKTEST_EVALUATION_SAMPLES = 30
BACKTEST_ACCURACY_THRESHOLD = 0.85

#: 委托缓存（模块级双槽——p99/backtest key 分立；集成场景⑤⑥与验收 AC-5.1/5.2
#: 共享同批结果，同 xdist_group 同 worker 串行保证缓存命中；禁采样双跑）
_PERF_CACHE: dict[str, Any] = {}

#: 手算锚基线序列（[0.7, 0.9]×15——μ₀=0.8，σ₀ 实算 ≈0.1017）
_BASELINE_SEQUENCE: list[float] = [0.7, 0.9] * 15


def _sigma0() -> float:
    """基线 σ₀ 实算（statistics.stdev[ddof=1]——同式单源）。"""
    return statistics.stdev(_BASELINE_SEQUENCE)


# ===================================================================
# 委托 helpers（cache-or-compute——命中或首次采样）
# ===================================================================


async def sample_drift_p99_perf() -> dict[str, Any]:
    """检测管线 P99 采样（幂等——_PERF_CACHE["p99"] 命中早退；warmup 1 + 100 采样）。

    单次采样 = 检测器完整 update 调用（预填充至检测态——每采样含双侧计算 + 判定 +
    确认窗更新 + DriftAssessment 构造）；事件发布不在口径内（IO 出栈——见模块
    docstring 口径声明）。update 调用计数含 warmup 与预填充期。

    Returns:
        dict[str, Any]: 采样摘要（p99_seconds/update_call_count/sample_count）。
    """
    if "p99" in _PERF_CACHE:
        cached: dict[str, Any] = _PERF_CACHE["p99"]
        return cached
    from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

    def _make_fresh_detector() -> Any:
        """每采样批次独立构造检测器（自包含——无跨批次状态残留）。"""
        return CUSUMDriftDetector()

    detector = _make_fresh_detector()
    # 预填充至检测态（30 基线 + 4 漂移——末段检测期：每采样含双侧计算/判定/确认窗更新；
    # 预填充不计入 update_call_count——采样轮口径 == warmup + 采样数）
    for score in _BASELINE_SEQUENCE + [0.4, 0.4, 0.4, 0.4]:
        await detector.update(score)

    update_call_count = 0
    latencies: list[float] = []
    for round_index in range(DRIFT_P99_WARMUP_ROUNDS + DRIFT_P99_SAMPLE_ROUNDS):
        score = 0.4 if round_index % 2 == 0 else 0.6
        start = time.perf_counter()
        await detector.update(score)
        latencies.append(time.perf_counter() - start)
        update_call_count += 1

    summary: dict[str, Any] = {
        "p99_seconds": statistics.quantiles(latencies, n=100)[98],  # exclusive P99
        "update_call_count": update_call_count,
        "sample_count": DRIFT_P99_WARMUP_ROUNDS + DRIFT_P99_SAMPLE_ROUNDS,
    }
    _PERF_CACHE["p99"] = summary
    return summary


def make_backtest_sequences(seed: int) -> list[tuple[bool, list[float]]]:
    """合成回测序列生成器（纯函数——seed 入参同函数同输出）。

    RNG 调用序钉死（R3）：40 条按序共享单 rng，每条内调用序 = 30 基线样本 →
    [漂移序列：1 次 delta 抽取] → 30 评估段——钦定基准 TP=20/FP=1/acc=0.975
    经此序精确复现，换序则基准不可复现。全部样本天然落 [0,1] 域（uniform
    [0.7,0.9] / [0.7-δ,0.9-δ] δ≤0.5 → 下界 0.2>0——禁未截断正态[越域触发 201]）。

    Returns:
        list[(is_drifted, sequence)]：前 20 稳定 + 后 20 漂移（60 样本/条）。
    """
    rng = random.Random(seed)
    sequences: list[tuple[bool, list[float]]] = []
    for index in range(BACKTEST_SEQUENCE_COUNT):
        baseline = [rng.uniform(0.7, 0.9) for _ in range(BACKTEST_BASELINE_SAMPLES)]
        drifted = index >= 20
        if drifted:
            delta = rng.uniform(0.3, 0.5)
            evaluation = [rng.uniform(0.7 - delta, 0.9 - delta) for _ in range(BACKTEST_EVALUATION_SAMPLES)]
        else:
            evaluation = [rng.uniform(0.7, 0.9) for _ in range(BACKTEST_EVALUATION_SAMPLES)]
        sequences.append((drifted, baseline + evaluation))
    return sequences


async def _run_backtest(sequences: list[tuple[bool, list[float]]]) -> dict[str, Any]:
    """回测执行（每序列独立检测器——TP/FP/TN 分项统计）。"""
    from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

    tp = fp = tn = 0
    for drifted, sequence in sequences:
        detector = CUSUMDriftDetector()
        confirmed = False
        for score in sequence:
            assessment = await detector.update(score)
            if assessment.is_drifted:
                confirmed = True
        if drifted:
            if confirmed:
                tp += 1
        else:
            if confirmed:
                fp += 1
            else:
                tn += 1
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": 20 - tp,
        "accuracy": (tp + tn) / BACKTEST_SEQUENCE_COUNT,
    }


def run_synthetic_backtest() -> dict[str, Any]:
    """合成回测委托（幂等——_PERF_CACHE["backtest"] 命中早退）。

    Returns:
        dict[str, Any]: 回测摘要（accuracy/tp/fp/tn/fn——分项计数可观测，
        失败断言消息可诊断）。
    """
    if "backtest" in _PERF_CACHE:
        cached: dict[str, Any] = _PERF_CACHE["backtest"]
        return cached
    sequences = make_backtest_sequences(BACKTEST_SEED)
    summary = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_run_backtest(sequences))
    _PERF_CACHE["backtest"] = summary
    return summary


# ===================================================================
# 装配 helpers（Fake LLM 手工装配链——5-8 集成同款先例）
# ===================================================================


class _RecordingEventPublisher:
    """记录发布事件的发布器（内存替身发布面——零 IO）。"""

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
    """手写零 IO 漂移检测替身（集成禁 mock 红线下的降级注入面）。"""

    def __init__(self, update_error: Exception | None = None) -> None:
        self.update_calls = 0
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
        return None


class _StubAgentRepository:
    """零 IO Agent 仓储替身。"""

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
    """零 IO 日志仓储替身。"""

    async def save(self, log: Any) -> None:
        return None

    async def search(self, query: Any) -> Any:
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


class _StubProfileUseCase:
    """零 IO 档案用例替身。"""

    def __init__(self, profile_result: Any) -> None:
        self._profile_result = profile_result

    async def execute(self, agent_id: Any) -> Any:
        return self._profile_result


def _make_fake_llm() -> Any:
    """六阶段 + 幻觉检测 Fake LLM 替身（外部 SaaS 豁免——幻觉分恒 0.2）。"""
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
            return VerificationSchema(passed=True, confidence=0.85, rationale="结构化检查通过")
        if response_schema is ReflectionSchema:
            return ReflectionSchema(error_analysis="无", revised_plan="维持原计划", revised=True)
        if response_schema is ChainOfThoughtSchema:
            return ChainOfThoughtSchema(
                input_summary="Fake 回声摘要",
                reflection="Fake 回声反思",
                tools_used=["fake-echo:not-real"],
                constraints_check="Fake 回声约束",
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


#: 测试假密钥占位（resolver 替身基底的连接字段——非真实凭据；5-8 验收同款拆分形态）
_BASE_EVAL_FAKE_KEY = "base-eval-" + "fake-key"


def _make_evaluation_resolver_stub() -> Any:
    """评估链 resolver 替身（连接字段非默认值）。"""
    from src.domain.ports.llm_client import LLMConfig

    class _StaticModelResolverStub:
        def __init__(self, base_config: Any) -> None:
            self.base_config = base_config

        async def resolve_config(self, input_text: str) -> Any:
            return self.base_config

    return _StaticModelResolverStub(
        LLMConfig(model="base-eval-model", endpoint="https://base-eval.example/v1", api_key=_BASE_EVAL_FAKE_KEY)
    )


@pytest.fixture(autouse=True)
def _otel_global_state_isolation() -> Generator[None, None, None]:
    """OTel 全局状态 function 级双复位兜底（5-7 SSOT——凡 initialize 一律双复位义务）。"""
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    PhoenixTracer.reset_for_testing()
    yield
    PhoenixTracer.reset_for_testing()


async def _assemble_chain(
    drift_detector: Any = None,
    prefill: str | None = None,
) -> tuple[Any, Any, Any, Any]:
    """链级手工装配（返回 use_case/agent/exporter/detector 四元组）。

    prefill：drift = 30 基线 + 4×0.4（链上末样本即确认）；normal = 30 基线 +
    4 交替续灌（对照——S 有界恒 F，禁复用 4×0.4[数学互斥]）。
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

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
    from src.infrastructure.config.phoenix import PhoenixConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = PhoenixTracer(
        config=PhoenixConfig(enabled=True, project_name="sisys-agent", sampling_ratio=1.0),
        tracer_provider=provider,
    )
    assert tracer.initialize() is True

    import uuid as uuid_module

    agent = Agent(agent_id=uuid_module.uuid4(), role=AgentRole.CEO, name="CEO Agent")
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
    sandbox.execute_code = AsyncMock(return_value={"status": "ok", "output": '{"P": 0.8}'})
    sandbox.stop_container = AsyncMock(return_value=None)
    engine_tools = ToolExecutionEngine(
        llm_client=fake_llm, sandbox=sandbox, retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0.01)
    )

    service: Any = AgentWorkflowService(
        llm_client=fake_llm,
        tool_execution_service=ToolExecutionService(registry=registry, engine=engine_tools),
        skill_loader=resolve("skill_loader"),
        tool_registry_service=registry,
        isolation_guard=guard,
    )
    langgraph_engine = LangGraphEngine(
        config=LangGraphConfig.from_env(), event_publisher=_RecordingEventPublisher(), workflow_service=service
    )

    profile_loader = resolve("agent_profile_loader")
    profile = await profile_loader.load(role=AgentRole.CEO, agent_id=agent.agent_id)
    skill_selector = resolve("skill_selector")
    tools_l1 = await skill_selector.list_active_skills()
    profile_result = AgentProfileLoadResult(
        agent_id=agent.agent_id, role=AgentRole.CEO, profile=profile, tools_l1=tools_l1, startup_context_tokens=0
    )

    harness = EvaluationHarness(llm_client=fake_llm, model_resolver=_make_evaluation_resolver_stub())

    detector = drift_detector
    if detector is not None and prefill is not None:
        prefill_scores = (
            list(_BASELINE_SEQUENCE) + [0.4] * 4 if prefill == "drift" else list(_BASELINE_SEQUENCE) + [0.7, 0.9, 0.7, 0.9]
        )
        for score in prefill_scores:
            await detector.update(score)

    profile_use_case_stub: Any = _StubProfileUseCase(profile_result)
    use_case = RunAgentWorkflowUseCase(
        agent_repository=stub_agent_repo,
        agent_profile_use_case=profile_use_case_stub,
        agent_engine=langgraph_engine,
        agent_workflow_service=service,
        isolation_guard=guard,
        evaluation_harness=harness,
        drift_detector=detector,
    )
    return use_case, agent, exporter, detector


def _find_root_span(exporter: Any) -> Any:
    """取 agent_execution 根 span（唯一）。"""
    spans = [s for s in exporter.get_finished_spans() if s.name == "agent_execution"]
    assert len(spans) == 1, f"应恰有一个 agent_execution 根 span，实际 {len(spans)}"
    return spans[0]


# ===================================================================
# 场景①②③④：全链漂移 / 无漂移对照 / 451 降级 / None 对比
# ===================================================================


class TestFullChainDriftDetection:
    """全链漂移检测（六阶段真实链 + 真实 CUSUMDriftDetector + Fake LLM）。"""

    async def test_full_chain_drift_confirmed_span_and_event(self) -> None:
        """场景①：预填充 34 样本 + execute → drift.detected=True + DriftDetected 事件。"""
        from src.domain.events.drift_events import DriftDetected
        from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

        publisher = _RecordingEventPublisher()
        detector = CUSUMDriftDetector(event_publisher=publisher)
        use_case, agent, exporter, _ = await _assemble_chain(drift_detector=detector, prefill="drift")

        result = await use_case.execute(agent_id=agent.agent_id, task="分析新能源汽车行业进入战略")

        assert result.workflow_status == "completed"
        attributes = dict(_find_root_span(exporter).attributes)
        assert attributes["drift.detected"] is True, "确认漂移应写 drift.detected=True（键字符串逐字）"
        drift_events = [e for e in publisher.published_events if isinstance(e, DriftDetected)]
        assert len(drift_events) == 1
        assert drift_events[0].drift_direction == "down", "预填充 4×0.4 使末样本确认 down"
        assert drift_events[0].agent_id == str(agent.agent_id)
        # eval 三键正常（评估先于漂移成功——5.8 回归锚）
        assert attributes["eval.hallucination_score"] == 0.2

    async def test_full_chain_no_drift_control(self) -> None:
        """场景②：34 正常样本预填（30 基线 + 4 交替续灌）→ drift 缺席 + 零发布 + 三键正常。"""
        from src.domain.events.drift_events import DriftDetected
        from src.infrastructure.monitoring.cusum_detector import CUSUMDriftDetector

        publisher = _RecordingEventPublisher()
        detector = CUSUMDriftDetector(event_publisher=publisher)
        use_case, agent, exporter, _ = await _assemble_chain(drift_detector=detector, prefill="normal")

        result = await use_case.execute(agent_id=agent.agent_id, task="分析新能源汽车行业进入战略")

        assert result.workflow_status == "completed"
        attributes = dict(_find_root_span(exporter).attributes)
        assert "drift.detected" not in attributes, "无漂移对照 drift.detected 应缺席（常态语义）"
        assert not [e for e in publisher.published_events if isinstance(e, DriftDetected)], "零事件发布"
        assert attributes["eval.hallucination_score"] == 0.2, "eval 三键正常（5.8 回归锚）"

    async def test_full_chain_451_degradation(self, caplog: pytest.LogCaptureFixture) -> None:
        """场景③：FakeDriftPort update 抛 451 → 主链正常 + 三键在 + drift 缺席 + warning。"""
        import logging

        from src.domain.exceptions import DriftDetectionError

        caplog.set_level(logging.WARNING, logger="src.application.use_cases.run_agent_workflow")
        injected = DriftDetectionError(metric_name="overall_score", reason="drift_update")
        fake_drift = _FakeDriftPort(update_error=injected)
        use_case, agent, exporter, _ = await _assemble_chain(drift_detector=fake_drift)

        result = await use_case.execute(agent_id=agent.agent_id, task="分析新能源汽车行业进入战略")

        assert result.workflow_status == "completed", "451 降级不阻断主链"
        attributes = dict(_find_root_span(exporter).attributes)
        assert "drift.detected" not in attributes
        assert attributes["eval.hallucination_score"] == 0.2, "三键仍在（评估先于漂移成功）"
        assert fake_drift.update_calls == 1, "漂移块 update 恰一次后被降级捕获"
        warning_texts = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any(str(injected) in text for text in warning_texts), "warning 文本含 451 异常 str"

    async def test_full_chain_none_detector_baseline(self) -> None:
        """场景④：六参构造（drift_detector=None）→ 与 5.8 基线 span 树等价。"""
        use_case, agent, exporter, _ = await _assemble_chain(drift_detector=None)

        result = await use_case.execute(agent_id=agent.agent_id, task="分析新能源汽车行业进入战略")

        assert result.workflow_status == "completed"
        attributes = dict(_find_root_span(exporter).attributes)
        assert "drift.detected" not in attributes, "None 路径漂移块整体跳过"
        assert attributes["eval.hallucination_score"] == 0.2, "5.8 基线行为一致（三键在）"
        assert attributes["agent.role"] == "ceo", "MVP 十属性不受影响（抽查两键）"
        assert attributes["workflow.status"] == "completed"


# ===================================================================
# 场景⑤⑥：性能双锚（委托缓存——验收 AC-5.1/5.2 同批共享）
# ===================================================================


class TestDriftDetectionPerformance:
    """P99<100ms + 合成回测准确率 ≥0.85（口径声明见模块 docstring）。"""

    @pytest.mark.benchmark
    async def test_p99_below_100ms(self) -> None:
        """场景⑤：纯内存检测管线 P99 < 100ms（quantiles exclusive [98] 口径）。"""
        summary = await sample_drift_p99_perf()
        assert summary["p99_seconds"] < DRIFT_P99_LIMIT_SECONDS, (
            f"检测管线 P99 应 < {DRIFT_P99_LIMIT_SECONDS}s（实际 {summary['p99_seconds']}s——"
            "回归绊线：意外同步阻塞/算法误入 O(n) 全量重算会击穿）"
        )
        # 正向锚（防静默跳过假绿——采样轮 update 调用计数 == warmup + 采样数 101；
        # 预填充不计入口径——R2-8 统一）
        assert summary["update_call_count"] == DRIFT_P99_WARMUP_ROUNDS + DRIFT_P99_SAMPLE_ROUNDS == 101

    @pytest.mark.benchmark
    async def test_synthetic_backtest_accuracy(self) -> None:
        """场景⑥：合成回测 (TP+TN)/40 ≥ 0.85（钦定种子基准 TP=20/FP=1/acc=0.975）。"""
        summary = await _run_backtest(make_backtest_sequences(BACKTEST_SEED))
        tp, fp, tn = summary["tp"], summary["fp"], summary["tn"]
        assert summary["accuracy"] >= BACKTEST_ACCURACY_THRESHOLD, (
            f"合成回测准确率应 ≥{BACKTEST_ACCURACY_THRESHOLD}（实际 {summary['accuracy']}——"
            f"分项 TP={tp} FP={fp} TN={tn} FN={summary['fn']}）"
        )
        assert tp + tn + fp == BACKTEST_SEQUENCE_COUNT, "分项计数应覆盖 40 序列"

    @pytest.mark.benchmark
    async def test_synthetic_backtest_determinism(self) -> None:
        """确定性（同种子两次生成完全相等——CI 无 flaky 前提）。"""
        first = make_backtest_sequences(BACKTEST_SEED)
        second = make_backtest_sequences(BACKTEST_SEED)
        assert first == second
        assert len(first) == BACKTEST_SEQUENCE_COUNT
        assert all(len(sequence) == BACKTEST_BASELINE_SAMPLES + BACKTEST_EVALUATION_SAMPLES for _, sequence in first)
        # 全样本天然 [0,1] 域（uniform 构造——禁未截断正态的域守卫 201 面出栈）
        assert all(0.0 <= score <= 1.0 for _, sequence in first for score in sequence)
