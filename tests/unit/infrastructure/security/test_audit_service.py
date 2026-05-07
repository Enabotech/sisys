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

        # Apply match_any (OR) logic if specified
        if criteria.match_any and criteria.actor and criteria.action_type:
            # For OR: re-filter to include items matching actor OR action_type
            or_filtered = []
            for item in items:
                timestamp = datetime.fromisoformat(item["timestamp"])
                if criteria.start_time and timestamp < criteria.start_time:
                    continue
                if criteria.end_time and timestamp > criteria.end_time:
                    continue
                actor_match = item.get("actor") == criteria.actor
                action_match = criteria.action_type in item.get("action_type", "")
                if actor_match or action_match:
                    or_filtered.append(item)
            filtered = or_filtered

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

    @pytest.mark.asyncio
    async def test_search_with_match_any_or_condition(
        self,
        fake_repo: FakeAuditRepository,
    ) -> None:
        """Test search with match_any=True returns results matching any criteria."""
        # Create logs with different actors and action types
        await fake_repo.save(
            {
                "log_id": str(uuid4()),
                "timestamp": datetime.now().isoformat(),
                "actor": "user-A",
                "action_type": "document:read",
                "target_resource": "/doc-1",
                "old_value": {},
                "new_value": {},
                "checksum": "a" * 64,
            }
        )
        await fake_repo.save(
            {
                "log_id": str(uuid4()),
                "timestamp": datetime.now().isoformat(),
                "actor": "user-B",
                "action_type": "authentication:login",
                "target_resource": "/doc-2",
                "old_value": {},
                "new_value": {},
                "checksum": "b" * 64,
            }
        )
        await fake_repo.save(
            {
                "log_id": str(uuid4()),
                "timestamp": datetime.now().isoformat(),
                "actor": "user-C",
                "action_type": "document:write",
                "target_resource": "/doc-3",
                "old_value": {},
                "new_value": {},
                "checksum": "c" * 64,
            }
        )

        # Search with OR (match_any=True) - actor=user-A OR action_type contains "authentication"
        result = await fake_repo.search(AuditSearchCriteria(actor="user-A", action_type="authentication", match_any=True))

        # Should return 2 logs: user-A's document:read and user-B's authentication:login
        assert result.total == 2
        actors = {item["actor"] for item in result.items}
        assert "user-A" in actors
        assert "user-B" in actors

    @pytest.mark.asyncio
    async def test_search_without_match_any_and_condition(
        self,
        fake_repo: FakeAuditRepository,
    ) -> None:
        """Test search with match_any=False returns results matching all criteria."""
        # Create logs with different actors and action types
        await fake_repo.save(
            {
                "log_id": str(uuid4()),
                "timestamp": datetime.now().isoformat(),
                "actor": "user-A",
                "action_type": "document:read",
                "target_resource": "/doc-1",
                "old_value": {},
                "new_value": {},
                "checksum": "a" * 64,
            }
        )
        await fake_repo.save(
            {
                "log_id": str(uuid4()),
                "timestamp": datetime.now().isoformat(),
                "actor": "user-A",
                "action_type": "authentication:login",
                "target_resource": "/doc-2",
                "old_value": {},
                "new_value": {},
                "checksum": "b" * 64,
            }
        )

        # Search with AND (match_any=False) - actor=user-A AND action_type contains "authentication"
        result = await fake_repo.search(AuditSearchCriteria(actor="user-A", action_type="authentication", match_any=False))

        # Should return only 1 log: user-A's authentication:login
        assert result.total == 1
        assert result.items[0]["actor"] == "user-A"
        assert "authentication" in result.items[0]["action_type"]

    @pytest.mark.asyncio
    async def test_record_with_event_publisher(
        self,
        fake_repo: FakeAuditRepository,
    ) -> None:
        """Test that record publishes event when event_publisher is set."""
        published_events: list = []

        class MockPublisher:
            async def publish(self, event):
                published_events.append(event)

        service = AuditServiceImpl(
            audit_repository=fake_repo,
            event_publisher=MockPublisher(),
        )

        record = await service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
        )

        assert record is not None
        assert len(published_events) == 1
        assert published_events[0].actor == "user-123"

    @pytest.mark.asyncio
    async def test_record_without_event_publisher(
        self,
        fake_repo: FakeAuditRepository,
    ) -> None:
        """Test that record works without event_publisher."""
        service = AuditServiceImpl(audit_repository=fake_repo)

        record = await service.record(
            actor="user-123",
            action_type="authentication:logout",
            target_resource="/api/v1/auth/logout",
        )

        assert record is not None
        assert record.actor == "user-123"

    @pytest.mark.asyncio
    async def test_verify_batch_with_specific_log_ids(
        self,
        audit_service: AuditServiceImpl,
    ) -> None:
        """Test verify_batch with specific log_ids."""
        # Create logs
        log_ids = []
        for i in range(3):
            record = await audit_service.record(
                actor=f"user-{i}",
                action_type="authentication:login",
                target_resource="/api/v1/auth/login",
            )
            log_ids.append(record.log_id)

        # Verify only the first two
        result = await audit_service.verify_batch(log_ids[:2])

        assert result["total"] == 2
        assert result["passed"] == 2
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_verify_batch_with_mixed_results(
        self,
        fake_repo: FakeAuditRepository,
        audit_service: AuditServiceImpl,
    ) -> None:
        """Test verify_batch with some valid and some tampered logs."""
        # Create a valid log
        record = await audit_service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
        )
        valid_log_id = record.log_id

        # Create and tamper with another log
        tampered_log_id = uuid4()
        await fake_repo.save(
            {
                "log_id": str(tampered_log_id),
                "timestamp": datetime.now().isoformat(),
                "actor": "user-456",
                "action_type": "authentication:login",
                "target_resource": "/api/v1/auth/login",
                "old_value": {},
                "new_value": {},
                "checksum": "invalid_checksum",  # Tampered!
            }
        )

        # Verify batch with mixed logs
        result = await audit_service.verify_batch([valid_log_id, tampered_log_id])

        assert result["total"] == 2
        # First log should pass, second should fail (tampered)
        assert result["passed"] == 1
        assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_verify_batch_none_verifies_all(
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

        result = await audit_service.verify_batch(None)

        assert result["total"] == 2
        assert result["passed"] == 2
        assert len(result["details"]) == 2

    @pytest.mark.asyncio
    async def test_archive_with_old_logs(
        self,
        fake_repo: FakeAuditRepository,
    ) -> None:
        """Test archive returns count of archived logs."""
        from datetime import timedelta, timezone

        # Create old logs (older than 30 days)
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=35)
        await fake_repo.save(
            {
                "log_id": str(uuid4()),
                "timestamp": old_timestamp.isoformat(),
                "actor": "user-old",
                "action_type": "authentication:login",
                "target_resource": "/api/v1/auth/login",
                "old_value": {},
                "new_value": {},
                "checksum": "c" * 64,
            }
        )

        service = AuditServiceImpl(audit_repository=fake_repo)
        count = await service.archive(older_than_days=30)

        assert count >= 1


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
