"""Tests for StrategicPlan domain entity."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from src.domain.entities.strategic_plan import BLMPhase, PlanStatus, StrategicPlan


def _make_plan(**kwargs) -> StrategicPlan:
    """Factory helper for StrategicPlan."""
    defaults: dict = {
        "plan_id": uuid.uuid4(),
        "name": "Test Plan",
    }
    defaults.update(kwargs)
    return StrategicPlan(**defaults)


class TestStrategicPlanCreation:
    """Test StrategicPlan entity creation."""

    def test_create_minimal_plan(self):
        """Can create a plan with minimal arguments."""
        plan = _make_plan()
        assert plan.plan_id is not None
        assert plan.name == "Test Plan"
        assert plan.current_phase == BLMPhase.STRATEGIC_INTENT
        assert plan.status == PlanStatus.DRAFT

    def test_plan_has_default_timestamps(self):
        """Plan has created_at and updated_at timestamps."""
        plan = _make_plan()
        assert isinstance(plan.created_at, datetime)
        assert isinstance(plan.updated_at, datetime)

    def test_plan_has_empty_completed_phases(self):
        """Plan starts with no completed phases."""
        plan = _make_plan()
        assert plan.completed_phases == []


class TestStrategicPlanValidation:
    """Test StrategicPlan invariant validation."""

    def test_valid_plan_passes_validation(self):
        """A correctly constructed plan passes validation."""
        plan = _make_plan()
        assert plan.validate() is True

    def test_plan_with_empty_name_fails(self):
        """Plan with empty name fails validation."""
        plan = _make_plan(name="")
        with pytest.raises(ValueError, match="name must not be empty"):
            plan.validate()

    def test_plan_with_whitespace_name_fails(self):
        """Plan with whitespace-only name fails validation."""
        plan = _make_plan(name="   ")
        with pytest.raises(ValueError, match="name must not be empty"):
            plan.validate()

    def test_plan_with_invalid_id_fails(self):
        """Plan with non-UUID id fails validation."""
        plan = _make_plan()
        object.__setattr__(plan, "plan_id", cast(uuid.UUID, "not-a-uuid"))
        with pytest.raises(ValueError, match="plan_id must be a valid UUID"):
            plan.validate()

    def test_plan_timestamps_valid(self):
        """created_at must be before or equal to updated_at."""
        plan = _make_plan()
        object.__setattr__(plan, "created_at", datetime.now(UTC) + timedelta(days=1))
        object.__setattr__(plan, "updated_at", datetime.now(UTC))
        with pytest.raises(ValueError, match="created_at must be before"):
            plan.validate()


class TestStrategicPlanPhaseTransition:
    """Test BLM phase advancement."""

    def test_advance_to_next_phase(self):
        """Can advance to the next BLM phase."""
        plan = _make_plan()
        plan.advance_phase(BLMPhase.MARKET_INSIGHT)
        assert plan.current_phase == BLMPhase.MARKET_INSIGHT
        assert BLMPhase.STRATEGIC_INTENT in plan.completed_phases

    def test_cannot_advance_backwards(self):
        """Cannot advance to an earlier phase."""
        plan = _make_plan()
        plan.advance_phase(BLMPhase.MARKET_INSIGHT)
        with pytest.raises(ValueError, match="Can only advance"):
            plan.advance_phase(BLMPhase.STRATEGIC_INTENT)

    def test_cannot_skip_phases(self):
        """P0-02 Fix: Cannot skip intermediate phases."""
        plan = _make_plan()
        with pytest.raises(ValueError, match="immediately next phase"):
            plan.advance_phase(BLMPhase.EXECUTION_MONITORING)

    def test_cannot_advance_archived_plan(self):
        """P0-03 Fix: Cannot advance archived plan."""
        plan = _make_plan(status=PlanStatus.ARCHIVED)
        with pytest.raises(ValueError, match="Cannot advance phase"):
            plan.advance_phase(BLMPhase.MARKET_INSIGHT)

    def test_cannot_advance_approved_plan(self):
        """P0-03 Fix: Cannot advance approved plan."""
        plan = _make_plan(status=PlanStatus.APPROVED)
        with pytest.raises(ValueError, match="Cannot advance phase"):
            plan.advance_phase(BLMPhase.MARKET_INSIGHT)

    def test_complete_current_phase(self):
        """complete_phase() marks current phase done and advances."""
        plan = _make_plan()
        plan.complete_phase()
        assert BLMPhase.STRATEGIC_INTENT in plan.completed_phases
        assert plan.current_phase == BLMPhase.MARKET_INSIGHT

    def test_updated_at_changes_on_phase_advance(self):
        """updated_at is updated when advancing phases."""
        plan = _make_plan()
        old_time = plan.updated_at
        plan.advance_phase(BLMPhase.MARKET_INSIGHT)
        assert plan.updated_at >= old_time

    def test_cannot_advance_past_final_phase(self):
        """P0-01 Fix: Cannot advance past EXECUTION_MONITORING."""
        plan = _make_plan()
        # Advance through all phases
        for phase in [
            BLMPhase.MARKET_INSIGHT,
            BLMPhase.STRATEGIC_DESIGN,
            BLMPhase.ORGANIZATIONAL_DESIGN,
            BLMPhase.IMPLEMENTATION_PLANNING,
            BLMPhase.EXECUTION_MONITORING,
        ]:
            plan.advance_phase(phase)
        assert plan.current_phase == BLMPhase.EXECUTION_MONITORING
        # Now attempting to advance again should fail with clear message
        with pytest.raises(ValueError, match="has reached the final phase"):
            plan.advance_phase(BLMPhase.EXECUTION_MONITORING)

    def test_completed_phases_consistency_validation(self):
        """P1-01 Fix: current_phase must not be in completed_phases."""
        plan = _make_plan()
        plan.advance_phase(BLMPhase.MARKET_INSIGHT)
        assert BLMPhase.STRATEGIC_INTENT in plan.completed_phases
        # Corrupt the state by adding current_phase to completed_phases
        plan.completed_phases.append(BLMPhase.MARKET_INSIGHT)
        with pytest.raises(ValueError, match="current_phase must not be in completed_phases"):
            plan.validate()

    def test_completed_phases_no_duplicates(self):
        """P1-01 Fix: advance_phase/complete_phase prevent duplicate entries."""
        plan = _make_plan()
        plan.advance_phase(BLMPhase.MARKET_INSIGHT)
        # External code tries to add duplicate
        plan.completed_phases.append(BLMPhase.STRATEGIC_INTENT)
        assert plan.completed_phases.count(BLMPhase.STRATEGIC_INTENT) == 2
        # advance_phase should NOT add another duplicate
        plan.advance_phase(BLMPhase.STRATEGIC_DESIGN)
        assert plan.completed_phases.count(BLMPhase.MARKET_INSIGHT) == 1

    def test_cannot_complete_past_final_phase(self):
        """Re-review Fix: complete_phase() has final phase guard."""
        plan = _make_plan()
        for phase in [
            BLMPhase.MARKET_INSIGHT,
            BLMPhase.STRATEGIC_DESIGN,
            BLMPhase.ORGANIZATIONAL_DESIGN,
            BLMPhase.IMPLEMENTATION_PLANNING,
            BLMPhase.EXECUTION_MONITORING,
        ]:
            plan.advance_phase(phase)
        with pytest.raises(ValueError, match="has reached the final phase"):
            plan.complete_phase()

    def test_cannot_complete_archived_plan(self):
        """Re-review Fix: complete_phase() has status guard."""
        plan = _make_plan(status=PlanStatus.ARCHIVED)
        with pytest.raises(ValueError, match="Cannot complete phase"):
            plan.complete_phase()

    def test_cannot_complete_approved_plan(self):
        """Re-review Fix: complete_phase() has status guard."""
        plan = _make_plan(status=PlanStatus.APPROVED)
        with pytest.raises(ValueError, match="Cannot complete phase"):
            plan.complete_phase()
