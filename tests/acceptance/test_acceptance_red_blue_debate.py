"""Story 4.5 红蓝辩论机制基础 — 验收测试（BDD 步骤实现）

本文件遵循项目验收测试规范（R6 模板 test_acceptance_postgresql_relational_layer.py 的
@scenario 显式绑定模式 + 4.1a 的 context dict 跨步骤传递模式组合）：

- 步骤函数使用 @given / @when / @then 装饰器 + context: dict[str, Any] fixture
- 使用真实服务实例：真实 RedBlueDebateService + DebateEvaluator + InMemoryDebateSessionRepository
  + 真实 DebateCompleted 领域事件（仅 LLMClientPort / EventPublisher 端口适配器 Fake——
  CLAUDE.md §5 允许面：mock 仅限无安全清理场景的纯端口适配器）
- 步骤严格按 AC 顺序（AC-1 ~ AC-9 + 收尾验收），`# ====` 分隔
- 异常处理：使用 try/except 捕获到 context["query_error"]，Then 步骤断言 isinstance + error.code
- **禁止 mock** 核心域服务（CLAUDE.md §5 红线）；**禁止** @pytest.mark.asyncio（context 数据丢失
  红线）——步骤函数为同步 def，经模块级 event_loop fixture 的 run_until_complete() 驱动
- Fake LLM 按 response_schema 身份分派（PerspectiveAnalysisSchema + temperature 区分红蓝 /
  RiskViewSchema 合成），**禁止**按 system_prompt 子串分派（裁判 prompt 同时含红蓝标记必误路由）

运行命令:
    poetry run pytest tests/acceptance/test_acceptance_red_blue_debate.py -v
"""

from __future__ import annotations

import ast
import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenario, then, when

from src.application.services.debate_prompts import PERSPECTIVE_PROMPT_MAP, SYNTHESIS_SYSTEM_PROMPT
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
from src.domain.entities.debate_session import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    DebateSession,
    DebateSessionState,
)
from src.domain.events.debate_events import DebateCompleted
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.exceptions import (
    DebateGenerationError,
    DebateLowDivergenceError,
    DebateSynthesisError,
    EntityStateTransitionError,
    EntityValidationError,
    LLMAPIError,
)
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.llm_client import LLMClientPort
from src.domain.services.debate_evaluator import DebateEvaluator
from src.domain.value_objects.debate import (
    ConsensusArea,
    DebatePerspective,
    DebateQuality,
    DebateResult,
    DebateTopic,
    DisagreementArea,
    PerspectiveAnalysis,
    RiskView,
)
from src.domain.value_objects.tool_execution import ExecutionContext

# ============================================================================
# @scenario 显式绑定（R6 模板模式，36 个场景）
# ============================================================================


@scenario("test_acceptance_red_blue_debate.feature", "AC-1.1 - 合法构造全部辩论值对象与枚举")
def test_ac_1_1_valid_vos() -> None:
    """AC-1.1 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-1.2 - 组1议题边界校验（title 空/超 200、background 超 8000）")
def test_ac_1_2_topic_boundary() -> None:
    """AC-1.2 场景绑定"""


@scenario(
    "test_acceptance_red_blue_debate.feature",
    "AC-1.3 - 组2视角分析校验（stance 空/arguments 0 与 9 条/含空串/confidence 越界）",
)
def test_ac_1_3_perspective_validation() -> None:
    """AC-1.3 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-1.4 - 组3区域字段校验（area 空/描述类字段空串）")
def test_ac_1_4_area_fields() -> None:
    """AC-1.4 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-1.5 - 组4风险视图校验（区域空/risk_level 非法/overlap_rate 越界）")
def test_ac_1_5_risk_view_validation() -> None:
    """AC-1.5 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-1.6 - 组5质量与结果校验（DebateQuality 越界/duration_ms 负数）")
def test_ac_1_6_quality_result_validation() -> None:
    """AC-1.6 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-2.1 - 状态机合法全路径迁移与 state_version 递增")
def test_ac_2_1_legal_transitions() -> None:
    """AC-2.1 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-2.2 - 非法状态迁移抛 EntityStateTransitionError")
def test_ac_2_2_illegal_transition() -> None:
    """AC-2.2 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-2.3 - 终态不变量违反抛 EntityValidationError")
def test_ac_2_3_terminal_invariants() -> None:
    """AC-2.3 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-3.1 - DebateGenerationError 构造与上下文")
def test_ac_3_1_generation_error() -> None:
    """AC-3.1 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-3.2 - DebateSynthesisError 构造与上下文")
def test_ac_3_2_synthesis_error() -> None:
    """AC-3.2 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-3.3 - DebateLowDivergenceError 构造与上下文")
def test_ac_3_3_low_divergence_error() -> None:
    """AC-3.3 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-3.4 - 三异常 HTTP 状态码映射（500/500/422）")
def test_ac_3_4_http_mapping() -> None:
    """AC-3.4 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-4.1 - compute_repetition_rate 已知值与空文本边界")
def test_ac_4_1_repetition_rate() -> None:
    """AC-4.1 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-4.2 - compute_gain_rate 已知值与空文本边界")
def test_ac_4_2_gain_rate() -> None:
    """AC-4.2 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-4.3 - evaluate_overlap 两极值与中文用例")
def test_ac_4_3_overlap_extremes() -> None:
    """AC-4.3 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-4.4 - 空文本与空 bigram 并集边界返回 0.0")
def test_ac_4_4_empty_bigram() -> None:
    """AC-4.4 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-5.1 - 仓储 save→get_by_id roundtrip")
def test_ac_5_1_repository_roundtrip() -> None:
    """AC-5.1 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-5.2 - 未知名查询返回 None")
def test_ac_5_2_unknown_id_none() -> None:
    """AC-5.2 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-5.3 - 50 并发保存零丢失")
def test_ac_5_3_concurrent_saves() -> None:
    """AC-5.3 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-6.1 - DebateCompleted 事件构造与 to_dict/from_dict roundtrip")
def test_ac_6_1_event_roundtrip() -> None:
    """AC-6.1 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-6.2 - 双通道登记 YAML 与 DEFAULT_MAPPINGS 一致")
def test_ac_6_2_channel_mapping() -> None:
    """AC-6.2 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-7.1 - Happy path 辩论结果三段结构完整")
def test_ac_7_1_happy_path() -> None:
    """AC-7.1 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-7.2 - 温度阶梯 system_prompt 角色锚定断言（红 0.8/蓝 0.5/合成 0.2）")
def test_ac_7_2_temperature_profile() -> None:
    """AC-7.2 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-7.3 - 红蓝生成时间窗口重叠（gather 并发）")
def test_ac_7_3_concurrent_windows() -> None:
    """AC-7.3 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-7.4 - 视角互相不可见（合成调用豁免）")
def test_ac_7_4_perspective_independence() -> None:
    """AC-7.4 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-7.5 - 红视角生成失败抛 DebateGenerationError")
def test_ac_7_5_generation_failure() -> None:
    """AC-7.5 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-7.6 - 合成失败抛 DebateSynthesisError")
def test_ac_7_6_synthesis_failure() -> None:
    """AC-7.6 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-7.7 - 红蓝论点完全相同抛 DebateLowDivergenceError")
def test_ac_7_7_low_divergence() -> None:
    """AC-7.7 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-7.8 - 分化警告区（0.80≤重叠率<0.95）不抛异常")
def test_ac_7_8_warning_zone() -> None:
    """AC-7.8 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-7.9 - 事件发布字段断言")
def test_ac_7_9_event_publish() -> None:
    """AC-7.9 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-8.1 - 三端口注册与 PortSpec 元数据完整")
def test_ac_8_1_port_specs() -> None:
    """AC-8.1 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-8.2 - Resolver 解析真实服务实例")
def test_ac_8_2_resolver_instances() -> None:
    """AC-8.2 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-9.1 - 领域零依赖与温度常量对齐")
