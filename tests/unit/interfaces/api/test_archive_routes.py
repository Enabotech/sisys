"""战略档案 API 路由单元测试

验证 GET/POST 路由的正确性，使用 TestClient + mock 服务。
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware


def _make_token() -> object:
    """构造测试用 TokenPayload"""
    from datetime import UTC, datetime

    from src.domain.value_objects.token_payload import TokenPayload

    return TokenPayload(
        user_id=uuid.uuid4(),
        username="testuser",
        roles=("admin",),
        exp=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _make_archive(overrides: dict[str, Any] | None = None) -> StrategicArchive:
    """创建测试用档案实体"""
    archive_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    archive = StrategicArchive(
        archive_id=archive_id,
        plan_id=plan_id,
        plan_type="SP",
        archive_type=ArchiveType.ASSUMPTION,
        assumptions={"key": "value"},
        decision_basis={},
        execution_deviation={},
        metadata_ref="strategic_archives:test",
    )
    if overrides:
        for key, value in overrides.items():
            setattr(archive, key, value)
    return archive


def _make_app() -> tuple[TestClient, AsyncMock]:
    """创建带档案路由的测试 FastAPI 应用"""
    from src.interfaces.api.strategic_archive import create_archive_router

    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)

    service = AsyncMock()
    service.archive_plan.return_value = _make_archive()
    service.get_archive.return_value = _make_archive()
    service.query_archive.return_value = [_make_archive()]

    mock_user = _make_token()

    def get_user_override():
        return mock_user

    router = create_archive_router(
        archive_service=service,
        get_current_user_override=get_user_override,
    )
    app.include_router(router)

    return TestClient(app), service


class TestListEntries:
    """GET /api/v1/archive/entries"""

    def test_returns_200(self) -> None:
        """返回 200"""
        client, _ = _make_app()
        response = client.get("/api/v1/archive/entries")
        assert response.status_code == 200

    def test_returns_list(self) -> None:
        """返回列表"""
        client, _ = _make_app()
        response = client.get("/api/v1/archive/entries")
        assert isinstance(response.json(), list)

    def test_supports_filters(self) -> None:
        """支持过滤参数"""
        client, _ = _make_app()
        response = client.get(
            "/api/v1/archive/entries",
            params={
                "archive_type": "assumption",
                "plan_type": "SP",
                "plan_id": str(uuid.uuid4()),
                "offset": 0,
                "limit": 20,
            },
        )
        assert response.status_code == 200


class TestGetEntry:
    """GET /api/v1/archive/entries/{archive_id}"""

    def test_returns_200(self) -> None:
        """返回 200"""
        client, service = _make_app()
        archive_id = uuid.uuid4()
        service.get_archive.return_value = _make_archive({"archive_id": archive_id})
        response = client.get(f"/api/v1/archive/entries/{archive_id}")
        assert response.status_code == 200

    def test_returns_archive(self) -> None:
        """返回档案对象"""
        client, service = _make_app()
        archive_id = uuid.uuid4()
        service.get_archive.return_value = _make_archive({"archive_id": archive_id})
        response = client.get(f"/api/v1/archive/entries/{archive_id}")
        data = response.json()
        assert data["archive_id"] == str(archive_id)

    def test_returns_404_on_not_found(self) -> None:
        """不存在时返回 404"""
        from src.domain.exceptions.archive_exceptions import ArchiveNotFoundError

        client, service = _make_app()
        service.get_archive.side_effect = ArchiveNotFoundError(archive_id=uuid.uuid4())
        response = client.get(f"/api/v1/archive/entries/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_returns_400_on_invalid_id(self) -> None:
        """非法 archive_id 返回 400"""
        client, _ = _make_app()
        response = client.get("/api/v1/archive/entries/not-a-uuid")
        assert response.status_code == 400


class TestArchivePlan:
    """POST /api/v1/archive/archive"""

    def test_returns_201(self) -> None:
        """返回 201 Created"""
        client, _ = _make_app()
        response = client.post(
            "/api/v1/archive/archive",
            json={
                "plan_id": str(uuid.uuid4()),
                "plan_type": "SP",
                "assumptions": {"key": "value"},
            },
        )
        assert response.status_code == 201

    def test_returns_archive(self) -> None:
        """返回创建的档案"""
        client, _ = _make_app()
        response = client.post(
            "/api/v1/archive/archive",
            json={
                "plan_id": str(uuid.uuid4()),
                "plan_type": "SP",
                "assumptions": {"key": "value"},
            },
        )
        data = response.json()
        assert "archive_id" in data

    def test_validates_required_fields(self) -> None:
        """必须字段验证：缺少 plan_id 返回 400/422"""
        client, _ = _make_app()
        response = client.post(
            "/api/v1/archive/archive",
            json={},
        )
        assert response.status_code in (400, 422)


class TestListByPlan:
    """GET /api/v1/archive/plans/{plan_id}"""

    def test_returns_200(self) -> None:
        """返回 200"""
        client, _ = _make_app()
        plan_id = uuid.uuid4()
        response = client.get(f"/api/v1/archive/plans/{plan_id}")
        assert response.status_code == 200

    def test_returns_list(self) -> None:
        """返回列表"""
        client, _ = _make_app()
        plan_id = uuid.uuid4()
        response = client.get(f"/api/v1/archive/plans/{plan_id}")
        assert isinstance(response.json(), list)


class TestAuth:
    """认证测试"""

    def test_no_auth_override_returns_401(self) -> None:
        """无认证覆盖返回 401"""
        from src.interfaces.api.strategic_archive import create_archive_router

        app = FastAPI()
        app.add_middleware(ExceptionContextMiddleware)
        register_exception_handlers(app)

        router = create_archive_router(
            archive_service=AsyncMock(),
            get_current_user_override=None,
        )
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/v1/archive/entries")
        assert response.status_code == 401


class TestUpdateValidity:
    """PATCH /api/v1/archive/entries/{archive_id}"""

    def test_returns_200(self) -> None:
        """返回 200"""
        client, service = _make_app()
        archive_id = uuid.uuid4()
        service.set_validity_period.return_value = _make_archive({"archive_id": archive_id})
        response = client.patch(
            f"/api/v1/archive/entries/{archive_id}",
            json={"valid_from": "2026-01-01T00:00:00Z", "valid_until": "2027-12-31T00:00:00Z"},
        )
        assert response.status_code == 200

    def test_returns_archive_with_validity(self) -> None:
        """返回包含有效期字段的档案"""
        client, service = _make_app()
        archive_id = uuid.uuid4()
        service.set_validity_period.return_value = _make_archive({"archive_id": archive_id})
        response = client.patch(
            f"/api/v1/archive/entries/{archive_id}",
            json={"valid_from": "2026-01-01T00:00:00Z", "valid_until": "2027-12-31T00:00:00Z"},
        )
        data = response.json()
        assert data["archive_id"] == str(archive_id)
        assert "valid_from" in data
        assert "valid_until" in data

    def test_returns_400_on_invalid_id(self) -> None:
        """非法 archive_id 返回 400"""
        client, _ = _make_app()
        response = client.patch(
            "/api/v1/archive/entries/not-a-uuid",
            json={"valid_from": "2026-01-01T00:00:00Z"},
        )
        assert response.status_code == 400

    def test_returns_400_on_naive_datetime(self) -> None:
        """naive datetime 返回 400"""
        client, _ = _make_app()
        archive_id = uuid.uuid4()
        response = client.patch(
            f"/api/v1/archive/entries/{archive_id}",
            json={"valid_from": "2026-01-01T00:00:00"},
        )
        assert response.status_code == 400

    def test_returns_409_on_conflict(self) -> None:
        """有效期冲突返回 409"""
        from src.domain.exceptions.archive_exceptions import ValidityPeriodConflictError

        client, service = _make_app()
        archive_id = uuid.uuid4()
        service.set_validity_period.side_effect = ValidityPeriodConflictError(archive_id=archive_id)
        response = client.patch(
            f"/api/v1/archive/entries/{archive_id}",
            json={"valid_from": "2026-01-01T00:00:00Z", "valid_until": "2027-12-31T00:00:00Z"},
        )
        assert response.status_code == 409


class TestStalenessCheck:
    """POST /api/v1/archive/staleness-checks"""

    def test_returns_200(self) -> None:
        """返回 200"""
        client, _ = _make_app()
        response = client.post("/api/v1/archive/staleness-checks")
        assert response.status_code == 200

    def test_returns_marked_list(self) -> None:
        """返回 marked 列表"""
        client, service = _make_app()
        archive_id = uuid.uuid4()
        service.mark_stale_archives.return_value = [_make_archive({"archive_id": archive_id})]
        response = client.post("/api/v1/archive/staleness-checks")
        data = response.json()
        assert "marked" in data
        assert isinstance(data["marked"], list)
        assert str(archive_id) in data["marked"]


class TestStalenessStatusFiltering:
    """GET /entries?staleness_status= 陈旧状态过滤测试（Story 3.12 AC-6）"""

    def test_passes_staleness_status_stale_to_query(self) -> None:
        """staleness_status=stale 传递给 ArchiveQuery.staleness_status"""
        client, service = _make_app()
        response = client.get("/api/v1/archive/entries", params={"staleness_status": "stale"})
        assert response.status_code == 200
        # 验证 service.query_archive 收到的 ArchiveQuery 包含 staleness_status
        call_args = service.query_archive.call_args[0][0]
        assert call_args.staleness_status == "stale"

    def test_passes_staleness_status_fresh_to_query(self) -> None:
        """staleness_status=fresh 传递给 ArchiveQuery.staleness_status"""
        client, service = _make_app()
        response = client.get("/api/v1/archive/entries", params={"staleness_status": "fresh"})
        assert response.status_code == 200
        call_args = service.query_archive.call_args[0][0]
        assert call_args.staleness_status == "fresh"

    def test_default_staleness_status_none(self) -> None:
        """不传 staleness_status 时默认 None（向后兼容）"""
        client, service = _make_app()
        response = client.get("/api/v1/archive/entries")
        assert response.status_code == 200
        call_args = service.query_archive.call_args[0][0]
        assert call_args.staleness_status is None


class TestArchiveResponseStalenessFields:
    """ArchiveResponse 陈旧标记字段测试（Story 3.12 AC-6）"""

    def test_response_contains_staleness_fields(self) -> None:
        """ArchiveResponse 包含 is_stale/stale_reason/stale_since 字段"""
        client, service = _make_app()
        archive = _make_archive(
            {
                "metadata": {
                    "staleness": "stale",
                    "stale_reason": "expired",
                    "stale_since": "2026-08-15T00:00:00+00:00",
                }
            }
        )
        service.get_archive.return_value = archive
        archive_id = uuid.uuid4()
        service.get_archive.return_value.archive_id = archive_id
        response = client.get(f"/api/v1/archive/entries/{archive_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["is_stale"] is True
        assert data["stale_reason"] == "expired"
        assert data["stale_since"] == "2026-08-15T00:00:00+00:00"

    def test_response_contains_staleness_fields_defaults(self) -> None:
        """ArchiveResponse 无陈旧标记时默认 is_stale=False"""
        client, service = _make_app()
        archive_id = uuid.uuid4()
        service.get_archive.return_value = _make_archive({"archive_id": archive_id})
        response = client.get(f"/api/v1/archive/entries/{archive_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["is_stale"] is False
        assert data["stale_reason"] is None
        assert data["stale_since"] is None
