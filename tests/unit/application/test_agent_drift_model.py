"""DriftAssessment 模型与 DriftDetectionPort 端口形态单元测试——Story 5.9。

覆盖面：DriftAssessment 构造（frozen 十字段）/ observed_value 域守卫（越界/bool/
非数值参数化 → ValidationError 201 三段式）/ cusum 非负 / sample_count 下界 /
Literal 域守卫（direction/level）/ 一致性守卫（is_drifted × direction/level）/
frozen 不可变 / 端口方法 callable（REQUIRED_METHODS 契约面）。

Run with:
    poetry run pytest tests/unit/application/test_agent_drift_model.py -v
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from src.application.ports.agent_drift import DriftAssessment, DriftDetectionPort
from src.domain.exceptions import ValidationError


def _make_assessment(**overrides: Any) -> DriftAssessment:
    """构造合法基线 assessment（未确认检测态形态 + 覆盖注入——值类型 Any 容纳域外注入）。"""
    kwargs: dict[str, Any] = {
        "is_drifted": False,
        "baseline_ready": True,
        "drift_direction": "none",
        "drift_level": "none",
        "cusum_high": 0.0,
        "cusum_low": 0.3491,
        "baseline_mean": 0.8,
        "baseline_std": 0.1017,
        "observed_value": 0.4,
        "sample_count": 31,
    }
    kwargs.update(overrides)
    return DriftAssessment(**kwargs)


class TestDriftAssessmentConstruction:
    """构造与 frozen（应用层 DTO——EvaluationResult 同层同风格）。"""

    def test_construct_with_all_fields(self) -> None:
        """十字段构造真值断言。"""
        assessment = _make_assessment()
        assert assessment.is_drifted is False
        assert assessment.baseline_ready is True
        assert assessment.drift_direction == "none"
        assert assessment.drift_level == "none"
        assert assessment.cusum_high == 0.0
        assert assessment.cusum_low == 0.3491
        assert assessment.baseline_mean == 0.8
        assert assessment.baseline_std == 0.1017
        assert assessment.observed_value == 0.4
        assert assessment.sample_count == 31

    def test_confirmed_form_construct(self) -> None:
        """确认形态构造（is_drifted=True + direction/level 非 none）。"""
        assessment = _make_assessment(
            is_drifted=True,
            drift_direction="down",
            drift_level="severe",
            cusum_low=1.7457,
            sample_count=35,
        )
        assert assessment.is_drifted is True
        assert assessment.drift_direction == "down"
        assert assessment.drift_level == "severe"

    def test_frozen_immutable(self) -> None:
        """frozen 不可变断言（setattr 动态形式绕过静态只读检查）。"""
        assessment = _make_assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(assessment, "is_drifted", True)


class TestDriftAssessmentObservedValueDomainGuard:
    """observed_value 域守卫（[0,1] 闭区间 + bool 拒 + 数值类型——201 三段式）。"""

    @pytest.mark.parametrize("bad_value", [-0.01, 1.01, -1.0, 2.0], ids=["neg", "over", "neg-one", "two"])
    def test_out_of_range_raises_201(self, bad_value: float) -> None:
        """越界参数化 → ValidationError 201 + context 携字段名。"""
        with pytest.raises(ValidationError) as exc_info:
            _make_assessment(observed_value=bad_value)
        assert exc_info.value.code == "EXCEPTION_201"
        assert "observed_value" in exc_info.value.context

    @pytest.mark.parametrize("bad_value", [True, False], ids=["true", "false"])
    def test_bool_rejected(self, bad_value: bool) -> None:
        """bool 拒（True 是 int 子类——5.8 EvaluationResult 同款守卫）。"""
        with pytest.raises(ValidationError) as exc_info:
            _make_assessment(observed_value=bad_value)
        assert exc_info.value.code == "EXCEPTION_201"

    @pytest.mark.parametrize("bad_value", ["0.8", None], ids=["str", "none"])
    def test_non_numeric_rejected(self, bad_value: object) -> None:
        """非数值拒（str/None）。"""
        with pytest.raises(ValidationError) as exc_info:
            _make_assessment(observed_value=bad_value)
        assert exc_info.value.code == "EXCEPTION_201"


class TestDriftAssessmentNumericDomainGuards:
    """cusum 非负与 sample_count 下界守卫。"""

    @pytest.mark.parametrize("field", ["cusum_high", "cusum_low"], ids=["high", "low"])
    def test_negative_cusum_raises_201(self, field: str) -> None:
        """cusum 负值拒（双侧累积和 max(0,·) 语义——恒 ≥0）。"""
        with pytest.raises(ValidationError) as exc_info:
            _make_assessment(**{field: -0.1})
        assert exc_info.value.code == "EXCEPTION_201"
        assert field in exc_info.value.context

    def test_zero_sample_count_raises_201(self) -> None:
        """sample_count ≥1 下界（0 拒——update 至少灌入一样本才返回）。"""
        with pytest.raises(ValidationError) as exc_info:
            _make_assessment(sample_count=0)
        assert exc_info.value.code == "EXCEPTION_201"
        assert "sample_count" in exc_info.value.context


class TestDriftAssessmentLiteralGuards:
    """drift_direction/drift_level Literal 域守卫。"""

    @pytest.mark.parametrize("bad_direction", ["upward", "DOWN", ""], ids=["upward", "upper", "empty"])
    def test_invalid_direction_raises_201(self, bad_direction: str) -> None:
        """direction 域外值拒（合法 {"up","down","none"}）。"""
        with pytest.raises(ValidationError) as exc_info:
            _make_assessment(drift_direction=bad_direction)
        assert exc_info.value.code == "EXCEPTION_201"
        assert "drift_direction" in exc_info.value.context

    @pytest.mark.parametrize("bad_level", ["minor", "critical", ""], ids=["minor", "critical", "empty"])
    def test_invalid_level_raises_201(self, bad_level: str) -> None:
        """level 域外值拒（合法 {"moderate","severe","none"}——minor 观察档 OD-5 不可达）。"""
        with pytest.raises(ValidationError) as exc_info:
            _make_assessment(drift_level=bad_level)
        assert exc_info.value.code == "EXCEPTION_201"
        assert "drift_level" in exc_info.value.context


class TestDriftAssessmentConsistencyGuards:
    """is_drifted × direction/level 一致性守卫（确认语义锁）。"""

    def test_drifted_with_none_level_raises_201(self) -> None:
        """is_drifted=True + level="none" 拒（level="none" 泄入事件语义污染防线）。"""
        with pytest.raises(ValidationError) as exc_info:
            _make_assessment(is_drifted=True, drift_direction="down", drift_level="none")
        assert exc_info.value.code == "EXCEPTION_201"

    def test_drifted_with_none_direction_raises_201(self) -> None:
        """is_drifted=True + direction="none" 拒。"""
        with pytest.raises(ValidationError) as exc_info:
            _make_assessment(is_drifted=True, drift_direction="none", drift_level="severe")
        assert exc_info.value.code == "EXCEPTION_201"

    def test_not_drifted_with_non_none_level_raises_201(self) -> None:
        """is_drifted=False + level 非 none 拒（未确认态 level 必 none——确认语义只锁 level）。"""
        with pytest.raises(ValidationError) as exc_info:
            _make_assessment(is_drifted=False, drift_direction="up", drift_level="moderate")
        assert exc_info.value.code == "EXCEPTION_201"

    def test_not_drifted_with_direction_allowed(self) -> None:
        """is_drifted=False + direction 探测值合法（方向在未确认时可带探测值——只锁 level）。"""
        assessment = _make_assessment(is_drifted=False, drift_direction="up", drift_level="none")
        assert assessment.drift_direction == "up"


class TestDriftDetectionPortShape:
    """端口形态（runtime_checkable Protocol——契约测试 11 维度之单测面）。"""

    def test_port_methods_defined(self) -> None:
        """REQUIRED_METHODS 在位（update + trigger_recalibration——OD-7 单方法原子化）。"""
        for method in ("update", "trigger_recalibration"):
            assert hasattr(DriftDetectionPort, method), f"端口应定义 {method}"

    def test_port_is_runtime_checkable_protocol(self) -> None:
        """runtime_checkable（isinstance 消费面——组合根接线断言前提）。"""

        class _DummyDetector:
            async def update(self, score: float) -> DriftAssessment:
                return _make_assessment()

            async def trigger_recalibration(self, assessment: DriftAssessment, agent_id: str | None = None) -> None:
                return None

        assert isinstance(_DummyDetector(), DriftDetectionPort)
