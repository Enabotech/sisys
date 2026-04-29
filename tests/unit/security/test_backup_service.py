"""Tests for Backup Service.

Tests backup operations for 等保 2.0 Level 3.
Reference: Story 1.12 等保 2.0 三级基础要求
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.infrastructure.security.backup_service import (
    BackupNotFoundError,
    BackupService,
    BackupStatus,
    BackupType,
)


class TestBackupService:
    """Tests for Backup Service."""

    @pytest.fixture
    def backup_service(self):
        """Create backup service instance."""
        return BackupService()

    @pytest.mark.asyncio
    async def test_create_full_backup(self, backup_service):
        """Should create full backup successfully."""
        user_id = uuid4()

        record = await backup_service.create_full_backup(
            user_id=user_id,
            description="Test full backup",
        )

        assert record.backup_type == BackupType.FULL
        assert record.status == BackupStatus.COMPLETED
        assert record.size_bytes > 0
        assert len(record.checksum) > 0

    @pytest.mark.asyncio
    async def test_create_incremental_backup(self, backup_service):
        """Should create incremental backup successfully."""
        user_id = uuid4()

        # Create base full backup first
        full_backup = await backup_service.create_full_backup(
            user_id=user_id,
            description="Base full backup",
        )

        # Create incremental backup
        record = await backup_service.create_incremental_backup(
            user_id=user_id,
            base_backup_id=full_backup.id,
            description="Test incremental backup",
        )

        assert record.backup_type == BackupType.INCREMENTAL
        assert record.status == BackupStatus.COMPLETED
        assert record.size_bytes > 0

    @pytest.mark.asyncio
    async def test_create_incremental_without_base_fails(self, backup_service):
        """Should raise error when base backup not found."""
        user_id = uuid4()

        with pytest.raises(BackupNotFoundError, match="Base backup .* not found"):
            await backup_service.create_incremental_backup(
                user_id=user_id,
                base_backup_id=uuid4(),  # Non-existent base
                description="Test incremental backup",
            )

    @pytest.mark.asyncio
    async def test_verify_backup_success(self, backup_service):
        """Should verify backup successfully."""
        user_id = uuid4()

        record = await backup_service.create_full_backup(
            user_id=user_id,
            description="Test full backup",
        )

        result = await backup_service.verify_backup(record.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_backup_not_found(self, backup_service):
        """Should raise error when backup not found for verify."""
        with pytest.raises(BackupNotFoundError, match="Backup .* not found"):
            await backup_service.verify_backup(uuid4())

    @pytest.mark.asyncio
    async def test_get_backup_success(self, backup_service):
        """Should get backup successfully."""
        user_id = uuid4()

        created = await backup_service.create_full_backup(
            user_id=user_id,
            description="Test full backup",
        )

        record = await backup_service.get_backup(created.id)
        assert record is not None
        assert record.id == created.id

    @pytest.mark.asyncio
    async def test_get_backup_not_found(self, backup_service):
        """Should return None when backup not found."""
        record = await backup_service.get_backup(uuid4())
        assert record is None

    @pytest.mark.asyncio
    async def test_list_backups_empty(self, backup_service):
        """Should return empty list when no backups."""
        # Create a fresh service with no records
        service = BackupService()
        service._backup_records.clear()

        records = await service.list_backups(limit=10)
        assert len(records) == 0

    @pytest.mark.asyncio
    async def test_list_backups_with_filter(self, backup_service):
        """Should filter backups correctly."""
        user_id = uuid4()

        # Create a full backup
        await backup_service.create_full_backup(
            user_id=user_id,
            description="Test full backup",
        )

        records = await backup_service.list_backups(
            backup_type=BackupType.FULL,
            status=BackupStatus.COMPLETED,
            limit=10,
        )
        assert all(r.backup_type == BackupType.FULL for r in records)

    @pytest.mark.asyncio
    async def test_get_latest_full_backup(self, backup_service):
        """Should get latest full backup."""
        user_id = uuid4()

        await backup_service.create_full_backup(
            user_id=user_id,
            description="Test full backup",
        )

        record = await backup_service.get_latest_full_backup()
        assert record is not None
        assert record.backup_type == BackupType.FULL

    @pytest.mark.asyncio
    async def test_get_latest_full_backup_none_exists(self):
        """Should return None when no full backup exists."""
        service = BackupService()
        service._backup_records.clear()  # Clear all records

        record = await service.get_latest_full_backup()
        assert record is None


class TestRecoveryService:
    """Tests for Recovery Service."""

    @pytest.fixture
    def recovery_service(self):
        """Create recovery service instance."""
        from src.infrastructure.security.backup_service import RecoveryService

        return RecoveryService()

    @pytest.fixture
    def backup_and_recovery_services(self):
        """Create backup and recovery services."""
        from src.infrastructure.security.backup_service import BackupService, RecoveryService

        backup = BackupService()
        recovery = RecoveryService(backup_service=backup)
        return backup, recovery

    @pytest.mark.asyncio
    async def test_recover_from_backup_success(self, backup_and_recovery_services):
        """Should recover from backup successfully."""
        backup_service, recovery_service = backup_and_recovery_services
        user_id = uuid4()

        backup = await backup_service.create_full_backup(user_id=user_id, description="Test backup")

        result = await recovery_service.recover_from_backup(backup.id)

        assert result["status"] == "success"
        assert result["backup_id"] == str(backup.id)
        assert result["size_bytes"] == backup.size_bytes

    @pytest.mark.asyncio
    async def test_recover_from_backup_not_found(self, recovery_service):
        """Should raise error when backup not found."""
        from src.infrastructure.security.backup_service import BackupNotFoundError

        with pytest.raises(BackupNotFoundError):
            await recovery_service.recover_from_backup(uuid4())

    @pytest.mark.asyncio
    async def test_recover_from_backup_incomplete_raises(self, backup_and_recovery_services):
        """Should raise error when backup is not completed."""
        from src.infrastructure.security.backup_service import RecoveryError

        backup_service, recovery_service = backup_and_recovery_services
        user_id = uuid4()

        # Create a backup record manually that's in progress
        record = await backup_service.create_full_backup(user_id=user_id)
        # Set status to IN_PROGRESS (not COMPLETED)
        backup_service._backup_records[record.id].status = BackupStatus.IN_PROGRESS

        with pytest.raises(RecoveryError):
            await recovery_service.recover_from_backup(record.id)

    @pytest.mark.asyncio
    async def test_recover_incremental_chain(self, backup_and_recovery_services):
        """Should recover incremental backup chain."""
        backup_service, recovery_service = backup_and_recovery_services
        user_id = uuid4()

        full_backup = await backup_service.create_full_backup(user_id=user_id, description="Full backup")
        await backup_service.create_incremental_backup(
            user_id=user_id,
            base_backup_id=full_backup.id,
            description="Incremental 1",
        )
        await backup_service.create_incremental_backup(
            user_id=user_id,
            base_backup_id=full_backup.id,
            description="Incremental 2",
        )

        result = await recovery_service.recover_incremental_chain(full_backup.id)

        assert result["status"] == "success"
        assert result["base_backup_id"] == str(full_backup.id)
        assert result["incremental_count"] == 2

    @pytest.mark.asyncio
    async def test_recover_incremental_chain_base_not_found(self, recovery_service):
        """Should raise error when base backup not found."""
        from src.infrastructure.security.backup_service import BackupNotFoundError

        with pytest.raises(BackupNotFoundError):
            await recovery_service.recover_incremental_chain(uuid4())

    @pytest.mark.asyncio
    async def test_estimate_recovery_time(self, backup_and_recovery_services):
        """Should estimate recovery time correctly."""
        backup_service, recovery_service = backup_and_recovery_services
        user_id = uuid4()

        backup = await backup_service.create_full_backup(user_id=user_id)

        estimated = await recovery_service.estimate_recovery_time(backup.id)

        # 100MB at 10MB/s = 10 seconds
        assert estimated == 10.0

    @pytest.mark.asyncio
    async def test_estimate_recovery_time_not_found(self, recovery_service):
        """Should return 0 when backup not found."""
        estimated = await recovery_service.estimate_recovery_time(uuid4())

        assert estimated == 0.0

    @pytest.mark.asyncio
    async def test_recovery_includes_target_path(self, backup_and_recovery_services):
        """Should include target path in recovery result."""
        backup_service, recovery_service = backup_and_recovery_services
        user_id = uuid4()

        backup = await backup_service.create_full_backup(user_id=user_id)

        result = await recovery_service.recover_from_backup(
            backup.id,
            target_path="/custom/path",
        )

        assert result["target_path"] == "/custom/path"
