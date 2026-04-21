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
