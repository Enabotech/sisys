"""Story 4.5 — 红蓝辩论值对象单元测试

验证 DebatePerspective / DebateTopic / PerspectiveAnalysis / ConsensusArea /
DisagreementArea / RiskView / DebateQuality / DebateResult 的不变量校验
（8 类型 = 7 个 frozen dataclass VO + 1 个枚举）。

约束：
- 不变量违反抛 EntityValidationError（EXCEPTION_242），禁止 ValueError
- 全部值对象 frozen 不可变（setattr 触发 FrozenInstanceError）
- 每条子约束一独立用例（AC-1 验证标准），非按组
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import cast

import pytest

from src.domain.exceptions import EntityValidationError
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


def _make_debate_topic(
    tenant_id: uuid.UUID | None = None,
    title: str = "公司是否应在下一财年进入东南亚市场",
    background: str = "",
    debate_id: uuid.UUID | None = None,
) -> DebateTopic:
    """构造 DebateTopic（测试工厂，默认全合法）。"""
    return DebateTopic(
        tenant_id=tenant_id if tenant_id is not None else uuid.uuid4(),
        title=title,
        background=background,
        debate_id=debate_id if debate_id is not None else uuid.uuid4(),
    )


def _make_perspective(
    perspective: DebatePerspective = DebatePerspective.RED_AGGRESSIVE,
    stance: str = "应当立即进入东南亚市场",
    arguments: tuple[str, ...] = ("市场窗口期稍纵即逝", "本地竞品尚未形成垄断"),
    risks: tuple[str, ...] = ("初期投入可能超预算",),
    recommendations: tuple[str, ...] = ("优先布局核心城市",),
    confidence: float = 0.8,
) -> PerspectiveAnalysis:
    """构造 PerspectiveAnalysis（测试工厂，默认全合法）。"""
    return PerspectiveAnalysis(
        perspective=perspective,
        stance=stance,
        arguments=arguments,
        risks=risks,
        recommendations=recommendations,
        confidence=confidence,
    )


def _make_consensus(
    area: str = "市场潜力",
    description: str = "双方认可东南亚市场增长潜力",
    confidence: float = 0.9,
) -> ConsensusArea:
    """构造 ConsensusArea（测试工厂，默认全合法）。"""
    return ConsensusArea(area=area, description=description, confidence=confidence)


def _make_disagreement(
    area: str = "进入时机",
    red_position: str = "立即进入抢占先机",
    blue_position: str = "延后观察规避风险",
    risk_note: str = "时机误判将放大投入风险",
) -> DisagreementArea:
    """构造 DisagreementArea（测试工厂，默认全合法）。"""
    return DisagreementArea(
        area=area,
        red_position=red_position,
        blue_position=blue_position,
        risk_note=risk_note,
    )


def _make_risk_view(
    consensus_areas: tuple[ConsensusArea, ...] | None = None,
    disagreement_areas: tuple[DisagreementArea, ...] | None = None,
    overall_risk_level: str = "MEDIUM",
    overlap_rate: float = 0.35,
    warnings: tuple[str, ...] = (),
) -> RiskView:
    """构造 RiskView（测试工厂，默认全合法）。"""
    return RiskView(
        consensus_areas=consensus_areas if consensus_areas is not None else (_make_consensus(),),
        disagreement_areas=disagreement_areas if disagreement_areas is not None else (_make_disagreement(),),
        overall_risk_level=overall_risk_level,
        overlap_rate=overlap_rate,
        warnings=warnings,
    )


def _make_quality(overlap_rate: float = 0.35) -> DebateQuality:
    """构造 DebateQuality（测试工厂，默认全合法）。"""
    return DebateQuality(overlap_rate=overlap_rate)


def _make_result(duration_ms: int = 1200) -> DebateResult:
    """构造 DebateResult（测试工厂，默认全合法）。"""
    return DebateResult(
        debate_id=uuid.uuid4(),
        topic_title="公司是否应在下一财年进入东南亚市场",
        red_analysis=_make_perspective(perspective=DebatePerspective.RED_AGGRESSIVE),
        blue_analysis=_make_perspective(
            perspective=DebatePerspective.BLUE_CONSERVATIVE,
            stance="应当延后观察再进入",
            confidence=0.6,
        ),
        risk_view=_make_risk_view(),
        quality=_make_quality(),
        duration_ms=duration_ms,
    )


# ===================================================================
# DebatePerspective 枚举
# ===================================================================


class TestDebatePerspective:
    def test_enum_members_complete(self) -> None:
        """两视角枚举成员与值完整"""
        assert DebatePerspective.RED_AGGRESSIVE.value == "red_aggressive"
        assert DebatePerspective.BLUE_CONSERVATIVE.value == "blue_conservative"
        assert len(DebatePerspective) == 2

    def test_enum_is_immutable_and_str_based(self) -> None:
        """枚举天然不可变且基于 str（序列化友好）"""
        assert isinstance(DebatePerspective.RED_AGGRESSIVE.value, str)


# ===================================================================
# 组 1: DebateTopic 议题边界
# ===================================================================


class TestDebateTopic:
    def test_valid_construction_with_defaults(self) -> None:
        """合法构造：默认 debate_id/created_at 自动生成"""
        tenant_id = uuid.uuid4()
        topic = _make_debate_topic(tenant_id=tenant_id, background="议题背景")
        assert topic.tenant_id == tenant_id
        assert topic.title == "公司是否应在下一财年进入东南亚市场"
        assert topic.background == "议题背景"
        assert isinstance(topic.debate_id, uuid.UUID)
        assert topic.created_at is not None

    def test_invalid_tenant_id_raises(self) -> None:
        """tenant_id 必须 UUID（防御分支）"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_debate_topic(tenant_id=cast(uuid.UUID, "not-a-uuid"))
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "tenant_id"

    def test_invalid_debate_id_raises(self) -> None:
        """debate_id 必须 UUID（R1-F04——与 DebateSession/DebateResult 共用主键同款校验）"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_debate_topic(debate_id=cast(uuid.UUID, "not-a-uuid"))
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "debate_id"

    def test_explicit_valid_debate_id_passes(self) -> None:
        """显式合法 debate_id 通过（与 DebateSession 聚合根共用标识）"""
        debate_id = uuid.uuid4()
        topic = _make_debate_topic(debate_id=debate_id)
        assert topic.debate_id == debate_id

    @pytest.mark.parametrize(
        ("bad_title", "case_name"),
        [
            ("", "title 空串"),
            ("议" * 201, "title 201 字超上限"),
        ],
        ids=["empty-title", "title-201-chars"],
    )
    def test_invalid_title_raises(self, bad_title: str, case_name: str) -> None:
        """title 非空且 ≤ 200 字符（每条子约束独立用例）"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_debate_topic(title=bad_title)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "title"

    def test_title_200_chars_boundary_passes(self) -> None:
        """边界值 200 字合法（闭区间上界）"""
        topic = _make_debate_topic(title="议" * 200)
        assert len(topic.title) == 200

    def test_background_8001_chars_raises(self) -> None:
        """background ≤ 8000 字符"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_debate_topic(background="景" * 8001)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "background"

    def test_background_8000_chars_boundary_passes(self) -> None:
        """边界值 8000 字合法"""
        topic = _make_debate_topic(background="景" * 8000)
        assert len(topic.background) == 8000


# ===================================================================
# 组 2: PerspectiveAnalysis 视角校验
# ===================================================================


class TestPerspectiveAnalysis:
    def test_valid_construction(self) -> None:
        """合法构造全字段"""
        analysis = _make_perspective()
        assert analysis.perspective is DebatePerspective.RED_AGGRESSIVE
        assert analysis.stance
        assert len(analysis.arguments) == 2
        assert analysis.confidence == 0.8

    def test_empty_risks_and_recommendations_allowed(self) -> None:
        """risks/recommendations 允许空 tuple"""
        analysis = _make_perspective(risks=(), recommendations=())
        assert analysis.risks == ()
        assert analysis.recommendations == ()

    def test_empty_stance_raises(self) -> None:
        """stance 非空"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perspective(stance="")
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "stance"

    def test_zero_arguments_raises(self) -> None:
        """arguments 1~8 条（下界）"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perspective(arguments=())
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "arguments"

    def test_nine_arguments_raises(self) -> None:
        """arguments 1~8 条（上界）"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perspective(arguments=tuple(f"论点{i}" for i in range(9)))
        assert exc_info.value.code == "EXCEPTION_242"

    def test_argument_with_empty_string_raises(self) -> None:
        """arguments 每条非空"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perspective(arguments=("论点一", ""))
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "arguments"

    def test_eight_arguments_boundary_passes(self) -> None:
        """边界值 8 条合法"""
        analysis = _make_perspective(arguments=tuple(f"论点{i}" for i in range(8)))
        assert len(analysis.arguments) == 8

    @pytest.mark.parametrize("bad_confidence", [-0.01, -1.0, 1.01, 2.0], ids=["neg-small", "neg-one", "over-small", "over-two"])
    def test_confidence_out_of_range_raises(self, bad_confidence: float) -> None:
        """confidence ∈ [0.0, 1.0]"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perspective(confidence=bad_confidence)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "confidence"

    def test_confidence_boundaries_pass(self) -> None:
        """边界值 0.0 与 1.0 合法"""
        assert _make_perspective(confidence=0.0).confidence == 0.0
        assert _make_perspective(confidence=1.0).confidence == 1.0

    def test_invalid_perspective_type_raises(self) -> None:
        """perspective 枚举合法（非枚举值拒绝）"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perspective(perspective=cast(DebatePerspective, "激进派"))
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "perspective"

    def test_risk_with_empty_string_raises(self) -> None:
        """risks 每条非空"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perspective(risks=("",))
        assert exc_info.value.code == "EXCEPTION_242"

    def test_recommendation_with_empty_string_raises(self) -> None:
        """recommendations 每条非空"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perspective(recommendations=("",))
        assert exc_info.value.code == "EXCEPTION_242"


# ===================================================================
# 组 3: ConsensusArea / DisagreementArea 区域字段
# ===================================================================


class TestConsensusArea:
    def test_valid_construction(self) -> None:
        area = _make_consensus()
        assert area.area == "市场潜力"
        assert area.confidence == 0.9

    def test_empty_area_raises(self) -> None:
        """area 非空"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_consensus(area="")
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "area"

    def test_empty_description_raises(self) -> None:
        """description 非空"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_consensus(description="")
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "description"

    @pytest.mark.parametrize("bad_confidence", [-0.01, 1.01], ids=["neg", "over"])
    def test_confidence_out_of_range_raises(self, bad_confidence: float) -> None:
        """confidence ∈ [0.0, 1.0]"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_consensus(confidence=bad_confidence)
        assert exc_info.value.code == "EXCEPTION_242"


