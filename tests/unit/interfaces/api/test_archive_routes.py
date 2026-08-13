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

    def test_returns_200(self) -> None:
        """返回 200"""
        client, _ = _make_app()
        response = client.post(
            "/api/v1/archive/archive",
            json={
                "plan_id": str(uuid.uuid4()),
                "plan_type": "SP",
                "assumptions": {"key": "value"},
            },
        )
        assert response.status_code == 200

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
