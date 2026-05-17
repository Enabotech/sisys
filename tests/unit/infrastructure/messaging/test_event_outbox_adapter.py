"""Task 3 TDD Tests — EventOutboxAdapter conversion tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.events import (
    AgentDecided,
    DocumentProcessed,
    ToolExecuted,
)
from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.adapters.event_outbox_adapter import EventOutboxAdapter, EventRegistry
from src.infrastructure.messaging.outbox.outbox import OutboxEntity


class TestEventOutboxAdapterConversion:
    """EventOutboxAdapter roundtrip conversion tests."""

    def test_document_processed_roundtrip(self):
        """DocumentProcessed → OutboxEntity → DomainEvent (fields preserved in payload)."""
        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 10, "tables": 2},
            embedding=[0.1] * 1024,
        )
        entity = EventOutboxAdapter.from_domain_event(event)
        restored = EventOutboxAdapter.to_domain_event(entity)

        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        # Fields preserved in payload (UUIDs are serialized as strings)
        assert str(restored.payload.get("document_id")) == str(event.document_id)
        assert restored.payload.get("parse_result") == event.parse_result

    def test_tool_executed_roundtrip(self):
        """ToolExecuted → OutboxEntity → DomainEvent."""
        from uuid import uuid4

        tool_id = uuid4()
        event = ToolExecuted(
            tool_id=tool_id,
            execution_result={"status": "success"},
            cost_audit={"tokens": 1000, "cost": 0.01},
        )
        entity = EventOutboxAdapter.from_domain_event(event)
        restored = EventOutboxAdapter.to_domain_event(entity)

        assert restored.event_type == event.event_type
        assert str(restored.payload.get("tool_id")) == str(event.tool_id)

    def test_agent_decided_roundtrip(self):
        """AgentDecided → OutboxEntity → DomainEvent."""
        from uuid import uuid4

        agent_id = uuid4()
        event = AgentDecided(
            agent_id=agent_id,
            decision_result={"strategy": "growth"},
            confidence=0.85,
        )
        entity = EventOutboxAdapter.from_domain_event(event)
        restored = EventOutboxAdapter.to_domain_event(entity)

        assert restored.event_type == event.event_type
        assert str(restored.payload.get("agent_id")) == str(event.agent_id)
        assert restored.payload.get("confidence") == event.confidence

    def test_all_event_types_registered(self):
        """All 10 event types should be registered in EventRegistry."""
        expected_types = [
            "DocumentProcessed",
            "ToolExecuted",
            "AgentDecided",
            "CheckpointReached",
            "CorrectionApproved",
            "StrategicDeviationWarning",
            "HeartbeatTriggered",
            "IsolationLevelSwitched",
            "CheckpointRecovered",
            "RoutingDecided",
        ]
        for event_type in expected_types:
            event_class = EventRegistry.get(event_type)
            assert event_class is not None, f"{event_type} not registered"

    def test_unknown_event_type_raises_error(self):
        """Should raise ValueError for unknown event type."""
        entity = OutboxEntity()
        entity.event_type = "NonExistentEvent"
        entity.payload = {}

        with pytest.raises(ValueError, match="Unknown event_type"):
            EventOutboxAdapter.to_domain_event(entity)


class TestEventRegistry:
    """EventRegistry 注册表行为测试。"""

    def test_reset_clears_registry(self) -> None:
        """reset 应清空注册表。"""
        # 先构建
        EventRegistry.get("DocumentProcessed")
        assert EventRegistry._built is True
        assert len(EventRegistry._registry) > 0

        EventRegistry.reset()
        assert EventRegistry._built is False
        assert len(EventRegistry._registry) == 0

    def test_rebuild_after_reset(self) -> None:
        """reset 后首次 get 应重新构建。"""
        EventRegistry.reset()
        event_class = EventRegistry.get("DocumentProcessed")
        assert event_class is not None
        assert EventRegistry._built is True

    def test_register_manual_event_type(self) -> None:
        """应支持手动注册自定义事件类型。"""
        EventRegistry.reset()

        # 注册已有事件类型（安全的手动注册测试）
        EventRegistry.register("DocumentProcessed", DocumentProcessed)
        result = EventRegistry.get("DocumentProcessed")
        assert result is DocumentProcessed

    def test_register_triggers_build_if_not_built(self) -> None:
        """在未构建状态下 register 应先构建。"""
        EventRegistry.reset()
        assert EventRegistry._built is False

        EventRegistry.register("DocumentProcessed", DocumentProcessed)
        assert EventRegistry._built is True

    def test_get_returns_correct_subclass(self) -> None:
        """get 应返回正确的事件子类。"""
        cls = EventRegistry.get("ToolExecuted")
        assert cls is ToolExecuted

        cls = EventRegistry.get("AgentDecided")
        assert cls is AgentDecided

    def test_subclasses_are_recursively_collected(self) -> None:
        """注册表应递归收集所有子类。"""
        EventRegistry.reset()
        # 触发构建
        EventRegistry.get("DocumentProcessed")
        # 所有直接子类应被收集
        for subclass in DomainEvent.__subclasses__():
            assert subclass.__name__ in EventRegistry._registry


class TestEventOutboxAdapterFromDomainEvent:
    """from_domain_event 转换细节测试。"""

    def test_entity_fields_populated(self) -> None:
        """OutboxEntity 应正确填充所有字段。"""
        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 5},
            embedding=[0.1] * 1024,
        )
        entity = EventOutboxAdapter.from_domain_event(event)

        assert entity.event_id == event.event_id
        assert entity.event_type == event.event_type
        assert entity.status == "pending"
        assert entity.created_at == event.timestamp
        assert isinstance(entity.payload, dict)

    def test_entity_payload_contains_event_data(self) -> None:
        """payload 应包含事件的序列化数据。"""
        doc_id = uuid4()
        event = DocumentProcessed(
            document_id=doc_id,
            parse_result={"pages": 3},
            embedding=[0.1] * 1024,
        )
        entity = EventOutboxAdapter.from_domain_event(event)
        payload = entity.payload

        assert "event_id" in payload
        assert "event_type" in payload
        assert payload["event_type"] == "DocumentProcessed"
