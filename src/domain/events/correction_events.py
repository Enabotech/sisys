"""Correction domain event."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class CorrectionApproved(DomainEvent):
    """Event emitted when a correction has been approved."""

    correction_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="CorrectionApproved", init=False)
    correction_type: str = ""
    previous_value: Any = None
    new_value: Any = None
    approval_chain: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.correction_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Correction")
