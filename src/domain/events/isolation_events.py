"""Isolation level domain event."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .base import DomainEvent
from .enums import IsolationLevel


@dataclass(frozen=True)
class IsolationLevelSwitched(DomainEvent):
    """Event emitted when an Agent's isolation level is switched."""

    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="IsolationLevelSwitched", init=False)
    previous_level: IsolationLevel = IsolationLevel.L4_HARD
    target_level: IsolationLevel = IsolationLevel.L4_HARD
    trigger_reason: str = ""
    approval_chain: list[str] = field(default_factory=list)
    switch_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Agent")
