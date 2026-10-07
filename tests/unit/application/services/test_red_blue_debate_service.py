"""Story 4.5 — RedBlueDebateService 应用服务单元测试

验证温度阶梯编排核心：双视角并发生成（gather）→ 分化度门控 →
风险视图合成 → 事件发布。

关键断言形态：
- 温度断言锚定 system_prompt 角色标记（独立于 temperature 的信号，
  防"按分派身份断言温度"循环论证——红蓝温度互换必红）
- 并发窗口断言（Fake side_effect 内 sleep 制造事件循环切换点 +
  start/end 时间戳窗口重叠——零耗时下并发/串行不可判别）
- 视角独立性断言限定两次 PerspectiveAnalysisSchema 调用（合成豁免）
- 事件发布双形态失败（PublishResult is_success=False 与 raise）不覆写结果

Mock 边界：仅 LLMClientPort / EventPublisher 端口适配器 Fake（spec 约束），
真实 DebateEvaluator + InMemoryDebateSessionRepository。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.services.debate_prompts import PERSPECTIVE_PROMPT_MAP
from src.application.services.debate_schemas import (
    ConsensusAreaSchema,
    DisagreementAreaSchema,
    PerspectiveAnalysisSchema,
    RiskViewSchema,
)
from src.application.services.red_blue_debate_service import (
    OVERLAP_HARD_THRESHOLD,
    OVERLAP_WARNING_THRESHOLD,
    TEMPERATURE_PROFILE,
    RedBlueDebateService,
)
from src.domain.entities.debate_session import DebateSessionState
from src.domain.events.debate_events import DebateCompleted
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.exceptions import DebateGenerationError, EntityValidationError, LLMAPIError
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.llm_client import LLMClientPort
from src.domain.services.debate_evaluator import DebateEvaluator
from src.domain.value_objects.debate import DebatePerspective, DebateTopic
from src.domain.value_objects.tool_execution import ExecutionContext
from src.infrastructure.storage.inmemory.debate_session_repository import InMemoryDebateSessionRepository

# 37 字无重复字符论点：蓝=红改第 23 字（"建立"→"独立"，实改"建"→"独"）→ J=34/38≈0.895 ∈ [0.80, 0.95) 警告区
_WARNING_RED_ARG = "东南亚市场窗口期正打开需果断布局渠道供应链并建立本地化运营团队抢占先发优势"
_WARNING_BLUE_ARG = "东南亚市场窗口期正打开需果断布局渠道供应链并建立本地化运营团队抢占先发优势".replace("建立", "独立")


def _make_topic(title: str = "公司是否应在下一财年进入东南亚市场") -> DebateTopic:
    """构造合法辩论议题"""
    return DebateTopic(
        tenant_id=uuid.uuid4(),
        title=title,
        background="东南亚数字经济增速全球领先，但本地化合规与渠道竞争存在不确定性。",
    )


def _make_execution_context(topic: DebateTopic) -> ExecutionContext:
    """构造执行上下文"""
    return ExecutionContext(tenant_id=topic.tenant_id)


def _make_red_schema(arguments: list[str] | None = None) -> PerspectiveAnalysisSchema:
    """构造红方 Schema 实例"""
    return PerspectiveAnalysisSchema(
        stance="应当立即进入东南亚市场抢占先机",
        arguments=arguments or ["市场窗口期稍纵即逝，先发优势决定长期格局", "本地竞品尚未形成垄断，进入成本处于低位"],
        risks=["初期投入可能超预算"],
        recommendations=["优先布局新加坡与印尼市场"],
        confidence=0.8,
    )


def _make_blue_schema(arguments: list[str] | None = None) -> PerspectiveAnalysisSchema:
    """构造蓝方 Schema 实例"""
    return PerspectiveAnalysisSchema(
        stance="应当延后观察再进入东南亚市场",
        arguments=arguments or ["合规与关税政策存在不确定性", "本地化运营能力尚未验证"],
        risks=["贸然进入可能造成沉没成本"],
        recommendations=["先以合作伙伴模式小规模试点"],
        confidence=0.6,
    )


def _make_risk_schema() -> RiskViewSchema:
    """构造风险全景 Schema 实例（overlap_rate 服务端注入，Schema 无该字段）"""
    return RiskViewSchema(
        consensus_areas=[
            ConsensusAreaSchema(area="市场潜力", description="双方认可东南亚市场增长潜力", confidence=0.9),
        ],
        disagreement_areas=[
            DisagreementAreaSchema(
                area="进入时机",
                red_position="立即进入抢占先机",
                blue_position="延后观察规避风险",
                risk_note="时机误判将放大投入风险",
            ),
        ],
        overall_risk_level="MEDIUM",
    )


def _make_fake_llm(
    red: Any,
    blue: Any,
    risk: Any,
    perspective_delay_sec: float = 0.05,
) -> Any:
    """构造 Fake LLM（按 response_schema 身份 + temperature 分派）

    记录六字段元组 (prompt, system_prompt, response_schema, temperature, start_ts, end_ts)
    挂到 _debate_calls 属性供温度/独立性/并发窗口断言。

    Args:
        red: 红方 Schema 实例或 Exception 实例（Exception 时红分支 raise）
        blue: 蓝方 Schema 实例或 Exception 实例
        risk: 合成 Schema 实例或 Exception 实例
        perspective_delay_sec: 视角分支 sleep（制造切换点，并发断言前置条件）
    """
    calls: list[tuple[str, str | None, type, float | None, float, float]] = []
    configs: list[Any] = []
    mock: Any = AsyncMock(spec=LLMClientPort)

    async def _structured_generate(
        prompt: str,
        response_schema: type,
        config: Any = None,
        system_prompt: str | None = None,
    ) -> Any:
        start_ts = time.perf_counter()
        try:
            temperature = config.temperature if config is not None else None
            if response_schema is PerspectiveAnalysisSchema:
                await asyncio.sleep(perspective_delay_sec)
                selected = red if temperature == TEMPERATURE_PROFILE["red"] else blue
                if isinstance(selected, Exception):
                    raise selected
                return selected
            if response_schema is RiskViewSchema:
                if isinstance(risk, Exception):
                    raise risk
                return risk
            raise AssertionError(f"未预期的 response_schema: {response_schema}")
        finally:
            end_ts = time.perf_counter()
            calls.append((prompt, system_prompt, response_schema, config.temperature if config else None, start_ts, end_ts))
            configs.append(config)

    mock.structured_generate.side_effect = _structured_generate
    mock._debate_calls = calls
    mock._debate_configs = configs
    return mock


def _make_publisher() -> AsyncMock:
    """构造 Fake EventPublisher（返回全通道成功 PublishResult）"""
    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish.return_value = PublishResult(
        event_id="evt-unit-success",
        results=(ChannelResult(channel_name="inmemory", success=True),),
    )
    return publisher


def _build_service(
    fake_llm: Any,
    publisher: AsyncMock | None = None,
    repository: InMemoryDebateSessionRepository | None = None,
) -> tuple[RedBlueDebateService, InMemoryDebateSessionRepository, AsyncMock]:
    """组装被测服务（真实 Evaluator/Repository + 端口 Fake）"""
    evaluator = DebateEvaluator()
    repo = repository if repository is not None else InMemoryDebateSessionRepository()
    event_publisher = publisher if publisher is not None else _make_publisher()
    service = RedBlueDebateService(
        llm_client=fake_llm,
        evaluator=evaluator,
        session_repository=repo,
        event_publisher=event_publisher,
    )
    return service, repo, event_publisher


# ===================================================================
# Happy path：三段结构
# ===================================================================


class TestHappyPath:
    async def test_result_three_sections(self) -> None:
        """Happy path：DebateResult 三段结构完整（red/blue/risk_view）"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        service, repo, _ = _build_service(fake_llm)
        topic = _make_topic()

        result = await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert result.debate_id == topic.debate_id
        assert result.topic_title == topic.title
        assert result.red_analysis.perspective is DebatePerspective.RED_AGGRESSIVE
        assert result.blue_analysis.perspective is DebatePerspective.BLUE_CONSERVATIVE
        assert result.red_analysis.stance == "应当立即进入东南亚市场抢占先机"
        assert result.blue_analysis.stance == "应当延后观察再进入东南亚市场"
        assert len(result.risk_view.consensus_areas) >= 1
        assert len(result.risk_view.disagreement_areas) >= 1
        assert result.risk_view.overall_risk_level == "MEDIUM"
        assert result.quality.overlap_rate == result.risk_view.overlap_rate
        assert result.quality.gain_rate is None
        assert result.quality.repetition_rate is None
        assert result.duration_ms >= 0

    async def test_session_state_transitions_persisted(self) -> None:
        """仓储状态追踪：终态 COMPLETED 且四字段回填（每次迁移后 save 纪律）"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        service, repo, _ = _build_service(fake_llm)
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        session = await repo.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.COMPLETED
        assert session.red_analysis is not None
        assert session.blue_analysis is not None
        assert session.risk_view is not None
        assert session.completed_at is not None
        assert session.state_version == 3  # IDLE→GENERATING→SYNTHESIZING→COMPLETED

    async def test_llm_called_three_times(self) -> None:
        """LLM 恰好调用 3 次（红 + 蓝 + 合成）"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert fake_llm.structured_generate.call_count == 3


