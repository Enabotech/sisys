"""Tests for DomainEvent base class."""

import dataclasses
import uuid
from datetime import datetime

import pytest

from src.domain.events.base import DomainEvent
from src.domain.exceptions import EntityValidationError


class TestDomainEventCreation:
    """Test DomainEvent creation."""

    def test_create_domain_event(self):
        """Can create a domain event with required fields."""
        agg_id = uuid.uuid4()
        event = DomainEvent(
            aggregate_id=agg_id,
            event_type="TestEvent",
            payload={"key": "value"},
        )
        assert event.event_id is not None
        assert event.aggregate_id == agg_id
        assert event.event_type == "TestEvent"
        assert event.payload == {"key": "value"}
        assert isinstance(event.timestamp, datetime)

    def test_event_has_auto_generated_id(self):
        """Event ID is auto-generated UUID."""
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="TestEvent",
        )
        assert isinstance(event.event_id, uuid.UUID)

    def test_event_has_auto_timestamp(self):
        """Event has auto-generated timestamp."""
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="TestEvent",
        )
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_frozen_event_is_immutable(self):
        """DomainEvent is frozen (immutable)."""
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="TestEvent",
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            event.event_type = "Changed"


class TestDomainEventSerialization:
    """Test DomainEvent serialization."""

    def test_to_dict(self):
        """Can serialize event to dict."""
        agg_id = uuid.uuid4()
        event = DomainEvent(
            aggregate_id=agg_id,
            event_type="TestEvent",
            payload={"data": 42},
        )
        d = event.to_dict()
        assert d["event_type"] == "TestEvent"
        assert d["aggregate_id"] == str(agg_id)
        assert d["payload"] == {"data": 42}
        assert "timestamp" in d

    def test_from_dict_roundtrip(self):
        """Can serialize and deserialize event."""
        agg_id = uuid.uuid4()
        event = DomainEvent(
            aggregate_id=agg_id,
            event_type="TestEvent",
            payload={"data": 42},
        )
        d = event.to_dict()
        restored = DomainEvent.from_dict(d)
        assert restored.event_id == event.event_id
        assert restored.aggregate_id == event.aggregate_id
        assert restored.event_type == event.event_type
        assert restored.payload == event.payload
        assert restored.timestamp == event.timestamp

    def test_to_dict_excludes_none_aggregate_id(self):
        """P0-01 Fix: aggregate_id=None is excluded from dict."""
        event = DomainEvent(
            aggregate_id=None,
            event_type="TestEvent",
        )
        d = event.to_dict()
        assert "aggregate_id" not in d

    def test_from_dict_with_none_aggregate_id(self):
        """P0-01 Fix: from_dict handles missing aggregate_id gracefully."""
        event = DomainEvent(
            aggregate_id=None,
            event_type="TestEvent",
        )
        d = event.to_dict()
        restored = DomainEvent.from_dict(d)
        assert restored.aggregate_id is None

    def test_payload_non_json_serializable_raises(self):
        """P1-04 Fix: Non-JSON-serializable payload raises ValueError."""
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="TestEvent",
            payload={"bad_key": set()},  # set is not JSON serializable
        )
        with pytest.raises(EntityValidationError, match="not JSON serializable"):
            event.to_dict()

    def test_payload_json_serializable_passes(self):
        """P1-04 Fix: JSON-serializable payload passes."""
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="TestEvent",
            payload={"key": "value", "number": 42},
        )
        d = event.to_dict()  # Should not raise
        assert d["payload"] == {"key": "value", "number": 42}

    def test_from_dict_missing_event_id_raises(self):
        """Missing event_id raises ValueError."""
        with pytest.raises(EntityValidationError, match="Missing required field: event_id"):
            DomainEvent.from_dict({"event_type": "Test", "timestamp": "2026-01-01T00:00:00+00:00"})

    def test_from_dict_missing_event_type_raises(self):
        """Missing event_type raises ValueError."""
        with pytest.raises(EntityValidationError, match="Missing required field: event_type"):
            DomainEvent.from_dict({"event_id": str(uuid.uuid4()), "timestamp": "2026-01-01T00:00:00+00:00"})

    def test_from_dict_missing_timestamp_raises(self):
        """Missing timestamp raises ValueError."""
        with pytest.raises(EntityValidationError, match="Missing required field: timestamp"):
            DomainEvent.from_dict({"event_id": str(uuid.uuid4()), "event_type": "Test"})

    def test_from_dict_invalid_uuid_raises(self):
        """Invalid UUID raises ValueError."""
        with pytest.raises(EntityValidationError, match="Invalid event_id"):
            DomainEvent.from_dict(
                {
                    "event_id": "not-a-uuid",
                    "event_type": "Test",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            )

    def test_from_dict_invalid_timestamp_raises(self):
        """Invalid timestamp raises ValueError."""
        with pytest.raises(EntityValidationError, match="Invalid timestamp"):
            DomainEvent.from_dict(
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "Test",
                    "timestamp": "not-a-datetime",
                }
            )

    def test_empty_event_type_raises(self):
        """P1-05 Fix: Empty event_type raises ValueError in to_dict()."""
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="",
        )
        with pytest.raises(EntityValidationError, match="event_type must not be empty"):
            event.to_dict()

    def test_from_dict_invalid_event_id_raises(self):
        """P0-01 Fix: Invalid event_id raises ValueError with context."""
        with pytest.raises(EntityValidationError, match="Invalid event_id"):
            DomainEvent.from_dict(
                {
                    "event_id": "not-a-uuid",
                    "event_type": "TestEvent",
                    "timestamp": "2024-01-01T00:00:00+00:00",
                    "payload": {},
                }
            )

    def test_from_dict_invalid_aggregate_id_raises(self):
        """P0-01 Fix: Invalid aggregate_id raises ValueError with context."""
        with pytest.raises(EntityValidationError, match="Invalid aggregate_id"):
            DomainEvent.from_dict(
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "TestEvent",
                    "timestamp": "2024-01-01T00:00:00+00:00",
                    "aggregate_id": "not-a-uuid",
                    "payload": {},
                }
            )

    def test_from_dict_invalid_correlation_id_raises(self):
        """追踪字段与核心字段同构：Invalid correlation_id 包装 242（禁裸 ValueError 逃逸）。"""
        with pytest.raises(EntityValidationError, match="Invalid correlation_id"):
            DomainEvent.from_dict(
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "TestEvent",
                    "timestamp": "2024-01-01T00:00:00+00:00",
                    "correlation_id": "not-a-uuid",
                    "payload": {},
                }
            )

    def test_from_dict_invalid_causation_id_raises(self):
        """追踪字段与核心字段同构：Invalid causation_id 包装 242（禁裸 ValueError 逃逸）。"""
        with pytest.raises(EntityValidationError, match="Invalid causation_id"):
            DomainEvent.from_dict(
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "TestEvent",
                    "timestamp": "2024-01-01T00:00:00+00:00",
                    "causation_id": "not-a-uuid",
                    "payload": {},
                }
            )

    def test_from_dict_empty_correlation_id_treated_as_absent(self):
        """空串追踪字段等价「未提供」→ None（恢复 R2 前互操作宽容语义——外部生产方写 ""
        拒收会在消费侧被静默丢弃，比容忍更糟；fail-loud 收缩至非空畸形）。"""
        event = DomainEvent.from_dict(
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "Test",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "correlation_id": "",
                "payload": {},
            }
        )
        assert event.correlation_id is None

    def test_from_dict_bare_special_form_annotation_raises(self):
        """字符串注解求值为非类型（如元组）→ TypeError 包装 242
        （redis_subscriber 只捕 ValueError/DomainError，裸 TypeError 击穿逐消息隔离；
        同族形态：求值为裸特殊形式如 Optional 漏 [None]）。"""
        bare_special_cls = dataclasses.dataclass(frozen=True)(
            type(
                "_BareSpecialEventR3",
                (DomainEvent,),
                {"__annotations__": {"bad_field": "('int', 'str')"}, "bad_field": None},
            )
        )
        DomainEvent.register("BareSpecialEventR3", bare_special_cls)
        try:
            with pytest.raises(EntityValidationError, match="Unresolvable type annotations"):
                DomainEvent.from_dict(
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_type": "BareSpecialEventR3",
                        "timestamp": "2024-01-01T00:00:00+00:00",
                        "payload": {"bad_field": "x"},
                    }
                )
        finally:
            DomainEvent._registry.pop("BareSpecialEventR3", None)

    def test_from_dict_malformed_annotation_raises(self):
        """畸形表达式字符串注解（如 list[int[）→ SyntaxError 包装 242（禁裸逃逸）。"""
        malformed_cls = dataclasses.dataclass(frozen=True)(
            type(
                "_MalformedEventR3",
                (DomainEvent,),
                {"__annotations__": {"bad_field": "list[int["}, "bad_field": None},
            )
        )
        DomainEvent.register("MalformedEventR3", malformed_cls)
        try:
            with pytest.raises(EntityValidationError, match="Unresolvable type annotations"):
                DomainEvent.from_dict(
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_type": "MalformedEventR3",
                        "timestamp": "2024-01-01T00:00:00+00:00",
                        "payload": {"bad_field": "x"},
                    }
                )
        finally:
            DomainEvent._registry.pop("MalformedEventR3", None)

    def test_from_dict_unresolvable_annotation_raises(self):
        """不可解析类型注解（模块命名空间外的名字）包装 242（禁裸 NameError 逃逸）。"""
        # 经 type() 动态建类 + __annotations__ 字典注入字符串注解：本文件未启用
        # from __future__ import annotations，注解字面量语法会在类定义期求值为
        # 类型对象（永不触发 get_type_hints 解析失败）；dict 注入形态使字符串
        # 注解原样进入 dataclass 字段，get_type_hints 解析时抛 NameError（测试意图）
        unresolvable_cls = dataclasses.dataclass(frozen=True)(
            type(
                "_UnresolvableEventR2",
                (DomainEvent,),
                {"__annotations__": {"bad_field": "NameAbsentFromModuleNamespace"}, "bad_field": ""},
            )
        )
        DomainEvent.register("UnresolvableEventR2", unresolvable_cls)
        try:
            with pytest.raises(EntityValidationError, match="Unresolvable type annotations"):
                DomainEvent.from_dict(
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_type": "UnresolvableEventR2",
                        "timestamp": "2024-01-01T00:00:00+00:00",
                        "payload": {"bad_field": "x"},
                    }
                )
        finally:
            DomainEvent._registry.pop("UnresolvableEventR2", None)
