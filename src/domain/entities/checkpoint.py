"""Checkpoint domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


@dataclass
class CorrectionRecord:
    """P1-06 Fix: Strongly typed correction record for checkpoints.

    Attributes:
        correction_id: Unique identifier for this correction.
        correction_type: Type of correction (e.g., L0, L1, L2, L3).
        previous_value: The value before correction.
        new_value: The value after correction.
        applied_by: User or system that applied the correction.
        applied_at: Timestamp when correction was applied.
    """

    correction_type: str
    previous_value: str = ""
    new_value: str = ""
    applied_by: str = ""
    applied_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class RecoveryMode(str, Enum):
    """Checkpoint recovery modes."""

    REPLAY = "replay"
    OVERRIDE = "override"


class CheckpointStatus(str, Enum):
    """Checkpoint completion status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    RECOVERED = "recovered"


@dataclass
class Checkpoint:
    """Checkpoint entity with phase identification and recovery capability.

    Invariant constraints:
    - checkpoint_id must be a valid UUID
    - phase_identifier must not be empty
    - status must be a valid CheckpointStatus
    """

    checkpoint_id: uuid.UUID
    phase_identifier: str
    status: CheckpointStatus = CheckpointStatus.PENDING
    recovery_mode: RecoveryMode | None = None
    summary: str = ""
    correction_records: list[CorrectionRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate(self) -> bool:
        """Validate invariant constraints.

        Returns:
            True if all invariants are satisfied.

        Raises:
            ValueError: If any invariant is violated.
        """
        if not isinstance(self.checkpoint_id, uuid.UUID):
            raise ValueError("checkpoint_id must be a valid UUID")
        if not self.phase_identifier or not self.phase_identifier.strip():
            raise ValueError("phase_identifier must not be empty")
        if not isinstance(self.status, CheckpointStatus):
            raise ValueError("status must be a valid CheckpointStatus")
        return True

    def complete(self) -> None:
        """Mark checkpoint as completed.

        Valid transitions: PENDING -> COMPLETED, IN_PROGRESS -> COMPLETED,
        RECOVERED -> COMPLETED.

        Raises:
            ValueError: If checkpoint is already completed.
        """
        # P1-01 Fix: Add state guard
        if self.status == CheckpointStatus.COMPLETED:
            raise ValueError("Checkpoint is already completed")
        self.status = CheckpointStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        self.updated_at = self.completed_at

    def recover(self, mode: RecoveryMode) -> None:
        """Recover from this checkpoint using specified mode.

        Valid transitions: PENDING -> RECOVERED, IN_PROGRESS -> RECOVERED,
        RECOVERED -> RECOVERED (re-recover with different mode).
        Cannot recover a COMPLETED checkpoint.

        Args:
            mode: Recovery mode (REPLAY or OVERRIDE).

        Raises:
            ValueError: If checkpoint is already completed.
        """
        # P1-02 Fix: Add state guard
        if self.status == CheckpointStatus.COMPLETED:
            raise ValueError("Cannot recover a completed checkpoint")
        self.recovery_mode = mode
        self.status = CheckpointStatus.RECOVERED
        self.updated_at = datetime.now(UTC)