class TestDisagreementArea:
    def test_valid_construction(self) -> None:
        """合法构造（无 confidence 字段系有意设计——对立立场不存在单一置信度）"""
        area = _make_disagreement()
        assert area.red_position and area.blue_position and area.risk_note
        assert not hasattr(area, "confidence")

    def test_empty_area_raises(self) -> None:
        """area 非空"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_disagreement(area="")
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.parametrize(
        ("field", "bad_value"),
        [
            ("red_position", ""),
            ("blue_position", ""),
            ("risk_note", ""),
        ],
        ids=["red-empty", "blue-empty", "risk-note-empty"],
    )
    def test_empty_position_fields_raise(self, field: str, bad_value: str) -> None:
        """描述类字段（立场/风险提示）非空——每条子约束独立用例"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_disagreement(**{field: bad_value})
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == field


# ===================================================================
# 组 4: RiskView 风险视图校验
# ===================================================================


class TestRiskView:
    def test_valid_construction(self) -> None:
        view = _make_risk_view()
        assert len(view.consensus_areas) == 1
        assert len(view.disagreement_areas) == 1
        assert view.overall_risk_level == "MEDIUM"
        assert view.overlap_rate == 0.35
        assert view.warnings == ()

    def test_empty_consensus_areas_raises(self) -> None:
        """consensus_areas ≥ 1"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_risk_view(consensus_areas=())
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "consensus_areas"

    def test_empty_disagreement_areas_raises(self) -> None:
        """disagreement_areas ≥ 1"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_risk_view(disagreement_areas=())
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "disagreement_areas"

    @pytest.mark.parametrize(
        "bad_level", ["CRITICAL", "low", "High", "", "M"], ids=["critical", "lower", "mixed", "empty", "short"]
    )
    def test_invalid_risk_level_raises(self, bad_level: str) -> None:
        """overall_risk_level ∈ {"LOW","MEDIUM","HIGH"}"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_risk_view(overall_risk_level=bad_level)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "overall_risk_level"

    @pytest.mark.parametrize("bad_rate", [-0.01, 1.01], ids=["neg", "over"])
    def test_overlap_rate_out_of_range_raises(self, bad_rate: float) -> None:
        """overlap_rate ∈ [0.0, 1.0]"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_risk_view(overlap_rate=bad_rate)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "overlap_rate"

    def test_overlap_rate_boundaries_pass(self) -> None:
        """边界值 0.0 与 1.0 合法"""
        assert _make_risk_view(overlap_rate=0.0).overlap_rate == 0.0
        assert _make_risk_view(overlap_rate=1.0).overlap_rate == 1.0

    @pytest.mark.parametrize("level", ["LOW", "MEDIUM", "HIGH"], ids=["low", "medium", "high"])
    def test_all_risk_levels_pass(self, level: str) -> None:
        """三档风险等级全合法"""
        assert _make_risk_view(overall_risk_level=level).overall_risk_level == level

    def test_warnings_non_default(self) -> None:
        """warnings 可携带分化偏弱警告"""
        view = _make_risk_view(warnings=("红蓝重叠率 0.85 ≥ 0.80，分化偏弱",))
        assert len(view.warnings) == 1


