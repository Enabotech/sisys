"""Tests for CheckpointSnapshot domain entity."""

import uuid
from datetime import UTC, datetime

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

    def test_snapshot_to_redis_hash(self) -> None:
        """RED: CheckpointSnapshot should serialize to Redis Hash format."""
        session_id = "test-session-456"
        snapshot = CheckpointSnapshot(
            session_id=session_id,
            stage_id="planning",
            state_version=1,
            state_data={"key": "value", "number": 42},
        )

        hash_data = snapshot.to_redis_hash()

        assert hash_data["session_id"] == session_id
        assert hash_data["stage_id"] == "planning"
        assert hash_data["state_version"] == "1"
        assert "key" in hash_data["state_data"]
        assert "number" in hash_data["state_data"]

    def test_snapshot_from_redis_hash(self) -> None:
        """RED: CheckpointSnapshot should deserialize from Redis Hash format."""
        data = {
            "snapshot_id": str(uuid.uuid4()),
            "session_id": "test-session-789",
            "stage_id": "execution",
            "state_version": "2",
            "state_data": '{"key": "value", "count": 100}',
            "timestamp": datetime.now(UTC).isoformat(),
            "ttl_seconds": "3600",
        }

        snapshot = CheckpointSnapshot.from_redis_hash(data)

        assert snapshot.session_id == "test-session-789"
        assert snapshot.stage_id == "execution"
        assert snapshot.state_version == 2
        assert snapshot.state_data["key"] == "value"
        assert snapshot.state_data["count"] == 100
        assert snapshot.ttl_seconds == 3600

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

        with pytest.raises(AttributeError):
            snapshot.session_id = "changed-session"  # type: ignore