def test_ac_9_1_architecture_scan() -> None:
    """AC-9.1 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "AC-9.2 - 纯编排开销小于 1 秒")
def test_ac_9_2_orchestration_overhead() -> None:
    """AC-9.2 场景绑定"""


@scenario("test_acceptance_red_blue_debate.feature", "收尾 - 覆盖率门禁达标")
def test_final_coverage_gate() -> None:
    """收尾验收场景绑定"""


# ============================================================================
# fixtures
# ============================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态"""
    return {}


@pytest.fixture(scope="module")
def event_loop():
    """模块级事件循环，用于 run_until_complete()"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# 测试数据构造（Fake LLM 返回的 Schema 实例与议题）
# ============================================================================

# 37 字无重复字符论点（保证 bigram 无坍缩）：改第 20 字"应"→"变"后
# J = (36-2)/(36+2) = 34/38 ≈ 0.895 ∈ [0.80, 0.95) 警告区
_WARNING_RED_ARG = "东南亚市场窗口期正打开需果断布局渠道供应链并建立本地化运营团队抢占先发优势"
_WARNING_BLUE_ARG = "东南亚市场窗口期正打开需果断布局渠道供应链并变立本地化运营团队抢占先发优势"


def _make_topic(title: str = "公司是否应在下一财年进入东南亚市场") -> DebateTopic:
    """构造合法辩论议题（测试唯一 debate_id 由调用方捕获）"""
    return DebateTopic(
        tenant_id=uuid.uuid4(),
        title=title,
        background="东南亚数字经济增速全球领先，但本地化合规与渠道竞争存在不确定性。",
    )


def _make_red_schema(arguments: list[str] | None = None) -> PerspectiveAnalysisSchema:
    """构造红方（激进派）视角 Schema 实例"""
    return PerspectiveAnalysisSchema(
        stance="应当立即进入东南亚市场抢占先机",
        arguments=arguments or ["市场窗口期稍纵即逝，先发优势决定长期格局", "本地竞品尚未形成垄断，进入成本处于低位"],
        risks=["初期投入可能超预算"],
        recommendations=["优先布局新加坡与印尼市场"],
        confidence=0.8,
    )


def _make_blue_schema(arguments: list[str] | None = None) -> PerspectiveAnalysisSchema:
    """构造蓝方（保守派）视角 Schema 实例"""
    return PerspectiveAnalysisSchema(
        stance="应当延后观察再进入东南亚市场",
        arguments=arguments or ["合规与关税政策存在不确定性", "本地化运营能力尚未验证"],
        risks=["贸然进入可能造成沉没成本"],
        recommendations=["先以合作伙伴模式小规模试点"],
        confidence=0.6,
    )


def _make_risk_schema() -> RiskViewSchema:
    """构造风险全景视图合成 Schema 实例（overlap_rate 由服务端注入，Schema 无该字段）"""
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
    """构造 Fake LLM 客户端（按 response_schema 身份 + temperature 分派）

    Args:
        red: 红方 Schema 实例或 Exception 实例（Exception 时红视角分支 raise）
        blue: 蓝方 Schema 实例或 Exception 实例
        risk: 合成 Schema 实例或 Exception 实例
        perspective_delay_sec: 视角分支内 sleep 秒数（制造事件循环切换点，
            并发窗口断言的前置条件——零耗时下并发与串行不可判别）

    Returns:
        AsyncMock(spec=LLMClientPort)，挂 _debate_calls 属性记录六字段元组
        (prompt, system_prompt, response_schema, temperature, start_ts, end_ts)；
        另挂 _debate_configs 平行列表记录完整 config 对象（timeout 断言用，
        与六字段元组互不影响——R1-F06）
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
                # 视角分支：制造事件循环切换点，供并发窗口断言
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
    """构造 Fake EventPublisher（返回全通道成功的 PublishResult）"""
    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish.return_value = PublishResult(
        event_id="evt-bdd-success",
        results=(ChannelResult(channel_name="inmemory", success=True),),
    )
    return publisher


def _build_service(
    fake_llm: AsyncMock,
    publisher: AsyncMock | None = None,
) -> tuple[RedBlueDebateService, Any, AsyncMock]:
    """组装真实服务链（真实 Service/Evaluator/Repository + 端口 Fake）"""
    from src.infrastructure.storage.inmemory.debate_session_repository import InMemoryDebateSessionRepository

    evaluator = DebateEvaluator()
    repository = InMemoryDebateSessionRepository()
    event_publisher = publisher if publisher is not None else _make_publisher()
    service = RedBlueDebateService(
        llm_client=fake_llm,
        evaluator=evaluator,
        session_repository=repository,
        event_publisher=event_publisher,
    )
    return service, repository, event_publisher


# ============================================================================
# AC-1: 领域值对象与枚举 + 不变量校验
# ============================================================================


@given("红蓝辩论领域类型与服务已初始化")
def given_debate_types_ready(context: dict[str, Any]) -> None:
    """背景步骤：类型经顶部 import 已就绪，初始化共享状态容器"""
    context.setdefault("vo_errors", [])


@given("一组合法的辩论领域构造输入")
def given_valid_vo_inputs(context: dict[str, Any]) -> None:
    """准备合法构造基准数据（越界用例在其基础上覆写单一维度）"""
    context["tenant_id"] = uuid.uuid4()


@given("一个新建的辩论会话聚合根")
def given_new_debate_session(context: dict[str, Any]) -> None:
    """构造 IDLE 状态的辩论会话聚合根"""
    context["session"] = DebateSession(
        debate_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        title="公司是否应在下一财年进入东南亚市场",
    )


@when("构造全部辩论值对象合法实例")
def when_construct_all_valid_vos(context: dict[str, Any]) -> None:
    """构造 8 类型合法实例（7 frozen VO + 1 枚举）"""
    red = PerspectiveAnalysis(
        perspective=DebatePerspective.RED_AGGRESSIVE,
        stance="应当立即进入",
        arguments=("窗口期稍纵即逝",),
        risks=("初期投入高",),
        recommendations=("优先布局核心市场",),
        confidence=0.8,
    )
    blue = PerspectiveAnalysis(
        perspective=DebatePerspective.BLUE_CONSERVATIVE,
        stance="应当延后观察",
        arguments=("政策不确定性高",),
        risks=(),
        recommendations=(),
        confidence=0.6,
    )
    consensus = ConsensusArea(area="市场潜力", description="双方认可增长潜力", confidence=0.9)
    disagreement = DisagreementArea(
        area="进入时机",
        red_position="立即进入",
        blue_position="延后观察",
        risk_note="时机误判放大投入风险",
    )
    risk_view = RiskView(
        consensus_areas=(consensus,),
        disagreement_areas=(disagreement,),
        overall_risk_level="MEDIUM",
        overlap_rate=0.35,
    )
    context["valid_instances"] = {
        "topic": _make_topic(),
        "red": red,
        "blue": blue,
        "consensus": consensus,
        "disagreement": disagreement,
        "risk_view": risk_view,
        "quality": DebateQuality(overlap_rate=0.35),
        "result": DebateResult(
            debate_id=uuid.uuid4(),
            topic_title="测试议题",
            red_analysis=red,
            blue_analysis=blue,
            risk_view=risk_view,
            quality=DebateQuality(overlap_rate=0.35),
            duration_ms=100,
        ),
        "perspective_enum": DebatePerspective.RED_AGGRESSIVE,
    }


@then("全部实例字段完整且不可变")
def then_all_instances_valid_and_frozen(context: dict[str, Any]) -> None:
    """断言字段值符合预期且 frozen（setattr 抛 FrozenInstanceError）"""
    import dataclasses

    instances = context["valid_instances"]
    assert instances["topic"].title == "公司是否应在下一财年进入东南亚市场"
    assert instances["red"].perspective is DebatePerspective.RED_AGGRESSIVE
    assert instances["blue"].perspective is DebatePerspective.BLUE_CONSERVATIVE
    assert instances["risk_view"].overall_risk_level == "MEDIUM"
    assert instances["quality"].gain_rate is None and instances["quality"].repetition_rate is None
    assert instances["result"].duration_ms == 100
    # 枚举成员完整
    assert {p.value for p in DebatePerspective} == {"red_aggressive", "blue_conservative"}
    # 全部 dataclass 实例 frozen（setattr 触发 FrozenInstanceError）
    for name, instance in instances.items():
        if name == "perspective_enum" or not dataclasses.is_dataclass(instance):
            continue
        field_name = next(iter(f.name for f in dataclasses.fields(instance)))
        try:
            setattr(instance, field_name, None)  # frozen 下应抛 FrozenInstanceError
            raise AssertionError(f"{name} 应为 frozen dataclass")
        except dataclasses.FrozenInstanceError:
            pass


