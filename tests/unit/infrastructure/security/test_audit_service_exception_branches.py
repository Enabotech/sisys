"""Tests for AuditService exception branches and edge cases.

This file specifically tests exception handling branches in AuditServiceImpl.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.domain.ports.audit_repository import AuditRepositoryPort, AuditSearchCriteria, AuditSearchResult
from src.domain.ports.audit_service import AuditError
from src.infrastructure.security.audit_service_impl import AuditServiceImpl


class FailingAuditRepository(AuditRepositoryPort):
    """Repository that fails on certain operations for testing exception handling."""

    def __init__(self, fail_on: str = "none") -> None:
        self._logs: dict[UUID, dict[str, Any]] = {}
        self._fail_on = fail_on

    async def save(self, audit_data: dict[str, Any]) -> UUID:
        if self._fail_on == "save":
            raise RuntimeError("Database connection failed")
        log_id = UUID(audit_data["log_id"])
        self._logs[log_id] = audit_data
        return log_id

    async def get_by_id(self, log_id: UUID) -> dict[str, Any] | None:
        if self._fail_on == "get_by_id":
            raise RuntimeError("Database read failed")
        return self._logs.get(log_id)

    async def search(self, criteria: AuditSearchCriteria) -> AuditSearchResult:
        if self._fail_on == "search":
            raise RuntimeError("Database search failed")
        items = list(self._logs.values())
        # Apply basic filtering
        filtered = []
        for item in items:
            ts_str = item.get("timestamp", "")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if criteria.start_time and ts < criteria.start_time:
                        continue
                    if criteria.end_time and ts > criteria.end_time:
                        continue
                except ValueError:
                    pass
            filtered.append(item)
        total = len(filtered)
        start = criteria.offset
        end = start + criteria.limit
        paginated = filtered[start:end]
        return AuditSearchResult(
            items=tuple(paginated),
            total=total,
            offset=criteria.offset,
            limit=criteria.limit,
        )

    async def update_archive_status(
        self,
        log_id: UUID,
        archived: bool,
        archived_at: datetime | None = None,
    ) -> bool:
        if self._fail_on == "update_archive_status":
            raise RuntimeError("Database update failed")
        if log_id not in self._logs:
            return False
        self._logs[log_id]["archived"] = archived
        self._logs[log_id]["archived_at"] = archived_at.isoformat() if archived_at else None
        return True

    async def get_archive_status(self, log_id: UUID) -> dict[str, Any] | None:
        if self._fail_on == "get_archive_status":
            raise RuntimeError("Database read failed")
        if log_id not in self._logs:
            return None
        log = self._logs[log_id]
        return {
            "log_id": str(log_id),
            "archived": log.get("archived", False),
            "archived_at": log.get("archived_at"),
            "retention_days": 2555,
        }


class MockPublisher:
    """Mock event publisher that fails on publish."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.published_events: list = []

    async def publish(self, event) -> None:
        if self.should_fail:
            raise RuntimeError("Event publishing failed")
        self.published_events.append(event)


