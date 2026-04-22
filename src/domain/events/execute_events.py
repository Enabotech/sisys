"""Executed domain event — emitted after execute completes task execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class Executed(DomainEvent):
    """Event emitted when execute mechanism completes task execution.

    This event flows after route decision (Story 1.14b) and contains
    execution results. Downstream listeners publish corresponding
    domain events (DocumentProcessed/ToolExecuted/AgentDecided) based
    on business_event_type.
    """

    session_id: str = ""
    task_context: dict[str, Any] = field(default_factory=dict)
    execution_result: dict[str, Any] = field(default_factory=dict)
    cost_estimate: float = 0.0
    latency_ms: float = 0.0
    business_event_type: str = ""  # "DocumentProcessed" | "ToolExecuted" | "AgentDecided"
    route_target: str = ""  # Target that was selected by route
    route_score: float = 0.0  # Routing confidence score

    def __post_init__(self) -> None:
        """Set event_type, aggregate_id, and aggregate_type for event tracking."""
        if not self.event_type:
            object.__setattr__(self, "event_type", "Executed")
        if self.aggregate_id is None and self.event_id:
            object.__setattr__(self, "aggregate_id", self.event_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Execute")


# Register Executed after class definition
DomainEvent._registry["Executed"] = Executed
