"""Infrastructure layer adapters."""

from .event_outbox_adapter import EventOutboxAdapter, EventRegistry

__all__ = ["EventOutboxAdapter", "EventRegistry"]
