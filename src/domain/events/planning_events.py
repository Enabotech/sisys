"""Strategic planning domain events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .base import DomainEvent
from .enums import DeviationLevel, DeviationType


@dataclass(frozen=True)
class StrategicDeviationWarning(DomainEvent):
    """Event emitted when strategic plan deviates from expected trajectory."""

    warning_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="StrategicDeviationWarning", init=False)
    deviation_type: DeviationType = DeviationType.BUDGET_OVERUN
    deviation_level: DeviationLevel = DeviationLevel.MINOR
    actual_value: float = 0.0
    planned_value: float = 0.0
    threshold: float = 10.0

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.warning_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "StrategicPlan")