def _expect_entity_validation_error(context: dict[str, Any], cases: list[tuple[str, Any]]) -> None:
    """逐条子约束触发构造并断言 EntityValidationError（242）的共用助手

    Args:
        context: BDD 共享状态
        cases: (用例名, 构造 callable) 列表，构造 callable 应抛 EntityValidationError

    Note:
        每条用例断言通过后 append 用例名到 context["vo_errors"]（R1-F06 接线）——
        Then「抛出 EntityValidationError」据此断言本场景至少验证 1 条 242 用例。
    """
    for case_name, factory in cases:
        try:
            factory()
        except EntityValidationError as exc:
            assert exc.code == "EXCEPTION_242", f"{case_name}: code={exc.code}"
            context["vo_errors"].append(case_name)
        else:
            raise AssertionError(f"{case_name}: 应抛 EntityValidationError")


@when("以越界参数构造 DebateTopic")
def when_construct_invalid_topic(context: dict[str, Any]) -> None:
    """组 1 议题边界：title 空/201 字、background 8001 字（每条子约束独立触发）"""
    tenant_id = context["tenant_id"]

    def make(title: str = "合法议题", background: str = "") -> DebateTopic:
        return DebateTopic(tenant_id=tenant_id, title=title, background=background)

    _expect_entity_validation_error(
        context,
        [
            ("title 空串", lambda: make(title="")),
            ("title 201 字", lambda: make(title="议" * 201)),
            ("background 8001 字", lambda: make(background="景" * 8001)),
        ],
    )


@when("以越界参数构造 PerspectiveAnalysis")
def when_construct_invalid_perspective(context: dict[str, Any]) -> None:
    """组 2 视角校验：stance 空/arguments 0 与 9 条/含空串/confidence 越界/枚举非法"""

    def make(
        stance: str = "合法立场",
        arguments: tuple = ("论点一",),
        confidence: float = 0.5,
        perspective: DebatePerspective = DebatePerspective.RED_AGGRESSIVE,
    ) -> PerspectiveAnalysis:
        return PerspectiveAnalysis(perspective=perspective, stance=stance, arguments=arguments, confidence=confidence)

    _expect_entity_validation_error(
        context,
        [
            ("stance 空串", lambda: make(stance="")),
            ("arguments 0 条", lambda: make(arguments=())),
            ("arguments 9 条", lambda: make(arguments=tuple(f"论点{i}" for i in range(9)))),
            ("arguments 含空串", lambda: make(arguments=("论点一", ""))),
            ("confidence > 1", lambda: make(confidence=1.01)),
            ("confidence < 0", lambda: make(confidence=-0.01)),
        ],
    )
    # 枚举合法性：perspective 传非法枚举值
    try:
        make(perspective=cast(DebatePerspective, "激进派"))
    except (EntityValidationError, ValueError):
        pass
    else:
        raise AssertionError("非法枚举值应被拒绝")


@when("以越界参数构造共识与分歧区域")
def when_construct_invalid_areas(context: dict[str, Any]) -> None:
    """组 3 区域字段：area 空/描述类字段空串/ConsensusArea confidence 越界"""
    _expect_entity_validation_error(
        context,
        [
            ("ConsensusArea.area 空", lambda: ConsensusArea(area="", description="共识内容", confidence=0.9)),
            ("ConsensusArea.description 空", lambda: ConsensusArea(area="主题", description="", confidence=0.9)),
            ("ConsensusArea.confidence 越界", lambda: ConsensusArea(area="主题", description="内容", confidence=1.5)),
            (
                "DisagreementArea.area 空",
                lambda: DisagreementArea(area="", red_position="红", blue_position="蓝", risk_note="风险"),
            ),
            (
                "DisagreementArea.red_position 空",
                lambda: DisagreementArea(area="主题", red_position="", blue_position="蓝", risk_note="风险"),
            ),
            (
                "DisagreementArea.blue_position 空",
                lambda: DisagreementArea(area="主题", red_position="红", blue_position="", risk_note="风险"),
            ),
            (
                "DisagreementArea.risk_note 空",
                lambda: DisagreementArea(area="主题", red_position="红", blue_position="蓝", risk_note=""),
            ),
        ],
    )


@when("以越界参数构造 RiskView")
def when_construct_invalid_risk_view(context: dict[str, Any]) -> None:
    """组 4 视图校验：两组区域空/risk_level 非法/overlap_rate 越界"""
    consensus = (ConsensusArea(area="主题", description="内容", confidence=0.9),)
    disagreement = (DisagreementArea(area="主题", red_position="红", blue_position="蓝", risk_note="风险"),)

    def make(
        consensus_areas: tuple = consensus,
        disagreement_areas: tuple = disagreement,
        overall_risk_level: str = "MEDIUM",
        overlap_rate: float = 0.5,
    ) -> RiskView:
        return RiskView(
            consensus_areas=consensus_areas,
            disagreement_areas=disagreement_areas,
            overall_risk_level=overall_risk_level,
            overlap_rate=overlap_rate,
        )

    _expect_entity_validation_error(
        context,
        [
            ("consensus_areas 空", lambda: make(consensus_areas=())),
            ("disagreement_areas 空", lambda: make(disagreement_areas=())),
            ("risk_level 非法", lambda: make(overall_risk_level="CRITICAL")),
            ("overlap_rate < 0", lambda: make(overlap_rate=-0.01)),
            ("overlap_rate > 1", lambda: make(overlap_rate=1.01)),
        ],
    )


@when("以越界参数构造质量与结果对象")
def when_construct_invalid_quality_result(context: dict[str, Any]) -> None:
    """组 5 质量与结果：DebateQuality.overlap_rate 越界 / DebateResult.duration_ms 负数"""
    red = PerspectiveAnalysis(perspective=DebatePerspective.RED_AGGRESSIVE, stance="立场", arguments=("论点",), confidence=0.5)
    blue = PerspectiveAnalysis(
        perspective=DebatePerspective.BLUE_CONSERVATIVE, stance="立场", arguments=("论点",), confidence=0.5
    )
    risk_view = RiskView(
        consensus_areas=(ConsensusArea(area="主题", description="内容", confidence=0.9),),
        disagreement_areas=(DisagreementArea(area="主题", red_position="红", blue_position="蓝", risk_note="风险"),),
        overall_risk_level="LOW",
        overlap_rate=0.5,
    )

    def make_result(duration_ms: int = 100) -> DebateResult:
        return DebateResult(
            debate_id=uuid.uuid4(),
            topic_title="议题",
            red_analysis=red,
            blue_analysis=blue,
            risk_view=risk_view,
            quality=DebateQuality(overlap_rate=0.5),
            duration_ms=duration_ms,
        )

    _expect_entity_validation_error(
        context,
        [
            ("DebateQuality.overlap_rate < 0", lambda: DebateQuality(overlap_rate=-0.01)),
            ("DebateQuality.overlap_rate > 1", lambda: DebateQuality(overlap_rate=1.01)),
            ("duration_ms 负数", lambda: make_result(duration_ms=-1)),
        ],
    )


@then("抛出 EntityValidationError")
def then_entity_validation_error(context: dict[str, Any]) -> None:
    """本场景至少验证 1 条 242 用例（R1-F06 接线后为真断言——旧形态恒真空）"""
    assert context.get("vo_errors"), "vo_errors 为空：when 步骤未收集任何 242 验证用例"


@then("错误码为 EXCEPTION_242")
def then_error_code_242(context: dict[str, Any]) -> None:
    """错误码 242 断言（与 when 助手中的 code 校验一致）"""
    error = context.get("query_error")
    if error is not None:
        assert error.code == "EXCEPTION_242"


# ============================================================================
# AC-2: DebateSession 聚合根 + 状态机
# ============================================================================


