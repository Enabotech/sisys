"""Task 5 TDD Tests — EventListenerAsync (AC-5)."""

from __future__ import annotations

from abc import ABC

from src.domain.events.base import DomainEvent
from src.domain.events.listener import EventListener, EventListenerAsync


class TestEventListenerAsyncInterface:
    """EventListenerAsync interface tests."""

    def test_event_listener_async_is_abc(self) -> None:
        """EventListenerAsync should be an abstract base class."""
        assert issubclass(EventListenerAsync, ABC)

    def test_event_listener_async_has_async_handle_method(self) -> None:
        """EventListenerAsync should declare async_handle method."""
        # Check that the method exists and is abstract
        assert hasattr(EventListenerAsync, "async_handle")
        # The method should be an abstract method
        assert getattr(EventListenerAsync.async_handle, "__isabstractmethod__", False)

    def test_event_listener_async_not_same_as_event_listener(self) -> None:
        """EventListenerAsync should be independent from EventListener."""
        # They should be separate interfaces, not one inheriting from the other
        assert EventListenerAsync is not EventListener

    def test_event_listener_async_does_not_inherit_from_event_listener(self) -> None:
        """EventListenerAsync should NOT inherit from EventListener."""
        # EventListenerAsync is independent - does not extend EventListener
        assert not issubclass(EventListenerAsync, EventListener)


class TestEventListenerAsyncConcrete:
    """Test implementing EventListenerAsync in a concrete class."""

    def test_concrete_implementation_can_be_created(self) -> None:
        """A concrete class implementing EventListenerAsync can be instantiated."""

        class SimpleAsyncListener(EventListenerAsync):
            async def async_handle(self, event: DomainEvent) -> None:
                """Handle the event asynchronously."""
                pass

        listener = SimpleAsyncListener()
        assert listener is not None

    def test_concrete_implementation_handles_event(self) -> None:
        """Concrete implementation should handle events via async_handle."""
        handled_events: list[DomainEvent] = []

        class TrackingAsyncListener(EventListenerAsync):
            async def async_handle(self, event: DomainEvent) -> None:
                handled_events.append(event)

        listener = TrackingAsyncListener()
        event = DomainEvent(event_type="TestEvent")
        import asyncio

        asyncio.run(listener.async_handle(event))
        assert len(handled_events) == 1
        assert handled_events[0].event_type == "TestEvent"

    def test_concrete_implementation_with_multiple_handlers(self) -> None:
        """Concrete implementation supports multiple async handlers."""
        call_count = 0

        class CountingAsyncListener(EventListenerAsync):
            async def async_handle(self, event: DomainEvent) -> None:
                nonlocal call_count
                call_count += 1

        listener = CountingAsyncListener()
        event = DomainEvent(event_type="TestEvent")
        import asyncio

        asyncio.run(listener.async_handle(event))
        asyncio.run(listener.async_handle(event))
        assert call_count == 2
