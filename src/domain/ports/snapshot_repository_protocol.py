"""SnapshotRepositoryProtocol — domain port for checkpoint snapshot storage.

This protocol defines the interface for snapshot repository adapters.
Infrastructure layer implements this protocol for persistent storage.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot


@runtime_checkable
class SnapshotRepositoryProtocol(Protocol):
    """Protocol for snapshot storage (implemented by infrastructure).

    Defines the interface for saving, loading, and deleting checkpoint
    snapshots used for session state recovery.
    """

    async def save(self, snapshot: CheckpointSnapshot) -> None:
        """Save a snapshot to storage.

        Args:
            snapshot: Checkpoint snapshot to persist
        """
        ...

    async def load(self, session_id: str) -> CheckpointSnapshot | None:
        """Load the latest snapshot for a session.

        Args:
            session_id: Session identifier

        Returns:
            Latest snapshot or None if no snapshot exists
        """
        ...

    async def delete(self, session_id: str) -> None:
        """Delete snapshots for a session.

        Args:
            session_id: Session identifier
        """
        ...
