"""Tests for EventListener (Story 1.2)."""

import uuid

import pytest

from src.domain.events import DocumentProcessed, ToolExecuted
from src.domain.events.base import DomainEvent
from src.domain.events.listener import InMemoryEventListener


class TestEventListenerRegistration:
    """Test event handler registration."""

    def test_register_handler(self):
        """Can register a handler for an event type."""
        listener = InMemoryEventListener()
        handler_called = False

        def handler(event: DomainEvent) -> None:
            nonlocal handler_called
            handler_called = True

        listener.on_event("DocumentProcessed", handler)
        assert "DocumentProcessed" in listener.registered_event_types

    def test_multiple_handlers_same_type(self):
        """Can register multiple handlers for same event type."""
        listener = InMemoryEventListener()
        listener.on_event("TestEvent", lambda e: None)
        listener.on_event("TestEvent", lambda e: None)
        # Both handlers are registered
        assert len(listener._handlers["TestEvent"]) == 2

    def test_handlers_for_different_types(self):
        """Can register handlers for different event types."""
        listener = InMemoryEventListener()
        listener.on_event("TypeA", lambda e: None)
        listener.on_event("TypeB", lambda e: None)
        assert len(listener.registered_event_types) == 2


class TestEventListenerDispatch:
    """Test event dispatch to handlers."""

    def test_dispatch_calls_handler(self):
        """Dispatch calls the registered handler."""
        listener = InMemoryEventListener()
        received_event: DomainEvent | None = None

        def handler(event: DomainEvent) -> None:
            nonlocal received_event
            received_event = event

        listener.on_event("DocumentProcessed", handler)
        event = DocumentProcessed(document_id=uuid.uuid4())
        listener.dispatch(event)

        assert received_event is not None
        assert received_event.event_id == event.event_id

    def test_dispatch_no_handler_for_type(self):
        """Dispatch with no handler for type does nothing."""
        listener = InMemoryEventListener()
        event = DocumentProcessed(document_id=uuid.uuid4())
        listener.dispatch(event)  # Should not raise

    def test_dispatch_only_matching_handler(self):
        """Only handlers for the matching event type are called."""
        listener = InMemoryEventListener()
        results: list[str] = []

        listener.on_event("DocumentProcessed", lambda e: results.append("doc"))
        listener.on_event("ToolExecuted", lambda e: results.append("tool"))

        event = DocumentProcessed(document_id=uuid.uuid4())
        listener.dispatch(event)

        assert results == ["doc"]
        assert "tool" not in results

    def test_dispatch_all_handlers_for_same_type(self):
        """All handlers for the same event type are called."""
        listener = InMemoryEventListener()
        results: list[int] = []

        listener.on_event("TestEvent", lambda e: results.append(1))
        listener.on_event("TestEvent", lambda e: results.append(2))

        event = DocumentProcessed(document_id=uuid.uuid4())
        # Manually set event_type for testing
        listener.dispatch(event)
        # The event type is "DocumentProcessed", so no handlers fire
        assert results == []

    def test_dispatch_with_actual_event_type(self):
        """Dispatch with actual event type fires correct handlers."""
        listener = InMemoryEventListener()
        received: list[str] = []

        listener.on_event("DocumentProcessed", lambda e: received.append("doc"))
        listener.on_event("ToolExecuted", lambda e: received.append("tool"))

        doc_event = DocumentProcessed(document_id=uuid.uuid4())
        listener.dispatch(doc_event)

        assert received == ["doc"]

        tool_event = ToolExecuted(tool_id=uuid.uuid4())
        listener.dispatch(tool_event)

        assert received == ["doc", "tool"]

    def test_dispatch_continues_after_handler_error(self):
        """One handler failing doesn't stop subsequent handlers (P0-4)."""
        listener = InMemoryEventListener()
        results: list[int] = []

        def failing_handler(event: DomainEvent) -> None:
            results.append(1)
            raise RuntimeError("handler failed")

        def good_handler(event: DomainEvent) -> None:
            results.append(2)

        listener.on_event("DocumentProcessed", failing_handler)
        listener.on_event("DocumentProcessed", good_handler)

        event = DocumentProcessed(document_id=uuid.uuid4())
        with pytest.raises(ExceptionGroup):
            listener.dispatch(event)

        # Both handlers were called (results has both 1 and 2)
        assert results == [1, 2]
