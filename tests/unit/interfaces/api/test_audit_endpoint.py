"""Tests for Audit API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from src.domain.ports.audit_repository import AuditSearchCriteria, AuditSearchResult
from src.interfaces.api.audit import (
    ArchiveRequest,
    ArchiveResponse,
    ArchiveStatusResponse,
    AuditLogListResponse,
    AuditLogResponse,
    IntegrityVerifyDetail,
    IntegrityVerifyRequest,
    IntegrityVerifyResponse,
    create_audit_router,
)


class FakeAuditRepository:
    """Fake implementation for testing."""

    def __init__(self) -> None:
        self._logs: dict[UUID, dict[str, Any]] = {}
        self._archive_status: dict[UUID, dict[str, Any]] = {}

    async def save(self, audit_data: dict[str, Any]) -> UUID:
        log_id = UUID(audit_data["log_id"])
        self._logs[log_id] = audit_data
        return log_id

    async def get_by_id(self, log_id: UUID) -> dict[str, Any] | None:
        return self._logs.get(log_id)

    async def search(self, criteria: AuditSearchCriteria) -> AuditSearchResult:
        items = list(self._logs.values())
        # Filter by criteria
        filtered = []
        for item in items:
            timestamp = datetime.fromisoformat(item["timestamp"])
            if criteria.start_time and timestamp < criteria.start_time:
                continue
            if criteria.end_time and timestamp > criteria.end_time:
                continue
            if criteria.actor and item.get("actor") != criteria.actor:
                continue
            if criteria.action_type and criteria.action_type not in item.get("action_type", ""):
                continue
            filtered.append(item)

        # Apply pagination
        start = criteria.offset
        end = start + criteria.limit
        paginated = filtered[start:end]

        return AuditSearchResult(
            items=tuple(paginated),
            total=len(filtered),
            offset=criteria.offset,
            limit=criteria.limit,
        )

    async def update_archive_status(
        self,
        log_id: UUID,
        archived: bool,
        archived_at: datetime | None = None,
    ) -> bool:
        if log_id not in self._logs:
            return False
        self._logs[log_id]["archived"] = archived
        self._logs[log_id]["archived_at"] = archived_at.isoformat() if archived_at else None
        return True

    async def get_archive_status(self, log_id: UUID) -> dict[str, Any] | None:
        if log_id not in self._logs:
            return None
        log = self._logs[log_id]
        return {
            "log_id": str(log_id),
            "archived": log.get("archived", False),
            "archived_at": log.get("archived_at"),
            "retention_days": 2555,
        }


class TestCreateAuditRouter:
    """Test create_audit_router factory function."""

    def test_create_audit_router_returns_api_router(self) -> None:
        """Test create_audit_router returns an APIRouter."""
        router = create_audit_router(
            get_audit_service=MagicMock,
            get_audit_repository=MagicMock,
        )
        assert router is not None
        assert router.prefix == "/audit"
        assert len(router.routes) == 5


class TestAuditLogResponseModel:
    """Test AuditLogResponse model."""

    def test_audit_log_response_all_fields(self) -> None:
        """Test AuditLogResponse with all fields."""
        response = AuditLogResponse(
            log_id="test-123",
            timestamp=datetime.now(),
            actor="user-456",
            action_type="authentication:login",
            target_resource="/api/v1/auth",
            old_value={"key": "old"},
            new_value={"key": "new"},
            correction_level=1,
            checksum="abc123",
            archived=True,
            archived_at=datetime.now(),
            correlation_id="corr-789",
        )

        assert response.log_id == "test-123"
        assert response.actor == "user-456"
        assert response.archived is True

    def test_audit_log_response_minimal(self) -> None:
        """Test AuditLogResponse with minimal fields."""
        response = AuditLogResponse(log_id="test-123")

        assert response.log_id == "test-123"
        assert response.timestamp is None
        assert response.archived is False

    def test_audit_log_response_with_isoformat_timestamp(self) -> None:
        """Test AuditLogResponse parses isoformat timestamp correctly."""
        ts = datetime.now()
        response = AuditLogResponse(
            log_id="test-123",
            timestamp=ts,
            actor="user-456",
        )
        assert response.timestamp == ts


class TestIntegrityVerifyDetail:
    """Test IntegrityVerifyDetail model."""

    def test_integrity_verify_detail_all_fields(self) -> None:
        """Test IntegrityVerifyDetail with all fields."""
        detail = IntegrityVerifyDetail(
            log_id="test-123",
            status="passed",
            message="Verification successful",
        )

        assert detail.log_id == "test-123"
        assert detail.status == "passed"
        assert detail.message == "Verification successful"

    def test_integrity_verify_detail_minimal(self) -> None:
        """Test IntegrityVerifyDetail with minimal fields."""
        detail = IntegrityVerifyDetail(
            log_id="test-123",
            status="failed",
        )

        assert detail.log_id == "test-123"
        assert detail.status == "failed"
        assert detail.message is None


class TestIntegrityVerifyResponse:
    """Test IntegrityVerifyResponse model."""

    def test_integrity_verify_response(self) -> None:
        """Test IntegrityVerifyResponse with details."""
        response = IntegrityVerifyResponse(
            total=3,
            passed=2,
            failed=1,
            details=[
                IntegrityVerifyDetail(log_id="1", status="passed"),
                IntegrityVerifyDetail(log_id="2", status="passed"),
                IntegrityVerifyDetail(log_id="3", status="failed", message="Checksum mismatch"),
            ],
        )

        assert response.total == 3
        assert response.passed == 2
        assert response.failed == 1


class TestArchiveRequest:
    """Test ArchiveRequest model."""

    def test_archive_request_default(self) -> None:
        """Test ArchiveRequest with default values."""
        request = ArchiveRequest()
        assert request.older_than_days == 30

    def test_archive_request_custom_days(self) -> None:
        """Test ArchiveRequest with custom days."""
        request = ArchiveRequest(older_than_days=60)
        assert request.older_than_days == 60

    def test_archive_request_invalid_days_zero(self) -> None:
        """Test ArchiveRequest rejects zero days."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ArchiveRequest(older_than_days=0)

    def test_archive_request_invalid_days_negative(self) -> None:
        """Test ArchiveRequest rejects negative days."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ArchiveRequest(older_than_days=-1)


class TestArchiveResponse:
    """Test ArchiveResponse model."""

    def test_archive_response(self) -> None:
        """Test ArchiveResponse model."""
        response = ArchiveResponse(archived_count=42)
        assert response.archived_count == 42


class TestArchiveStatusResponse:
    """Test ArchiveStatusResponse model."""

    def test_archive_status_response_archived(self) -> None:
        """Test ArchiveStatusResponse when archived."""
        response = ArchiveStatusResponse(
            log_id="test-123",
            archived=True,
            archived_at=datetime.now(),
            retention_days=2555,
        )

        assert response.log_id == "test-123"
        assert response.archived is True
        assert response.retention_days == 2555

    def test_archive_status_response_not_archived(self) -> None:
        """Test ArchiveStatusResponse when not archived."""
        response = ArchiveStatusResponse(
            log_id="test-123",
            archived=False,
            retention_days=2555,
        )

        assert response.archived is False
        assert response.archived_at is None


class TestAuditLogListResponse:
    """Test AuditLogListResponse model."""

    def test_audit_log_list_response(self) -> None:
        """Test AuditLogListResponse with items."""
        response = AuditLogListResponse(
            items=[
                AuditLogResponse(log_id="1", actor="user-1"),
                AuditLogResponse(log_id="2", actor="user-2"),
            ],
            total=10,
            offset=0,
            limit=20,
        )

        assert len(response.items) == 2
        assert response.total == 10
        assert response.offset == 0
        assert response.limit == 20


class TestIntegrityVerifyRequest:
    """Test IntegrityVerifyRequest model."""

    def test_integrity_verify_request_with_log_ids(self) -> None:
        """Test IntegrityVerifyRequest with log_ids."""
        request = IntegrityVerifyRequest(log_ids=["id-1", "id-2"])
        assert request.log_ids == ["id-1", "id-2"]

    def test_integrity_verify_request_empty(self) -> None:
        """Test IntegrityVerifyRequest with empty log_ids."""
        request = IntegrityVerifyRequest(log_ids=None)
        assert request.log_ids is None
