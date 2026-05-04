"""In-memory event bus implementation (MVP).

Implements both EventPublisher and event distribution with idempotency.
Uses a set of processed event IDs for deduplication (TTL simulated).
Thread-safe via threading.RLock.
"""

from __future__ import annotations

import threading
import uuid

from src.domain.events.base import DomainEvent
from src.domain.events.listener import InMemoryEventListener
from src.domain.ports.event_publisher import InMemoryEventPublisher


class InMemoryEventBus(InMemoryEventPublisher):
    """In-memory event bus with idempotency guarantee (MVP).

    Maintains a set of processed event IDs to prevent duplicate processing.
    Events are dispatched to registered listeners by event type.

    Thread-safe: all public methods are protected by a reentrant lock.

    Attributes:
        processed_event_ids: Set of already-processed event IDs.
        listener: The event listener to dispatch events to.
    """

    def __init__(self, listener: InMemoryEventListener | None = None) -> None:
        """Initialize the event bus.

        Args:
            listener: Optional event listener for dispatching events.
        """
        self._lock = threading.RLock()
        self.processed_event_ids: set[uuid.UUID] = set()
        self._listener = listener
        self._published_events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event with idempotency check.

        Events are dispatched to listeners first, then recorded as processed.
        This ensures that if dispatch fails, the event can be retried.

        Args:
            event: The domain event to publish.

        Raises:
            ValueError: If event is None.
        """
        if event is None:
            raise ValueError("event must not be None")

        with self._lock:
            # Idempotency check
            if event.event_id in self.processed_event_ids:
                return  # Already processed, skip

            # Dispatch to listener first, then record as processed
            if self._listener is not None:
                self._listener.dispatch(event)

            # Record as processed (only after successful dispatch)
            self.processed_event_ids.add(event.event_id)
            self._published_events.append(event)

    @property
    def published_events(self) -> list[DomainEvent]:
        """Return list of all published events (in order)."""
        with self._lock:
            return list(self._published_events)

    def reset(self) -> None:
        """Clear all processed event IDs and published events (for testing)."""
        with self._lock:
            self.processed_event_ids.clear()
            self._published_events.clear()
