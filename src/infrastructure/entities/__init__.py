"""Infrastructure layer entities."""

from .outbox import InvalidStateTransitionError, OutboxEntity

__all__ = ["OutboxEntity", "InvalidStateTransitionError"]
