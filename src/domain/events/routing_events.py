"""Routing decision domain event."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from .base import DomainEvent


@dataclass(frozen=True)
class RoutingDecided(DomainEvent):
    """Event emitted when a UDMR routing decision is made.

    L1 (compliance) and L2 (four-factor scoring) fields are populated by Story 11.x.
    L3 (local/cloud static routing) fields are populated by Story 1.17.
    """

    task_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="RoutingDecided", init=False)
    l1_compliance_result: dict[str, Any] = field(default_factory=dict)
    l2_factor_scores: dict[str, float] = field(default_factory=dict)
    final_routing_score: float = 0.0
    # L3 静态路由字段（Story 1.17）
    route_type: Literal["local", "cloud"] = "local"
    selected_model: str = ""
    estimated_cost: float = 0.0
    fallback_reason: Literal["timeout", "unavailable", "health_check_failed"] | None = None
    # 健康检查结果（Story 1.17）
    health_check_passed: bool = True
    health_check_latency_ms: float = 0.0

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.task_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "RoutingTask")