# ===================================================================
# 温度阶梯（system_prompt 角色标记锚定）
# ===================================================================


class TestTemperatureProfile:
    async def test_temperature_anchored_by_system_prompt(self) -> None:
        """system_prompt 锚定：含"激进派"==0.8 / 含"保守派"==0.5 / 裁判==0.2"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        calls = fake_llm._debate_calls
        perspective_calls = [c for c in calls if c[2] is PerspectiveAnalysisSchema]
        synthesis_calls = [c for c in calls if c[2] is RiskViewSchema]
        assert len(perspective_calls) == 2
        assert len(synthesis_calls) == 1

        for _prompt, system_prompt, _schema, temperature, _s, _e in perspective_calls:
            assert system_prompt is not None
            if "激进派" in system_prompt:
                assert temperature == TEMPERATURE_PROFILE["red"], f"红视角（system_prompt 含激进派）温度 {temperature} 应为 0.8"
            if "保守派" in system_prompt:
                assert temperature == TEMPERATURE_PROFILE["blue"], (
                    f"蓝视角（system_prompt 含保守派）温度 {temperature} 应为 0.5"
                )
        for _prompt, system_prompt, _schema, temperature, _s, _e in synthesis_calls:
            assert "裁判" in (system_prompt or "")
            assert temperature == TEMPERATURE_PROFILE["synthesis"]

    async def test_temperature_swapped_implementation_would_fail(self) -> None:
        """判别力验证：红蓝温度互换时锚定断言必红（防循环论证的结构性验证）

        构造 swapped Fake（红温度 0.5 / 蓝 0.8 分派），正确实现的调用
        system_prompt 与温度错配 → 本测试的锚定逻辑应检测到异常形态。
        """
        # swapped Fake：temperature==0.5 → 红（与正确实现相反）
        swapped = AsyncMock(spec=LLMClientPort)

        async def _swapped_generate(prompt, response_schema, config=None, system_prompt=None):
            if response_schema is PerspectiveAnalysisSchema:
                await asyncio.sleep(0.01)
                temperature = config.temperature if config else None
                selected = _make_red_schema() if temperature == 0.5 else _make_blue_schema()
                return selected
            return _make_risk_schema()

        swapped.structured_generate.side_effect = _swapped_generate
        service, _, _ = _build_service(swapped)
        topic = _make_topic()

        result = await service.run_debate(topic=topic, context=_make_execution_context(topic))
        # 正确实现下 swapped Fake 返回的视角与 system_prompt 错配：
        # 红调用（system_prompt 含激进派、温度 0.8）命中 swapped 的 blue 分支
        assert result.red_analysis.stance == "应当延后观察再进入东南亚市场", (
            "swapped Fake 下红视角收到蓝方结果——若此断言失败说明实现温度传参与预期不符"
        )

    async def test_all_temperatures_sorted(self) -> None:
        """补充全量断言：三次温度 sorted == [0.2, 0.5, 0.8]（CI 可验证的温度阶梯证据）"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        temperatures = sorted(c[3] for c in fake_llm._debate_calls)
        assert temperatures == [0.2, 0.5, 0.8]

    async def test_per_call_timeout_passed(self) -> None:
        """per-call timeout 传递：默认 12.0（不依赖 LLMConfig 默认 600s）"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        for call_args in fake_llm.structured_generate.call_args_list:
            config = call_args.kwargs.get("config") or call_args.args[2]
            assert config is not None
            assert config.timeout == 12.0

    async def test_custom_per_call_timeout(self) -> None:
        """自定义 per_call_timeout_sec 生效"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        evaluator = DebateEvaluator()
        repo = InMemoryDebateSessionRepository()
        service = RedBlueDebateService(
            llm_client=fake_llm,
            evaluator=evaluator,
            session_repository=repo,
            event_publisher=_make_publisher(),
            per_call_timeout_sec=5.5,
        )
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        for call_args in fake_llm.structured_generate.call_args_list:
            config = call_args.kwargs.get("config") or call_args.args[2]
            assert config.timeout == 5.5

    async def test_base_config_connection_fields_inherited(self) -> None:
        """base_config 连接字段继承守护（R1-F03）：三次调用的 endpoint/api_key/model 与基底一致

        回归形态：_build_call_config 若改为直接 LLMConfig(temperature, timeout)
        丢弃 base（集成测试捕获过的真实缺陷形态），生产将静默丢失连接配置——
        本用例在 CI 可运行面守住 dataclasses.replace 的继承语义。
        """
        from src.domain.ports.llm_client import LLMConfig

        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        fake_api_key = "test-key"  # pragma: allowlist secret
        base = LLMConfig(model="test-model", endpoint="http://test-endpoint", api_key=fake_api_key, timeout=99.0)
        repo = InMemoryDebateSessionRepository()
        service = RedBlueDebateService(
            llm_client=fake_llm,
            evaluator=DebateEvaluator(),
            session_repository=repo,
            event_publisher=_make_publisher(),
            base_config=base,
        )
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        configs = list(fake_llm._debate_configs)
        assert len(configs) == 3
        for config in configs:
            # 连接字段继承基底（replace 派生新实例，值相等而非同一性）
            assert config.endpoint == "http://test-endpoint"
            assert config.api_key == f"{fake_api_key}"
            assert config.model == "test-model"
            # 温度与 timeout 按调用覆写（优先于 base.timeout=99.0）
            assert config.timeout == 12.0
        assert {c.temperature for c in configs} == {0.8, 0.5, 0.2}


