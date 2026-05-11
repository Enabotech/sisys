"""RoutingDecision value object for UDMRouter."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


@dataclass(frozen=True)
class RoutingDecision:
    """Value object representing a routing decision for UDMRouter.

    Attributes:
        log_id: Unique identifier for the routing decision log
        task_id: The task identifier this decision applies to
        session_id: The session identifier
        route_type: Type of routing - "local" or "cloud"
        selected_model: The model selected for routing
        cost_estimate: Estimated cost in USD
        cost_actual: Actual cost in USD (default 0)
        latency_ms: Routing decision latency in milliseconds
        fallback_reason: Reason for fallback to cloud (optional)
        timestamp: Decision timestamp
    """

    log_id: uuid.UUID
    task_id: str
    session_id: str
    route_type: Literal["local", "cloud"]
    selected_model: str
    cost_estimate: float = 0.0
    cost_actual: float = 0.0
    latency_ms: float = 0.0
    fallback_reason: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate invariants after construction."""
        self.validate()

    def validate(self) -> None:
        """Validate invariant constraints.

        Raises:
            ValueError: If any invariant is violated.
        """
        if not isinstance(self.log_id, uuid.UUID):
            raise ValueError("log_id must be a valid UUID")
        if not self.task_id or not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.session_id or not self.session_id.strip():
            raise ValueError("session_id must not be empty")
        if self.route_type not in ("local", "cloud"):
            raise ValueError(f"route_type must be one of: local, cloud. Got: {self.route_type}")
        if self.cost_estimate < 0:
            raise ValueError(f"cost_estimate must be non-negative. Got: {self.cost_estimate}")
        if self.cost_actual < 0:
            raise ValueError(f"cost_actual must be non-negative. Got: {self.cost_actual}")
        if self.latency_ms < 0:
            raise ValueError(f"latency_ms must be non-negative. Got: {self.latency_ms}")
        if not self.selected_model or not self.selected_model.strip():
            raise ValueError("selected_model must not be empty")
        if self.fallback_reason is not None and self.fallback_reason not in (
            "timeout",
            "unavailable",
            "health_check_failed",
        ):
            raise ValueError(
                f"fallback_reason must be one of: timeout, unavailable, health_check_failed. Got: {self.fallback_reason}"
            )
