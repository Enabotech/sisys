"""Event publisher interface.

This interface is defined in the domain layer and implemented
in the infrastructure layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .base import DomainEvent


class EventPublisher(ABC):
    """Abstract event publisher interface.

    Implementations in the infrastructure layer publish events to
    the appropriate message bus (RabbitMQ, Redis pub/sub, etc.).

    P1-07 Fix: Use ABC to prevent direct instantiation.
    """

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event.

        Args:
            event: The domain event to publish.

        Raises:
            NotImplementedError: Always, since this is an abstract interface.
        """
