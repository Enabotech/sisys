"""Task 3 TDD Tests — EventOutboxAdapter conversion tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.events import (
    AgentDecided,
    DocumentProcessed,
    ToolExecuted,
)
from src.infrastructure.adapters.event_outbox_adapter import EventOutboxAdapter, EventRegistry
from src.infrastructure.entities.outbox import OutboxEntity


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
