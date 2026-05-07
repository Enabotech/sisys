"""Tests for Audit API endpoints using TestClient."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.ports.audit_repository import AuditSearchCriteria, AuditSearchResult
from src.domain.ports.audit_service import AuditRecord
from src.interfaces.api.audit import create_audit_router


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
            if criteria.actor and item.get("actor") != criteria.actor:
                continue
            if criteria.action_type and criteria.action_type not in item.get("action_type", ""):
                continue
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


class FakeAuditService:
    """Fake audit service for testing."""

    def __init__(self, repo: FakeAuditRepository) -> None:
        self._repo = repo

    async def record(
        self,
        actor: str,
        action_type: str,
        target_resource: str,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> AuditRecord:
        log_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        self._repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": timestamp.isoformat(),
            "actor": actor,
            "action_type": action_type,
            "target_resource": target_resource,
            "old_value": old_value,
            "new_value": new_value,
            "correction_level": 0,
            "checksum": "a" * 64,
            "correlation_id": correlation_id,
        }
        return AuditRecord(
            log_id=log_id,
            timestamp=timestamp,
            actor=actor,
            action_type=action_type,
            target_resource=target_resource,
            old_value=old_value or {},
            new_value=new_value or {},
            correction_level=0,
        )

    async def verify_integrity(self, log_id: UUID) -> bool:
        log = self._repo._logs.get(log_id)
        if not log:
            return False
        return True

    async def verify_batch(self, log_ids: list[UUID] | None) -> dict[str, Any]:
        if log_ids is None:
            log_ids = list(self._repo._logs.keys())
        details = []
        passed = 0
        for lid in log_ids:
            log = self._repo._logs.get(lid)
            if log:
                details.append({"log_id": str(lid), "status": "passed", "message": "OK"})
                passed += 1
            else:
                details.append({"log_id": str(lid), "status": "failed", "message": "Not found"})
        return {"total": len(log_ids), "passed": passed, "failed": len(log_ids) - passed, "details": details}

    async def archive(self, older_than_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        count = 0
        for log_id, log in list(self._repo._logs.items()):
            ts_str = log.get("timestamp", "")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts < cutoff:
                        log["archived"] = True
                        count += 1
                except ValueError:
                    pass
        return count


@pytest.fixture
def fake_repo() -> FakeAuditRepository:
    return FakeAuditRepository()


@pytest.fixture
def fake_service(fake_repo: FakeAuditRepository) -> FakeAuditService:
    return FakeAuditService(fake_repo)


@pytest.fixture
def app(fake_repo: FakeAuditRepository, fake_service: FakeAuditService) -> FastAPI:
    application = FastAPI()
    application.include_router(
        create_audit_router(
            get_audit_service=lambda: fake_service,
            get_audit_repository=lambda: fake_repo,
        )
    )
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestSearchAuditLogs:
    """Test GET /audit/logs endpoint."""

    def test_search_returns_empty_list(self, client: TestClient) -> None:
        """Test search returns empty when no logs exist."""
        response = client.get("/audit/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_search_returns_logs(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test search returns existing logs."""
        log_id = uuid4()
        fake_repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "user-123",
            "action_type": "authentication:login",
            "target_resource": "/api/v1/auth/login",
            "old_value": None,
            "new_value": {"status": "success"},
            "correction_level": 0,
            "checksum": "a" * 64,
            "archived": False,
            "archived_at": None,
            "correlation_id": "corr-123",
        }

        response = client.get("/audit/logs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["actor"] == "user-123"

    def test_search_with_actor_filter(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test search with actor filter."""
        for i in range(3):
            log_id = uuid4()
            fake_repo._logs[log_id] = {
                "log_id": str(log_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": f"user-{i}",
                "action_type": "authentication:login",
                "target_resource": "/api/v1/auth/login",
                "old_value": None,
                "new_value": None,
                "correction_level": 0,
                "checksum": "b" * 64,
                "archived": False,
                "archived_at": None,
                "correlation_id": None,
            }

        response = client.get("/audit/logs", params={"actor": "user-0"})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["actor"] == "user-0"

    def test_search_with_action_type_filter(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test search with action_type filter."""
        log_id1 = uuid4()
        log_id2 = uuid4()
        fake_repo._logs[log_id1] = {
            "log_id": str(log_id1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "user-1",
            "action_type": "authentication:login",
            "target_resource": "/api/v1/auth/login",
            "old_value": None,
            "new_value": None,
            "correction_level": 0,
            "checksum": "c" * 64,
            "archived": False,
            "archived_at": None,
            "correlation_id": None,
        }
        fake_repo._logs[log_id2] = {
            "log_id": str(log_id2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "user-2",
            "action_type": "document:upload",
            "target_resource": "/api/v1/docs/doc-1",
            "old_value": None,
            "new_value": None,
            "correction_level": 0,
            "checksum": "d" * 64,
            "archived": False,
            "archived_at": None,
            "correlation_id": None,
        }

        response = client.get("/audit/logs", params={"action_type": "login"})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "login" in data["items"][0]["action_type"]

    def test_search_with_pagination(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test search with offset and limit."""
        for i in range(5):
            log_id = uuid4()
            fake_repo._logs[log_id] = {
                "log_id": str(log_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": f"user-{i}",
                "action_type": "test:action",
                "target_resource": f"/resource/{i}",
                "old_value": None,
                "new_value": None,
                "correction_level": 0,
                "checksum": "e" * 64,
                "archived": False,
                "archived_at": None,
                "correlation_id": None,
            }

        response = client.get("/audit/logs", params={"offset": 2, "limit": 2})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["offset"] == 2
        assert data["limit"] == 2


class TestGetAuditLog:
    """Test GET /audit/logs/{log_id} endpoint."""

    def test_get_log_success(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test get log returns log details."""
        log_id = uuid4()
        fake_repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "user-123",
            "action_type": "authentication:login",
            "target_resource": "/api/v1/auth/login",
            "old_value": None,
            "new_value": {"status": "success"},
            "correction_level": 0,
            "checksum": "f" * 64,
            "archived": False,
            "archived_at": None,
            "correlation_id": None,
        }

        response = client.get(f"/audit/logs/{log_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["log_id"] == str(log_id)
        assert data["actor"] == "user-123"

    def test_get_log_invalid_uuid(self, client: TestClient) -> None:
        """Test get log with invalid UUID returns 400."""
        response = client.get("/audit/logs/not-a-uuid")

        assert response.status_code == 400
        assert "Invalid log_id format" in response.json()["detail"]

    def test_get_log_not_found(self, client: TestClient) -> None:
        """Test get log not found returns 404."""
        response = client.get(f"/audit/logs/{uuid4()}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestVerifyIntegrity:
    """Test POST /audit/verify endpoint."""

    def test_verify_empty_request(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test verify with empty request verifies all."""
        log_id = uuid4()
        fake_repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "user-123",
            "action_type": "test:action",
            "target_resource": "/resource",
            "old_value": None,
            "new_value": None,
            "correction_level": 0,
            "checksum": "g" * 64,
            "archived": False,
            "archived_at": None,
            "correlation_id": None,
        }

        response = client.post("/audit/verify", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["passed"] == 1

    def test_verify_specific_log_ids(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test verify with specific log_ids."""
        log_id1 = uuid4()
        log_id2 = uuid4()
        fake_repo._logs[log_id1] = {
            "log_id": str(log_id1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "user-1",
            "action_type": "test:action",
            "target_resource": "/resource/1",
            "old_value": None,
            "new_value": None,
            "correction_level": 0,
            "checksum": "h" * 64,
            "archived": False,
            "archived_at": None,
            "correlation_id": None,
        }
        fake_repo._logs[log_id2] = {
            "log_id": str(log_id2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "user-2",
            "action_type": "test:action",
            "target_resource": "/resource/2",
            "old_value": None,
            "new_value": None,
            "correction_level": 0,
            "checksum": "i" * 64,
            "archived": False,
            "archived_at": None,
            "correlation_id": None,
        }

        response = client.post("/audit/verify", json={"log_ids": [str(log_id1), str(log_id2)]})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["passed"] == 2

    def test_verify_invalid_log_id_format(self, client: TestClient) -> None:
        """Test verify with invalid log_id format returns 400."""
        response = client.post("/audit/verify", json={"log_ids": ["not-a-uuid"]})

        assert response.status_code == 400
        assert "Invalid log_id format" in response.json()["detail"]


class TestGetArchiveStatus:
    """Test GET /audit/archive/status endpoint."""

    def test_get_archive_status_success(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test get archive status returns status."""
        log_id = uuid4()
        fake_repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": "user-123",
            "action_type": "test:action",
            "target_resource": "/resource",
            "old_value": None,
            "new_value": None,
            "correction_level": 0,
            "checksum": "j" * 64,
            "archived": True,
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "correlation_id": None,
        }

        response = client.get("/audit/archive/status", params={"log_id": str(log_id)})

        assert response.status_code == 200
        data = response.json()
        assert data["log_id"] == str(log_id)
        assert data["archived"] is True
        assert data["retention_days"] == 2555

    def test_get_archive_status_invalid_uuid(self, client: TestClient) -> None:
        """Test get archive status with invalid UUID returns 400."""
        response = client.get("/audit/archive/status", params={"log_id": "invalid"})

        assert response.status_code == 400
        assert "Invalid log_id format" in response.json()["detail"]

    def test_get_archive_status_not_found(self, client: TestClient) -> None:
        """Test get archive status not found returns 404."""
        response = client.get("/audit/archive/status", params={"log_id": str(uuid4())})

        assert response.status_code == 404


class TestArchiveLogs:
    """Test POST /audit/archive endpoint."""

    def test_archive_default_days(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test archive with default older_than_days."""
        # Create an old log
        old_time = datetime.now(timezone.utc) - timedelta(days=35)
        log_id = uuid4()
        fake_repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": old_time.isoformat(),
            "actor": "user-old",
            "action_type": "test:action",
            "target_resource": "/resource",
            "old_value": None,
            "new_value": None,
            "correction_level": 0,
            "checksum": "k" * 64,
            "archived": False,
            "archived_at": None,
            "correlation_id": None,
        }

        response = client.post("/audit/archive", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["archived_count"] == 1

    def test_archive_custom_days(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test archive with custom older_than_days."""
        # Create a log that's 15 days old
        old_time = datetime.now(timezone.utc) - timedelta(days=15)
        log_id = uuid4()
        fake_repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": old_time.isoformat(),
            "actor": "user-old",
            "action_type": "test:action",
            "target_resource": "/resource",
            "old_value": None,
            "new_value": None,
            "correction_level": 0,
            "checksum": "l" * 64,
            "archived": False,
            "archived_at": None,
            "correlation_id": None,
        }

        response = client.post("/audit/archive", json={"older_than_days": 10})

        assert response.status_code == 200
        data = response.json()
        assert data["archived_count"] == 1

    def test_archive_no_old_logs(self, client: TestClient, fake_repo: FakeAuditRepository) -> None:
        """Test archive when no logs match criteria."""
        # Create a recent log
        recent_time = datetime.now(timezone.utc) - timedelta(days=5)
        log_id = uuid4()
        fake_repo._logs[log_id] = {
            "log_id": str(log_id),
            "timestamp": recent_time.isoformat(),
            "actor": "user-recent",
            "action_type": "test:action",
            "target_resource": "/resource",
            "old_value": None,
            "new_value": None,
            "correction_level": 0,
            "checksum": "m" * 64,
            "archived": False,
            "archived_at": None,
            "correlation_id": None,
        }

        response = client.post("/audit/archive", json={"older_than_days": 30})

        assert response.status_code == 200
        data = response.json()
        assert data["archived_count"] == 0


class TestAuditRouterPrefix:
    """Test router configuration."""

    def test_router_has_correct_prefix(self, app: FastAPI) -> None:
        """Test router has /audit prefix."""
        audit_paths = [r.path for r in app.routes if hasattr(r, "path") and r.path.startswith("/audit")]
        assert len(audit_paths) == 5  # 5 audit endpoints