@when("执行辩论会话状态机合法全路径迁移")
def when_legal_full_path_transitions(context: dict[str, Any]) -> None:
    """IDLE→GENERATING→SYNTHESIZING→COMPLETED 全路径（终态前回填必填字段）"""
    session = context["session"]
    assert session.state is DebateSessionState.IDLE
    session.transition_to(DebateSessionState.GENERATING)
    session.transition_to(DebateSessionState.SYNTHESIZING)
    # 终态不变量：COMPLETED 前回填 risk_view 与 completed_at
    session.risk_view = RiskView(
        consensus_areas=(ConsensusArea(area="主题", description="内容", confidence=0.9),),
        disagreement_areas=(DisagreementArea(area="主题", red_position="红", blue_position="蓝", risk_note="风险"),),
        overall_risk_level="LOW",
        overlap_rate=0.5,
    )
    from datetime import UTC, datetime

    session.completed_at = datetime.now(UTC)
    session.transition_to(DebateSessionState.COMPLETED)
    context["session"] = session


@then("状态迁移成功且 state_version 递增")
def then_state_version_incremented(context: dict[str, Any]) -> None:
    """三次合法迁移后 state_version == 3 且处于终态"""
    session = context["session"]
    assert session.state is DebateSessionState.COMPLETED
    assert session.state_version == 3
    assert session.state in TERMINAL_STATES


@when("对辩论会话执行非法状态迁移")
def when_illegal_transitions(context: dict[str, Any]) -> None:
    """非法迁移：COMPLETED→GENERATING 与 IDLE→SYNTHESIZING 跳态"""
    from datetime import UTC, datetime

    errors: list[EntityStateTransitionError] = []
    # 用例 1：COMPLETED → GENERATING（终态迁出）
    completed = DebateSession(
        debate_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        title="议题",
        state=DebateSessionState.COMPLETED,
        risk_view=RiskView(
            consensus_areas=(ConsensusArea(area="主题", description="内容", confidence=0.9),),
            disagreement_areas=(DisagreementArea(area="主题", red_position="红", blue_position="蓝", risk_note="风险"),),
            overall_risk_level="LOW",
            overlap_rate=0.5,
        ),
        completed_at=datetime.now(UTC),
    )
    try:
        completed.transition_to(DebateSessionState.GENERATING)
    except EntityStateTransitionError as exc:
        errors.append(exc)
    # 用例 2：IDLE → SYNTHESIZING（跳态）
    idle = DebateSession(debate_id=uuid.uuid4(), tenant_id=uuid.uuid4(), title="议题")
    try:
        idle.transition_to(DebateSessionState.SYNTHESIZING)
    except EntityStateTransitionError as exc:
        errors.append(exc)
    assert len(errors) == 2, "两条非法迁移用例均应抛 EntityStateTransitionError"
    context["transition_errors"] = errors


@then("抛出 EntityStateTransitionError")
def then_state_transition_error(context: dict[str, Any]) -> None:
    """断言异常类型（迁移矩阵拒绝）"""
    errors = context.get("transition_errors", [])
    assert all(isinstance(e, EntityStateTransitionError) for e in errors)


@then("错误码为 EXCEPTION_243")
def then_error_code_243(context: dict[str, Any]) -> None:
    """错误码 243 断言"""
    errors = context.get("transition_errors", [])
    assert all(e.code == "EXCEPTION_243" for e in errors)


@when("直接构造缺失终态字段的辩论会话")
def when_construct_terminal_without_fields(context: dict[str, Any]) -> None:
    """终态不变量：COMPLETED 缺 risk_view/completed_at、FAILED 缺 failure_reason、非终态带 completed_at"""
    from datetime import UTC, datetime

    risk_view = RiskView(
        consensus_areas=(ConsensusArea(area="主题", description="内容", confidence=0.9),),
        disagreement_areas=(DisagreementArea(area="主题", red_position="红", blue_position="蓝", risk_note="风险"),),
        overall_risk_level="LOW",
        overlap_rate=0.5,
    )
    context["terminal_violations"] = [
        (
            "COMPLETED 缺 risk_view",
            lambda: DebateSession(
                debate_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                title="议题",
                state=DebateSessionState.COMPLETED,
                completed_at=datetime.now(UTC),
            ),
        ),
        (
            "COMPLETED 缺 completed_at",
            lambda: DebateSession(
                debate_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                title="议题",
                state=DebateSessionState.COMPLETED,
                risk_view=risk_view,
            ),
        ),
        (
            "FAILED 缺 failure_reason",
            lambda: DebateSession(
                debate_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                title="议题",
                state=DebateSessionState.FAILED,
            ),
        ),
        (
            "非终态携带 completed_at",
            lambda: DebateSession(
                debate_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                title="议题",
                state=DebateSessionState.GENERATING,
                completed_at=datetime.now(UTC),
            ),
        ),
    ]
    # 复用共用助手断言（R1-F06 接线——同步收集 vo_errors 供 Then 非空断言）
    _expect_entity_validation_error(context, context["terminal_violations"])


# ============================================================================
# AC-3: 3 个新辩论领域异常
# ============================================================================


def _make_llm_cause() -> LLMAPIError:
    """构造 LLM 底层异常（cause 链注入用）"""
    return LLMAPIError(message="模拟 LLM API 失败")


@when("构造 DebateGenerationError 异常实例")
def when_construct_generation_error(context: dict[str, Any]) -> None:
    """构造 420 异常（含 cause 链）并序列化"""
    cause = _make_llm_cause()
    context["debate_exception"] = DebateGenerationError(
        debate_id=str(uuid.uuid4()),
        perspective="red_aggressive",
        topic_title="公司是否应在下一财年进入东南亚市场" * 10,
        cause=cause,
    )
    context["debate_exception_dict"] = context["debate_exception"].to_dict()


@when("构造 DebateSynthesisError 异常实例")
def when_construct_synthesis_error(context: dict[str, Any]) -> None:
    """构造 421 异常（含 cause 链）并序列化"""
    cause = _make_llm_cause()
    context["debate_exception"] = DebateSynthesisError(
        debate_id=str(uuid.uuid4()),
        topic_title="公司是否应在下一财年进入东南亚市场" * 10,
        cause=cause,
    )
    context["debate_exception_dict"] = context["debate_exception"].to_dict()


@when("构造 DebateLowDivergenceError 异常实例")
def when_construct_low_divergence_error(context: dict[str, Any]) -> None:
    """构造 422 异常并序列化"""
    context["debate_exception"] = DebateLowDivergenceError(
        debate_id=str(uuid.uuid4()),
        overlap_rate=0.97,
        red_summary="红方论点摘要",
        blue_summary="蓝方论点摘要",
    )
    context["debate_exception_dict"] = context["debate_exception"].to_dict()


@then("异常上下文携带领域字段且 cause 链保留")
def then_exception_context_and_cause(context: dict[str, Any]) -> None:
    """断言 to_dict 含全部 context 字段 + cause 链解析"""
    exc = context["debate_exception"]
    data = context["debate_exception_dict"]
    assert data["code"] == exc.code
    assert data["context"], "context 不可为空"
    if isinstance(exc, DebateGenerationError):
        assert set(data["context"]) == {"debate_id", "perspective", "topic_title"}
        assert len(data["context"]["topic_title"]) <= 100, "topic_title 截断至 100 字符"
        assert "cause" in data and data["cause"]["code"] == "EXCEPTION_330"
    elif isinstance(exc, DebateSynthesisError):
        assert set(data["context"]) == {"debate_id", "topic_title"}
        assert "cause" in data and data["cause"]["code"] == "EXCEPTION_330"
    else:
        assert set(data["context"]) == {"debate_id", "overlap_rate", "red_summary", "blue_summary"}
        assert data["context"]["overlap_rate"] == 0.97


@then("错误码为 EXCEPTION_420")
def then_error_code_420(context: dict[str, Any]) -> None:
    """错误码 420 断言（构造形态与运行时形态复用）"""
    error = context.get("query_error") or context.get("debate_exception")
    assert error is not None
    assert error.code == "EXCEPTION_420"