# ===================================================================
# 组 5: DebateQuality / DebateResult 质量与结果
# ===================================================================


class TestDebateQuality:
    def test_valid_construction_with_v1_reserved_none(self) -> None:
        """MVP：gain_rate/repetition_rate 默认 None（V1 多轮预留）"""
        quality = _make_quality()
        assert quality.overlap_rate == 0.35
        assert quality.gain_rate is None
        assert quality.repetition_rate is None

    @pytest.mark.parametrize("bad_rate", [-0.01, 1.01], ids=["neg", "over"])
    def test_overlap_rate_out_of_range_raises(self, bad_rate: float) -> None:
        """overlap_rate ∈ [0.0, 1.0]"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_quality(overlap_rate=bad_rate)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "overlap_rate"

    def test_v1_fields_acceptable_when_set(self) -> None:
        """V1 演进：显式传 gain_rate/repetition_rate 合法"""
        quality = DebateQuality(overlap_rate=0.3, gain_rate=0.12, repetition_rate=0.2)
        assert quality.gain_rate == 0.12
        assert quality.repetition_rate == 0.2


class TestDebateResult:
    def test_valid_construction(self) -> None:
        result = _make_result()
        assert result.red_analysis.perspective is DebatePerspective.RED_AGGRESSIVE
        assert result.blue_analysis.perspective is DebatePerspective.BLUE_CONSERVATIVE
        assert result.duration_ms == 1200

    def test_invalid_debate_id_raises(self) -> None:
        """debate_id 必须 UUID（防御分支）"""
        with pytest.raises(EntityValidationError) as exc_info:
            DebateResult(
                debate_id=cast(uuid.UUID, "not-a-uuid"),
                topic_title="议题",
                red_analysis=_make_perspective(),
                blue_analysis=_make_perspective(perspective=DebatePerspective.BLUE_CONSERVATIVE),
                risk_view=_make_risk_view(),
                quality=_make_quality(),
                duration_ms=100,
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "debate_id"

    def test_negative_duration_ms_raises(self) -> None:
        """duration_ms ≥ 0"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_result(duration_ms=-1)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context.get("field") == "duration_ms"

    def test_zero_duration_ms_passes(self) -> None:
        """边界值 0 合法"""
        assert _make_result(duration_ms=0).duration_ms == 0


# ===================================================================
# 不可变设计（全部 frozen dataclass）
# ===================================================================


class TestImmutability:
    @pytest.mark.parametrize(
        "factory",
        [
            _make_debate_topic,
            _make_perspective,
            _make_consensus,
            _make_disagreement,
            _make_risk_view,
            _make_quality,
            _make_result,
        ],
        ids=["topic", "perspective", "consensus", "disagreement", "risk-view", "quality", "result"],
    )
    def test_all_vos_are_frozen(self, factory) -> None:
        """7 个 VO 均 frozen（setattr 抛 FrozenInstanceError）"""
        instance = factory()
        assert dataclasses.is_dataclass(instance)
        first_field = next(iter(dataclasses.fields(instance))).name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(instance, first_field, "mutated")

    def test_tuple_not_list_fields(self) -> None:
        """集合类字段全部 tuple（不可变）替代 list"""
        analysis = _make_perspective()
        view = _make_risk_view()
        assert isinstance(analysis.arguments, tuple)
        assert isinstance(analysis.risks, tuple)
        assert isinstance(view.consensus_areas, tuple)
        assert isinstance(view.disagreement_areas, tuple)
        assert isinstance(view.warnings, tuple)
