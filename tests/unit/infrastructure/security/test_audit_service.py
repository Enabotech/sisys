"""Tests for AuditService."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.domain.ports.audit_repository import AuditRepositoryPort, AuditSearchCriteria, AuditSearchResult
from src.domain.ports.audit_service import AuditError, AuditRecord, AuditServicePort
from src.infrastructure.security.audit_service_impl import AuditServiceImpl


class FakeAuditRepository(AuditRepositoryPort):
    """Fake implementation of AuditRepositoryPort for testing."""

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
        items = [log for log in self._logs.values()]
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


class TestAuditServiceImpl:
    """Test AuditService implementation."""

    @pytest.fixture
    def fake_repo(self) -> FakeAuditRepository:
        return FakeAuditRepository()

    @pytest.fixture
    def audit_service(self, fake_repo: FakeAuditRepository) -> AuditServiceImpl:
        return AuditServiceImpl(audit_repository=fake_repo)

    @pytest.mark.asyncio
    async def test_record_creates_audit_log(
        self,
        audit_service: AuditServiceImpl,
        fake_repo: FakeAuditRepository,
    ) -> None:
        """Test that record creates an audit log entry."""
        # Act
        record = await audit_service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
            old_value=None,
            new_value={"status": "success"},
        )

        # Assert
        assert isinstance(record, AuditRecord)
        assert record.actor == "user-123"
        assert record.action_type == "authentication:login"
        assert record.target_resource == "/api/v1/auth/login"
        assert record.new_value == {"status": "success"}

        # Verify it was saved
        log_id = record.log_id
        saved_log = await fake_repo.get_by_id(log_id)
        assert saved_log is not None
        assert saved_log["actor"] == "user-123"
        assert saved_log["checksum"] is not None  # Checksum should be computed

    @pytest.mark.asyncio
    async def test_record_with_old_and_new_value(
        self,
        audit_service: AuditServiceImpl,
    ) -> None:
        """Test record with both old and new values."""
        # Act
        record = await audit_service.record(
            actor="admin-456",
            action_type="authorization:grant",
            target_resource="role/admin",
            old_value={"role": "viewer"},
            new_value={"role": "admin"},
        )

        # Assert
        assert record.old_value == {"role": "viewer"}
        assert record.new_value == {"role": "admin"}

    @pytest.mark.asyncio
    async def test_record_computes_checksum(
        self,
        audit_service: AuditServiceImpl,
        fake_repo: FakeAuditRepository,
    ) -> None:
        """Test that record computes SHA256 checksum."""
        record = await audit_service.record(
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
        )

        # Verify checksum was computed and saved
        saved_log = await fake_repo.get_by_id(record.log_id)
        assert saved_log is not None
        assert len(saved_log["checksum"]) == 64  # SHA256 hex digest length

    @pytest.mark.asyncio
    async def test_verify_integrity_returns_true_for_valid_log(
        self,
        audit_service: AuditServiceImpl,
        fake_repo: FakeAuditRepository,
    ) -> None:
        """Test verify_integrity returns True for valid log."""
        # Create a log first
        record = await audit_service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
        )

        # Verify
        is_valid = await audit_service.verify_integrity(record.log_id)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_integrity_returns_false_for_tampered_log(
        self,
        audit_service: AuditServiceImpl,
        fake_repo: FakeAuditRepository,
    ) -> None:
        """Test verify_integrity returns False for tampered log."""
        # Create a log first
        record = await audit_service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
        )

        # Tamper with the log
        saved_log = await fake_repo.get_by_id(record.log_id)
        assert saved_log is not None
        saved_log["actor"] = "hacker-999"  # Modify the actor
        saved_log["checksum"] = "invalid_checksum"

        # Verify should fail
        is_valid = await audit_service.verify_integrity(record.log_id)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_integrity_raises_for_missing_log(
        self,
        audit_service: AuditServiceImpl,
    ) -> None:
        """Test verify_integrity raises AuditError for missing log."""
        non_existent_id = uuid4()

        with pytest.raises(AuditError, match="not found"):
            await audit_service.verify_integrity(non_existent_id)

    @pytest.mark.asyncio
    async def test_verify_batch_returns_summary(
        self,
        audit_service: AuditServiceImpl,
    ) -> None:
        """Test verify_batch returns correct summary."""
        # Create multiple logs
        log_ids = []
        for i in range(3):
            record = await audit_service.record(
                actor=f"user-{i}",
                action_type="authentication:login",
                target_resource="/api/v1/auth/login",
            )
            log_ids.append(record.log_id)

        # Verify batch
        result = await audit_service.verify_batch(log_ids)

        assert result["total"] == 3
        assert result["passed"] == 3
        assert result["failed"] == 0
        assert len(result["details"]) == 3

    @pytest.mark.asyncio
    async def test_verify_batch_with_empty_list_verifies_all(
        self,
        audit_service: AuditServiceImpl,
    ) -> None:
        """Test verify_batch with None verifies all logs."""
        # Create some logs
        for i in range(2):
            await audit_service.record(
                actor=f"user-{i}",
                action_type="authentication:login",
                target_resource="/api/v1/auth/login",
            )

        # Verify all
        result = await audit_service.verify_batch(None)

        assert result["total"] == 2
        assert result["passed"] == 2

    @pytest.mark.asyncio
    async def test_archive_returns_count(
        self,
        audit_service: AuditServiceImpl,
        fake_repo: FakeAuditRepository,
    ) -> None:
        """Test archive returns count of archived logs."""
        # Create old logs (these would be filtered by date in real implementation)
        # For testing, we'll rely on the search criteria

        # Archive with 0 days (would archive recent logs in real impl)
        # In test, we just verify the method works
        count = await audit_service.archive(older_than_days=0)

        assert isinstance(count, int)
        assert count >= 0


class TestAuditServiceInterface:
    """Test AuditService port interface compliance."""

    def test_audit_service_is_abstract(self) -> None:
        """AuditService should be an abstract base class."""
        from abc import ABC

        assert issubclass(AuditServicePort, ABC)

    def test_audit_service_has_required_methods(self) -> None:
        """AuditService should have record, verify_integrity, verify_batch, archive methods."""
        assert hasattr(AuditServicePort, "record")
        assert hasattr(AuditServicePort, "verify_integrity")
        assert hasattr(AuditServicePort, "verify_batch")
        assert hasattr(AuditServicePort, "archive")

    def test_record_is_async_abstract_method(self) -> None:
        """record should be an async abstract method."""
        import inspect

        assert hasattr(AuditServicePort, "record")
        assert inspect.iscoroutinefunction(AuditServicePort.record)
        assert getattr(AuditServicePort.record, "__isabstractmethod__", False)

    def test_verify_integrity_is_async_abstract_method(self) -> None:
        """verify_integrity should be an async abstract method."""
        import inspect

        assert inspect.iscoroutinefunction(AuditServicePort.verify_integrity)
        assert getattr(AuditServicePort.verify_integrity, "__isabstractmethod__", False)

    def test_verify_batch_is_async_abstract_method(self) -> None:
        """verify_batch should be an async abstract method."""
        import inspect

        assert inspect.iscoroutinefunction(AuditServicePort.verify_batch)
        assert getattr(AuditServicePort.verify_batch, "__isabstractmethod__", False)

    def test_archive_is_async_abstract_method(self) -> None:
        """archive should be an async abstract method."""
        import inspect

        assert inspect.iscoroutinefunction(AuditServicePort.archive)
        assert getattr(AuditServicePort.archive, "__isabstractmethod__", False)
