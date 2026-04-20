"""Test AuditServiceImpl - Red Phase (Test First).

TDD Cycle: Red -> Green -> Refactor
Reference: Story 1.10 Task 1 - Audit Log Core Service
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest


class TestAuditServiceLog:
    """Test AuditService.log() method."""

    @pytest.mark.asyncio
    async def test_log_creates_audit_entry(self):
        """log() creates audit log and outbox entry."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        mock_session = mock.AsyncMock()
        mock_session.flush = mock.AsyncMock()

        service = AuditServiceImpl(session=mock_session)

        log_id = await service.log(
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={"status": "draft"},
            new_value={"status": "published"},
        )

        assert isinstance(log_id, uuid.UUID)

        # Verify add was called for both outbox and audit_log
        assert mock_session.add.called
        assert mock_session.flush.called

    @pytest.mark.asyncio
    async def test_log_with_correction_level(self):
        """log() supports correction_level for FR-SC-04."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        mock_session = mock.AsyncMock()
        mock_session.flush = mock.AsyncMock()

        service = AuditServiceImpl(session=mock_session)

        log_id = await service.log(
            actor="user-123",
            action_type="correction:apply",
            target_resource="document/doc-456",
            correction_level=2,
        )

        assert isinstance(log_id, uuid.UUID)


class TestAuditServiceQuery:
    """Test AuditService.query() method."""

    @pytest.mark.asyncio
    async def test_query_returns_paginated_results(self):
        """query() returns paginated audit logs."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        mock_session = mock.AsyncMock()

        # Mock the query results
        mock_result = mock.Mock()
        mock_result.scalar.return_value = 1
        mock_result.scalars.return_value.all.return_value = []

        mock_session.execute.return_value = mock_result

        service = AuditServiceImpl(session=mock_session)

        result = await service.query(page=1, page_size=10)

        assert "items" in result
        assert "total" in result
        assert "page" in result
        assert "page_size" in result
        assert "total_pages" in result

    @pytest.mark.asyncio
    async def test_query_with_time_range(self):
        """query() filters by start_time and end_time."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        mock_session = mock.AsyncMock()

        mock_result = mock.Mock()
        mock_result.scalar.return_value = 0
        mock_result.scalars.return_value.all.return_value = []

        mock_session.execute.return_value = mock_result

        service = AuditServiceImpl(session=mock_session)

        start_time = datetime.now(UTC) - timedelta(days=7)
        end_time = datetime.now(UTC)

        result = await service.query(start_time=start_time, end_time=end_time)

        assert "items" in result
        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_query_with_actor_filter(self):
        """query() filters by actor."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        mock_session = mock.AsyncMock()

        mock_result = mock.Mock()
        mock_result.scalar.return_value = 0
        mock_result.scalars.return_value.all.return_value = []

        mock_session.execute.return_value = mock_result

        service = AuditServiceImpl(session=mock_session)

        result = await service.query(actor="user-123")

        assert "items" in result

    @pytest.mark.asyncio
    async def test_query_with_correction_level(self):
        """query() filters by correction_level (FR-SC-04)."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        mock_session = mock.AsyncMock()

        mock_result = mock.Mock()
        mock_result.scalar.return_value = 0
        mock_result.scalars.return_value.all.return_value = []

        mock_session.execute.return_value = mock_result

        service = AuditServiceImpl(session=mock_session)

        result = await service.query(correction_level=1)

        assert "items" in result


class TestAuditServiceGetById:
    """Test AuditService.get_by_id() method."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_audit_entry(self):
        """get_by_id() returns audit log entry by log_id."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        log_id = uuid.uuid4()

        mock_model = mock.Mock()
        mock_model.to_dict.return_value = {
            "log_id": str(log_id),
            "actor": "user-123",
            "action_type": "document:upload",
        }

        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model

        mock_session = mock.AsyncMock()
        mock_session.execute.return_value = mock_result

        service = AuditServiceImpl(session=mock_session)

        result = await service.get_by_id(log_id)

        assert result is not None
        assert result["actor"] == "user-123"

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self):
        """get_by_id() returns None when entry not found."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = mock.AsyncMock()
        mock_session.execute.return_value = mock_result

        service = AuditServiceImpl(session=mock_session)

        result = await service.get_by_id(uuid.uuid4())

        assert result is None


class TestAuditServiceGetStats:
    """Test AuditService.get_stats() method."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_statistics(self):
        """get_stats() returns audit statistics."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        mock_result = mock.Mock()
        mock_result.scalar.return_value = 100

        mock_action_type_result = mock.Mock()
        mock_action_type_result.all.return_value = [("auth:login", 50), ("doc:upload", 50)]

        mock_actor_result = mock.Mock()
        mock_actor_result.all.return_value = [("user-123", 100)]

        mock_session = mock.AsyncMock()
        # First call for total, then for action_type, then for actor
        mock_session.execute.side_effect = [mock_result, mock_action_type_result, mock_actor_result]

        service = AuditServiceImpl(session=mock_session)

        result = await service.get_stats()

        assert "total_entries" in result
        assert "by_action_type" in result
        assert "by_actor" in result
        assert "time_range" in result


class TestAuditServiceVerifyIntegrity:
    """Test AuditService.verify_integrity() method."""

    @pytest.mark.asyncio
    async def test_verify_integrity_returns_true_for_valid(self):
        """verify_integrity() returns True when checksum valid."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        mock_model = mock.Mock()
        mock_model.verify_checksum.return_value = True

        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model

        mock_session = mock.AsyncMock()
        mock_session.execute.return_value = mock_result

        service = AuditServiceImpl(session=mock_session)

        result = await service.verify_integrity(uuid.uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_integrity_returns_false_for_tampered(self):
        """verify_integrity() returns False when checksum invalid."""
        from src.infrastructure.audit.audit_service import AuditServiceImpl

        mock_model = mock.Mock()
        mock_model.verify_checksum.return_value = False

        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model

        mock_session = mock.AsyncMock()
        mock_session.execute.return_value = mock_result

        service = AuditServiceImpl(session=mock_session)

        result = await service.verify_integrity(uuid.uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_integrity_raises_when_not_found(self):
        """verify_integrity() raises AuditNotFoundError when entry not found."""
        from src.infrastructure.audit.audit_service import AuditNotFoundError, AuditServiceImpl

        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = mock.AsyncMock()
        mock_session.execute.return_value = mock_result

        service = AuditServiceImpl(session=mock_session)

        with pytest.raises(AuditNotFoundError):
            await service.verify_integrity(uuid.uuid4())
