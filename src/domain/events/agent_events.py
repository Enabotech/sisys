"""Agent domain event."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class AgentDecided(DomainEvent):
    """Event emitted when an Agent has made a decision."""

    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="AgentDecided", init=False)
    decision_result: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Agent")
