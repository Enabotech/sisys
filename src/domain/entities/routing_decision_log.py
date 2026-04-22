"""RoutingDecisionLog domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class RoutingDecisionLog:
    """Log entry for routing decisions.

    Stores routing decision details for audit and cost tracking.
    WORM storage required (7-year retention per compliance requirements).

    Invariant constraints:
    - log_id must be a valid UUID
    - task_id must not be empty
    - session_id must not be empty
    - route_type must be one of: "hash", "semantic", "mixed"
    - route_score must be between 0.0 and 1.0
    """

    log_id: uuid.UUID
    task_id: str
    session_id: str
    route_type: str  # "hash" | "semantic" | "mixed"
    route_target: str  # Target Agent or tool ID
    route_score: float  # Routing confidence/score (0.0 to 1.0)
    cost_estimate: float = 0.0  # Estimated cost in USD
    latency_ms: float = 0.0  # Routing decision latency in milliseconds
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    worm_storage_ref: str = ""  # WORM storage reference for compliance

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
        if self.route_type not in ("hash", "semantic", "mixed"):
            raise ValueError(f"route_type must be one of: hash, semantic, mixed. Got: {self.route_type}")
        if not (0.0 <= self.route_score <= 1.0):
            raise ValueError(f"route_score must be between 0.0 and 1.0. Got: {self.route_score}")
        if self.cost_estimate < 0:
            raise ValueError(f"cost_estimate must be non-negative. Got: {self.cost_estimate}")
        if self.latency_ms < 0:
            raise ValueError(f"latency_ms must be non-negative. Got: {self.latency_ms}")
