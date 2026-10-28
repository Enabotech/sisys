"""评估端口模型单元测试（Story 5.8）——EvaluationResult + 双端口 + 权重常量。

覆盖面：EvaluationResult 构造四字段 / 分数域 [0,1] 守卫（越界参数化 + bool 拒 →
ValidationError 201）/ frozen 不可变 / EVALUATION_WEIGHTS 两组和为 1.0 元断言 /
双端口 Protocol 方法形态（REQUIRED_METHODS callable）。

Run with:
    poetry run pytest tests/unit/application/test_agent_evaluation_model.py -v
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from src.application.ports.agent_evaluation import (
    ACTUAL_FACTUAL_WEIGHT,
    CONFIDENCE_ACCURACY_WEIGHT,
    CONTEXT_ARTIFACT_WEIGHT,
    CONTEXT_CITATION_WEIGHT,
    CONTEXT_RELEVANCE_WEIGHT,
    CONTEXT_TOOL_TRACE_WEIGHT,
    EVALUATION_WEIGHTS,
    HALLUCINATION_WEIGHT,
    AgentEvaluationPort,
    EvaluationModelResolverPort,
    EvaluationResult,
)
from src.domain.exceptions import ValidationError


def _valid_kwargs() -> dict[str, float]:
    """合法四分数构造基底。"""
    return {
        "hallucination_score": 0.2,
        "context_relevance": 0.4,
        "confidence_accuracy": 0.55,
        "overall_score": 0.5,
    }


class TestEvaluationResultConstruction:
    """构造与四分数语义。"""

    def test_construct_with_all_fields(self) -> None:
        """四字段全量构造与取值。"""
        result = EvaluationResult(**_valid_kwargs())
        assert result.hallucination_score == 0.2
        assert result.context_relevance == 0.4
        assert result.confidence_accuracy == 0.55
        assert result.overall_score == 0.5

    def test_boundary_values_accepted(self) -> None:
        """边界值 0.0/1.0 合法（闭区间）。"""
        result = EvaluationResult(
            hallucination_score=0.0,
            context_relevance=0.0,
            confidence_accuracy=0.0,
            overall_score=0.0,
        )
        assert result.hallucination_score == 0.0
        result_full = EvaluationResult(
            hallucination_score=1.0,
            context_relevance=1.0,
            confidence_accuracy=1.0,
            overall_score=1.0,
        )
        assert result_full.overall_score == 1.0


class TestEvaluationResultDomainGuard:
    """分数域 [0,1] 守卫（越界/类型错 → 201）。"""

    @pytest.mark.parametrize("bad_value", [-0.01, 1.01, 2.0, -1.0])
    @pytest.mark.parametrize(
        "field",
        ["hallucination_score", "context_relevance", "confidence_accuracy", "overall_score"],
    )
    def test_out_of_range_raises_201(self, field: str, bad_value: float) -> None:
        """越界参数化（四字段 × 越界值）→ 201 三段式（isinstance/code/context 字段名）。"""
        kwargs = {**_valid_kwargs(), field: bad_value}
        with pytest.raises(ValidationError) as exc_info:
            EvaluationResult(**kwargs)
        caught = exc_info.value
        assert isinstance(caught, ValidationError)
        assert caught.code == "EXCEPTION_201"
        assert field in caught.context, f"context 应携越界字段名 {field}: {caught.context}"
        assert caught.context[field] == str(bad_value)

    @pytest.mark.parametrize(
        "field",
        ["hallucination_score", "context_relevance", "confidence_accuracy", "overall_score"],
    )
    def test_bool_rejected(self, field: str) -> None:
        """bool 拒（bool 是 int 子类——显式拒绝防隐性分数）。"""
        kwargs = {**_valid_kwargs(), field: True}
        with pytest.raises(ValidationError) as exc_info:
            EvaluationResult(**kwargs)
        assert exc_info.value.code == "EXCEPTION_201"

    @pytest.mark.parametrize(
        "field",
        ["hallucination_score", "context_relevance", "confidence_accuracy", "overall_score"],
    )
    def test_string_type_rejected(self, field: str) -> None:
        """字符串类型拒（类型守卫 isinstance(x, (int, float))）。"""
        kwargs: dict[str, Any] = {**_valid_kwargs(), field: "0.5"}
        with pytest.raises(ValidationError) as exc_info:
            EvaluationResult(**kwargs)
        assert exc_info.value.code == "EXCEPTION_201"


class TestEvaluationResultFrozen:
    """frozen 不可变。"""

    def test_frozen_instance_error_on_assign(self) -> None:
        """赋值 raises FrozenInstanceError（setattr 动态形态——mypy 不做属性赋值检查）."""
        result = EvaluationResult(**_valid_kwargs())
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, "overall_score", 0.99)


class TestEvaluationWeights:
    """权重常量单源（防漂移——两组和为 1.0 元断言）。

    承重注记（CR1-F9）：下方两个 ``== 1.0`` 直接相等断言是 EvaluationResult
    [0,1] 域守卫不崩主链的前提——权重和二进制精确时全满场景 cr/overall 恰触
    1.0 不越界；任一权重改动选到非精确组合（如 0.1+0.2+0.7=1.0000000000000002）
    则 201 击穿降级网。**未来重标定者禁改 math.isclose**（改即静默拆护栏）。
    """

    def test_overall_weights_sum_to_one(self) -> None:
        """overall 三维权重和精确 == 1.0（二进制精确——R3 实算确认；承重断言见类 docstring）。"""
        assert HALLUCINATION_WEIGHT + CONTEXT_RELEVANCE_WEIGHT + CONFIDENCE_ACCURACY_WEIGHT == 1.0

    def test_context_weights_sum_to_one(self) -> None:
        """证据支撑度三元权重和精确 == 1.0（承重断言见类 docstring）。"""
        assert CONTEXT_CITATION_WEIGHT + CONTEXT_ARTIFACT_WEIGHT + CONTEXT_TOOL_TRACE_WEIGHT == 1.0

    def test_expected_weight_values(self) -> None:
        """权重值钉死（OD-3/OD-4/OD-5 裁定锚）。"""
        assert HALLUCINATION_WEIGHT == 0.4
        assert CONTEXT_RELEVANCE_WEIGHT == 0.35
        assert CONFIDENCE_ACCURACY_WEIGHT == 0.25
        assert ACTUAL_FACTUAL_WEIGHT == 0.5
        assert CONTEXT_CITATION_WEIGHT == 0.4
        assert CONTEXT_ARTIFACT_WEIGHT == 0.3
        assert CONTEXT_TOOL_TRACE_WEIGHT == 0.3

    def test_evaluation_weights_mapping_complete(self) -> None:
        """EVALUATION_WEIGHTS 聚合常量含七键。"""
        assert EVALUATION_WEIGHTS == {
            "HALLUCINATION_WEIGHT": HALLUCINATION_WEIGHT,
            "CONTEXT_RELEVANCE_WEIGHT": CONTEXT_RELEVANCE_WEIGHT,
            "CONFIDENCE_ACCURACY_WEIGHT": CONFIDENCE_ACCURACY_WEIGHT,
            "ACTUAL_FACTUAL_WEIGHT": ACTUAL_FACTUAL_WEIGHT,
            "CONTEXT_CITATION_WEIGHT": CONTEXT_CITATION_WEIGHT,
            "CONTEXT_ARTIFACT_WEIGHT": CONTEXT_ARTIFACT_WEIGHT,
            "CONTEXT_TOOL_TRACE_WEIGHT": CONTEXT_TOOL_TRACE_WEIGHT,
        }


class TestPortProtocols:
    """双端口 Protocol 形态。"""

    def test_agent_evaluation_port_methods(self) -> None:
        """AgentEvaluationPort REQUIRED_METHODS callable。"""
        assert hasattr(AgentEvaluationPort, "evaluate")
        assert callable(AgentEvaluationPort.evaluate)

    def test_evaluation_model_resolver_port_methods(self) -> None:
        """EvaluationModelResolverPort REQUIRED_METHODS callable。"""
        assert hasattr(EvaluationModelResolverPort, "resolve_config")
        assert callable(EvaluationModelResolverPort.resolve_config)

    def test_protocols_runtime_checkable(self) -> None:
        """@runtime_checkable Protocol（结构子类型校验可用）。"""

        class _EvalStub:
            async def evaluate(self, result): ...

        class _ResolverStub:
            async def resolve_config(self, input_text: str): ...

        assert isinstance(_EvalStub(), AgentEvaluationPort)
        assert isinstance(_ResolverStub(), EvaluationModelResolverPort)
