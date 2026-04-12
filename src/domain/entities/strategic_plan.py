"""StrategicPlan domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class BLMPhase(str, Enum):
    """BLM (Business Leadership Model) phases."""

    STRATEGIC_INTENT = "strategic_intent"
    MARKET_INSIGHT = "market_insight"
    STRATEGIC_DESIGN = "strategic_design"
    ORGANIZATIONAL_DESIGN = "organizational_design"
    IMPLEMENTATION_PLANNING = "implementation_planning"
    EXECUTION_MONITORING = "execution_monitoring"


class PlanStatus(str, Enum):
    """Strategic plan status."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    ARCHIVED = "archived"


@dataclass
class StrategicPlan:
    """StrategicPlan entity following BLM six-phase model.

    Invariant constraints:
    - plan_id must be a valid UUID
    - name must not be empty
    - current_phase must be a valid BLMPhase
    - created_at must be before updated_at
    """

    plan_id: uuid.UUID
    name: str
    description: str = ""
    current_phase: BLMPhase = BLMPhase.STRATEGIC_INTENT
    status: PlanStatus = PlanStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_phases: list[BLMPhase] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate invariant constraints.

        Returns:
            True if all invariants are satisfied.

        Raises:
            ValueError: If any invariant is violated.
        """
        if not isinstance(self.plan_id, uuid.UUID):
            raise ValueError("plan_id must be a valid UUID")
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not isinstance(self.current_phase, BLMPhase):
            raise ValueError("current_phase must be a valid BLMPhase")
        # P2-05 Fix: created_at/updated_at have default_factory, never None
        if self.created_at > self.updated_at:
            raise ValueError("created_at must be before or equal to updated_at")
        # P1-01 Fix: Validate completed_phases consistency
        if self.current_phase in self.completed_phases:
            raise ValueError("current_phase must not be in completed_phases")
        return True

    def advance_phase(self, next_phase: BLMPhase) -> None:
        """Advance to the next BLM phase.

        Args:
            next_phase: The next BLM phase to advance to.

        Raises:
            ValueError: If phase transition is invalid or plan is archived/approved.
        """
        # P0-03: Status guard — cannot advance archived or approved plans
        if self.status in (PlanStatus.ARCHIVED, PlanStatus.APPROVED):
            raise ValueError(f"Cannot advance phase when plan is {self.status.value}")

        # P0-01 Fix: Guard against advancing past the final phase
        if self.current_phase == BLMPhase.EXECUTION_MONITORING:
            raise ValueError(
                "Plan has reached the final phase (EXECUTION_MONITORING), " "no further phase advancement possible"
            )

        phase_order = list(BLMPhase)
        current_idx = phase_order.index(self.current_phase)
        next_idx = phase_order.index(next_phase)

        # P0-02: Must advance to immediately next phase (no skipping)
        if next_idx != current_idx + 1:
            raise ValueError("Can only advance to the immediately next phase")

        # P1-01 Fix: Prevent duplicate entries in completed_phases
        if self.current_phase not in self.completed_phases:
            self.completed_phases.append(self.current_phase)
        self.current_phase = next_phase
        self.updated_at = datetime.now(UTC)

    def complete_phase(self) -> None:
        """Mark current phase as completed and advance.

        Raises:
            ValueError: If plan is archived/approved or already at final phase.
        """
        # Status guard — cannot complete archived or approved plans
        if self.status in (PlanStatus.ARCHIVED, PlanStatus.APPROVED):
            raise ValueError(f"Cannot complete phase when plan is {self.status.value}")

        # Final phase guard — cannot complete past the final phase
        if self.current_phase == BLMPhase.EXECUTION_MONITORING:
            raise ValueError(
                "Plan has reached the final phase (EXECUTION_MONITORING), " "no further phase advancement possible"
            )

        # P1-01 Fix: Prevent duplicate entries in completed_phases
        if self.current_phase not in self.completed_phases:
            self.completed_phases.append(self.current_phase)
        phase_order = list(BLMPhase)
        current_idx = phase_order.index(self.current_phase)
        if current_idx < len(phase_order) - 1:
            self.current_phase = phase_order[current_idx + 1]
        self.updated_at = datetime.now(UTC)
