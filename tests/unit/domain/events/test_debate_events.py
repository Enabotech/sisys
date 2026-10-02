"""Story 4.5 — DebateCompleted 领域事件单元测试

验证事件构造（aggregate 归属/metadata 透传/超长 title 截断）、
to_dict/from_dict roundtrip（_registry 多态注册生效）与 frozen 不变性。
"""

from __future__ import annotations

import dataclasses
import uuid

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.debate_events import DebateCompleted


def _make_event(topic_title: str = "公司是否应在下一财年进入东南亚市场") -> DebateCompleted:
    """构造标准 DebateCompleted 事件（测试工厂）"""
    return DebateCompleted(
        debate_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        topic_title=topic_title,
        red_stance="应当立即进入抢占先机",
        blue_stance="应当延后观察规避风险",
        consensus_count=2,
        disagreement_count=1,
        overlap_rate=0.35,
        overall_risk_level="MEDIUM",
        duration_ms=8500,
        temperature_profile={"red": 0.8, "blue": 0.5, "synthesis": 0.2},
    )


class TestDebateCompletedConstruction:
    def test_event_type_fixed(self) -> None:
        """event_type 固定为 DebateCompleted（init=False 自动注册）"""
        event = _make_event()
        assert event.event_type == "DebateCompleted"

    def test_aggregate_type_is_debate_session(self) -> None:
        """aggregate_type 填 DebateSession"""
        event = _make_event()
        assert event.aggregate_type == "DebateSession"

    def test_aggregate_id_is_debate_id(self) -> None:
        """aggregate_id 填 debate_id"""
        debate_id = uuid.uuid4()
        event2 = DebateCompleted(
            debate_id=debate_id,
            tenant_id=uuid.uuid4(),
            topic_title="议题",
            red_stance="红",
            blue_stance="蓝",
            consensus_count=1,
            disagreement_count=1,
            overlap_rate=0.5,
            overall_risk_level="LOW",
            duration_ms=100,
            temperature_profile={"red": 0.8, "blue": 0.5, "synthesis": 0.2},
        )
        assert event2.aggregate_id == debate_id

    def test_metadata_carries_tenant_id(self) -> None:
        """metadata 透传 tenant_id"""
        tenant_id = uuid.uuid4()
        event = DebateCompleted(
            debate_id=uuid.uuid4(),
            tenant_id=tenant_id,
            topic_title="议题",
            red_stance="红",
            blue_stance="蓝",
            consensus_count=1,
            disagreement_count=1,
            overlap_rate=0.5,
            overall_risk_level="LOW",
            duration_ms=100,
            temperature_profile={"red": 0.8, "blue": 0.5, "synthesis": 0.2},
        )
        assert event.metadata.get("tenant_id") == tenant_id

    def test_topic_title_truncated_over_100_chars(self) -> None:
        """topic_title 超 100 字符经 object.__setattr__ 截断（frozen 惯例）"""
        long_title = "超长议题标题" * 30  # 150 字符
        event = _make_event(topic_title=long_title)
        assert len(event.topic_title) == 100
        assert event.topic_title == long_title[:100]

    def test_topic_title_unchanged_under_100(self) -> None:
        """100 字符以内不截断"""
        title = "题" * 100
        event = _make_event(topic_title=title)
        assert event.topic_title == title

    def test_inherits_domain_event(self) -> None:
        """继承 DomainEvent 基类（核心字段完整）"""
        event = _make_event()
        assert isinstance(event, DomainEvent)
        assert hasattr(event, "event_id")
        assert hasattr(event, "timestamp")
        assert hasattr(event, "schema_version")


class TestDebateCompletedRoundtrip:
    def test_to_dict_payload_complete(self) -> None:
        """to_dict 的 payload 含全部子类字段（temperature_profile 可 JSON 序列化）"""
        event = _make_event()
        data = event.to_dict()
        payload = data["payload"]
        for field_name in (
            "debate_id",
            "tenant_id",
            "topic_title",
            "red_stance",
            "blue_stance",
            "consensus_count",
            "disagreement_count",
            "overlap_rate",
            "overall_risk_level",
            "duration_ms",
            "temperature_profile",
        ):
            assert field_name in payload, f"payload 缺少 {field_name}"
        assert payload["temperature_profile"] == {"red": 0.8, "blue": 0.5, "synthesis": 0.2}

    def test_from_dict_roundtrip(self) -> None:
        """to_dict → from_dict roundtrip（_registry 多态注册生效）

        注：与项目历史行为对齐（test_event_contract_tool_executed.py），
        from_dict 不把 payload 字符串还原为 UUID，断言使用 str() 比较。
        """
        event = _make_event()
        data = event.to_dict()
        restored = DomainEvent.from_dict(data)
        assert isinstance(restored, DebateCompleted)
        assert restored.event_type == "DebateCompleted"
        assert restored.aggregate_type == "DebateSession"
        assert restored.aggregate_id == event.debate_id  # 核心字段保持 UUID
        assert restored.debate_id == str(event.debate_id)  # payload 字段保持字符串
        assert restored.consensus_count == event.consensus_count
        assert restored.disagreement_count == event.disagreement_count
        assert restored.overlap_rate == event.overlap_rate
        assert restored.overall_risk_level == event.overall_risk_level
        assert restored.duration_ms == event.duration_ms
        assert restored.temperature_profile == event.temperature_profile
        # from_dict 后 metadata 保持 tenant_id 透传
        assert restored.metadata.get("tenant_id") == event.tenant_id

    def test_from_dict_roundtrip_truncated_title(self) -> None:
        """超长 title 的 roundtrip 截断值保持一致"""
        long_title = "超长议题标题" * 30
        event = _make_event(topic_title=long_title)
        restored = DomainEvent.from_dict(event.to_dict())
        assert isinstance(restored, DebateCompleted)
        assert restored.topic_title == long_title[:100]


class TestDebateCompletedInvariants:
    def test_event_is_frozen(self) -> None:
        """frozen dataclass 不可变"""
        event = _make_event()
        assert dataclasses.is_dataclass(event)
        with pytest.raises(AttributeError):
            setattr(event, "consensus_count", 99)

    def test_registry_auto_registration(self) -> None:
        """event_type init=False 自动注册进 _registry（多态反序列化前提）"""
        from src.domain.events.base import DomainEvent as Base

        assert Base._registry.get("DebateCompleted") is DebateCompleted
