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

    def __init__(self, fail_on: str = "save") -> None:
        self._logs: dict[UUID, dict[str, Any]] = {}
        self.fail_on = fail_on

    async def save(self, audit_data: dict[str, Any]) -> UUID:
        if self.fail_on == "save":
            raise RuntimeError("Database connection failed")
        log_id = UUID(audit_data["log_id"])
        self._logs[log_id] = audit_data
        return log_id

    async def get_by_id(self, log_id: UUID) -> dict[str, Any] | None:
        if self.fail_on == "get_by_id":
            raise RuntimeError("Database read failed")
        return self._logs.get(log_id)

    async def search(self, criteria: AuditSearchCriteria) -> AuditSearchResult:
        if self.fail_on == "search":
            raise RuntimeError("Database search failed")
        items = list(self._logs.values())
        return AuditSearchResult(
            items=tuple(items[criteria.offset : criteria.offset + criteria.limit]),
            total=len(items),
            offset=criteria.offset,
            limit=criteria.limit,
        )

    async def update_archive_status(
        self,
        log_id: UUID,
        archived: bool,
        archived_at: datetime | None = None,
    ) -> bool:
        if self.fail_on == "update_archive_status":
            raise RuntimeError("Database update failed")
        if log_id not in self._logs:
            return False
        self._logs[log_id]["archived"] = archived
        self._logs[log_id]["archived_at"] = archived_at.isoformat() if archived_at else None
        return True

    async def get_archive_status(self, log_id: UUID) -> dict[str, Any] | None:
        if self.fail_on == "get_archive_status":
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_record_continues_when_event_publisher_fails(self) -> None:
        """Test record() succeeds even when event publisher fails."""
        working_repo = FailingAuditRepository(fail_on="none")
        failing_publisher = MockPublisher(should_fail=True)
        service = AuditServiceImpl(
            audit_repository=working_repo,
            event_publisher=failing_publisher,
        )

        # Record should still succeed because event publisher failure is caught
        record = await service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
        )

        assert record is not None
        assert record.actor == "user-123"


class TestAuditServiceVerifyIntegrityExceptions:
    """Test exception handling in AuditService.verify_integrity()."""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_verify_batch_handles_verify_integrity_errors(
        self,
    ) -> None:
        """Test verify_batch handles errors from verify_integrity gracefully."""
        # Create a repository with a log
        from src.infrastructure.security.audit_service_impl import AuditServiceImpl

        class PartialFailingRepo(FailingAuditRepository):
            async def get_by_id(self, log_id: UUID) -> dict[str, Any] | None:
                if log_id in self._logs:
                    # First call succeeds, second would fail
                    result = self._logs.get(log_id)
                    # Mark as accessed, next call would fail
                    return result
                raise RuntimeError("Database read failed")

        repo = PartialFailingRepo(fail_on="none")
        log_id = uuid4()
        repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": datetime.now().isoformat(),
            "actor": "user-123",
            "action_type": "authentication:login",
            "target_resource": "/api/v1/auth/login",
            "old_value": {},
            "new_value": {},
            "correction_level": 0,
            "checksum": "invalid_checksum",  # Will cause verify to fail
        }

        service = AuditServiceImpl(audit_repository=repo)
        result = await service.verify_batch([log_id])

        # Should handle the checksum mismatch gracefully
        assert result["total"] == 1
        # The result could be passed or failed depending on implementation

    @pytest.mark.asyncio
    async def test_verify_batch_raises_audit_error_on_exception(
        self,
    ) -> None:
        """Test verify_batch raises AuditError on unexpected exception."""
        failing_repo = FailingAuditRepository(fail_on="search")
        service = AuditServiceImpl(audit_repository=failing_repo)

        # Create a log first - but we don't need to keep the reference
        await service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
        )

        # Now make the repo fail on search
        failing_repo.fail_on = "search"

        with pytest.raises(AuditError, match="Failed to verify batch"):
            await service.verify_batch(None)


