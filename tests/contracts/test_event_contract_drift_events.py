"""DriftDetected 领域事件契约测试——Story 5.9 注册/aggregate/to_dict 三断言。

先例形态：tests/contracts/test_event_contract_tool_version_events.py（模块级 EVENTS
字典 + 注册断言 + aggregate_type 断言 + payload 契约断言 + JSON roundtrip）。

Run with:
    poetry run pytest tests/contracts/test_event_contract_drift_events.py -v
"""

from __future__ import annotations

import json

from src.domain.events.base import DomainEvent
from src.domain.events.drift_events import DriftDetected

EVENT_TYPE = "DriftDetected"


def _make_sample_event() -> DriftDetected:
    """构造样本事件（确认漂移形态——severe down 手算锚字段值）。"""
    return DriftDetected(
        agent_id="agent-contract",
        metric_name="overall_score",
        drift_direction="down",
        drift_level="severe",
        cusum_high=0.0,
        cusum_low=1.7457,
        baseline_mean=0.8,
        baseline_std=0.1017,
        observed_value=0.4,
        sample_count=35,
    )


class TestDriftDetectedEventContract:
    """事件契约三断言（注册 / aggregate_type / to_dict payload）。"""

    def test_event_registered_in_domain_registry(self) -> None:
        """注册断言（event_type init=False 写法触发 __init_subclass__ 自动注册）。"""
        assert DomainEvent._registry.get(EVENT_TYPE) is DriftDetected, "DriftDetected 应注册于 DomainEvent._registry"

    def test_aggregate_type_is_agent_evaluation(self) -> None:
        """aggregate_type 断言（漂移的监控对象是 Agent 评估质量——与 5.8「评估非领域概念」分界）。"""
        event = _make_sample_event()
        assert event.aggregate_type == "AgentEvaluation"
        assert event.aggregate_id == event.drift_id

    def test_to_dict_payload_contract(self) -> None:
        """to_dict payload 含全部业务字段（agent_id 在场——R2 补锚）。"""
        event = _make_sample_event()
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
        assert payload["agent_id"] == "agent-contract", "agent_id 应在 payload 序列化在场"
        assert payload["recommended_action"] == "manual_review"

    def test_to_dict_round_trip_json(self) -> None:
        """JSON roundtrip（outbox JSONB / RabbitMQ body 序列化前提）。"""
        data = _make_sample_event().to_dict()
        encoded = json.dumps(data, ensure_ascii=False)
        decoded = json.loads(encoded)
        assert decoded["event_type"] == EVENT_TYPE
        assert decoded["aggregate_type"] == "AgentEvaluation"
