"""Tests for EventStore and InMemoryEventStore (Story 1.2)."""

import uuid

import pytest

from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent
from src.domain.events.store import EventStore
from src.infrastructure.messaging.message_serializer import InMemoryEventStore


class TestEventStoreInterface:
    """Test EventStore abstract interface."""

    def test_cannot_instantiate_abstract_store(self):
        """Cannot instantiate EventStore directly (ABC)."""
        with pytest.raises(TypeError):
            EventStore()  # type: ignore


class TestInMemoryEventStoreSave:
    """Test InMemoryEventStore save functionality."""

    def test_save_single_event(self):
        """Can save a single event."""
        store = InMemoryEventStore()
        event = DocumentProcessed(document_id=uuid.uuid4())
        store.save_events([event])
        retrieved = store.get_events(event.aggregate_id)  # type: ignore
        assert len(retrieved) == 1
        assert retrieved[0].event_id == event.event_id

    def test_save_multiple_events(self):
        """Can save multiple events for same aggregate."""
        store = InMemoryEventStore()
        agg_id = uuid.uuid4()
        events = [
            DocumentProcessed(document_id=agg_id),
            DocumentProcessed(document_id=agg_id),
            DocumentProcessed(document_id=agg_id),
        ]
        store.save_events(events)
        retrieved = store.get_events(agg_id)
        assert len(retrieved) == 3

    def test_save_events_for_different_aggregates(self):
        """Events for different aggregates are stored separately."""
        store = InMemoryEventStore()
        agg1 = uuid.uuid4()
        agg2 = uuid.uuid4()
        events1 = [DocumentProcessed(document_id=agg1)]
        events2 = [DocumentProcessed(document_id=agg2)]
        store.save_events(events1)
        store.save_events(events2)
        assert len(store.get_events(agg1)) == 1
        assert len(store.get_events(agg2)) == 1

    def test_save_events_with_none_aggregate_id(self):
        """Events with None aggregate_id are not stored."""
        store = InMemoryEventStore()
        event = DomainEvent(aggregate_id=None, event_type="TestEvent")
        store.save_events([event])
        # No aggregate_id means no retrieval possible
        assert len(store._events_by_aggregate) == 0


class TestInMemoryEventStoreQuery:
    """Test InMemoryEventStore query functionality."""

    def test_get_events_for_unknown_aggregate(self):
        """Returns empty list for unknown aggregate."""
        store = InMemoryEventStore()
        result = store.get_events(uuid.uuid4())
        assert result == []

    def test_get_events_returns_in_order(self):
        """Events are returned in the order they were saved."""
        store = InMemoryEventStore()
        agg_id = uuid.uuid4()
        events = [DocumentProcessed(document_id=agg_id) for _ in range(5)]
        store.save_events(events)
        retrieved = store.get_events(agg_id)
        assert len(retrieved) == 5
        for i, event in enumerate(retrieved):
            assert event.event_id == events[i].event_id


class TestInMemoryEventStoreVersionQuery:
    """Test InMemoryEventStore version range queries."""

    def test_get_events_by_version_full_range(self):
        """Can retrieve all events by version range."""
        store = InMemoryEventStore()
        agg_id = uuid.uuid4()
        events = [DocumentProcessed(document_id=agg_id) for _ in range(5)]
        store.save_events(events)
        result = store.get_events_by_version(agg_id, 1, 5)
        assert len(result) == 5

    def test_get_events_by_version_partial_range(self):
        """Can retrieve subset of events by version range."""
        store = InMemoryEventStore()
        agg_id = uuid.uuid4()
        events = [DocumentProcessed(document_id=agg_id) for _ in range(5)]
        store.save_events(events)
        result = store.get_events_by_version(agg_id, 2, 4)
        assert len(result) == 3
        # Versions 2, 3, 4 (0-based: 1, 2, 3)
        assert result[0].event_id == events[1].event_id

    def test_get_events_by_version_single_event(self):
        """Can retrieve single event by version."""
        store = InMemoryEventStore()
        agg_id = uuid.uuid4()
        events = [DocumentProcessed(document_id=agg_id) for _ in range(3)]
        store.save_events(events)
        result = store.get_events_by_version(agg_id, 2, 2)
        assert len(result) == 1
        assert result[0].event_id == events[1].event_id

    def test_get_events_by_version_out_of_range(self):
        """Returns empty list for out-of-range versions."""
        store = InMemoryEventStore()
        agg_id = uuid.uuid4()
        events = [DocumentProcessed(document_id=agg_id) for _ in range(3)]
        store.save_events(events)
        result = store.get_events_by_version(agg_id, 10, 20)
        assert result == []

    def test_get_events_by_version_unknown_aggregate(self):
        """Returns empty list for unknown aggregate."""
        store = InMemoryEventStore()
        result = store.get_events_by_version(uuid.uuid4(), 1, 10)
        assert result == []


class TestInMemoryEventStoreClear:
    """Test InMemoryEventStore clear functionality."""

    def test_clear_removes_all_events(self):
        """Clear removes all stored events."""
        store = InMemoryEventStore()
        agg_id = uuid.uuid4()
        store.save_events([DocumentProcessed(document_id=agg_id)])
        assert len(store.get_events(agg_id)) == 1
        store.clear()
        assert len(store.get_events(agg_id)) == 0
