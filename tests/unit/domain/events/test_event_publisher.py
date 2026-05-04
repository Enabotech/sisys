"""Tests for event publisher and InMemoryEventBus (Story 1.2)."""

import uuid
from typing import cast

import pytest

from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent
from src.domain.events.listener import InMemoryEventListener
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus


class TestEventPublisherInterface:
    """Test EventPublisher abstract interface."""

    def test_cannot_instantiate_abstract_publisher(self):
        """Cannot instantiate EventPublisher directly (ABC)."""
        from src.domain.ports.event_publisher import InMemoryEventPublisher

        with pytest.raises(TypeError):
            InMemoryEventPublisher()


class TestInMemoryEventBusPublish:
    """Test InMemoryEventBus publish functionality."""

    def test_publish_single_event(self):
        """Can publish a single event."""
        bus = InMemoryEventBus()
        event = DocumentProcessed(document_id=uuid.uuid4())
        bus.publish(event)
        assert len(bus.published_events) == 1
        assert bus.published_events[0].event_id == event.event_id

    def test_publish_multiple_events(self):
        """Can publish multiple events in order."""
        bus = InMemoryEventBus()
        events = [
            DocumentProcessed(document_id=uuid.uuid4()),
            DocumentProcessed(document_id=uuid.uuid4()),
            DocumentProcessed(document_id=uuid.uuid4()),
        ]
        for event in events:
            bus.publish(event)
        assert len(bus.published_events) == 3
        assert [e.event_id for e in bus.published_events] == [e.event_id for e in events]

    def test_publish_records_event_id(self):
        """Published event's ID is recorded in processed set."""
        bus = InMemoryEventBus()
        event = DocumentProcessed(document_id=uuid.uuid4())
        bus.publish(event)
        assert event.event_id in bus.processed_event_ids

    def test_publish_none_raises(self):
        """Publishing None raises ValueError."""
        bus = InMemoryEventBus()
        with pytest.raises(ValueError, match="event must not be None"):
            bus.publish(cast(DomainEvent, None))


class TestInMemoryEventBusIdempotency:
    """Test InMemoryEventBus idempotency (deduplication)."""

    def test_duplicate_event_not_published(self):
        """Publishing same event twice only records it once."""
        bus = InMemoryEventBus()
        event = DocumentProcessed(document_id=uuid.uuid4())
        bus.publish(event)
        bus.publish(event)  # Duplicate
        assert len(bus.published_events) == 1

    def test_duplicate_event_idempotency_check(self):
        """Idempotency check prevents re-processing."""
        bus = InMemoryEventBus()
        event = DocumentProcessed(document_id=uuid.uuid4())
        bus.publish(event)
        initial_count = len(bus.processed_event_ids)
        bus.publish(event)
        assert len(bus.processed_event_ids) == initial_count  # No new entries

    def test_different_events_both_published(self):
        """Two different events are both published."""
        bus = InMemoryEventBus()
        event1 = DocumentProcessed(document_id=uuid.uuid4())
        event2 = DocumentProcessed(document_id=uuid.uuid4())
        bus.publish(event1)
        bus.publish(event2)
        assert len(bus.published_events) == 2


class TestInMemoryEventBusDispatch:
    """Test InMemoryEventBus event dispatch to listener."""

    def test_dispatch_to_listener(self) -> None:
        """Events are dispatched to registered listener."""
        listener = InMemoryEventListener()
        bus = InMemoryEventBus(listener=listener)

        received_events: list[DomainEvent] = []

        def handler(event: DomainEvent) -> None:
            received_events.append(event)

        listener.on_event("DocumentProcessed", handler)

        event = DocumentProcessed(document_id=uuid.uuid4())
        bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0].event_id == event.event_id

    def test_dispatch_filters_by_event_type(self) -> None:
        """Only handlers for the matching event type are called."""
        listener = InMemoryEventListener()
        bus = InMemoryEventBus(listener=listener)

        received: list[str] = []

        def handler_doc(event: DomainEvent) -> None:
            received.append("doc")

        def handler_tool(event: DomainEvent) -> None:
            received.append("tool")

        listener.on_event("DocumentProcessed", handler_doc)
        listener.on_event("ToolExecuted", handler_tool)

        event = DocumentProcessed(document_id=uuid.uuid4())
        bus.publish(event)

        assert received == ["doc"]
        assert "tool" not in received

    def test_no_listener_no_error(self):
        """Publishing without listeners works fine."""
        bus = InMemoryEventBus()
        event = DocumentProcessed(document_id=uuid.uuid4())
        bus.publish(event)  # Should not raise
        assert len(bus.published_events) == 1

    def test_multiple_handlers_same_event_type(self) -> None:
        """Multiple handlers for same event type all receive event."""
        listener = InMemoryEventListener()
        bus = InMemoryEventBus(listener=listener)

        results: list[int] = []

        def handler1(event: DomainEvent) -> None:
            results.append(1)

        def handler2(event: DomainEvent) -> None:
            results.append(2)

        def handler3(event: DomainEvent) -> None:
            results.append(3)

        listener.on_event("DocumentProcessed", handler1)
        listener.on_event("DocumentProcessed", handler2)
        listener.on_event("DocumentProcessed", handler3)

        event = DocumentProcessed(document_id=uuid.uuid4())
        bus.publish(event)

        assert results == [1, 2, 3]


class TestInMemoryEventBusReset:
    """Test InMemoryEventBus reset functionality."""

    def test_reset_clears_processed_ids(self):
        """Reset clears processed event IDs."""
        bus = InMemoryEventBus()
        bus.publish(DocumentProcessed(document_id=uuid.uuid4()))
        assert len(bus.processed_event_ids) == 1
        bus.reset()
        assert len(bus.processed_event_ids) == 0

    def test_reset_clears_published_events(self):
        """Reset clears published events list."""
        bus = InMemoryEventBus()
        bus.publish(DocumentProcessed(document_id=uuid.uuid4()))
        assert len(bus.published_events) == 1
        bus.reset()
        assert len(bus.published_events) == 0


class TestInMemoryEventBusDispatchOrder:
    """Test dispatch-before-record ordering (P0-5)."""

    def test_dispatch_before_record(self) -> None:
        """Event is dispatched before being marked as processed."""
        listener = InMemoryEventListener()
        bus = InMemoryEventBus(listener=listener)
        captured_during_dispatch: bool | None = None

        def capture_handler(event: DomainEvent) -> None:
            nonlocal captured_during_dispatch
            captured_during_dispatch = event.event_id in bus.processed_event_ids

        listener.on_event("DocumentProcessed", capture_handler)
        event = DocumentProcessed(document_id=uuid.uuid4())
        bus.publish(event)

        # During dispatch, event was NOT yet marked as processed
        assert captured_during_dispatch is False
        # After publish completes, it IS marked as processed
        assert event.event_id in bus.processed_event_ids
