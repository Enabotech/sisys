"""Routing decision domain event."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class RoutingDecided(DomainEvent):
    """Event emitted when a UDMR routing decision is made."""

    task_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="RoutingDecided", init=False)
    l1_compliance_result: dict[str, Any] = field(default_factory=dict)
    l2_factor_scores: dict[str, float] = field(default_factory=dict)
    final_routing_score: float = 0.0
    selected_model: str = ""
    estimated_cost: float = 0.0

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.task_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "RoutingTask")