# ===================================================================
# 红蓝并发（gather 窗口重叠）
# ===================================================================


class TestConcurrentGeneration:
    async def test_generation_windows_overlap(self) -> None:
        """红蓝生成窗口重叠（blue.start < red.end 且 red.start < blue.end——串行实现必红）"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema(), perspective_delay_sec=0.1)
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        calls = fake_llm._debate_calls
        perspective_calls = [c for c in calls if c[2] is PerspectiveAnalysisSchema]
        assert len(perspective_calls) == 2
        first, second = perspective_calls
        red_call = first if "激进派" in (first[1] or "") else second
        blue_call = second if red_call is first else first

        assert blue_call[4] < red_call[5], "蓝视角应在红视角结束前开始（并发证据缺失）"
        assert red_call[4] < blue_call[5], "红视角应在蓝视角结束前开始（并发证据缺失）"

    async def test_perspective_span_below_serial_threshold(self) -> None:
        """单边计时：视角窗口总跨度 < 1.8×delay（串行两次 ≈ 2×delay 必超标；1.8 留 CI 调度抖动余量）"""
        delay = 0.1
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema(), perspective_delay_sec=delay)
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        perspective_calls = [c for c in fake_llm._debate_calls if c[2] is PerspectiveAnalysisSchema]
        span = max(c[5] for c in perspective_calls) - min(c[4] for c in perspective_calls)
        assert span < 1.8 * delay, f"视角生成跨度 {span:.3f}s ≥ 1.8×delay，疑似串行实现"


# ===================================================================
# 视角独立性（生成阶段互相不可见，合成豁免）
# ===================================================================


class TestPerspectiveIndependence:
    async def test_generation_prompts_isolated(self) -> None:
        """红/蓝 prompt 与 system_prompt 互不含对方 stance/论点（防锚定偏差）"""
        red_schema = _make_red_schema()
        blue_schema = _make_blue_schema()
        fake_llm = _make_fake_llm(red_schema, blue_schema, _make_risk_schema())
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        calls = fake_llm._debate_calls
        perspective_calls = [c for c in calls if c[2] is PerspectiveAnalysisSchema]
        red_call = next(c for c in perspective_calls if "激进派" in (c[1] or ""))
        blue_call = next(c for c in perspective_calls if "保守派" in (c[1] or ""))

        for blue_argument in blue_schema.arguments:
            assert blue_argument not in red_call[0], "红视角 prompt 不应包含蓝方论点"
        for red_argument in red_schema.arguments:
            assert red_argument not in blue_call[0], "蓝视角 prompt 不应包含红方论点"
        assert blue_schema.stance not in red_call[0]
        assert red_schema.stance not in blue_call[0]

    async def test_synthesis_prompt_contains_both_sides(self) -> None:
        """合成调用豁免：user prompt 按设计同时含红蓝双方论点 JSON（对抗发生在合成阶段）"""
        red_schema = _make_red_schema()
        blue_schema = _make_blue_schema()
        fake_llm = _make_fake_llm(red_schema, blue_schema, _make_risk_schema())
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        synthesis_call = next(c for c in fake_llm._debate_calls if c[2] is RiskViewSchema)
        for red_argument in red_schema.arguments:
            assert red_argument in synthesis_call[0], "合成 prompt 应包含红方论点"
        for blue_argument in blue_schema.arguments:
            assert blue_argument in synthesis_call[0], "合成 prompt 应包含蓝方论点"

    async def test_prompt_uses_topic_and_background(self) -> None:
        """视角 user prompt 含议题与背景（议题信息承载）"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic(title="独特议题标识XYZ")

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        perspective_calls = [c for c in fake_llm._debate_calls if c[2] is PerspectiveAnalysisSchema]
        assert all("独特议题标识XYZ" in c[0] for c in perspective_calls)

    async def test_prompt_map_prompts_actually_used(self) -> None:
        """服务实际使用 PERSPECTIVE_PROMPT_MAP 的 system_prompt（模块接线验证）"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        await service.run_debate(topic=topic, context=_make_execution_context(topic))

        perspective_calls = [c for c in fake_llm._debate_calls if c[2] is PerspectiveAnalysisSchema]
        used_system_prompts = {c[1] for c in perspective_calls}
        expected_prompts = {
            PERSPECTIVE_PROMPT_MAP[DebatePerspective.RED_AGGRESSIVE]["system_prompt"],
            PERSPECTIVE_PROMPT_MAP[DebatePerspective.BLUE_CONSERVATIVE]["system_prompt"],
        }
        assert used_system_prompts == expected_prompts


# ===================================================================
# 事件发布
# ===================================================================


class TestEventPublish:
    async def test_debate_completed_published_once_with_fields(self) -> None:
        """DebateCompleted 发布一次 + 事件字段值断言"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        service, _, publisher = _build_service(fake_llm)
        topic = _make_topic()

        result = await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert publisher.publish.call_count == 1
        event = publisher.publish.call_args[0][0]
        assert isinstance(event, DebateCompleted)
        assert event.debate_id == result.debate_id
        assert event.tenant_id == topic.tenant_id
        assert event.topic_title == topic.title
        assert event.red_stance == result.red_analysis.stance
        assert event.blue_stance == result.blue_analysis.stance
        assert event.consensus_count == len(result.risk_view.consensus_areas)
        assert event.disagreement_count == len(result.risk_view.disagreement_areas)
        assert event.overlap_rate == result.risk_view.overlap_rate
        assert event.overall_risk_level == result.risk_view.overall_risk_level
        assert event.duration_ms == result.duration_ms
        assert event.temperature_profile == {"red": 0.8, "blue": 0.5, "synthesis": 0.2}

    async def test_publish_result_failure_does_not_override(self) -> None:
        """事件发布失败（PublishResult is_success=False）不覆写辩论结果"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        failing_publisher = AsyncMock(spec=EventPublisher)
        failing_publisher.publish.return_value = PublishResult(event_id="evt-all-failed", results=())
        service, _, _ = _build_service(fake_llm, publisher=failing_publisher)
        topic = _make_topic()

        result = await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert result is not None
        assert result.red_analysis is not None  # 辩论结果完好

    async def test_publish_raise_does_not_override(self) -> None:
        """事件发布抛异常（契约外防御）不覆写辩论结果"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        raising_publisher = AsyncMock(spec=EventPublisher)
        raising_publisher.publish.side_effect = RuntimeError("publisher crashed")
        service, _, _ = _build_service(fake_llm, publisher=raising_publisher)
        topic = _make_topic()

        result = await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert result is not None
        assert result.risk_view is not None

    async def test_thresholds_constants(self) -> None:
        """门控阈值常量（0.95 硬 / 0.80 警告）+ 温度阶梯常量（架构绊线）"""
        assert OVERLAP_HARD_THRESHOLD == 0.95
        assert OVERLAP_WARNING_THRESHOLD == 0.80
        assert TEMPERATURE_PROFILE == {"red": 0.8, "blue": 0.5, "synthesis": 0.2}


