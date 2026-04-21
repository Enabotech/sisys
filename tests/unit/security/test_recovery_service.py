"""Tests for Recovery Service.

Tests backup recovery operations for 等保 2.0 Level 3.
Reference: Story 1.12 等保 2.0 三级基础要求
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.infrastructure.security.models import BackupRecord, BackupStatus, BackupType
from src.infrastructure.security.recovery_service import (
    RecoveryError,
    RecoveryService,
)


class TestRecoveryService:
    """Tests for Recovery Service."""

    @pytest.fixture
    def mock_backup_service(self):
        """Create mock backup service."""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def recovery_service(self, mock_backup_service):
        """Create recovery service with mock backup service."""
        return RecoveryService(backup_service=mock_backup_service)

    @pytest.fixture
    def sample_backup(self):
        """Create sample backup record."""
        return BackupRecord(
            id=uuid4(),
            backup_type=BackupType.FULL,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            status=BackupStatus.COMPLETED,
            size_bytes=1024 * 1024 * 100,  # 100 MB
            checksum="abc123def456",  # pragma: allowlist secret
            location="/var/sisys/backups/test",
        )

    @pytest.mark.asyncio
    async def test_recover_from_backup_success(self, recovery_service, mock_backup_service, sample_backup):
        """Should recover from backup successfully."""
        mock_backup_service.get_backup.return_value = sample_backup

        result = await recovery_service.recover_from_backup(
            backup_id=str(sample_backup.id),
            target_path="/tmp/restored",
        )

        assert result["status"] == "success"
        assert result["backup_id"] == str(sample_backup.id)
        assert result["target_path"] == "/tmp/restored"
        assert result["size_bytes"] == sample_backup.size_bytes
        assert "duration_seconds" in result

    @pytest.mark.asyncio
    async def test_recover_from_backup_not_found(self, recovery_service, mock_backup_service):
        """Should raise RecoveryError when backup not found."""
        mock_backup_service.get_backup.return_value = None

        with pytest.raises(RecoveryError, match="not found"):
            await recovery_service.recover_from_backup(
                backup_id=str(uuid4()),
                target_path="/tmp/restored",
            )

    @pytest.mark.asyncio
    async def test_recover_from_backup_invalid_uuid(self, recovery_service):
        """Should raise RecoveryError for invalid UUID."""
        with pytest.raises(RecoveryError, match="Invalid backup ID format"):
            await recovery_service.recover_from_backup(
                backup_id="invalid-uuid",
                target_path="/tmp/restored",
            )

    @pytest.mark.asyncio
    async def test_recover_from_backup_not_completed(self, recovery_service, mock_backup_service, sample_backup):
        """Should raise RecoveryError when backup not completed."""
        sample_backup.status = BackupStatus.IN_PROGRESS
        mock_backup_service.get_backup.return_value = sample_backup

        with pytest.raises(RecoveryError, match="not completed"):
            await recovery_service.recover_from_backup(
                backup_id=str(sample_backup.id),
                target_path="/tmp/restored",
            )

    @pytest.mark.asyncio
    async def test_recover_incremental_chain_success(self, recovery_service, mock_backup_service, sample_backup):
        """Should recover incremental chain successfully."""
        mock_backup_service.get_backup.return_value = sample_backup

        incremental1 = BackupRecord(
            id=uuid4(),
            backup_type=BackupType.INCREMENTAL,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            status=BackupStatus.COMPLETED,
            size_bytes=1024 * 100,  # 100 KB
            checksum="inc1",
            location="/var/sisys/backups/inc1",
        )
        incremental2 = BackupRecord(
            id=uuid4(),
            backup_type=BackupType.INCREMENTAL,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            status=BackupStatus.COMPLETED,
            size_bytes=1024 * 50,  # 50 KB
            checksum="inc2",
            location="/var/sisys/backups/inc2",
        )

        mock_backup_service.list_backups.return_value = [incremental1, incremental2]

        result = await recovery_service.recover_incremental_chain(
            base_backup_id=str(sample_backup.id),
            target_path="/tmp/point_in_time",
        )

        assert result["status"] == "success"
        assert result["base_backup_id"] == str(sample_backup.id)
        assert result["incremental_count"] == 2
        assert result["target_path"] == "/tmp/point_in_time"

    @pytest.mark.asyncio
    async def test_recover_incremental_chain_base_not_found(self, recovery_service, mock_backup_service):
        """Should raise RecoveryError when base backup not found."""
        mock_backup_service.get_backup.return_value = None

        with pytest.raises(RecoveryError, match="Base backup .* not found"):
            await recovery_service.recover_incremental_chain(
                base_backup_id=str(uuid4()),
                target_path="/tmp/restored",
            )

    @pytest.mark.asyncio
    async def test_recover_incremental_chain_invalid_uuid(self, recovery_service):
        """Should raise RecoveryError for invalid base backup UUID."""
        with pytest.raises(RecoveryError, match="Invalid backup ID format"):
            await recovery_service.recover_incremental_chain(
                base_backup_id="invalid-uuid",
                target_path="/tmp/restored",
            )

    @pytest.mark.asyncio
    async def test_estimate_recovery_time(self, recovery_service, mock_backup_service, sample_backup):
        """Should estimate recovery time correctly."""
        mock_backup_service.get_backup.return_value = sample_backup

        estimated_time = await recovery_service.estimate_recovery_time(str(sample_backup.id))

        # 100 MB at 10 MB/s = 10 seconds
        assert estimated_time == pytest.approx(10.0, rel=0.1)

    @pytest.mark.asyncio
    async def test_estimate_recovery_time_invalid_uuid(self, recovery_service):
        """Should return 0.0 for invalid UUID."""
        estimated_time = await recovery_service.estimate_recovery_time("invalid-uuid")
        assert estimated_time == 0.0

    @pytest.mark.asyncio
    async def test_estimate_recovery_time_backup_not_found(self, recovery_service, mock_backup_service):
        """Should return 0.0 when backup not found."""
        mock_backup_service.get_backup.return_value = None

        estimated_time = await recovery_service.estimate_recovery_time(str(uuid4()))
        assert estimated_time == 0.0

    def test_recovery_service_default_backup_service(self):
        """Should create default backup service when not provided."""
        service = RecoveryService()
        assert service._backup_service is not None

    def test_recovery_error_message(self):
        """RecoveryError should have correct message."""
        error = RecoveryError("Test error message")
        assert str(error) == "Test error message"


class TestRecoveryServiceSimulateRecovery:
    """Tests for RecoveryService._simulate_recovery method."""

    @pytest.mark.asyncio
    async def test_simulate_recovery_duration(self):
        """Should calculate recovery duration based on size."""
        service = RecoveryService()

        backup = BackupRecord(
            id=uuid4(),
            backup_type=BackupType.FULL,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            status=BackupStatus.COMPLETED,
            size_bytes=10 * 1024 * 1024,  # 10 MB
        )

        duration = await service._simulate_recovery(backup)

        # 10 MB at 10 MB/s = 1 second
        assert duration == pytest.approx(1.0, rel=0.1)
