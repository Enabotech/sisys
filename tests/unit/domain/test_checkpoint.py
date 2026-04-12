"""Tests for Checkpoint domain entity."""

import uuid

import pytest

from src.domain.entities.checkpoint import Checkpoint, CheckpointStatus, RecoveryMode


def _make_checkpoint(**kwargs) -> Checkpoint:
    """Factory helper for Checkpoint."""
    defaults: dict = {
        "checkpoint_id": uuid.uuid4(),
        "phase_identifier": "phase-1",
    }
    defaults.update(kwargs)
    return Checkpoint(**defaults)


class TestCheckpointCreation:
    """Test Checkpoint entity creation."""

    def test_create_minimal_checkpoint(self):
        """Can create a checkpoint with minimal arguments."""
        cp = _make_checkpoint()
        assert cp.checkpoint_id is not None
        assert cp.phase_identifier == "phase-1"
        assert cp.status == CheckpointStatus.PENDING
        assert cp.recovery_mode is None

    def test_checkpoint_has_empty_correction_records(self):
        """Checkpoint starts with empty correction records."""
        cp = _make_checkpoint()
        assert cp.correction_records == []


class TestCheckpointValidation:
    """Test Checkpoint invariant validation."""

    def test_valid_checkpoint_passes(self):
        """Correctly constructed checkpoint passes validation."""
        cp = _make_checkpoint()
        assert cp.validate() is True

    def test_invalid_id_fails(self):
        """Checkpoint with non-UUID id fails validation."""
        cp = _make_checkpoint()
        cp.checkpoint_id = "not-a-uuid"  # type: ignore
        with pytest.raises(ValueError, match="checkpoint_id must be a valid UUID"):
            cp.validate()

    def test_empty_phase_identifier_fails(self):
        """Checkpoint with empty phase_identifier fails validation."""
        cp = _make_checkpoint(phase_identifier="")
        with pytest.raises(ValueError, match="phase_identifier must not be empty"):
            cp.validate()

    def test_invalid_status_fails(self):
        """Checkpoint with invalid status fails validation."""
        cp = _make_checkpoint()
        cp.status = "invalid_status"  # type: ignore
        with pytest.raises(ValueError, match="status must be a valid CheckpointStatus"):
            cp.validate()


class TestCheckpointTransitions:
    """Test Checkpoint state transitions."""

    def test_complete_checkpoint(self):
        """Can complete a checkpoint."""
        cp = _make_checkpoint()
        cp.complete()
        assert cp.status == CheckpointStatus.COMPLETED
        assert cp.completed_at is not None

    def test_recover_checkpoint_replay(self):
        """Can recover a checkpoint in REPLAY mode."""
        cp = _make_checkpoint()
        cp.recover(RecoveryMode.REPLAY)
        assert cp.status == CheckpointStatus.RECOVERED
        assert cp.recovery_mode == RecoveryMode.REPLAY

    def test_recover_checkpoint_override(self):
        """Can recover a checkpoint in OVERRIDE mode."""
        cp = _make_checkpoint()
        cp.recover(RecoveryMode.OVERRIDE)
        assert cp.status == CheckpointStatus.RECOVERED
        assert cp.recovery_mode == RecoveryMode.OVERRIDE
