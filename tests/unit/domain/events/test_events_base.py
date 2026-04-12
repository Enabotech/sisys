"""Tests for DomainEvent base class."""

import uuid
from datetime import datetime

import pytest

from src.domain.events.base import DomainEvent


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
        assert isinstance(event.occurred_on, datetime)

    def test_event_has_auto_generated_id(self):
        """Event ID is auto-generated UUID."""
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="TestEvent",
        )
        assert isinstance(event.event_id, uuid.UUID)

    def test_event_has_auto_timestamp(self):
        """Event has auto-generated occurred_on timestamp."""
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="TestEvent",
        )
        assert isinstance(event.occurred_on, datetime)
        assert event.occurred_on.tzinfo is not None

    def test_frozen_event_is_immutable(self):
        """DomainEvent is frozen (immutable)."""
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="TestEvent",
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            event.event_type = "Changed"  # type: ignore


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
        assert "occurred_on" in d

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
