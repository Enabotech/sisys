"""档案有效期管理 API 契约测试

验证 PATCH /api/v1/archive/entries/{archive_id}、GET /api/v1/archive/entries 扩展参数、
POST /api/v1/archive/staleness-checks 的请求/响应结构。
契约测试在实现前（红阶段）失败，实现后（绿阶段）通过。
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
    service.set_validity_period.return_value = _make_archive()
    service.mark_stale_archives.return_value = [_make_archive()]

    mock_user = _make_token()

    def get_user_override():
        return mock_user

    router = create_archive_router(
        archive_service=service,
        get_current_user_override=get_user_override,
    )
    app.include_router(router)

    return TestClient(app), service


class TestArchiveValidityApiContract:
    """档案有效期管理 API 契约"""

    def test_patch_validity_calls_set_validity_period(self) -> None:
        """PATCH /entries/{id} 调用 service.set_validity_period"""
        client, service = _make_app()
        archive_id = uuid.uuid4()
        service.set_validity_period.return_value = _make_archive({"archive_id": archive_id})
        response = client.patch(
            f"/api/v1/archive/entries/{archive_id}",
            json={"valid_from": "2026-01-01T00:00:00Z", "valid_until": "2027-12-31T00:00:00Z"},
        )
        assert response.status_code == 200
        service.set_validity_period.assert_called_once()
        data = response.json()
        assert data["archive_id"] == str(archive_id)
        assert "valid_from" in data
        assert "valid_until" in data

    def test_get_entries_passes_validity_params_to_query(self) -> None:
        """GET /entries 将有效期查询参数传递给 ArchiveQuery"""
        client, service = _make_app()
        response = client.get(
            "/api/v1/archive/entries",
            params={"valid_from": "2026-01-01T00:00:00Z", "valid_until": "2027-12-31T00:00:00Z"},
        )
        assert response.status_code == 200
        service.query_archive.assert_called_once()
        query = service.query_archive.call_args[0][0]
        # 契约：query.valid_from/valid_until 为 timezone-aware datetime
        assert query.valid_from is not None
        assert query.valid_until is not None
        assert query.valid_from.tzinfo is not None
        assert query.valid_until.tzinfo is not None

    def test_get_entries_passes_validity_status(self) -> None:
        """GET /entries 支持 validity_status 参数"""
        client, service = _make_app()
        response = client.get("/api/v1/archive/entries", params={"validity_status": "valid"})
        assert response.status_code == 200
        query = service.query_archive.call_args[0][0]
        assert query.validity_status is not None
        assert query.validity_status.value == "valid"

    def test_post_staleness_checks_calls_mark_stale_archives(self) -> None:
        """POST /staleness-checks 调用 service.mark_stale_archives"""
        client, service = _make_app()
        response = client.post("/api/v1/archive/staleness-checks")
        assert response.status_code == 200
        service.mark_stale_archives.assert_called_once()
        data = response.json()
        assert "marked" in data
        assert isinstance(data["marked"], list)

    def test_archive_response_contains_validity_fields(self) -> None:
        """ArchiveResponse 包含 valid_from/valid_until 字符串字段"""
        client, _ = _make_app()
        response = client.get("/api/v1/archive/entries")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for item in data:
            assert "valid_from" in item
            assert "valid_until" in item
