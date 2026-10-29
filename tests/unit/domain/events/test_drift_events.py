"""DriftDetected 领域事件单元测试——Story 5.9 漂移检测确认事件。

覆盖面：构造（kw_only 必填）/ frozen 不可变 / drift_id 自动生成 / recommended_action
默认 / aggregate_type 与 __post_init__ / DomainEvent._registry 自动注册 / to_dict
序列化 payload 业务字段（含 agent_id 在场）。

Run with:
    poetry run pytest tests/unit/domain/events/test_drift_events.py -v
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.drift_events import DriftDetected


def _make_event(**overrides: Any) -> DriftDetected:
    """构造样本事件（合法必填字段基线 + 覆盖注入）。"""
    kwargs: dict[str, Any] = {
        "metric_name": "overall_score",
        "drift_direction": "down",
        "drift_level": "severe",
        "cusum_high": 0.0,
        "cusum_low": 1.7457,
        "baseline_mean": 0.8,
        "baseline_std": 0.1017,
        "observed_value": 0.4,
        "sample_count": 35,
    }
    kwargs.update(overrides)
    return DriftDetected(**kwargs)


class TestDriftDetectedConstruction:
    """构造与 kw_only 纪律（AgentProfileLoaded 先例——DomainEvent 基类字段全带默认值）。"""

    def test_construct_with_required_kwargs(self) -> None:
        """必填字段 kw_only 构造（九业务字段 + 默认字段）。"""
        event = _make_event()
        assert event.metric_name == "overall_score"
        assert event.drift_direction == "down"
        assert event.drift_level == "severe"
        assert event.cusum_low == 1.7457
        assert event.cusum_high == 0.0
        assert event.baseline_mean == 0.8
        assert event.baseline_std == 0.1017
        assert event.observed_value == 0.4
        assert event.sample_count == 35

    def test_event_type_fixed_init_false(self) -> None:
        """event_type 固定 DriftDetected（init=False——自动注册触发条件）。"""
        event = _make_event()
        assert event.event_type == "DriftDetected"

    def test_drift_id_auto_generated(self) -> None:
        """drift_id 自动生成（uuid4 default_factory——StrategicDeviationWarning.warning_id 模式）。"""
        first = _make_event()
        second = _make_event()
        assert isinstance(first.drift_id, uuid.UUID)
        assert first.drift_id != second.drift_id, "两次构造应生成不同 drift_id"

    def test_recommended_action_default_manual_review(self) -> None:
        """recommended_action 默认 manual_review（OD-6 人工介入单通道）。"""
        event = _make_event()
        assert event.recommended_action == "manual_review"

    def test_agent_id_default_none(self) -> None:
        """agent_id 默认 None（SINGLETON 跨 Agent 混流——None=未知/混合）。"""
        event = _make_event()
        assert event.agent_id is None

    def test_agent_id_explicit_passthrough(self) -> None:
        """agent_id 显式透传（execute 形参——人工介入定位维度）。"""
        event = _make_event(agent_id="agent-x")
        assert event.agent_id == "agent-x"

    def test_frozen_immutable(self) -> None:
        """frozen 不可变断言（FrozenInstanceError——setattr 动态形式绕过静态只读检查）。"""
        event = _make_event()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(event, "drift_level", "moderate")


class TestDriftDetectedAggregateAndRegistry:
    """aggregate 设置与自动注册（DomainEvent._registry 多态表）。"""

    def test_aggregate_id_from_drift_id(self) -> None:
        """__post_init__：aggregate_id ← drift_id。"""
        event = _make_event()
        assert event.aggregate_id == event.drift_id

    def test_aggregate_type_agent_evaluation(self) -> None:
        """aggregate_type 固定 AgentEvaluation（漂移的监控对象是 Agent 评估质量）。"""
        event = _make_event()
        assert event.aggregate_type == "AgentEvaluation"

    def test_registered_in_domain_registry(self) -> None:
        """DomainEvent._registry 自动注册（event_type init=False 写法触发）。"""
        assert DomainEvent._registry.get("DriftDetected") is DriftDetected

    def test_is_domain_event(self) -> None:
        """继承面：DomainEvent。"""
        assert isinstance(_make_event(), DomainEvent)


class TestDriftDetectedSerialization:
    """to_dict 序列化（payload 并入业务字段——事件契约三断言之序列化面）。"""

    def test_to_dict_payload_contains_business_fields(self) -> None:
        """payload 含全部业务字段（agent_id 在场断言——None 默认序列化）。"""
        event = _make_event()
        payload = event.to_dict()["payload"]
        for field in (
            "agent_id",
            "metric_name",
            "drift_direction",
            "drift_level",
            "cusum_high",
            "cusum_low",
            "baseline_mean",
            "baseline_std",
            "observed_value",
            "sample_count",
            "recommended_action",
        ):
            assert field in payload, f"payload 应含 {field}（实际 {sorted(payload)}）"

    def test_to_dict_top_level_fields(self) -> None:
        """顶层字段（event_type/aggregate_type——核心 schema 键）。"""
        data = _make_event().to_dict()
        assert data["event_type"] == "DriftDetected"
        assert data["aggregate_type"] == "AgentEvaluation"

    def test_to_dict_json_serializable(self) -> None:
        """整体 JSON 可序列化（outbox JSONB 前提）。"""
        import json

        json.dumps(_make_event(agent_id="agent-x").to_dict())
