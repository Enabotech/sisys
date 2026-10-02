"""Story 4.5 — debate_schemas（LLM 结构化输出 Schema）单元测试

验证 Pydantic Schema 字段约束（arguments 1~8/confidence 0~1/risk_level Literal）、
to_domain() 领域 VO 转换（含 list→tuple 转换职责）与越界拒绝。

约束：
- Schema 位于应用层（领域零依赖红线，Pydantic 仅应用层可用）
- to_domain() 承担 list→tuple 转换（VO 字段全 tuple，Schema 全 list）
- RiskView 的 overlap_rate/warnings 由服务端注入（不信任 LLM 输出分化度）
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.application.services.debate_schemas import (
    ConsensusAreaSchema,
    DisagreementAreaSchema,
    PerspectiveAnalysisSchema,
    RiskViewSchema,
)
from src.domain.value_objects.debate import (
    DebatePerspective,
    RiskView,
)


def _make_perspective_schema(
    stance: str = "应当立即进入东南亚市场",
    arguments: list[str] | None = None,
    risks: list[str] | None = None,
    recommendations: list[str] | None = None,
    confidence: float = 0.8,
) -> PerspectiveAnalysisSchema:
    """构造视角 Schema（测试工厂，默认全合法）"""
    return PerspectiveAnalysisSchema(
        stance=stance,
        arguments=arguments if arguments is not None else ["窗口期稍纵即逝", "竞品尚未垄断"],
        risks=risks if risks is not None else ["初期投入高"],
        recommendations=recommendations if recommendations is not None else ["优先核心市场"],
        confidence=confidence,
    )


def _make_consensus_schema(**overrides) -> ConsensusAreaSchema:
    """构造共识区域 Schema（测试工厂）"""
    defaults = {"area": "市场潜力", "description": "双方认可增长潜力", "confidence": 0.9}
    return ConsensusAreaSchema(**{**defaults, **overrides})


def _make_disagreement_schema(**overrides) -> DisagreementAreaSchema:
    """构造分歧区域 Schema（测试工厂）"""
    defaults = {
        "area": "进入时机",
        "red_position": "立即进入",
        "blue_position": "延后观察",
        "risk_note": "时机误判放大投入风险",
    }
    return DisagreementAreaSchema(**{**defaults, **overrides})


def _make_risk_view_schema(**overrides) -> RiskViewSchema:
    """构造风险视图 Schema（测试工厂，默认全合法）"""
    defaults = {
        "consensus_areas": [_make_consensus_schema()],
        "disagreement_areas": [_make_disagreement_schema()],
        "overall_risk_level": "MEDIUM",
    }
    return RiskViewSchema(**{**defaults, **overrides})


# ===================================================================
# PerspectiveAnalysisSchema 字段约束
# ===================================================================


class TestPerspectiveAnalysisSchemaConstraints:
    def test_valid_construction(self) -> None:
        """合法构造全字段"""
        schema = _make_perspective_schema()
        assert schema.stance == "应当立即进入东南亚市场"
        assert len(schema.arguments) == 2
        assert schema.confidence == 0.8

    def test_arguments_min_length(self) -> None:
        """arguments 至少 1 条"""
        with pytest.raises(ValidationError):
            _make_perspective_schema(arguments=[])

    def test_arguments_max_length(self) -> None:
        """arguments 至多 8 条"""
        with pytest.raises(ValidationError):
            _make_perspective_schema(arguments=[f"论点{i}" for i in range(9)])

    def test_arguments_8_boundary_passes(self) -> None:
        """边界值 8 条合法"""
        schema = _make_perspective_schema(arguments=[f"论点{i}" for i in range(8)])
        assert len(schema.arguments) == 8

    def test_confidence_out_of_range(self) -> None:
        """confidence ge=0 le=1"""
        with pytest.raises(ValidationError):
            _make_perspective_schema(confidence=1.01)
        with pytest.raises(ValidationError):
            _make_perspective_schema(confidence=-0.01)

    def test_confidence_boundaries_pass(self) -> None:
        """边界值 0.0/1.0 合法"""
        assert _make_perspective_schema(confidence=0.0).confidence == 0.0
        assert _make_perspective_schema(confidence=1.0).confidence == 1.0

    def test_empty_risks_allowed(self) -> None:
        """risks/recommendations 允许空 list（领域 VO 允许空 tuple）"""
        schema = _make_perspective_schema(risks=[], recommendations=[])
        assert schema.risks == []
        assert schema.recommendations == []


# ===================================================================
# RiskViewSchema 字段约束
# ===================================================================


class TestRiskViewSchemaConstraints:
    def test_valid_construction(self) -> None:
        """合法构造（无 overlap_rate 字段——服务端注入）"""
        schema = _make_risk_view_schema()
        assert schema.overall_risk_level == "MEDIUM"
        assert not hasattr(schema, "overlap_rate"), "Schema 不应含 overlap_rate（服务端裁决）"

    def test_consensus_areas_min_length(self) -> None:
        """consensus_areas 至少 1 条"""
        with pytest.raises(ValidationError):
            _make_risk_view_schema(consensus_areas=[])

    def test_disagreement_areas_min_length(self) -> None:
        """disagreement_areas 至少 1 条"""
        with pytest.raises(ValidationError):
            _make_risk_view_schema(disagreement_areas=[])

    @pytest.mark.parametrize("level", ["LOW", "MEDIUM", "HIGH"])
    def test_risk_level_literal_passes(self, level: str) -> None:
        """Literal 三档全合法"""
        assert _make_risk_view_schema(overall_risk_level=level).overall_risk_level == level

    @pytest.mark.parametrize("level", ["CRITICAL", "low", ""])
    def test_risk_level_invalid_rejected(self, level: str) -> None:
        """Literal 外值拒绝"""
        with pytest.raises(ValidationError):
            _make_risk_view_schema(overall_risk_level=level)

    def test_area_schema_confidence_constraint(self) -> None:
        """嵌套 ConsensusAreaSchema confidence 约束生效"""
        with pytest.raises(ValidationError):
            _make_risk_view_schema(consensus_areas=[_make_consensus_schema(confidence=1.5)])

    def test_area_schema_empty_description_rejected(self) -> None:
        """嵌套区域描述非空"""
        with pytest.raises(ValidationError):
            _make_risk_view_schema(consensus_areas=[_make_consensus_schema(description="")])

    def test_disagreement_position_empty_rejected(self) -> None:
        """嵌套分歧立场非空"""
        with pytest.raises(ValidationError):
            _make_risk_view_schema(disagreement_areas=[_make_disagreement_schema(red_position="")])


# ===================================================================
# to_domain() 领域 VO 转换
# ===================================================================


class TestToDomainConversion:
    def test_perspective_to_domain_red(self) -> None:
        """视角 Schema → PerspectiveAnalysis（红）"""
        schema = _make_perspective_schema()
        domain = schema.to_domain(DebatePerspective.RED_AGGRESSIVE)
        assert domain.perspective is DebatePerspective.RED_AGGRESSIVE
        assert domain.stance == schema.stance
        assert domain.confidence == 0.8

    def test_perspective_to_domain_blue(self) -> None:
        """视角 Schema → PerspectiveAnalysis（蓝）"""
        schema = _make_perspective_schema(stance="应当延后观察", confidence=0.6)
        domain = schema.to_domain(DebatePerspective.BLUE_CONSERVATIVE)
        assert domain.perspective is DebatePerspective.BLUE_CONSERVATIVE
        assert domain.confidence == 0.6

    def test_perspective_to_domain_list_to_tuple(self) -> None:
        """list→tuple 转换是 to_domain 职责"""
        schema = _make_perspective_schema()
        domain = schema.to_domain(DebatePerspective.RED_AGGRESSIVE)
        assert isinstance(domain.arguments, tuple)
        assert isinstance(domain.risks, tuple)
        assert isinstance(domain.recommendations, tuple)
        assert list(domain.arguments) == schema.arguments

    def test_risk_view_to_domain_with_server_injected_overlap(self) -> None:
        """RiskViewSchema → RiskView：overlap_rate/warnings 由服务端注入"""
        schema = _make_risk_view_schema()
        domain = schema.to_domain(overlap_rate=0.42, warnings=("分化偏弱警告",))
        assert isinstance(domain, RiskView)
        assert domain.overlap_rate == 0.42
        assert domain.warnings == ("分化偏弱警告",)
        assert domain.overall_risk_level == "MEDIUM"

    def test_risk_view_to_domain_default_no_warnings(self) -> None:
        """warnings 默认空 tuple"""
        schema = _make_risk_view_schema()
        domain = schema.to_domain(overlap_rate=0.3)
        assert domain.warnings == ()

    def test_risk_view_to_domain_nested_tuples(self) -> None:
        """嵌套区域也转 tuple"""
        schema = _make_risk_view_schema(
            consensus_areas=[_make_consensus_schema(), _make_consensus_schema(area="第二共识")],
        )
        domain = schema.to_domain(overlap_rate=0.3)
        assert isinstance(domain.consensus_areas, tuple)
        assert len(domain.consensus_areas) == 2
        assert isinstance(domain.disagreement_areas, tuple)

    def test_to_domain_double_invariant_enforcement(self) -> None:
        """Pydantic 校验 + 领域 VO 双重不变量：合法输入两端都过"""
        schema = _make_perspective_schema()
        domain = schema.to_domain(DebatePerspective.RED_AGGRESSIVE)
        assert 0.0 <= domain.confidence <= 1.0
        assert 1 <= len(domain.arguments) <= 8