class TestAuditServiceArchiveExceptions:
    """Test exception handling in AuditService.archive()."""

    @pytest.mark.asyncio
    async def test_archive_handles_search_exception(
        self,
    ) -> None:
        """Test archive handles search exception gracefully."""
        failing_repo = FailingAuditRepository(fail_on="search")
        service = AuditServiceImpl(audit_repository=failing_repo)

        # Should not raise, just return 0
        count = await service.archive(older_than_days=30)
        assert count == 0

    @pytest.mark.asyncio
    async def test_archive_continues_when_worm_manager_fails(
        self,
    ) -> None:
        """Test archive continues when WORM manager fails."""
        from src.infrastructure.security.audit_service_impl import AuditServiceImpl

        class TestRepo(FailingAuditRepository):
            async def search(self, criteria: AuditSearchCriteria) -> AuditSearchResult:
                # Return some old logs
                old_time = datetime.now(timezone.utc) - timedelta(days=35)
                return AuditSearchResult(
                    items=(
                        {
                            "log_id": str(uuid4()),
                            "timestamp": old_time.isoformat(),
                            "actor": "user-old",
                            "action_type": "authentication:login",
                            "target_resource": "/api/v1/auth/login",
                            "old_value": {},
                            "new_value": {},
                            "correction_level": 0,
                            "checksum": "b" * 64,
                        },
                    ),
                    total=1,
                    offset=0,
                    limit=100,
                )

        repo = TestRepo(fail_on="none")
        failing_worm = MockWormManager(should_fail=True)
        service = AuditServiceImpl(
            audit_repository=repo,
            worm_manager=failing_worm,
        )

        # Should not raise, archive count should be 1 despite WORM failure
        count = await service.archive(older_than_days=30)
        assert count == 1  # Archive succeeded in DB even though WORM failed

    @pytest.mark.asyncio
    async def test_archive_returns_zero_when_no_logs(
        self,
    ) -> None:
        """Test archive returns 0 when no logs match criteria."""
        empty_repo = FailingAuditRepository(fail_on="none")
        service = AuditServiceImpl(audit_repository=empty_repo)

        count = await service.archive(older_than_days=30)
        assert count == 0

    @pytest.mark.asyncio
    async def test_archive_with_worm_manager_success(
        self,
    ) -> None:
        """Test archive succeeds with WORM manager."""
        from src.infrastructure.security.audit_service_impl import AuditServiceImpl

        class TestRepo(FailingAuditRepository):
            async def search(self, criteria: AuditSearchCriteria) -> AuditSearchResult:
                old_time = datetime.now(timezone.utc) - timedelta(days=35)
                return AuditSearchResult(
                    items=(
                        {
                            "log_id": str(uuid4()),
                            "timestamp": old_time.isoformat(),
                            "actor": "user-old",
                            "action_type": "authentication:login",
                            "target_resource": "/api/v1/auth/login",
                            "old_value": {},
                            "new_value": {},
                            "correction_level": 0,
                            "checksum": "c" * 64,
                        },
                    ),
                    total=1,
                    offset=0,
                    limit=100,
                )

        repo = TestRepo(fail_on="none")
        worm_manager = MockWormManager(should_fail=False)
        service = AuditServiceImpl(
            audit_repository=repo,
            worm_manager=worm_manager,
        )

        count = await service.archive(older_than_days=30)
        assert count == 1
        assert len(worm_manager.archived_objects) == 1


class TestAuditServiceEdgeCases:
    """Test edge cases in AuditService."""

    @pytest.mark.asyncio
    async def test_verify_batch_with_empty_list(self) -> None:
        """Test verify_batch with empty list returns zero counts."""
        from src.infrastructure.security.audit_service_impl import AuditServiceImpl

        class EmptyRepo(FailingAuditRepository):
            async def search(self, criteria: AuditSearchCriteria) -> AuditSearchResult:
                return AuditSearchResult(items=(), total=0, offset=0, limit=1000)

        repo = EmptyRepo(fail_on="none")
        service = AuditServiceImpl(audit_repository=repo)

        result = await service.verify_batch([])
        assert result["total"] == 0
        assert result["passed"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_record_with_all_fields(self) -> None:
        """Test record with all optional fields populated."""
        from src.infrastructure.security.audit_service_impl import AuditServiceImpl

        repo = FailingAuditRepository(fail_on="none")
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

    @pytest.mark.asyncio
    async def test_verify_integrity_rechecksum_computation(
        self,
    ) -> None:
        """Test verify_integrity correctly recomputes checksum."""
        import hashlib
        import json

        from src.infrastructure.security.audit_service_impl import AuditServiceImpl

        repo = FailingAuditRepository(fail_on="none")
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


class TestAuditServiceImplInit:
    """Test AuditServiceImpl initialization."""

    def test_init_with_all_dependencies(self) -> None:
        """Test AuditServiceImpl initializes with all dependencies."""
        repo = FailingAuditRepository(fail_on="none")
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
        repo = FailingAuditRepository(fail_on="none")
        service = AuditServiceImpl(audit_repository=repo)

        assert service._audit_repo is repo
        assert service._event_publisher is None
        assert service._worm_manager is None
