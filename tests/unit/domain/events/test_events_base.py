"""Tests for DomainEvent base class."""

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