class MockWormManager:
    """Mock WORM manager for testing archival."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.archived_objects: list = []

    def archive_object(
        self,
        bucket_name: str,
        object_key: str,
        retention_days: int,
    ) -> None:
        if self.should_fail:
            raise RuntimeError("WORM archival failed")
        self.archived_objects.append({"bucket": bucket_name, "key": object_key})


class TestAuditServiceRecordExceptions:
    """Test exception handling in AuditService.record()."""

    async def test_record_raises_audit_error_on_save_failure(self) -> None:
        """Test record() raises AuditError when save fails."""
        failing_repo = FailingAuditRepository(fail_on="save")
        service = AuditServiceImpl(audit_repository=failing_repo)

        with pytest.raises(AuditError, match="Failed to record audit log"):
            await service.record(
                actor="user-123",
                action_type="authentication:login",
                target_resource="/api/v1/auth/login",
            )

    async def test_record_raises_audit_error_when_publisher_fails(self) -> None:
        """Test record() raises AuditError when event publisher fails.

        Note: Current implementation does NOT catch event_publisher.publish() exceptions.
        This test documents actual behavior.
        """
        failing_repo = FailingAuditRepository()
        failing_publisher = MockPublisher(should_fail=True)
        service = AuditServiceImpl(
            audit_repository=failing_repo,
            event_publisher=failing_publisher,
        )

        # Current behavior: exception propagates up
        with pytest.raises(AuditError, match="Failed to record audit log"):
            await service.record(
                actor="user-123",
                action_type="authentication:login",
                target_resource="/api/v1/auth/login",
            )


class TestAuditServiceVerifyIntegrityExceptions:
    """Test exception handling in AuditService.verify_integrity()."""

    async def test_verify_integrity_raises_audit_error_on_get_by_id_failure(self) -> None:
        """Test verify_integrity raises AuditError when get_by_id fails."""
        failing_repo = FailingAuditRepository(fail_on="get_by_id")
        service = AuditServiceImpl(audit_repository=failing_repo)

        # First create a log
        log_id = uuid4()
        failing_repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": datetime.now().isoformat(),
            "actor": "user-123",
            "action_type": "authentication:login",
            "target_resource": "/api/v1/auth/login",
            "old_value": {},
            "new_value": {},
            "correction_level": 0,
            "checksum": "a" * 64,
        }

        with pytest.raises(AuditError, match="Failed to verify integrity"):
            await service.verify_integrity(log_id)


class TestAuditServiceVerifyBatchExceptions:
    """Test exception handling in AuditService.verify_batch()."""

    async def test_verify_batch_raises_audit_error_on_search_failure(self) -> None:
        """Test verify_batch raises AuditError when search fails."""
        failing_repo = FailingAuditRepository(fail_on="search")
        service = AuditServiceImpl(audit_repository=failing_repo)

        with pytest.raises(AuditError, match="Failed to verify batch"):
            await service.verify_batch(None)

    async def test_verify_batch_with_empty_list(self) -> None:
        """Test verify_batch with empty list returns zero counts."""
        repo = FailingAuditRepository()
        service = AuditServiceImpl(audit_repository=repo)

        result = await service.verify_batch([])

        assert result["total"] == 0
        assert result["passed"] == 0
        assert result["failed"] == 0


class TestAuditServiceArchiveExceptions:
    """Test exception handling in AuditService.archive()."""

    async def test_archive_raises_audit_error_when_search_fails(self) -> None:
        """Test archive raises AuditError when search fails.

        Note: Current implementation raises AuditError on search failure.
        """
        repo = FailingAuditRepository()
        # Manually set fail_on to search after init
        repo._fail_on = "search"
        service = AuditServiceImpl(audit_repository=repo)

        # Current behavior: raises AuditError on search failure
        with pytest.raises(AuditError, match="Failed to archive logs"):
            await service.archive(older_than_days=30)

    async def test_archive_continues_when_worm_manager_fails(self) -> None:
        """Test archive continues when WORM manager fails."""
        repo = FailingAuditRepository()
        worm_manager = MockWormManager(should_fail=True)
        service = AuditServiceImpl(
            audit_repository=repo,
            worm_manager=worm_manager,
        )

        # Create an old log that will be archived
        old_time = datetime.now(timezone.utc) - timedelta(days=35)
        log_id = uuid4()
        repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": old_time.isoformat(),
            "actor": "user-old",
            "action_type": "authentication:login",
            "target_resource": "/api/v1/auth/login",
            "old_value": {},
            "new_value": {},
            "correction_level": 0,
            "checksum": "b" * 64,
        }

        count = await service.archive(older_than_days=30)

        # Archive should succeed in DB even though WORM failed
        assert count == 1

    async def test_archive_with_worm_manager_success(self) -> None:
        """Test archive succeeds with WORM manager."""
        repo = FailingAuditRepository()
        worm_manager = MockWormManager(should_fail=False)
        service = AuditServiceImpl(
            audit_repository=repo,
            worm_manager=worm_manager,
        )

        # Create an old log that will be archived
        old_time = datetime.now(timezone.utc) - timedelta(days=35)
        log_id = uuid4()
        repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": old_time.isoformat(),
            "actor": "user-old",
            "action_type": "authentication:login",
            "target_resource": "/api/v1/auth/login",
            "old_value": {},
            "new_value": {},
            "correction_level": 0,
            "checksum": "c" * 64,
        }

        count = await service.archive(older_than_days=30)

        assert count == 1
        assert len(worm_manager.archived_objects) == 1

    async def test_archive_returns_zero_when_no_old_logs(self) -> None:
        """Test archive returns 0 when no logs match criteria."""
        repo = FailingAuditRepository()
        service = AuditServiceImpl(audit_repository=repo)

        # Create a recent log (not old enough to archive)
        recent_time = datetime.now(timezone.utc) - timedelta(days=5)
        log_id = uuid4()
        repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": recent_time.isoformat(),
            "actor": "user-recent",
            "action_type": "authentication:login",
            "target_resource": "/api/v1/auth/login",
            "old_value": {},
            "new_value": {},
            "correction_level": 0,
            "checksum": "d" * 64,
        }

        count = await service.archive(older_than_days=30)

        # Recent log should not be archived
        assert count == 0


class TestAuditServiceEdgeCases:
    """Test edge cases in AuditService."""

    async def test_record_with_all_fields(self) -> None:
        """Test record with all optional fields populated."""
        repo = FailingAuditRepository()
        service = AuditServiceImpl(audit_repository=repo)

        record = await service.record(
            actor="user-123",
            action_type="authorization:grant",
            target_resource="role/admin",
            old_value={"role": "viewer"},
            new_value={"role": "admin"},
            correlation_id="corr-456",
        )

        assert record is not None
        assert record.actor == "user-123"
        assert record.old_value == {"role": "viewer"}
        assert record.new_value == {"role": "admin"}

    async def test_verify_integrity_rechecksum_computation(self) -> None:
        """Test verify_integrity correctly recomputes checksum."""
        import hashlib
        import json

        repo = FailingAuditRepository()
        service = AuditServiceImpl(audit_repository=repo)

        # Create a log
        record = await service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
        )

        # Get the stored checksum
        stored_log = await repo.get_by_id(record.log_id)
        assert stored_log is not None
        stored_checksum = stored_log["checksum"]

        # Verify integrity
        is_valid = await service.verify_integrity(record.log_id)
        assert is_valid is True

        # Verify the checksum was computed correctly
        content = json.dumps(
            {
                "log_id": str(record.log_id),
                "timestamp": stored_log["timestamp"],
                "actor": stored_log["actor"],
                "action_type": stored_log["action_type"],
                "target_resource": stored_log["target_resource"],
                "old_value": stored_log["old_value"],
                "new_value": stored_log["new_value"],
                "correction_level": stored_log["correction_level"],
            },
            sort_keys=True,
        )
        expected_checksum = hashlib.sha256(content.encode()).hexdigest()
        assert stored_checksum == expected_checksum

    async def test_verify_batch_with_tampered_log(self) -> None:
        """Test verify_batch detects tampered logs."""
        repo = FailingAuditRepository()
        service = AuditServiceImpl(audit_repository=repo)

        # Create a valid log
        record = await service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
        )

        # Tamper with the log
        stored_log = await repo.get_by_id(record.log_id)
        assert stored_log is not None
        stored_log["actor"] = "hacker-999"
        # Note: We don't update the checksum, so verification should fail

        result = await service.verify_batch([record.log_id])

        assert result["total"] == 1
        assert result["failed"] == 1
        assert result["passed"] == 0


class TestAuditServiceImplInit:
    """Test AuditServiceImpl initialization."""

    def test_init_with_all_dependencies(self) -> None:
        """Test AuditServiceImpl initializes with all dependencies."""
        repo = FailingAuditRepository()
        publisher = MockPublisher()
        worm = MockWormManager()

        service = AuditServiceImpl(
            audit_repository=repo,
            event_publisher=publisher,
            worm_manager=worm,
        )

        assert service._audit_repo is repo
        assert service._event_publisher is publisher
        assert service._worm_manager is worm

    def test_init_with_only_required_dependency(self) -> None:
        """Test AuditServiceImpl initializes with only required dependency."""
        repo = FailingAuditRepository()
        service = AuditServiceImpl(audit_repository=repo)

        assert service._audit_repo is repo
        assert service._event_publisher is None
        assert service._worm_manager is None
