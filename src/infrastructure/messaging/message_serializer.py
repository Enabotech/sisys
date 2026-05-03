"""In-memory event store implementation (MVP).

Stores events in memory using dictionaries and lists.
Suitable for testing and MVP; replace with PostgreSQL for production.
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from src.domain.events.base import DomainEvent
from src.domain.events.event_store import EventStore


class InMemoryEventStore(EventStore):
    """In-memory event store implementation (MVP).

    Uses in-memory dictionaries and lists to store events.
    Events are indexed by aggregate_id for efficient retrieval.

    Attributes:
        _events_by_aggregate: Mapping of aggregate_id to list of events.
    """

    def __init__(self) -> None:
        """Initialize the event store with empty storage."""
        self._events_by_aggregate: dict[UUID, list[DomainEvent]] = defaultdict(list)

    def save_events(self, events: list[DomainEvent]) -> None:
        """Persist a list of domain events to memory.

        Events are appended to the aggregate's event list in order.

        Args:
            events: The domain events to persist.
        """
        for event in events:
            if event.aggregate_id is not None:
                self._events_by_aggregate[event.aggregate_id].append(event)

    def get_events(self, aggregate_id: UUID) -> list[DomainEvent]:
        """Retrieve all events for a given aggregate.

        Args:
            aggregate_id: The ID of the aggregate root.

        Returns:
            List of domain events for the aggregate, in order.
        """
        return list(self._events_by_aggregate.get(aggregate_id, []))

    def get_events_by_version(
        self,
        aggregate_id: UUID,
        from_version: int,
        to_version: int,
    ) -> list[DomainEvent]:
        """Retrieve events for a given aggregate within a version range.

        Uses the event's position in the list as its version number
        (1-based indexing).

        Args:
            aggregate_id: The ID of the aggregate root.
            from_version: Start version (inclusive, 1-based).
            to_version: End version (inclusive, 1-based).

        Returns:
            List of domain events within the version range.

        Raises:
            ValueError: If from_version > to_version or versions are negative.
        """
        if from_version < 1 or to_version < 1:
            raise ValueError("Version numbers must be >= 1")
        if from_version > to_version:
            raise ValueError(f"from_version ({from_version}) must be <= to_version ({to_version})")
        all_events = self._events_by_aggregate.get(aggregate_id, [])
        # Convert 1-based version to 0-based index
        start_idx = max(0, from_version - 1)
        end_idx = min(len(all_events), to_version)
        return list(all_events[start_idx:end_idx])

    def clear(self) -> None:
        """Clear all stored events (for testing)."""
        self._events_by_aggregate.clear()
