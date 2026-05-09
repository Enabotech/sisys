"""Task 5 TDD Tests — EventListenerAsync (AC-5)."""

from __future__ import annotations

from unittest.mock import AsyncMock

from src.domain.events.base import DomainEvent
from src.domain.events.listener import EventListenerAsync


class TestEventListenerAsyncSignature:
    """Structural signature tests — verify async contract."""

    def test_async_handle_exists(self) -> None:
        """async_handle method must exist."""
        assert hasattr(EventListenerAsync, "async_handle")

    def test_async_handle_is_async(self) -> None:
        """async_handle should be an async method."""
        import inspect

        assert inspect.iscoroutinefunction(EventListenerAsync.async_handle)


class TestEventListenerAsyncMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec constraint."""

    async def test_mock_async_handle_verified(self) -> None:
        """Mock async_handle should be verifiable."""
        mock = AsyncMock(spec=EventListenerAsync)
        mock.async_handle.return_value = None

        event = DomainEvent(event_type="TestEvent")
        await mock.async_handle(event)
        mock.async_handle.assert_called_once_with(event)


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
