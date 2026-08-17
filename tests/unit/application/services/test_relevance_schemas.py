"""Story 3.7 检索相关性评估 Pydantic Schema 单元测试

验证 RelevanceEvaluation 和 RuleBasedEvaluation Schema 定义。
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError


class TestRelevanceEvaluationSchema:
    """RelevanceEvaluation Schema 验证"""

    def test_is_base_model_subclass(self) -> None:
        """RelevanceEvaluation 是 Pydantic BaseModel 子类"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        assert issubclass(RelevanceEvaluation, BaseModel)

    def test_has_dimension_fields(self) -> None:
        """包含 context_relevance completeness timeliness 维度字段"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        schema = RelevanceEvaluation.model_json_schema()
        props = schema["properties"]
        assert "context_relevance" in props
        assert "completeness" in props
        assert "timeliness" in props

    def test_has_reason_fields(self) -> None:
        """包含 context_relevance_reason completeness_reason timeliness_reason 理由字段"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        schema = RelevanceEvaluation.model_json_schema()
        props = schema["properties"]
        assert "context_relevance_reason" in props
        assert "completeness_reason" in props
        assert "timeliness_reason" in props

    def test_has_overall_score_computed_field(self) -> None:
        """包含 overall_score 字段"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        assert hasattr(RelevanceEvaluation, "overall_score")

    def test_has_should_block_computed_field(self) -> None:
        """包含 should_block 字段"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        assert hasattr(RelevanceEvaluation, "should_block")

    def test_has_block_reason_field(self) -> None:
        """包含 block_reason 字段"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        assert "block_reason" in RelevanceEvaluation.model_fields

    def test_overall_score_calculation(self) -> None:
        """overall_score 为 (context_relevance + completeness + timeliness) / 3.0"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        result = RelevanceEvaluation(
            context_relevance=0.8,
            context_relevance_reason="reason1",
            completeness=0.7,
            completeness_reason="reason2",
            timeliness=0.9,
            timeliness_reason="reason3",
        )
        expected = (0.8 + 0.7 + 0.9) / 3.0
        assert result.overall_score == expected

    def test_should_block_when_below_threshold(self) -> None:
        """综合评分 < 0.6 时 should_block=True"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        result = RelevanceEvaluation(
            context_relevance=0.5,
            context_relevance_reason="reason",
            completeness=0.5,
            completeness_reason="reason",
            timeliness=0.5,
            timeliness_reason="reason",
        )
        assert result.should_block is True
        assert result.block_reason is not None

    def test_should_not_block_when_above_threshold(self) -> None:
        """综合评分 >= 0.6 时 should_block=False"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        result = RelevanceEvaluation(
            context_relevance=0.8,
            context_relevance_reason="reason",
            completeness=0.8,
            completeness_reason="reason",
            timeliness=0.8,
            timeliness_reason="reason",
        )
        assert result.should_block is False
        assert result.block_reason is None

    def test_score_range_constraint(self) -> None:
        """各维度 score 范围约束在 0-1 之间"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        schema = RelevanceEvaluation.model_json_schema()
        props = schema["properties"]
        for field_name in ("context_relevance", "completeness", "timeliness"):
            field_props = props[field_name]
            assert field_props.get("minimum") == 0.0
            assert field_props.get("maximum") == 1.0

    def test_out_of_range_score_raises(self) -> None:
        """超出范围的分数抛出 ValidationError"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        with pytest.raises(ValidationError):
            RelevanceEvaluation(
                context_relevance=1.5,  # 超出范围
                context_relevance_reason="reason",
                completeness=0.5,
                completeness_reason="reason",
                timeliness=0.5,
                timeliness_reason="reason",
            )

    def test_negative_score_raises(self) -> None:
        """负数分数抛出 ValidationError"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        with pytest.raises(ValidationError):
            RelevanceEvaluation(
                context_relevance=-0.1,
                context_relevance_reason="reason",
                completeness=0.5,
                completeness_reason="reason",
                timeliness=0.5,
                timeliness_reason="reason",
            )

    def test_should_block_requires_block_reason(self) -> None:
        """should_block=True 时 block_reason 必须有值"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        result = RelevanceEvaluation(
            context_relevance=0.3,
            context_relevance_reason="reason",
            completeness=0.3,
            completeness_reason="reason",
            timeliness=0.3,
            timeliness_reason="reason",
        )
        assert result.should_block is True
        assert result.block_reason is not None

    def test_should_not_block_requires_none_block_reason(self) -> None:
        """should_block=False 时 block_reason 必须为 None"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        result = RelevanceEvaluation(
            context_relevance=0.9,
            context_relevance_reason="reason",
            completeness=0.9,
            completeness_reason="reason",
            timeliness=0.9,
            timeliness_reason="reason",
        )
        assert result.should_block is False
        assert result.block_reason is None

    def test_successful_construction(self) -> None:
        """正常构造不报错"""
        from src.application.services.relevance_schemas import RelevanceEvaluation

        result = RelevanceEvaluation(
            context_relevance=0.75,
            context_relevance_reason="reasonably relevant",
            completeness=0.60,
            completeness_reason="core info covered",
            timeliness=0.90,
            timeliness_reason="recent data",
        )
        assert result.context_relevance == 0.75
        assert result.completeness == 0.60
        assert result.timeliness == 0.90
        assert result.overall_score == (0.75 + 0.60 + 0.90) / 3.0


class TestRuleBasedEvaluationSchema:
    """RuleBasedEvaluation Schema 验证"""

    def test_is_base_model_subclass(self) -> None:
        """RuleBasedEvaluation 是 Pydantic BaseModel 子类"""
        from src.application.services.relevance_schemas import RuleBasedEvaluation

        assert issubclass(RuleBasedEvaluation, BaseModel)

    def test_has_required_fields(self) -> None:
        """包含 has_valid_results min_score max_score avg_score result_count quick_block 字段"""
        from src.application.services.relevance_schemas import RuleBasedEvaluation

        schema = RuleBasedEvaluation.model_json_schema()
        props = schema["properties"]
        assert "has_valid_results" in props
        assert "min_score" in props
        assert "max_score" in props
        assert "avg_score" in props
        assert "result_count" in props
        assert "quick_block" in props

    def test_empty_results_normalized(self) -> None:
        """空结果时 has_valid_results=False 且 min_score=max_score=avg_score=0.0"""
        from src.application.services.relevance_schemas import RuleBasedEvaluation

        result = RuleBasedEvaluation(has_valid_results=False)
        assert result.min_score == 0.0
        assert result.max_score == 0.0
        assert result.avg_score == 0.0
        assert result.result_count == 0

    def test_empty_results_quick_block(self) -> None:
        """空结果时 quick_block=True"""
        from src.application.services.relevance_schemas import RuleBasedEvaluation

        result = RuleBasedEvaluation(has_valid_results=False)
        assert result.quick_block is True

    def test_valid_results_construction(self) -> None:
        """有效结果构造"""
        from src.application.services.relevance_schemas import RuleBasedEvaluation

        result = RuleBasedEvaluation(
            has_valid_results=True,
            min_score=0.3,
            max_score=0.9,
            avg_score=0.65,
            result_count=10,
            quick_block=False,
        )
        assert result.has_valid_results is True
        assert result.min_score == 0.3
        assert result.max_score == 0.9
        assert result.avg_score == 0.65
        assert result.result_count == 10
        assert result.quick_block is False

    def test_low_avg_score_quick_block(self) -> None:
        """平均分低时 quick_block=True"""
        from src.application.services.relevance_schemas import RuleBasedEvaluation

        result = RuleBasedEvaluation(
            has_valid_results=True,
            min_score=0.1,
            max_score=0.4,
            avg_score=0.25,
            result_count=5,
            quick_block=True,
        )
        assert result.quick_block is True
