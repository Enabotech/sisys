"""Heartbeat domain event."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from .base import DomainEvent


@dataclass(frozen=True)
class HeartbeatTriggered(DomainEvent):
    """Event emitted when a periodic heartbeat timer triggers."""

    heartbeat_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="HeartbeatTriggered", init=False)
    wake_reason: str = ""
    todo_items: Sequence[str] = field(default_factory=tuple)
    cost_budget: float = 0.0

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.heartbeat_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Heartbeat")
