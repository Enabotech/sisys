"""Event store interface.

Defined in the domain layer, implemented in the infrastructure layer.
Provides persistence abstraction for event sourcing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from .base import DomainEvent


class EventStore(ABC):
    """Abstract event store interface for event sourcing.

    Implementations in the infrastructure layer persist and retrieve
    event streams by aggregate root.
    """

    @abstractmethod
    def save_events(self, events: list[DomainEvent]) -> None:
        """Persist a list of domain events.

        Args:
            events: The domain events to persist.

        Raises:
            NotImplementedError: Always, since this is an abstract interface.
        """

    @abstractmethod
    def get_events(self, aggregate_id: UUID) -> list[DomainEvent]:
        """Retrieve all events for a given aggregate.

        Args:
            aggregate_id: The ID of the aggregate root.

        Returns:
            List of domain events for the aggregate, in order.

        Raises:
            NotImplementedError: Always, since this is an abstract interface.
        """

    @abstractmethod
    def get_events_by_version(
        self,
        aggregate_id: UUID,
        from_version: int,
        to_version: int,
    ) -> list[DomainEvent]:
        """Retrieve events for a given aggregate within a version range.

        Args:
            aggregate_id: The ID of the aggregate root.
            from_version: Start version (inclusive).
            to_version: End version (inclusive).

        Returns:
            List of domain events within the version range.

        Raises:
            NotImplementedError: Always, since this is an abstract interface.
        """
