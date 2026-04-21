"""Triggered domain event — emitted after trigger extracts context from domain/heartbeat events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class Triggered(DomainEvent):
    """Event emitted when trigger mechanism extracts context from domain or heartbeat events.

    This event flows to Story 1.14b (route) for session-aware routing decisions.
    """

    # Note: event_type is inherited from DomainEvent (init=True, default="")
    # The actual event_type value "Triggered" is set via __post_init__
    trigger_type: str = ""  # "domain_event" | "heartbeat"
    session_id: str = ""
    agent_id: str | None = None
    task_context: dict[str, Any] = field(default_factory=dict)
    source_event_type: str = ""  # Original event that triggered (e.g., "DocumentProcessed")
    source_event_id: str | None = None

    def __post_init__(self) -> None:
        """Set event_type, aggregate_id, and aggregate_type for event tracking."""
        # Set event_type to class name if not already set
        if not self.event_type:
            object.__setattr__(self, "event_type", "Triggered")
        if self.aggregate_id is None and self.event_id:
            object.__setattr__(self, "aggregate_id", self.event_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Trigger")


# Register Triggered after class definition (manual registration needed due to init=False on event_type)
DomainEvent._registry["Triggered"] = Triggered
