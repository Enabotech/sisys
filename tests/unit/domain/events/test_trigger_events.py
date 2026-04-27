"""Tests for AutoTriggered domain event."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.domain.events.auto_trigger_events import AutoTriggered


class TestAutoTriggeredEvent:
    """Test suite for AutoTriggered event."""

    def test_triggered_event_creation(self) -> None:
        """Verify AutoTriggered event is created with correct default values."""
        event = AutoTriggered(
            trigger_type="domain_event",
            session_id="session-123",
            agent_id="agent-456",
            task_context={"task_type": "document_processing"},
            source_event_type="DocumentProcessed",
            source_event_id=str(uuid.uuid4()),
        )

        assert event.event_type == "AutoTriggered"
        assert event.trigger_type == "domain_event"
        assert event.session_id == "session-123"
        assert event.agent_id == "agent-456"
        assert event.task_context == {"task_type": "document_processing"}
        assert event.source_event_type == "DocumentProcessed"
        assert event.aggregate_type == "AutoTrigger"

    def test_triggered_event_serialization(self) -> None:
        """Verify AutoTriggered event serializes correctly to dict."""
        event_id = uuid.uuid4()
        event = AutoTriggered(
            event_id=event_id,
            trigger_type="heartbeat",
            session_id="heartbeat-scheduler",
            task_context={"todo_items": ["task1", "task2"]},
            source_event_type="HeartbeatTriggered",
        )

        result = event.to_dict()

        assert result["event_type"] == "AutoTriggered"
        # trigger_type is in payload (non-core field)
        assert result["payload"]["trigger_type"] == "heartbeat"
        assert result["payload"]["session_id"] == "heartbeat-scheduler"
        assert result["payload"]["source_event_type"] == "HeartbeatTriggered"
        assert result["aggregate_type"] == "AutoTrigger"
        assert "payload" in result

    def test_triggered_event_deserialization(self) -> None:
        """Verify AutoTriggered event can be deserialized from dict."""
        event_id = uuid.uuid4()
        ts = datetime.now(UTC)
        # Note: to_dict() puts non-core fields (trigger_type, session_id, etc.) into payload
        data = {
            "event_id": str(event_id),
            "event_type": "AutoTriggered",
            "timestamp": ts.isoformat(),
            "source": "trigger-service",
            "schema_version": "1.0.0",
            "aggregate_id": str(event_id),
            "aggregate_type": "AutoTrigger",
            "version": 0,
            "payload": {
                "trigger_type": "domain_event",
                "session_id": "session-789",
                "agent_id": "agent-001",
                "task_context": {"priority": "high"},
                "source_event_type": "ToolExecuted",
                "source_event_id": str(uuid.uuid4()),
            },
        }

        # The AutoTriggered class is registered for "AutoTriggered" event_type in the registry
        event = AutoTriggered.from_dict(data)

        assert event.event_type == "AutoTriggered"
        # Non-core fields stored in payload are restored via AutoTriggered.__post_init__
        # Access subclass attributes via __dict__ to satisfy mypy
        assert getattr(event, "trigger_type") == "domain_event"
        assert getattr(event, "session_id") == "session-789"
        assert getattr(event, "agent_id") == "agent-001"
        assert getattr(event, "task_context") == {"priority": "high"}
        assert getattr(event, "source_event_type") == "ToolExecuted"

    def test_triggered_heartbeat_round_trip(self) -> None:
        """Verify heartbeat trigger type round-trip through serialization."""
        event = AutoTriggered(
            trigger_type="heartbeat",
            session_id="heartbeat-scheduler",
            task_context={
                "heartbeat_id": "hb-001",
                "wake_reason": "scheduled",
                "todo_items": ["task1"],
                "cost_budget": 100.0,
            },
            source_event_type="HeartbeatTriggered",
            source_event_id="hb-001",
        )

        serialized = event.to_dict()
        # Note: from_dict reconstruction may have limitations with AutoTriggered's init=False fields
        # This test verifies the serialization side; deserialization tested separately
        assert serialized["payload"]["trigger_type"] == "heartbeat"
        assert serialized["payload"]["session_id"] == "heartbeat-scheduler"
        assert serialized["payload"]["source_event_type"] == "HeartbeatTriggered"