@then("错误码为 EXCEPTION_421")
def then_error_code_421(context: dict[str, Any]) -> None:
    """错误码 421 断言（构造形态与运行时形态复用）"""
    error = context.get("query_error") or context.get("debate_exception")
    assert error is not None
    assert error.code == "EXCEPTION_421"


@then("错误码为 EXCEPTION_422")
def then_error_code_422(context: dict[str, Any]) -> None:
    """错误码 422 断言（AC-3.3 与 AC-7.7 两处复用）"""
    error = context.get("query_error") or context.get("debate_exception")
    assert error is not None
    assert error.code == "EXCEPTION_422"


@when("构造三个辩论异常实例并查询 HTTP 映射")
def when_query_http_mapping(context: dict[str, Any]) -> None:
    """反向验证 _get_http_status 私有纯函数（acceptance 直接 import 先例）"""
    from src.interfaces.api.exception_handlers import _get_http_status

    context["http_statuses"] = [
        _get_http_status(DebateGenerationError(debate_id=str(uuid.uuid4()), perspective="red_aggressive", topic_title="议题")),
        _get_http_status(DebateSynthesisError(debate_id=str(uuid.uuid4()), topic_title="议题")),
        _get_http_status(
            DebateLowDivergenceError(debate_id=str(uuid.uuid4()), overlap_rate=0.97, red_summary="红", blue_summary="蓝")
        ),
    ]


@then("HTTP 状态码映射为 500/500/422")
def then_http_status_mapping(context: dict[str, Any]) -> None:
    """420/421→500、422→422（精确注册避免 isinstance 回退）"""
    assert context["http_statuses"] == [500, 500, 422]


# ============================================================================
# AC-4: DebateEvaluator 三算法
# ============================================================================


def _make_perspective(arguments: tuple[str, ...], perspective: DebatePerspective) -> PerspectiveAnalysis:
    """按论点元组构造视角分析（评估器入参）"""
    return PerspectiveAnalysis(perspective=perspective, stance="立场", arguments=arguments, confidence=0.5)


@when("计算重复率已知值与边界用例")
def when_compute_repetition(context: dict[str, Any]) -> None:
    """compute_repetition_rate 已知值 + 空文本边界"""
    evaluator = DebateEvaluator()
    context["computed"] = [
        (evaluator.compute_repetition_rate("ABC", "ABC"), 1.0),
        (evaluator.compute_repetition_rate("ABC", "ABD"), 1 / 3),  # bigram {AB,BC}∩{AB,BD}={AB}, 并集 3
        (evaluator.compute_repetition_rate("", ""), 0.0),
        (evaluator.compute_repetition_rate("ABC", ""), 0.0),
        (evaluator.compute_repetition_rate("", "ABC"), 0.0),
        (evaluator.compute_repetition_rate("市场进入", "市场退出"), 1 / 5),  # {市场,场进,进入}∩{市场,场退,退出}
    ]


@when("计算增益率已知值与边界用例")
def when_compute_gain(context: dict[str, Any]) -> None:
    """compute_gain_rate 已知值 + previous 为空边界"""
    evaluator = DebateEvaluator()
    context["computed"] = [
        (evaluator.compute_gain_rate("ABCD", "ABC"), 0.5),  # 差集 {CD}=1 / max(2,1)=2
        (evaluator.compute_gain_rate("ABC", "ABC"), 0.0),
        (evaluator.compute_gain_rate("ABC", ""), 1.0),  # previous 空 → 全新信息
        (evaluator.compute_gain_rate("", "ABC"), 0.0),  # current 空 → 差集空
        (evaluator.compute_gain_rate("市场进入窗口期", "市场进入"), 1.0),  # 差 3 / max(3,1)=3
    ]


@when("计算红蓝重叠率两极值与中文用例")
def when_compute_overlap(context: dict[str, Any]) -> None:
    """evaluate_overlap 两极值 + 中文论点对"""
    evaluator = DebateEvaluator()
    same_arguments = ("东南亚市场增长潜力巨大",)
    red_same = _make_perspective(same_arguments, DebatePerspective.RED_AGGRESSIVE)
    blue_same = _make_perspective(same_arguments, DebatePerspective.BLUE_CONSERVATIVE)
    red_unrelated = _make_perspective(("供应链本地化成本高企",), DebatePerspective.RED_AGGRESSIVE)
    blue_unrelated = _make_perspective(("关税政策存在不确定性",), DebatePerspective.BLUE_CONSERVATIVE)
    context["computed"] = [
        (evaluator.evaluate_overlap(red_same, blue_same), 1.0),
        (evaluator.evaluate_overlap(red_unrelated, blue_unrelated), 0.0),
    ]


@when("计算空文本与空 bigram 并集边界用例")
def when_compute_empty_bigram(context: dict[str, Any]) -> None:
    """空 bigram 并集返回 0.0（防 0/0 未定义）"""
    evaluator = DebateEvaluator()
    red_single = _make_perspective(("甲",), DebatePerspective.RED_AGGRESSIVE)
    blue_single = _make_perspective(("乙",), DebatePerspective.BLUE_CONSERVATIVE)
    blue_two = _make_perspective(("甲乙",), DebatePerspective.BLUE_CONSERVATIVE)
    context["computed"] = [
        (evaluator.evaluate_overlap(red_single, blue_single), 0.0),  # 双方 bigram 皆空
        (evaluator.evaluate_overlap(red_single, blue_two), 0.0),  # 一方 bigram 空 → 并集空交集空
    ]


@then("计算结果精确等于预期值")
def then_computed_exact_values(context: dict[str, Any]) -> None:
    """逐条精确断言"""
    for actual, expected in context["computed"]:
        assert actual == pytest.approx(expected), f"actual={actual}, expected={expected}"


# ============================================================================
# AC-5: DebateSessionRepositoryPort + InMemory 实现
# ============================================================================


@given("一个真实组装的 InMemory 辩论会话仓储")
def given_real_inmemory_repository(context: dict[str, Any]) -> None:
    """真实 InMemory 仓储实例"""
    from src.infrastructure.storage.inmemory.debate_session_repository import InMemoryDebateSessionRepository

    context["repository"] = InMemoryDebateSessionRepository()


