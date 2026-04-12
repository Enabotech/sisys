"""Isolation level and checkpoint recovery domain events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .base import DomainEvent
from .enums import IsolationLevel, RecoveryMode


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


@dataclass(frozen=True)
class CheckpointRecovered(DomainEvent):
    """Event emitted when a checkpoint is recovered from a previous state."""

    checkpoint_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="CheckpointRecovered", init=False)
    recovery_mode: RecoveryMode = RecoveryMode.REPLAY
    modification_content: dict[str, Any] = field(default_factory=dict)
    affected_checkpoints: list[str] = field(default_factory=list)
    consistency_risk_level: str = "low"
    execution_delay_ms: float = 0.0
    cost: float = 0.0

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.checkpoint_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Checkpoint")
