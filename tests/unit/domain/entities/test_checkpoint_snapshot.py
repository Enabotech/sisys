"""Tests for CheckpointSnapshot domain entity."""

import uuid

import pytest

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot


class TestCheckpointSnapshot:
    """TDD tests for CheckpointSnapshot entity."""

    def test_create_snapshot_with_required_fields(self) -> None:
        """RED: CheckpointSnapshot should be creatable with session_id."""
        session_id = "test-session-123"
        snapshot = CheckpointSnapshot(session_id=session_id)

        assert snapshot.session_id == session_id
        assert snapshot.snapshot_id is not None
        assert isinstance(snapshot.snapshot_id, uuid.UUID)
        assert snapshot.state_version == 0
        assert snapshot.state_data == {}
        assert snapshot.stage_id == ""

    def test_with_updated_state_creates_new_snapshot(self) -> None:
        """RED: with_updated_state should create new snapshot with merged state."""
        original = CheckpointSnapshot(
            session_id="test-session",
            stage_id="planning",
            state_version=1,
            state_data={"original_key": "original_value"},
        )

        updated = original.with_updated_state({"new_key": "new_value"})

        assert updated.session_id == original.session_id
        assert updated.stage_id == original.stage_id
        assert updated.state_version == 2
        assert updated.state_data["original_key"] == "original_value"
        assert updated.state_data["new_key"] == "new_value"
        assert updated.snapshot_id != original.snapshot_id

    def test_snapshot_immutability(self) -> None:
        """RED: CheckpointSnapshot should be immutable (frozen dataclass)."""
        snapshot = CheckpointSnapshot(session_id="test-session")
        field_name = "session_id"

        # Using setattr with string to bypass mypy's property check
        # This tests that frozen dataclass raises FrozenInstanceError
        with pytest.raises(Exception):
            setattr(snapshot, field_name, "changed-session")