@when("执行仓储保存与查询 roundtrip")
def when_repository_roundtrip(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """save → get_by_id 往返"""
    session = DebateSession(debate_id=uuid.uuid4(), tenant_id=uuid.uuid4(), title="roundtrip 议题")
    context["saved_session"] = event_loop.run_until_complete(context["repository"].save(session))
    context["loaded_session"] = event_loop.run_until_complete(context["repository"].get_by_id(session.debate_id))


@then("roundtrip 字段一致")
def then_roundtrip_consistent(context: dict[str, Any]) -> None:
    """字段一致断言（仓储与事件 roundtrip 复用）"""
    saved = context.get("saved_session")
    loaded = context.get("loaded_session")
    if saved is not None:
        assert loaded is not None
        assert loaded.debate_id == saved.debate_id
        assert loaded.title == saved.title
        assert loaded.state == saved.state
    event = context.get("roundtrip_event")
    if event is not None:
        restored = context["restored_event"]
        assert restored.debate_id == str(event.debate_id)  # payload 字段保持 str（项目历史行为）
        assert restored.topic_title == event.topic_title
        assert restored.consensus_count == event.consensus_count
        assert restored.disagreement_count == event.disagreement_count
        assert restored.overlap_rate == event.overlap_rate
        assert restored.temperature_profile == event.temperature_profile


@when("以未知名查询辩论会话")
def when_query_unknown_id(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """未知名查询"""
    context["unknown_result"] = event_loop.run_until_complete(context["repository"].get_by_id(uuid.uuid4()))


@then("查询返回 None")
def then_query_returns_none(context: dict[str, Any]) -> None:
    """未知名返回 None（不抛错）"""
    assert context["unknown_result"] is None


@when("50 个辩论会话并发保存")
def when_concurrent_saves(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """asyncio.gather 50 并发保存"""
    sessions = [DebateSession(debate_id=uuid.uuid4(), tenant_id=uuid.uuid4(), title=f"并发议题{i}") for i in range(50)]
    context["concurrent_sessions"] = sessions
    context["concurrent_results"] = event_loop.run_until_complete(
        asyncio.gather(*(context["repository"].save(s) for s in sessions))
    )


@then("并发保存零丢失")
def then_concurrent_no_loss(context: dict[str, Any]) -> None:
    """50 个会话全部落库"""
    for session in context["concurrent_sessions"]:
        loaded = context["repository"]._sessions.get(session.debate_id)
        assert loaded is not None, f"会话 {session.debate_id} 丢失"


# ============================================================================
# AC-6: DebateCompleted 事件 + 双通道注册
# ============================================================================


@when("构造 DebateCompleted 事件并序列化 roundtrip")
def when_event_roundtrip(context: dict[str, Any]) -> None:
    """事件构造（含超长 title 截断）+ to_dict/from_dict roundtrip"""
    long_title = "超长议题标题" * 30  # 150 字符 > 100
    event = DebateCompleted(
        debate_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        topic_title=long_title,
        red_stance="红方立场摘要",
        blue_stance="蓝方立场摘要",
        consensus_count=2,
        disagreement_count=1,
        overlap_rate=0.35,
        overall_risk_level="MEDIUM",
        duration_ms=8500,
        temperature_profile={"red": 0.8, "blue": 0.5, "synthesis": 0.2},
    )
    data = event.to_dict()
    context["roundtrip_event"] = event
    context["roundtrip_event_dict"] = data
    context["restored_event"] = DebateCompleted.from_dict(data)
    # 截断断言：payload 中 topic_title ≤ 100 字符
    assert len(data["payload"]["topic_title"]) <= 100


@then("双通道映射逐字段一致且为 RELIABLE")
def then_channel_mapping_consistent(context: dict[str, Any]) -> None:
    """YAML 与 DEFAULT_MAPPINGS 两处参数逐字段一致 + RELIABLE"""
    import yaml

    from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

    mapping = ChannelRouter.DEFAULT_MAPPINGS.get("DebateCompleted")
    assert mapping is not None, "DEFAULT_MAPPINGS 未注册 DebateCompleted"
    assert mapping.delivery_mode == DeliveryMode.RELIABLE
    assert mapping.redis_channel == "sisys:rt:debate_completed"
    assert mapping.rabbitmq_routing_key == "sisys.events.reliable.debate_completed"
    config_path = Path("configs/event_channels.yaml")
    with config_path.open(encoding="utf-8") as fh:
        yaml_cfg = yaml.safe_load(fh)["event_channels"]["DebateCompleted"]
    assert yaml_cfg["redis_channel"] == mapping.redis_channel
    assert yaml_cfg["rabbitmq_routing_key"] == mapping.rabbitmq_routing_key
    assert yaml_cfg["delivery_mode"] == "reliable"


@when("校验 DebateCompleted 双通道登记一致性")
def when_verify_channel_registration(context: dict[str, Any]) -> None:
    """双通道登记校验（登记动作，断言在 Then）"""
    context["channel_checked"] = True


# ============================================================================
# AC-7: RedBlueDebateService 应用服务编排
# ============================================================================


def _setup_service(context: dict[str, Any], fake_llm: AsyncMock, publisher: AsyncMock | None = None) -> None:
    """组装真实服务链并准备议题（步骤共用助手）"""
    service, repository, event_publisher = _build_service(fake_llm, publisher)
    context["service"] = service
    context["repository"] = repository
    context["publisher"] = event_publisher
    context["fake_llm"] = fake_llm
    context["topic"] = _make_topic()


@given("真实组装的辩论服务且 Fake LLM 返回标准红蓝合成结果")
def given_service_standard_results(context: dict[str, Any]) -> None:
    """标准 Happy path 组装（默认 0.05s 视角延迟）"""
    fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema())
    _setup_service(context, fake_llm)


@given("真实组装的辩论服务且 Fake LLM 视角生成注入延迟")
def given_service_with_delay(context: dict[str, Any]) -> None:
    """AC-7.3 并发窗口组装（0.1s 显式延迟）"""
    fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema(), perspective_delay_sec=0.1)
    _setup_service(context, fake_llm)


@given("真实组装的辩论服务且 Fake LLM 红视角生成失败")
def given_service_red_failure(context: dict[str, Any]) -> None:
    """红视角失败注入（red 参数为 Exception 实例）"""
    fake_llm = _make_fake_llm(_make_llm_cause(), _make_blue_schema(), _make_risk_schema())
    _setup_service(context, fake_llm)


@given("真实组装的辩论服务且 Fake LLM 合成失败")
def given_service_synthesis_failure(context: dict[str, Any]) -> None:
    """合成失败注入（risk 参数为 Exception 实例）"""
    fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_llm_cause())
    _setup_service(context, fake_llm)


@given("真实组装的辩论服务且 Fake LLM 红蓝论点完全相同")
def given_service_identical_arguments(context: dict[str, Any]) -> None:
    """红蓝 arguments 完全相同（J=1.0 稳定触发 422）"""
    same_arguments = ["市场窗口期稍纵即逝需要果断投入资源抢占先机", "本地竞品尚未形成垄断进入成本处于低位"]
    fake_llm = _make_fake_llm(
        _make_red_schema(arguments=list(same_arguments)),
        _make_blue_schema(arguments=list(same_arguments)),
        _make_risk_schema(),
    )
    _setup_service(context, fake_llm)


@given("真实组装的辩论服务且 Fake LLM 蓝论点微调一字")
def given_service_warning_zone(context: dict[str, Any]) -> None:
    """蓝=红改第 20 字一处 → J≈0.895 ∈ [0.80, 0.95) 警告区"""
    fake_llm = _make_fake_llm(
        _make_red_schema(arguments=[_WARNING_RED_ARG]),
        _make_blue_schema(arguments=[_WARNING_BLUE_ARG]),
        _make_risk_schema(),
    )
    _setup_service(context, fake_llm)


@given("真实组装的辩论服务且 Fake LLM 零耗时返回")
def given_service_zero_latency(context: dict[str, Any]) -> None:
    """AC-9.2 编排开销组装（零视角延迟）"""
    fake_llm = _make_fake_llm(_make_red_schema(), _make_blue_schema(), _make_risk_schema(), perspective_delay_sec=0.0)
    _setup_service(context, fake_llm)


