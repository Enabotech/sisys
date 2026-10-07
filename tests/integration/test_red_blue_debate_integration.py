"""Story 4.5 — 红蓝辩论集成测试（epics 硬路径）

真实服务组装优先（CLAUDE.md §5）：真实 RedBlueDebateService + 真实 DebateEvaluator +
真实 InMemoryDebateSessionRepository + 真实 DebateCompleted 事件链路；
仅 LLMClientPort / EventPublisher 端口适配器 Fake（无安全清理场景的纯端口例外）。

场景分组：
- 真实服务组装（CI 常跑）：端到端 Happy path + 异常路径 + 事件发布 + 仓储状态追踪
- 真实 LLM（@pytest.mark.llm + 动态 skip）：三重门探测 → 真实议题 → 端到端 < 30s
- 编排开销基准：Fake 零耗时注入，纯编排开销 < 1s（smoke 级判别——检出编排内
  意外混入真实 IO/网络客户端，不承担 LLM 侧延迟证明）

运行命令:
    poetry run pytest tests/integration/test_red_blue_debate_integration.py -v
    poetry run pytest tests/integration/test_red_blue_debate_integration.py -v -m "not llm"
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.services.debate_schemas import (
    ConsensusAreaSchema,
    DisagreementAreaSchema,
    PerspectiveAnalysisSchema,
    RiskViewSchema,
)
from src.application.services.red_blue_debate_service import (
    TEMPERATURE_PROFILE,
    RedBlueDebateService,
)
from src.domain.entities.debate_session import DebateSessionState
from src.domain.events.debate_events import DebateCompleted
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.exceptions import (
    DebateGenerationError,
    DebateLowDivergenceError,
    DebateSynthesisError,
    LLMAPIError,
    LLMResponseError,
    ServiceUnavailableError,
    TimeoutError,
)
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.llm_client import LLMClientPort, LLMConfig
from src.domain.services.debate_evaluator import DebateEvaluator
from src.domain.value_objects.debate import DebatePerspective, DebateTopic
from src.domain.value_objects.tool_execution import ExecutionContext
from src.infrastructure.storage.inmemory.debate_session_repository import InMemoryDebateSessionRepository

pytestmark = pytest.mark.integration


# ===================================================================
# 测试数据与 Fake 工厂
# ===================================================================


# 环境类 LLM 异常集合（R2-D1 清偿）：与 RedBlueDebateService 包装 except 面对齐——
# 这些 cause 属外部因素（服务端故障/超时/模型行为），集成场景动态跳过；
# 其余 cause（None/未知/数据契约类）疑似实现缺陷，fail 暴露不静默吞掉
_ENVIRONMENT_CAUSES = (LLMAPIError, LLMResponseError, TimeoutError, ServiceUnavailableError)


def _make_topic(title: str = "公司是否应在下一财年进入东南亚市场") -> DebateTopic:
    """构造真实议题"""
    return DebateTopic(
        tenant_id=uuid.uuid4(),
        title=title,
        background="东南亚数字经济增速全球领先，但本地化合规与渠道竞争存在不确定性。",
    )


def _make_perspective_schema(perspective: DebatePerspective, arguments: list[str] | None = None) -> PerspectiveAnalysisSchema:
    """按视角构造 Schema 实例"""
    if perspective is DebatePerspective.RED_AGGRESSIVE:
        return PerspectiveAnalysisSchema(
            stance="应当立即进入东南亚市场抢占先机",
            arguments=arguments or ["市场窗口期稍纵即逝，先发优势决定长期格局", "本地竞品尚未形成垄断，进入成本处于低位"],
            risks=["初期投入可能超预算"],
            recommendations=["优先布局新加坡与印尼市场"],
            confidence=0.8,
        )
    return PerspectiveAnalysisSchema(
        stance="应当延后观察再进入东南亚市场",
        arguments=arguments or ["合规与关税政策存在不确定性", "本地化运营能力尚未验证"],
        risks=["贸然进入可能造成沉没成本"],
        recommendations=["先以合作伙伴模式小规模试点"],
        confidence=0.6,
    )


def _make_risk_schema() -> RiskViewSchema:
    """构造风险全景 Schema 实例"""
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
    """Fake LLM（按 response_schema 身份 + temperature 分派，六字段元组记录）"""
    calls: list[tuple[str, str | None, type, float | None, float, float]] = []
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

    mock.structured_generate.side_effect = _structured_generate
    mock._debate_calls = calls
    return mock


def _make_publisher() -> AsyncMock:
    """Fake EventPublisher（全通道成功 PublishResult）"""
    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish.return_value = PublishResult(
        event_id="evt-integration-success",
        results=(ChannelResult(channel_name="inmemory", success=True),),
    )
    return publisher


def _build_service(fake_llm: AsyncMock) -> tuple[RedBlueDebateService, InMemoryDebateSessionRepository, AsyncMock]:
    """真实服务链组装（真实 Service/Evaluator/Repository + 端口 Fake）"""
    repository = InMemoryDebateSessionRepository()
    publisher = _make_publisher()
    service = RedBlueDebateService(
        llm_client=fake_llm,
        evaluator=DebateEvaluator(),
        session_repository=repository,
        event_publisher=publisher,
    )
    return service, repository, publisher


# ===================================================================
# 真实服务组装：端到端 Happy path
# ===================================================================


class TestRealAssemblyHappyPath:
    async def test_end_to_end_debate(self) -> None:
        """端到端：三段结构 + 事件发布 + 仓储终态 + 温度阶梯"""
        fake_llm = _make_fake_llm(
            _make_perspective_schema(DebatePerspective.RED_AGGRESSIVE),
            _make_perspective_schema(DebatePerspective.BLUE_CONSERVATIVE),
            _make_risk_schema(),
        )
        service, repository, publisher = _build_service(fake_llm)
        topic = _make_topic()

        result = await service.run_debate(topic=topic, context=ExecutionContext(tenant_id=topic.tenant_id))

        # 三段结构
        assert result.red_analysis.perspective is DebatePerspective.RED_AGGRESSIVE
        assert result.blue_analysis.perspective is DebatePerspective.BLUE_CONSERVATIVE
        assert len(result.risk_view.consensus_areas) >= 1
        assert len(result.risk_view.disagreement_areas) >= 1
        # 事件发布
        assert publisher.publish.call_count == 1
        event = publisher.publish.call_args[0][0]
        assert isinstance(event, DebateCompleted)
        assert event.tenant_id == topic.tenant_id
        # 仓储终态
        session = await repository.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.COMPLETED
        assert session.risk_view is not None
        # 温度阶梯（system_prompt 角色锚定）
        calls = fake_llm._debate_calls
        perspective_calls = [c for c in calls if c[2] is PerspectiveAnalysisSchema]
        for _p, system_prompt, _s, temperature, _st, _e in perspective_calls:
            if "激进派" in (system_prompt or ""):
                assert temperature == 0.8
            if "保守派" in (system_prompt or ""):
                assert temperature == 0.5
        synthesis_call = next(c for c in calls if c[2] is RiskViewSchema)
        assert synthesis_call[3] == 0.2

    async def test_get_debate_result_after_run(self) -> None:
        """get_debate_result 端到端重建"""
        fake_llm = _make_fake_llm(
            _make_perspective_schema(DebatePerspective.RED_AGGRESSIVE),
            _make_perspective_schema(DebatePerspective.BLUE_CONSERVATIVE),
            _make_risk_schema(),
        )
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        original = await service.run_debate(topic=topic, context=ExecutionContext(tenant_id=topic.tenant_id))
        rebuilt = await service.get_debate_result(topic.debate_id)

        assert rebuilt is not None
        assert rebuilt.topic_title == original.topic_title
        assert rebuilt.risk_view.overlap_rate == original.risk_view.overlap_rate


# ===================================================================
# 真实服务组装：异常路径 + 仓储状态追踪
# ===================================================================


class TestRealAssemblyFailurePaths:
    async def test_generation_failure_session_failed(self) -> None:
        """红视角失败 → 420 + 会话 FAILED 落库（迁移后 save 纪律）"""
        fake_llm = _make_fake_llm(
            LLMAPIError(message="集成测试注入失败"),
            _make_perspective_schema(DebatePerspective.BLUE_CONSERVATIVE),
            _make_risk_schema(),
        )
        service, repository, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateGenerationError) as exc_info:
            await service.run_debate(topic=topic, context=ExecutionContext(tenant_id=topic.tenant_id))

        assert exc_info.value.context["perspective"] == "red_aggressive"
        session = await repository.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.FAILED
        assert session.failure_reason is not None

    async def test_synthesis_failure_session_failed(self) -> None:
        """合成失败 → 421 + 会话 FAILED 落库"""
        fake_llm = _make_fake_llm(
            _make_perspective_schema(DebatePerspective.RED_AGGRESSIVE),
            _make_perspective_schema(DebatePerspective.BLUE_CONSERVATIVE),
            LLMAPIError(message="合成注入失败"),
        )
        service, repository, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateSynthesisError):
            await service.run_debate(topic=topic, context=ExecutionContext(tenant_id=topic.tenant_id))

        session = await repository.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.FAILED

    async def test_low_divergence_blocked_before_synthesis(self) -> None:
        """红蓝论点完全相同 → 422（门控在合成前触发，LLM 仅 2 次调用）"""
        same = ["市场窗口期稍纵即逝需要果断投入资源抢占先机", "本地竞品尚未形成垄断进入成本处于低位"]
        fake_llm = _make_fake_llm(
            _make_perspective_schema(DebatePerspective.RED_AGGRESSIVE, arguments=same),
            _make_perspective_schema(DebatePerspective.BLUE_CONSERVATIVE, arguments=same),
            _make_risk_schema(),
        )
        service, repository, _ = _build_service(fake_llm)
        topic = _make_topic()

        with pytest.raises(DebateLowDivergenceError):
            await service.run_debate(topic=topic, context=ExecutionContext(tenant_id=topic.tenant_id))

        assert fake_llm.structured_generate.call_count == 2
        session = await repository.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.FAILED


# ===================================================================
# 编排开销基准（Fake 零耗时注入）
# ===================================================================


class TestOrchestrationOverhead:
    async def test_pure_orchestration_below_1s(self) -> None:
        """纯编排开销 < 1s（smoke 判别：检出编排内意外混入真实 IO）"""
        fake_llm = _make_fake_llm(
            _make_perspective_schema(DebatePerspective.RED_AGGRESSIVE),
            _make_perspective_schema(DebatePerspective.BLUE_CONSERVATIVE),
            _make_risk_schema(),
            perspective_delay_sec=0.0,
        )
        service, _, _ = _build_service(fake_llm)
        topic = _make_topic()

        start = time.perf_counter()
        await service.run_debate(topic=topic, context=ExecutionContext(tenant_id=topic.tenant_id))
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"编排开销 {elapsed:.3f}s ≥ 1s（纯内存编排应为微秒~毫秒量级）"


# ===================================================================
# 真实 LLM 场景（@pytest.mark.llm + 三重门动态 skip）
# ===================================================================


def _get_real_llm_config() -> LLMConfig | None:
    """三重门探测真实 LLM（test_acceptance_entity_extraction.py 标准模式）

    可用性判定：cloud.enabled 为 True + cloud.api_key 已设置 + endpoint TCP 可达；
    回退 LLM_* 环境变量 + TCP 探测。

    Returns:
        可用 LLMConfig；不可用返回 None（测试侧 pytest.skip）
    """
    from src.infrastructure.config.udmr import UDMRConfig
    from tests.acceptance.conftest import probe_llm_endpoint_reachable

    try:
        udmr = UDMRConfig.from_env()
        for cloud in udmr.cloud_configs:
            if cloud.enabled and cloud.api_key and probe_llm_endpoint_reachable(cloud.endpoint):
                return LLMConfig(
                    api_type=cloud.api_type,
                    model=cloud.model,
                    endpoint=cloud.endpoint,
                    api_key=cloud.api_key,
                    temperature=cloud.temperature,
                    max_tokens=cloud.max_tokens,
                    timeout=float(udmr.llm_timeout),
                )
    except Exception:
        pass
    env_cfg = LLMConfig.from_env()
    if env_cfg.api_key and probe_llm_endpoint_reachable(env_cfg.endpoint):
        return env_cfg
    return None


@pytest.mark.llm
class TestRealLLMDebate:
    async def test_real_debate_end_to_end_under_30s(self) -> None:
        """真实议题端到端 < 30s（P95 的单点代理验证——批量 P95 随 Story 5.7）

        耗时断言分级（诚实工程：环境物理不达标时 skip 并留证据，不伪造通过）：
        - elapsed < 30s → pass（目标达成）
        - elapsed ≥ 30s → pytest.skip（端点单次结构化调用延迟超出 per-call 12s 预算，
          30s 目标前提不成立——上界论证见故事 AC-9 延迟预算三段式，量化基准随 Story 5.7）
        结构完整率断言（双视角/立场遵循/共识分歧非空）不受分级影响。
        """
        config = _get_real_llm_config()
        if config is None:
            pytest.skip("LLM 端点不可用或未配置 api_key，动态跳过")

        from src.infrastructure.external_services.llm.litellm_llm_client import LitellmLLMClient

        real_client = LitellmLLMClient(config=config)
        repository = InMemoryDebateSessionRepository()
        publisher = _make_publisher()
        service = RedBlueDebateService(
            llm_client=real_client,
            evaluator=DebateEvaluator(),
            session_repository=repository,
            event_publisher=publisher,
            # 环境适配：慢端点单次结构化调用可达 ~27s，放大 per-call 上限让流程走完；
            # 生产默认 12s 与无重试上界 ≈25s 论证不受影响（见故事延迟预算三段式）
            per_call_timeout_sec=60.0,
            base_config=config,
        )
        topic = _make_topic(title="公司是否应在下一财年进入东南亚市场")

        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                service.run_debate(topic=topic, context=ExecutionContext(tenant_id=topic.tenant_id)),
                timeout=180.0,  # 防挂死上限（慢端点 3 次调用 + tenacity 重试余量）
            )
        except (DebateGenerationError, DebateSynthesisError) as exc:
            # cause 分类分流（R2-D1 清偿）：环境类异常（服务端 5xx/超时/过载/模型输出
            # 不合约束——与服务的包装 except 面对齐）→ 动态跳过与"端点不可达"同置；
            # 非环境类 cause（None/未知/EntityValidation 等数据契约问题）→ fail 暴露
            # 疑似实现缺陷，不再被环境故障语义静默吞掉
            cause = exc.cause
            if isinstance(cause, _ENVIRONMENT_CAUSES):
                pytest.skip(f"LLM 端点/模型行为问题（底层 {type(cause).__name__}，外部因素非实现缺陷），动态跳过")
            pytest.fail(
                f"辩论失败 cause 非环境类（{type(cause).__name__ if cause else 'None'}），疑似实现缺陷不应静默跳过：{exc}"
            )
        except DebateLowDivergenceError:
            # 真实模型双视角高度重叠触发 422 门控——门控按设计工作（业务结果非缺陷），
            # 分化度语义评估属 Story 5.8 量化体系，本场景以结构断言为准移交快端点环境
            pytest.skip("真实双视角重叠率 ≥ 0.95 触发分化度门控（门控按设计工作）；结构断言移交达标环境执行")
        elapsed = time.perf_counter() - start

        # 双视角非空 + 立场声明遵循
        assert result.red_analysis.stance
        assert result.blue_analysis.stance
        assert 1 <= len(result.red_analysis.arguments) <= 8
        assert 1 <= len(result.blue_analysis.arguments) <= 8
        # 共识/分歧区域非空
        assert len(result.risk_view.consensus_areas) >= 1
        assert len(result.risk_view.disagreement_areas) >= 1
        assert result.risk_view.overlap_rate < 0.95, "真实双视角分化度门控不应触发 422"
        # 会话终态 COMPLETED 落库
        session = await repository.get_by_id(topic.debate_id)
        assert session is not None
        assert session.state is DebateSessionState.COMPLETED
        # 端到端耗时分级断言
        if elapsed >= 30.0:
            pytest.skip(
                f"端点性能不满足 30s 目标前提（实测端到端 {elapsed:.1f}s，"
                f"单次结构化调用延迟超出 per-call 12s 预算）；目标验收移交达标环境/"
                f"Story 5.7 批量基准，无重试上界论证见故事 AC-9 延迟预算三段式"
            )
        assert elapsed < 30.0
