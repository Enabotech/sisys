"""Story 4.5: DebateCompleted 事件契约测试

验证 DebateCompleted 事件的字段完整性、序列化 roundtrip、聚合根归属。

遵循项目标准事件契约测试模式（test_event_contract_tool_executed.py 同构）。
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.events.debate_events import DebateCompleted


def _make_event() -> DebateCompleted:
    """创建标准 DebateCompleted 事件实例。"""
    return DebateCompleted(
        debate_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        topic_title="公司是否应在下一财年进入东南亚市场",
        red_stance="应当立即进入抢占先机",
        blue_stance="应当延后观察规避风险",
        consensus_count=2,
        disagreement_count=1,
        overlap_rate=0.35,
        overall_risk_level="MEDIUM",
        duration_ms=8500,
        temperature_profile={"red": 0.8, "blue": 0.5, "synthesis": 0.2},
    )


class TestDebateCompletedEventSchema:
    """DebateCompleted 事件 Schema 完整性测试。"""

    def test_event_type_is_debate_completed(self) -> None:
        """事件类型固定为 DebateCompleted。"""
        event = _make_event()
        assert event.event_type == "DebateCompleted"

    def test_aggregate_id_set_to_debate_id(self) -> None:
        """aggregate_id 应为 debate_id。"""
        event = _make_event()
        assert event.aggregate_id == event.debate_id

    def test_aggregate_type_set_to_debate_session(self) -> None:
        """aggregate_type 应为 DebateSession。"""
        event = _make_event()
        assert event.aggregate_type == "DebateSession"

    def test_event_inherits_domain_event_fields(self) -> None:
        """事件应继承 DomainEvent 所有核心字段。"""
        from src.domain.events.base import DomainEvent

        event = _make_event()
        assert isinstance(event, DomainEvent)
        assert hasattr(event, "event_id")
        assert hasattr(event, "timestamp")
        assert hasattr(event, "source")
        assert hasattr(event, "schema_version")

    def test_event_has_all_subclass_fields(self) -> None:
        """事件应包含所有子类特有字段（11 个业务字段）。"""
        event = _make_event()
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
            assert hasattr(event, field_name)


class TestDebateCompletedEventSerialization:
    """DebateCompleted 事件序列化 roundtrip 测试。"""

    def test_to_dict_includes_business_fields(self) -> None:
        """to_dict 的 payload 应包含核心业务字段。"""
        event = _make_event()
        data = event.to_dict()
        assert data["event_type"] == "DebateCompleted"
        assert data["aggregate_type"] == "DebateSession"
        for field_name in (
            "debate_id",
            "red_stance",
            "blue_stance",
            "consensus_count",
            "disagreement_count",
            "overlap_rate",
            "temperature_profile",
        ):
            assert field_name in data["payload"]

    def test_from_dict_roundtrip(self) -> None:
        """to_dict → from_dict roundtrip 应等值（_registry 多态注册生效）。

        注：与项目历史行为对齐（tests/unit/domain/events/test_archive_events.py），
        from_dict 不会把字符串 payload 字段反序列化为 UUID，
        保持字符串原样，断言使用 str() 比较。
        """
        event = _make_event()
        data = event.to_dict()
        restored = DebateCompleted.from_dict(data)
        assert isinstance(restored, DebateCompleted), f"from_dict 应返回 DebateCompleted 实例，实际: {type(restored).__name__}"
        assert restored.aggregate_id == event.debate_id
        assert restored.debate_id == str(event.debate_id)
        assert restored.consensus_count == event.consensus_count
        assert restored.disagreement_count == event.disagreement_count
        assert restored.overlap_rate == event.overlap_rate
        assert restored.overall_risk_level == event.overall_risk_level
        assert restored.temperature_profile == event.temperature_profile


class TestDebateCompletedEventInvariants:
    """DebateCompleted 事件不变量测试。"""

    def test_event_is_frozen(self) -> None:
        """frozen dataclass 应不可变。"""
        event = _make_event()
        with pytest.raises(AttributeError):
            setattr(event, "consensus_count", 99)

    def test_event_is_domain_event_subclass(self) -> None:
        """事件应为 DomainEvent 子类。"""
        from src.domain.events.base import DomainEvent

        event = _make_event()
        assert isinstance(event, DomainEvent)

    def test_temperature_profile_matches_fr_sp10(self) -> None:
        """温度阶梯载荷与 FR-SP-10 V1 三阶段一致（绊线断言）。"""
        event = _make_event()
        assert event.temperature_profile == {"red": 0.8, "blue": 0.5, "synthesis": 0.2}
