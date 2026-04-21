"""Backup Service — Data backup and recovery for 等保 2.0 Level 3.

Implements backup and recovery services for data protection:
- Full backup
- Incremental backup
- Backup verification
- Recovery operations

等保 2.0 Level 3 要求:
- 备份恢复: 定期备份机制
- 每日全量备份
- 增量备份
- 恢复时间 < 1 小时
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from src.infrastructure.security.models import (
    BackupRecord,
    BackupStatus,
    BackupType,
)

if TYPE_CHECKING:
    pass


class BackupError(Exception):
    """Base exception for backup errors."""

    pass


class BackupNotFoundError(BackupError):
    """Backup record not found."""

    pass


class BackupVerificationError(BackupError):
    """Backup verification failed."""

    pass


class RecoveryError(BackupError):
    """Recovery operation failed."""

    pass


class BackupService:
    """Backup Service for managing data backups.

    Implements backup operations following 等保 2.0 Level 3 requirements:
    - Full backup (daily)
    - Incremental backup
    - Backup verification with checksum
    - Recovery operations
    """

    def __init__(
        self,
        storage_path: str = "/var/sisys/backups",
    ) -> None:
        """Initialize Backup Service.

        Args:
            storage_path: Base path for backup storage.
        """
        self._storage_path = storage_path
        # In-memory store for backup records (in production, use PostgreSQL)
        self._backup_records: dict[UUID, BackupRecord] = {}

    async def create_full_backup(
        self,
        user_id: UUID,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BackupRecord:
        """Create a full backup.

        Args:
            user_id: UUID of user initiating the backup.
            description: Optional backup description.
            metadata: Optional metadata dict.

        Returns:
            BackupRecord: Created backup record.
        """
        backup_id = uuid4()
        now = datetime.now(UTC)

        # Create backup record
        record = BackupRecord(
            id=backup_id,
            backup_type=BackupType.FULL,
            start_time=now,
            status=BackupStatus.IN_PROGRESS,
            user_id=user_id,
            description=description or "Full backup",
        )

        # In production: perform actual backup to MinIO/S3
        # For now, simulate backup operation
        record.size_bytes = await self._simulate_backup(record.id, BackupType.FULL)

        # Calculate checksum
        record.checksum = hashlib.sha256(f"{record.id}{record.start_time.isoformat()}{record.size_bytes}".encode()).hexdigest()

        # Set location
        record.location = f"{self._storage_path}/full/{record.id}.backup"

        record.end_time = datetime.now(UTC)
        record.status = BackupStatus.COMPLETED

        self._backup_records[record.id] = record

        return record

    async def create_incremental_backup(
        self,
        user_id: UUID,
        base_backup_id: UUID,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BackupRecord:
        """Create an incremental backup.

        Args:
            user_id: UUID of user initiating the backup.
            base_backup_id: UUID of the base full backup.
            description: Optional backup description.
            metadata: Optional metadata dict.

        Returns:
            BackupRecord: Created backup record.
        """
        # Verify base backup exists
        if base_backup_id not in self._backup_records:
            raise BackupNotFoundError(f"Base backup {base_backup_id} not found")

        backup_id = uuid4()
        now = datetime.now(UTC)

        record = BackupRecord(
            id=backup_id,
            backup_type=BackupType.INCREMENTAL,
            start_time=now,
            status=BackupStatus.IN_PROGRESS,
            user_id=user_id,
            description=description or "Incremental backup",
        )

        # In production: perform actual incremental backup
        record.size_bytes = await self._simulate_backup(record.id, BackupType.INCREMENTAL)

        # Calculate checksum
        record.checksum = hashlib.sha256(f"{record.id}{record.start_time.isoformat()}{record.size_bytes}".encode()).hexdigest()

        record.location = f"{self._storage_path}/incremental/{record.id}.backup"
        record.end_time = datetime.now(UTC)
        record.status = BackupStatus.COMPLETED

        self._backup_records[record.id] = record

        return record

    async def verify_backup(self, backup_id: UUID) -> bool:
        """Verify backup integrity.

        Args:
            backup_id: UUID of backup to verify.

        Returns:
            bool: True if backup is valid.

        Raises:
            BackupNotFoundError: If backup not found.
        """
        if backup_id not in self._backup_records:
            raise BackupNotFoundError(f"Backup {backup_id} not found")

        record = self._backup_records[backup_id]

        # In production: verify backup checksum against stored checksum
        # For now, simulate verification
        calculated_checksum = hashlib.sha256(
            f"{record.id}{record.start_time.isoformat()}{record.size_bytes}".encode()
        ).hexdigest()

        return calculated_checksum == record.checksum

    async def get_backup(self, backup_id: UUID) -> BackupRecord | None:
        """Get a backup record by ID.

        Args:
            backup_id: UUID of backup to retrieve.

        Returns:
            BackupRecord | None: Backup record if found.
        """
        return self._backup_records.get(backup_id)

    async def list_backups(
        self,
        backup_type: BackupType | None = None,
        status: BackupStatus | None = None,
        limit: int = 100,
    ) -> list[BackupRecord]:
        """List backup records.

        Args:
            backup_type: Filter by backup type.
            status: Filter by status.
            limit: Maximum number of records to return.

        Returns:
            list[BackupRecord]: List of matching backup records.
        """
        results = list(self._backup_records.values())

        if backup_type is not None:
            results = [r for r in results if r.backup_type == backup_type]

        if status is not None:
            results = [r for r in results if r.status == status]

        # Sort by start_time descending
        results.sort(key=lambda r: r.start_time, reverse=True)

        return results[:limit]

    async def get_latest_full_backup(self) -> BackupRecord | None:
        """Get the latest full backup.

        Returns:
            BackupRecord | None: Latest full backup record.
        """
        full_backups = await self.list_backups(backup_type=BackupType.FULL, limit=1)
        return full_backups[0] if full_backups else None

    async def _simulate_backup(self, backup_id: UUID, backup_type: BackupType) -> int:
        """Simulate backup operation.

        In production, this would perform actual backup to MinIO/S3.

        Args:
            backup_id: UUID of the backup.
            backup_type: Type of backup.

        Returns:
            int: Size of backed up data in bytes.
        """
        # Simulate backup size based on type
        if backup_type == BackupType.FULL:
            return 1024 * 1024 * 100  # 100 MB
        else:
            return 1024 * 1024 * 10  # 10 MB


class RecoveryService:
    """Recovery Service for restoring data from backups.

    Implements recovery operations following 等保 2.0 Level 3 requirements:
    - Full recovery
    - Point-in-time recovery
    - Recovery time < 1 hour (MVP target)
    """

    def __init__(
        self,
        backup_service: BackupService | None = None,
    ) -> None:
        """Initialize Recovery Service.

        Args:
            backup_service: Backup service instance.
        """
        self._backup_service = backup_service or BackupService()

    async def recover_from_backup(
        self,
        backup_id: UUID,
        target_path: str = "/var/sisys/restored",
    ) -> dict[str, Any]:
        """Recover data from a backup.

        Args:
            backup_id: UUID of backup to recover from.
            target_path: Target path for restored data.

        Returns:
            dict: Recovery result with metadata.

        Raises:
            BackupNotFoundError: If backup not found.
            RecoveryError: If recovery fails.
        """
        # Get backup record
        backup = await self._backup_service.get_backup(backup_id)
        if not backup:
            raise BackupNotFoundError(f"Backup {backup_id} not found")

        if not backup.is_completed():
            raise RecoveryError(f"Backup {backup_id} is not completed")

        # In production: perform actual recovery from MinIO/S3
        # For now, simulate recovery
        recovery_result = {
            "backup_id": str(backup_id),
            "backup_type": backup.backup_type.value,
            "target_path": target_path,
            "size_bytes": backup.size_bytes,
            "duration_seconds": await self._simulate_recovery(backup),
            "status": "success",
        }

        return recovery_result

    async def recover_incremental_chain(
        self,
        base_backup_id: UUID,
        target_path: str = "/var/sisys/restored",
    ) -> dict[str, Any]:
        """Recover from an incremental backup chain.

        Args:
            base_backup_id: UUID of base full backup.
            target_path: Target path for restored data.

        Returns:
            dict: Recovery result with metadata.

        Raises:
            BackupNotFoundError: If backup not found.
            RecoveryError: If recovery fails.
        """
        base_backup = await self._backup_service.get_backup(base_backup_id)
        if not base_backup:
            raise BackupNotFoundError(f"Base backup {base_backup_id} not found")

        # Find all incremental backups based on this full backup
        all_backups = await self._backup_service.list_backups(limit=1000)
        incremental_backups = [b for b in all_backups if b.backup_type == BackupType.INCREMENTAL]

        # Sort by start_time
        incremental_backups.sort(key=lambda b: b.start_time)

        total_size = base_backup.size_bytes
        total_duration = 0.0

        # Simulate recovery of base backup
        total_duration += await self._simulate_recovery(base_backup)

        # Simulate recovery of incremental backups
        for inc_backup in incremental_backups:
            total_size += inc_backup.size_bytes
            total_duration += await self._simulate_recovery(inc_backup)

        return {
            "base_backup_id": str(base_backup_id),
            "incremental_count": len(incremental_backups),
            "target_path": target_path,
            "total_size_bytes": total_size,
            "total_duration_seconds": total_duration,
            "status": "success",
        }

    async def estimate_recovery_time(self, backup_id: UUID) -> float:
        """Estimate recovery time for a backup.

        Args:
            backup_id: UUID of backup.

        Returns:
            float: Estimated recovery time in seconds.
        """
        backup = await self._backup_service.get_backup(backup_id)
        if not backup:
            return 0.0

        # Estimate: ~10MB/s recovery speed
        estimated_speed_mbps = 10.0
        size_mb = backup.size_bytes / (1024 * 1024)
        return size_mb / estimated_speed_mbps

    async def _simulate_recovery(self, backup: BackupRecord) -> float:
        """Simulate recovery operation.

        In production, this would perform actual recovery from MinIO/S3.

        Args:
            backup: Backup record to recover.

        Returns:
            float: Recovery duration in seconds.
        """
        # Simulate: ~10MB/s recovery speed
        size_mb = backup.size_bytes / (1024 * 1024)
        return size_mb / 10.0


# Global instances
_backup_service: BackupService | None = None
_recovery_service: RecoveryService | None = None


def get_backup_service() -> BackupService:
    """Get global Backup Service instance.

    Returns:
        BackupService: Global backup service instance.
    """
    global _backup_service
    if _backup_service is None:
        _backup_service = BackupService()
    return _backup_service


def get_recovery_service() -> RecoveryService:
    """Get global Recovery Service instance.

    Returns:
        RecoveryService: Global recovery service instance.
    """
    global _recovery_service
    if _recovery_service is None:
        _recovery_service = RecoveryService()
    return _recovery_service