@when("执行红蓝辩论")
def when_run_debate(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """执行 run_debate（结果/异常捕获到 context）"""
    event_loop.run_until_complete(_run_debate_async(context))


async def _run_debate_async(context: dict[str, Any]) -> None:
    """run_debate 异步执行体"""
    topic = context["topic"]
    execution_context = ExecutionContext(tenant_id=topic.tenant_id)
    try:
        context["result"] = await context["service"].run_debate(topic=topic, context=execution_context)
        context["query_error"] = None
    except Exception as exc:
        context["query_error"] = exc
        context["result"] = None


@then("辩论结果三段结构完整")
def then_result_three_sections(context: dict[str, Any]) -> None:
    """red/blue/risk_view 三段结构 + 质量对象"""
    result = context["result"]
    assert result is not None, f"run_debate 不应失败: {context.get('query_error')}"
    assert result.red_analysis.perspective is DebatePerspective.RED_AGGRESSIVE
    assert result.blue_analysis.perspective is DebatePerspective.BLUE_CONSERVATIVE
    assert result.red_analysis.stance
    assert result.blue_analysis.stance
    assert len(result.risk_view.consensus_areas) >= 1
    assert len(result.risk_view.disagreement_areas) >= 1
    assert result.risk_view.overall_risk_level in {"LOW", "MEDIUM", "HIGH"}
    assert 0.0 <= result.risk_view.overlap_rate <= 1.0
    assert result.quality.overlap_rate == result.risk_view.overlap_rate
    assert result.quality.gain_rate is None
    assert result.quality.repetition_rate is None
    assert result.duration_ms >= 0


@when("执行红蓝辩论并校验温度阶梯")
def when_run_debate_verify_temperature(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """执行辩论并按 system_prompt 角色标记锚定校验温度"""
    event_loop.run_until_complete(_run_debate_async(context))
    calls = context["fake_llm"]._debate_calls
    perspective_calls = [c for c in calls if c[2] is PerspectiveAnalysisSchema]
    synthesis_calls = [c for c in calls if c[2] is RiskViewSchema]
    assert len(perspective_calls) == 2 and len(synthesis_calls) == 1
    context["perspective_calls"] = perspective_calls
    context["synthesis_calls"] = synthesis_calls


@then("温度阶梯断言全部通过")
def then_temperature_profile_assertions(context: dict[str, Any]) -> None:
    """system_prompt 锚定：含"激进派"==0.8 / 含"保守派"==0.5 / 裁判==0.2；补充 sorted 全量"""
    for prompt, system_prompt, schema, temperature, _start, _end in context["perspective_calls"]:
        assert system_prompt is not None
        if "激进派" in system_prompt:
            assert temperature == TEMPERATURE_PROFILE["red"], f"红视角温度 {temperature} 应为 0.8"
        if "保守派" in system_prompt:
            assert temperature == TEMPERATURE_PROFILE["blue"], f"蓝视角温度 {temperature} 应为 0.5"
    for _prompt, system_prompt, _schema, temperature, _start, _end in context["synthesis_calls"]:
        assert "裁判" in (system_prompt or ""), "合成 system_prompt 应含裁判角色标记"
        assert temperature == TEMPERATURE_PROFILE["synthesis"]
    all_temperatures = sorted(c[3] for c in context["perspective_calls"] + context["synthesis_calls"])
    assert all_temperatures == [0.2, 0.5, 0.8]
    # per-call timeout 传递断言（默认 12.0，R1-F06——旧形态误断 temperature 非 None 近似恒真）
    for config in context["fake_llm"]._debate_configs:
        assert config is not None
        assert config.timeout == 12.0


@when("执行红蓝辩论并记录调用时间窗口")
def when_run_debate_record_windows(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """执行辩论并提取红蓝视角调用窗口"""
    context["window_start"] = time.perf_counter()
    event_loop.run_until_complete(_run_debate_async(context))
    context["window_elapsed"] = time.perf_counter() - context["window_start"]
    calls = context["fake_llm"]._debate_calls
    perspective_calls = [c for c in calls if c[2] is PerspectiveAnalysisSchema]
    assert len(perspective_calls) == 2
    context["perspective_calls"] = perspective_calls


@then("红蓝生成时间窗口重叠")
def then_generation_windows_overlap(context: dict[str, Any]) -> None:
    """窗口重叠断言（串行实现必红）+ 单边计时阈值"""
    first, second = context["perspective_calls"]
    red_call = first if "激进派" in (first[1] or "") else second
    blue_call = second if red_call is first else first
    red_start, red_end = red_call[4], red_call[5]
    blue_start, blue_end = blue_call[4], blue_call[5]
    # 窗口重叠：双方均在对方结束前开始
    assert blue_start < red_end, "蓝视角应在红视角结束前开始（并发证据缺失）"
    assert red_start < blue_end, "红视角应在蓝视角结束前开始（并发证据缺失）"
    # 单边计时：视角窗口总跨度 < 1.5 × delay（串行两次 ≈ 2×delay 必超标）
    span = max(red_end, blue_end) - min(red_start, blue_start)
    assert span < 1.5 * 0.1, f"视角生成跨度 {span:.3f}s 超过 1.5×delay，疑似串行实现"


@when("执行红蓝辩论并校验视角独立性")
def when_run_debate_verify_independence(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """执行辩论并断言红蓝互不可见（限定 PerspectiveAnalysisSchema 两次调用）"""
    event_loop.run_until_complete(_run_debate_async(context))
    calls = context["fake_llm"]._debate_calls
    perspective_calls = [c for c in calls if c[2] is PerspectiveAnalysisSchema]
    assert len(perspective_calls) == 2
    red_call = next(c for c in perspective_calls if "激进派" in (c[1] or ""))
    blue_call = next(c for c in perspective_calls if "保守派" in (c[1] or ""))
    red_schema = _make_red_schema()
    blue_schema = _make_blue_schema()
    # 红 prompt 不含蓝方 stance/论点标记，蓝 prompt 不含红方 stance/论点标记
    for blue_argument in blue_schema.arguments:
        assert blue_argument not in red_call[0], "红视角 prompt 不应包含蓝方论点（锚定偏差）"
    for red_argument in red_schema.arguments:
        assert red_argument not in blue_call[0], "蓝视角 prompt 不应包含红方论点（锚定偏差）"
    assert blue_schema.stance not in red_call[0]
    assert red_schema.stance not in blue_call[0]
    # system_prompt 角色标记锚定（红含激进派/蓝含保守派，双方均不含对方输出）
    assert "激进派" in (red_call[1] or "")
    assert "保守派" in (blue_call[1] or "")
    context["independence_verified"] = True


@then("视角独立性断言通过")
def then_independence_verified(context: dict[str, Any]) -> None:
    """独立性断言结果确认"""
    assert context.get("independence_verified") is True


@when("执行红蓝辩论并捕获异常")
def when_run_debate_capture_error(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """执行辩论并捕获异常（失败注入场景）"""
    event_loop.run_until_complete(_run_debate_async(context))
    assert context["query_error"] is not None, "失败注入场景应抛出异常"


@then("抛出 DebateGenerationError")
def then_debate_generation_error(context: dict[str, Any]) -> None:
    """420 异常类型与上下文断言"""
    error = context["query_error"]
    assert isinstance(error, DebateGenerationError)
    assert error.context["perspective"] == "red_aggressive"
    assert error.cause is not None, "cause 链应保留 LLM 底层异常"


@then("抛出 DebateSynthesisError")
def then_debate_synthesis_error(context: dict[str, Any]) -> None:
    """421 异常类型断言"""
    error = context["query_error"]
    assert isinstance(error, DebateSynthesisError)
    assert error.cause is not None


@then("辩论会话终态为 FAILED 且已落库")
def then_session_failed_persisted(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """失败路径经 repository.get_by_id 断言终态落库（迁移后 save 纪律）"""
    topic = context["topic"]
    session = event_loop.run_until_complete(context["repository"].get_by_id(topic.debate_id))
    assert session is not None, "失败会话应已落库"
    assert session.state is DebateSessionState.FAILED
    assert session.failure_reason is not None


@then("抛出 DebateLowDivergenceError")
def then_debate_low_divergence_error(context: dict[str, Any]) -> None:
    """422 异常类型与上下文断言"""
    error = context["query_error"]
    assert isinstance(error, DebateLowDivergenceError)
    assert error.context["overlap_rate"] >= OVERLAP_HARD_THRESHOLD


@then("风险视图携带分化偏弱警告")
def then_risk_view_has_warning(context: dict[str, Any]) -> None:
    """警告区：不抛异常 + warnings 非空 + 重叠率落在 [0.80, 0.95)"""
    result = context["result"]
    assert result is not None, f"警告区不应抛异常: {context.get('query_error')}"
    assert result.risk_view.warnings, "警告区 RiskView.warnings 应非空"
    assert OVERLAP_WARNING_THRESHOLD <= result.risk_view.overlap_rate < OVERLAP_HARD_THRESHOLD
    assert any("分化" in w or "重叠" in w for w in result.risk_view.warnings)


@when("执行红蓝辩论并校验事件发布")
def when_run_debate_verify_event(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """执行辩论并校验 DebateCompleted 发布"""
    event_loop.run_until_complete(_run_debate_async(context))
    context["publish_calls"] = context["publisher"].publish.call_args_list


@then("DebateCompleted 事件字段断言通过")
def then_event_fields_asserted(context: dict[str, Any]) -> None:
    """publish 一次 + 事件字段值断言"""
    publish_calls = context["publish_calls"]
    assert len(publish_calls) == 1, "DebateCompleted 应发布且仅发布一次"
    event = publish_calls[0][0][0]
    result = context["result"]
    assert isinstance(event, DebateCompleted)
    assert event.debate_id == result.debate_id
    assert event.tenant_id == context["topic"].tenant_id
    assert event.consensus_count == len(result.risk_view.consensus_areas)
    assert event.disagreement_count == len(result.risk_view.disagreement_areas)
    assert event.overlap_rate == result.risk_view.overlap_rate
    assert event.overall_risk_level == result.risk_view.overall_risk_level
    assert event.temperature_profile == {"red": 0.8, "blue": 0.5, "synthesis": 0.2}


# ============================================================================
# AC-8: composition_root 端口注册
# ============================================================================


@when("解析注册的辩论端口元数据")
def when_resolve_port_specs(context: dict[str, Any]) -> None:
    """读取三端口 PortSpec"""
    from src.domain.ports.registry import _global_registry

    context["port_specs"] = {
        name: _global_registry.get(name)
        for name in ("debate_session_repository", "debate_evaluator", "red_blue_debate_service")
    }


@then("端口元数据完整匹配")
def then_port_specs_match(context: dict[str, Any]) -> None:
    """PortSpec 元数据断言（name/version/owner/tags/lifetime）"""
    specs = context["port_specs"]
    for name, spec in specs.items():
        assert spec is not None, f"端口 {name} 未注册"
        assert spec.name == name
        assert spec.version == "v1.0.0"
        assert spec.owner == "tool-team"
        assert "debate" in spec.tags
    assert specs["debate_session_repository"].lifetime.value == "scoped"
    assert specs["debate_evaluator"].lifetime.value == "singleton"
    assert specs["red_blue_debate_service"].lifetime.value == "scoped"


@when("通过 Resolver 解析辩论端口")
def when_resolver_resolve(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """Resolver 解析三端口"""
    from src.domain.ports.resolver import Resolver

    resolver = Resolver()
    context["resolved"] = {
        "repository": resolver.resolve("debate_session_repository"),
        "evaluator": resolver.resolve("debate_evaluator"),
        "service": resolver.resolve("red_blue_debate_service"),
    }
    context["resolver"] = resolver


@then("解析返回真实服务实例")
def then_resolved_real_instances(context: dict[str, Any]) -> None:
    """解析结果 isinstance 断言 + SINGLETON 生效"""
    from src.application.ports.red_blue_debate_service import RedBlueDebateServicePort
    from src.domain.ports.debate_session_repository import DebateSessionRepositoryPort
    from src.domain.services.debate_evaluator import DebateEvaluator

    resolved = context["resolved"]
    assert isinstance(resolved["service"], RedBlueDebateService)
    assert isinstance(resolved["service"], RedBlueDebateServicePort)
    assert isinstance(resolved["repository"], DebateSessionRepositoryPort)
    assert isinstance(resolved["evaluator"], DebateEvaluator)
    # SINGLETON：两次 resolve 同一实例
    again = context["resolver"].resolve("debate_evaluator")
    assert again is resolved["evaluator"], "debate_evaluator 应为 SINGLETON"


# ============================================================================
# AC-9: 架构验证与编排性能
# ============================================================================


@when("扫描辩论领域文件依赖与温度常量")
def when_scan_architecture(context: dict[str, Any]) -> None:
    """AST 扫描 debate 领域文件 imports + 断言温度常量与迁移矩阵"""
    forbidden = {"pydantic", "sqlalchemy", "redis", "fastapi", "litellm", "langgraph", "prefect"}
    domain_files = [
        Path("src/domain/value_objects/debate.py"),
        Path("src/domain/entities/debate_session.py"),
        Path("src/domain/services/debate_evaluator.py"),
        Path("src/domain/ports/debate_session_repository.py"),
        Path("src/domain/events/debate_events.py"),
        Path("src/domain/exceptions/debate_exceptions.py"),
    ]
    for file_path in domain_files:
        assert file_path.exists(), f"{file_path} 应存在"
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        violated = imports & forbidden
        assert not violated, f"{file_path} 违反领域零依赖: {violated}"
    # 温度常量对齐 FR-SP-10
    assert TEMPERATURE_PROFILE == {"red": 0.8, "blue": 0.5, "synthesis": 0.2}
    assert OVERLAP_HARD_THRESHOLD == 0.95
    assert OVERLAP_WARNING_THRESHOLD == 0.80
    # 状态机迁移矩阵存在性
    assert VALID_TRANSITIONS[DebateSessionState.IDLE] == {DebateSessionState.GENERATING}
    # prompt 映射覆盖红蓝两键 + 角色标记
    assert set(PERSPECTIVE_PROMPT_MAP) == {DebatePerspective.RED_AGGRESSIVE, DebatePerspective.BLUE_CONSERVATIVE}
    assert "激进派" in PERSPECTIVE_PROMPT_MAP[DebatePerspective.RED_AGGRESSIVE]["system_prompt"]
    assert "保守派" in PERSPECTIVE_PROMPT_MAP[DebatePerspective.BLUE_CONSERVATIVE]["system_prompt"]
    assert "裁判" in SYNTHESIS_SYSTEM_PROMPT
    context["architecture_verified"] = True


@then("零依赖且温度常量对齐")
def then_zero_dependency_and_constants(context: dict[str, Any]) -> None:
    """架构扫描结果确认"""
    assert context.get("architecture_verified") is True


@when("测量纯编排开销")
def when_measure_orchestration_overhead(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """Fake 零耗时下测量 run_debate 端到端耗时"""
    start = time.perf_counter()
    event_loop.run_until_complete(_run_debate_async(context))
    context["orchestration_elapsed"] = time.perf_counter() - start


@then("编排开销小于 1 秒")
def then_overhead_below_1s(context: dict[str, Any]) -> None:
    """smoke 级判别（检出编排内意外混入真实 IO/网络客户端）"""
    assert context.get("query_error") is None
    assert context["orchestration_elapsed"] < 1.0, f"编排开销 {context['orchestration_elapsed']:.3f}s ≥ 1s"


# ============================================================================
# 收尾验收: src 与测试完成清单最终确认
# ============================================================================


@when("核对 src 与测试完成清单")
def when_check_completion_checklist(context: dict[str, Any]) -> None:
    """src 交付物与测试交付物存在性逐项核对"""
    src_files = [
        "src/domain/value_objects/debate.py",
        "src/domain/entities/debate_session.py",
        "src/domain/services/debate_evaluator.py",
        "src/domain/ports/debate_session_repository.py",
        "src/domain/exceptions/debate_exceptions.py",
        "src/domain/events/debate_events.py",
        "src/application/services/red_blue_debate_service.py",
        "src/application/services/debate_prompts.py",
        "src/application/services/debate_schemas.py",
        "src/application/ports/red_blue_debate_service.py",
        "src/infrastructure/storage/inmemory/debate_session_repository.py",
    ]
    test_files = [
        "tests/unit/domain/value_objects/test_debate.py",
        "tests/unit/domain/entities/test_debate_session.py",
        "tests/unit/domain/services/test_debate_evaluator.py",
        "tests/unit/domain/events/test_debate_events.py",
        "tests/unit/domain/exceptions/test_debate_exceptions.py",
        "tests/unit/application/services/test_red_blue_debate_service.py",
        "tests/unit/application/services/test_debate_prompts.py",
        "tests/unit/application/services/test_debate_schemas.py",
        "tests/unit/infrastructure/storage/test_debate_session_repository.py",
        "tests/unit/architecture/test_red_blue_debate.py",
        "tests/integration/test_red_blue_debate_integration.py",
        "tests/contracts/test_port_contract_red_blue_debate_service.py",
        "tests/contracts/test_port_contract_debate_session_repository.py",
        "tests/contracts/test_event_contract_debate_events.py",
        "tests/contracts/test_event_channel_mapping_debate.py",
        "tests/acceptance/test_acceptance_red_blue_debate.feature",
        "tests/acceptance/test_acceptance_red_blue_debate.py",
    ]
    context["checklist_files"] = [(p, Path(p).exists()) for p in src_files + test_files]


@then("完成清单逐项确认通过")
def then_checklist_all_present(context: dict[str, Any]) -> None:
    """全部交付物存在（覆盖率门禁由 CI --cov 执行，此处核验文件面）"""
    missing = [p for p, exists in context["checklist_files"] if not exists]
    assert not missing, f"完成清单缺失: {missing}"
