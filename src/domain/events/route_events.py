"""Routed domain event — emitted after route makes routing decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class Routed(DomainEvent):
    """Event emitted when route mechanism makes a routing decision.

    This event flows to Story 1.14c (execute) for task execution.
    """

    route_type: str = ""  # "hash" | "semantic" | "mixed"
    session_id: str = ""
    task_context: dict[str, Any] = field(default_factory=dict)
    route_target: str = ""  # Target Agent or tool ID
    route_score: float = 0.0  # Routing confidence/score
    trigger_event_type: str = ""  # Original trigger event type (e.g., "Triggered")
    trigger_event_id: str | None = None

    def __post_init__(self) -> None:
        """Set event_type, aggregate_id, and aggregate_type for event tracking."""
        if not self.event_type:
            object.__setattr__(self, "event_type", "Routed")
        if self.aggregate_id is None and self.event_id:
            object.__setattr__(self, "aggregate_id", self.event_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Route")


# Register Routed after class definition (manual registration needed due to init=False on event_type)
DomainEvent._registry["Routed"] = Routed