# ===================================================================
# get_debate_result 重建
# ===================================================================


class TestGetDebateResult:
    async def test_rebuild_from_completed_session(self) -> None:
        """COMPLETED 会话重建 DebateResult（quality/duration_ms 推导公式）"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
        service, repo, _ = _build_service(fake_llm)
        topic = _make_topic()

        original = await service.run_debate(topic=topic, context=_make_execution_context(topic))
        rebuilt = await service.get_debate_result(topic.debate_id)

        assert rebuilt is not None
        assert rebuilt.debate_id == original.debate_id
        assert rebuilt.topic_title == original.topic_title
        assert rebuilt.red_analysis.stance == original.red_analysis.stance
        assert rebuilt.blue_analysis.stance == original.blue_analysis.stance
        assert rebuilt.risk_view.overlap_rate == original.risk_view.overlap_rate
        assert rebuilt.quality.overlap_rate == original.risk_view.overlap_rate
        assert rebuilt.quality.gain_rate is None
        # duration_ms 重建语义（completed_at − started_at），非与原值全等
        session = await repo.get_by_id(topic.debate_id)
        assert session is not None and session.completed_at is not None
        expected_ms = round((session.completed_at - session.started_at).total_seconds() * 1000)
        assert rebuilt.duration_ms == expected_ms

    async def test_unknown_id_returns_none(self) -> None:
        """未知名返回 None"""
        service, _, _ = _build_service(_make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema()))
        assert await service.get_debate_result(uuid.uuid4()) is None

    async def test_failed_session_returns_none(self) -> None:
        """FAILED 会话（含未完成的中间态）返回 None——无 risk_view 数学上不可重建"""
        fake_llm = _make_fake_llm(_make_llm_error(), _make_blue_schema(), _make_risk_schema())
        service, repo, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateGenerationError):
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert await service.get_debate_result(topic.debate_id) is None


def _make_llm_error() -> LLMAPIError:
    """构造 LLM 底层异常"""
    return LLMAPIError(message="模拟 LLM API 失败")


# ===================================================================
# 异常路径与分化度门控（Task 7 循环 B）
# ===================================================================


class TestGenerationFailure:
    async def test_red_failure_raises_420_with_perspective(self) -> None:
        """红视角失败 → DebateGenerationError + context.perspective == red_aggressive"""
        fake_llm = _make_fake_llm(_make_llm_error(), _make_blue_schema(), _make_risk_schema())
        service, repo, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateGenerationError) as exc_info:
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert exc_info.value.code == "EXCEPTION_420"
        assert exc_info.value.context["perspective"] == "red_aggressive"
        assert exc_info.value.cause is not None
        assert isinstance(exc_info.value.cause, LLMAPIError)

        session = await repo.get_by_id(topic.debate_id)
        assert session is not None, "失败路径应落库"
        assert session.state is DebateSessionState.FAILED
        assert session.failure_reason is not None

    async def test_blue_failure_raises_420_with_perspective(self) -> None:
        """蓝视角对称用例：context.perspective == blue_conservative"""
        fake_llm = _make_fake_llm(_make_red_schema(), _make_llm_error(), _make_risk_schema())
        service, repo, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateGenerationError) as exc_info:
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert exc_info.value.context["perspective"] == "blue_conservative"
        session = await repo.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.FAILED

    async def test_generation_failure_cancels_sibling_task(self) -> None:
        """gather 异常语义：一方失败后兄弟任务被取消（防孤儿任务与 never retrieved 警告）"""
        fake_llm = AsyncMock(spec=LLMClientPort)

        async def _structured_generate(prompt, response_schema, config=None, system_prompt=None):
            temperature = config.temperature if config else None
            if response_schema is PerspectiveAnalysisSchema:
                if temperature == TEMPERATURE_PROFILE["red"]:
                    await asyncio.sleep(0.3)  # 红方慢：失败抛出后应被取消而非等满 0.3s
                    return _make_red_schema()
                await asyncio.sleep(0.02)
                raise _make_llm_error()  # 蓝方先失败
            return _make_risk_schema()

        fake_llm.structured_generate.side_effect = _structured_generate
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        start = time.perf_counter()
        with pytest.raises(DebateGenerationError):
            await service.run_debate(topic=topic, context=_make_execution_context(topic))
        elapsed = time.perf_counter() - start

        # gather 首异常立即传播不等兄弟；但失败清理段的第二 gather（return_exceptions=True）
        # 会等满未取消的红任务 0.3s——取消生效时远早于 0.3s（蓝方 0.02s + 取消传播）。
        # 计时守护的机理是第二 gather 的等待效应，非取消传播本身（R1-F08 勘正）。
        assert elapsed < 0.28, f"失败后耗时 {elapsed:.3f}s，疑似未取消兄弟任务（串行等满 0.3s）"


class TestSynthesisFailure:
    async def test_synthesis_failure_raises_421(self) -> None:
        """合成失败 → DebateSynthesisError + cause 链 + FAILED 落库"""
        from src.domain.exceptions import DebateSynthesisError

        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_llm_error())
        service, repo, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateSynthesisError) as exc_info:
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert exc_info.value.code == "EXCEPTION_421"
        assert exc_info.value.context["debate_id"] == str(topic.debate_id)
        assert exc_info.value.cause is not None

        session = await repo.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.FAILED
        assert session.failure_reason is not None


class TestDivergenceGate:
    async def test_identical_arguments_raises_422(self) -> None:
        """红蓝论点完全相同（J=1.0）→ DebateLowDivergenceError"""
        from src.domain.exceptions import DebateLowDivergenceError

        same_arguments = ["市场窗口期稍纵即逝需要果断投入资源抢占先机", "本地竞品尚未形成垄断进入成本处于低位"]
        fake_llm = _make_fake_llm(
            _make_red_schema(arguments=list(same_arguments)),
            _make_blue_schema(arguments=list(same_arguments)),
            _make_risk_schema(),
        )
        service, repo, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateLowDivergenceError) as exc_info:
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert exc_info.value.code == "EXCEPTION_422"
        assert exc_info.value.context["overlap_rate"] >= OVERLAP_HARD_THRESHOLD
        # 门控在合成前触发：LLM 仅 2 次调用（红+蓝，无合成）
        assert fake_llm.structured_generate.call_count == 2
        # session FAILED 落库
        session = await repo.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.FAILED

    async def test_warning_zone_no_raise_with_warnings(self) -> None:
        """0.80 ≤ 重叠率 < 0.95：不抛异常，risk_view.warnings 非空（J≈0.895 构造）"""
        fake_llm = _make_fake_llm(
            _make_red_schema(arguments=[_WARNING_RED_ARG]),
            _make_blue_schema(arguments=[_WARNING_BLUE_ARG]),
            _make_risk_schema(),
        )
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        result = await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert OVERLAP_WARNING_THRESHOLD <= result.risk_view.overlap_rate < OVERLAP_HARD_THRESHOLD
        assert result.risk_view.warnings, "警告区 RiskView.warnings 应非空"
        assert any("分化" in w or "重叠" in w for w in result.risk_view.warnings)
        # 停止生成失败：合成正常发生
        assert fake_llm.structured_generate.call_count == 3


class TestEntityValidationErrorNotWrapped:
    async def test_direct_vo_violation_propagates(self) -> None:
        """直接构造领域 VO 失败（242）不被服务吞掉——领域不变量的兜底验证

        Schema→VO 转换的 242 理论缝隙（Pydantic 过但 VO 败）由 Pydantic 与 VO
        约束对齐消解（NonEmptyStr 条目级校验，R1-F02），此处验证 242 的透传形态不经过服务包装。
        """
        with pytest.raises(EntityValidationError) as exc_info:
            DebateTopic(tenant_id=uuid.uuid4(), title="")
        assert exc_info.value.code == "EXCEPTION_242"

    async def test_perspective_to_domain_violation_marks_failed(self) -> None:
        """视角 Schema→VO 转换 242：session 转 FAILED 落库 + 透传（R1-F02 防御深度）

        Schema 加严后正常构造无法产生违规实例——用 model_construct（pydantic
        官方无校验构造 API）绕过 Schema 校验制造「Pydantic 过但 VO 败」形态，
        防端口实现返回手工构造的非法实例时 session 卡死 GENERATING。
        """
        invalid_red = PerspectiveAnalysisSchema.model_construct(
            stance="  ",  # 纯空白：VO strip 判空必拒
            arguments=["论点"],
            risks=[],
            recommendations=[],
            confidence=0.8,
        )
        fake_llm = _make_fake_llm(invalid_red, _make_blue_schema(), _make_risk_schema())
        service, repo, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(EntityValidationError) as exc_info:
            await service.run_debate(topic=topic, context=_make_execution_context(topic))
        assert exc_info.value.code == "EXCEPTION_242"

        session = await repo.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.FAILED
        # 精确断言分支身份语义（R3-MB 击杀——is not None 对空串恒真，实测存活过）
        assert session.failure_reason == "视角结构化输出领域不变量校验失败"

    async def test_risk_view_to_domain_violation_marks_failed(self) -> None:
        """合成侧 Schema→VO 转换 242：FAILED 落库 + 透传（:170-177 分支首次直接覆盖）

        同 model_construct 技巧：RiskViewSchema.consensus_areas=[] 绕过 Schema
        min_length=1，to_domain 构造 RiskView 时「共识区域至少 1 条」VO 不变量必拒。
        """
        invalid_risk = RiskViewSchema.model_construct(
            consensus_areas=[],
            disagreement_areas=[
                DisagreementAreaSchema(
                    area="进入时机",
                    red_position="立即进入",
                    blue_position="延后观察",
                    risk_note="时机误判放大投入风险",
                )
            ],
            overall_risk_level="MEDIUM",
        )
        fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), invalid_risk)
        service, repo, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(EntityValidationError) as exc_info:
            await service.run_debate(topic=topic, context=_make_execution_context(topic))
        assert exc_info.value.code == "EXCEPTION_242"

        session = await repo.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.FAILED
        # 精确断言分支身份语义（R3-MB2 击杀——区分合成侧与视角侧分支）
        assert session.failure_reason == "风险视图领域不变量校验失败"


# ===================================================================
# 异常包装边界（透传与兜底分支）
# ===================================================================


class TestExceptionWrappingBoundaries:
    async def test_llm_config_error_passthrough_on_generation(self) -> None:
        """LLMConfigError 透传不包装（配置错误非辩论领域异常）"""
        from src.domain.exceptions import LLMConfigError

        fake_llm = AsyncMock(spec=LLMClientPort)
        fake_llm.structured_generate.side_effect = LLMConfigError(config_key="api_key")
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(LLMConfigError):
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

    async def test_llm_config_error_passthrough_on_synthesis(self) -> None:
        """合成阶段 LLMConfigError 同样透传"""
        from src.domain.exceptions import LLMConfigError

        async def _generate(prompt, response_schema, config=None, system_prompt=None):
            if response_schema is RiskViewSchema:
                raise LLMConfigError(config_key="api_key")
            await asyncio.sleep(0.01)
            temperature = config.temperature if config else None
            return _make_red_schema() if temperature == 0.8 else _make_blue_schema()

        fake_llm = AsyncMock(spec=LLMClientPort)
        fake_llm.structured_generate.side_effect = _generate
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(LLMConfigError):
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

    async def test_unknown_exception_wrapped_as_420(self) -> None:
        """未知异常兜底包装为 DebateGenerationError（cause 链保留）"""
        fake_llm = AsyncMock(spec=LLMClientPort)
        fake_llm.structured_generate.side_effect = RuntimeError("unexpected crash")
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateGenerationError) as exc_info:
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert "RuntimeError" in exc_info.value.message
        assert isinstance(exc_info.value.cause, RuntimeError)

    async def test_unknown_exception_wrapped_as_421_on_synthesis(self) -> None:
        """合成阶段未知异常兜底包装为 DebateSynthesisError"""
        from src.domain.exceptions import DebateSynthesisError

        async def _generate(prompt, response_schema, config=None, system_prompt=None):
            if response_schema is RiskViewSchema:
                raise RuntimeError("synthesis crash")
            await asyncio.sleep(0.01)
            temperature = config.temperature if config else None
            return _make_red_schema() if temperature == 0.8 else _make_blue_schema()

        fake_llm = AsyncMock(spec=LLMClientPort)
        fake_llm.structured_generate.side_effect = _generate
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateSynthesisError) as exc_info:
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert isinstance(exc_info.value.cause, RuntimeError)

    async def test_non_schema_return_wrapped_as_420(self) -> None:
        """LLM 返回非 Schema 实例 → 包装为 DebateGenerationError（类型契约违反）"""
        fake_llm = AsyncMock(spec=LLMClientPort)
        fake_llm.structured_generate.return_value = "not-a-schema-instance"
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateGenerationError) as exc_info:
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert "不是 PerspectiveAnalysisSchema" in exc_info.value.message

    async def test_non_schema_return_wrapped_as_421_on_synthesis(self) -> None:
        """合成返回非 Schema 实例 → 包装为 DebateSynthesisError"""
        from src.domain.exceptions import DebateSynthesisError

        async def _generate(prompt, response_schema, config=None, system_prompt=None):
            if response_schema is RiskViewSchema:
                return "not-a-schema-instance"
            await asyncio.sleep(0.01)
            temperature = config.temperature if config else None
            return _make_red_schema() if temperature == 0.8 else _make_blue_schema()

        fake_llm = AsyncMock(spec=LLMClientPort)
        fake_llm.structured_generate.side_effect = _generate
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateSynthesisError) as exc_info:
            await service.run_debate(topic=topic, context=_make_execution_context(topic))

        assert "不是 RiskViewSchema" in exc_info.value.message
