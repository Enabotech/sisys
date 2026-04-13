"""Infrastructure repository implementations."""

from .outbox import InMemoryOutboxRepository

__all__ = ["InMemoryOutboxRepository"]
