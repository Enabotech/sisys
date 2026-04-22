"""CheckpointSnapshot — domain entity for session state snapshots.

Represents the state of a session at a specific point in time.
Used for中断恢复 and time-travel debugging capabilities.

Follows system axiom 2 (Externalized Memory): LLM context = cache,
disk memory = source of truth. Snapshots are serialized to Redis Hash
with configurable TTL (default 24h-30d).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class CheckpointSnapshot:
    """Domain entity representing a session state snapshot.

    Immutable once created. Supports serialization to Redis Hash format
    for storage and retrieval.

    Attributes:
        snapshot_id: Unique identifier for this snapshot
        session_id: Session this snapshot belongs to
        stage_id: Current execution stage (e.g., "planning", "execution")
        state_version: Version number for optimistic locking
        state_data: The actual state as key-value pairs
        timestamp: When this snapshot was created
        ttl_seconds: Time-to-live in seconds (24h-30d range: 86400-2592000)
    """

    snapshot_id: uuid.UUID = field(default_factory=uuid.uuid4)
    session_id: str = ""
    stage_id: str = ""
    state_version: int = 0
    state_data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    ttl_seconds: int = 86400  # Default 24 hours

    def to_redis_hash(self) -> dict[str, str]:
        """Serialize snapshot to Redis Hash format.

        Returns:
            Dictionary suitable for HSET operation
        """
        return {
            "snapshot_id": str(self.snapshot_id),
            "session_id": self.session_id,
            "stage_id": self.stage_id,
            "state_version": str(self.state_version),
            "state_data": json.dumps(self.state_data),
            "timestamp": self.timestamp.isoformat(),
            "ttl_seconds": str(self.ttl_seconds),
        }

    @classmethod
    def from_redis_hash(cls, data: dict[str, str]) -> CheckpointSnapshot:
        """Deserialize snapshot from Redis Hash format.

        Args:
            data: Dictionary from HGETALL operation

        Returns:
            CheckpointSnapshot instance
        """
        return cls(
            snapshot_id=uuid.UUID(data["snapshot_id"]),
            session_id=data["session_id"],
            stage_id=data["stage_id"],
            state_version=int(data["state_version"]),
            state_data=json.loads(data["state_data"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            ttl_seconds=int(data["ttl_seconds"]),
        )

    def with_updated_state(self, state_data: dict[str, Any], new_version: int | None = None) -> CheckpointSnapshot:
        """Create a new snapshot with updated state data.

        Args:
            state_data: New state data to merge
            new_version: Optional new version number (defaults to state_version + 1)

        Returns:
            New CheckpointSnapshot with merged state
        """
        merged_state = {**self.state_data, **state_data}
        return CheckpointSnapshot(
            snapshot_id=uuid.uuid4(),  # New snapshot ID
            session_id=self.session_id,
            stage_id=self.stage_id,
            state_version=new_version if new_version is not None else self.state_version + 1,
            state_data=merged_state,
            timestamp=datetime.now(UTC),
            ttl_seconds=self.ttl_seconds,
        )
