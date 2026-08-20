"""DomainDictionary API 路由单元测试

测试词典管理 REST API 端点：CRUD、热更新、快照、回滚。
使用 TestClient + mock service 验证请求/响应。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.exceptions import (
    DictionaryEntryConflictError,
    DictionaryNotFoundError,
)
from src.domain.value_objects.token_payload import TokenPayload
from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware


def _make_token(
    user_id: str = "11111111-1111-1111-1111-111111111111",
    username: str = "testuser",
    roles: tuple[str, ...] = ("admin",),
) -> TokenPayload:
    """构造测试用 TokenPayload"""
    return TokenPayload(
        user_id=uuid.UUID(user_id),
        username=username,
        roles=roles,
        exp=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _make_app() -> tuple[TestClient, AsyncMock]:
    """创建带词典路由的测试 FastAPI 应用"""
    from src.interfaces.api.domain_dictionary import create_document_dictionary_router

    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)

    service = AsyncMock()
    mock_user = _make_token()

    def get_user_override():
        return mock_user

    router = create_document_dictionary_router(
        dictionary_service=service,
        get_current_user_override=get_user_override,
    )
    app.include_router(router)

    return TestClient(app), service


# ===================================================================
# GET /entries
# ===================================================================


class TestListEntries:
    """列出词条测试"""

    def test_list_entries_success(self) -> None:
        """正常列出词条返回 200"""
        client, service = _make_app()
        service.list_entries = AsyncMock(return_value=[])
        service.count_entries = AsyncMock(return_value=0)

        resp = client.get("/api/v1/documents/dictionary/entries")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["page"] == 1
        assert data["total"] == 0


# ===================================================================
# POST /entries
# ===================================================================


class TestAddEntry:
    """添加词条测试"""

    def test_add_entry_success(self) -> None:
        """正常添加返回 201"""
        client, service = _make_app()
        service.add_entry = AsyncMock(return_value=_make_mock_entry(term="BLM", entity_type="CONCEPT", version=1))

        resp = client.post(
            "/api/v1/documents/dictionary/entries",
            json={"term": "BLM", "entity_type": "CONCEPT"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["term"] == "BLM"
        assert data["entity_type"] == "CONCEPT"

    def test_add_entry_missing_term(self) -> None:
        """缺少 term 返回 400（RequestValidationError）"""
        client, _ = _make_app()

        resp = client.post(
            "/api/v1/documents/dictionary/entries",
            json={"entity_type": "CONCEPT"},
        )

        assert resp.status_code in (400, 422)

    def test_add_entry_conflict(self) -> None:
        """重复词条返回 409"""
        client, service = _make_app()
        service.add_entry = AsyncMock(side_effect=DictionaryEntryConflictError(term="BLM"))

        resp = client.post(
            "/api/v1/documents/dictionary/entries",
            json={"term": "BLM", "entity_type": "CONCEPT"},
        )

        assert resp.status_code == 409
        data = resp.json()
        assert "EXCEPTION_271" in str(data["error"]["code"])


# ===================================================================
# PUT /entries/{term}
# ===================================================================


class TestUpdateEntry:
    """修改词条测试"""

    def test_update_entry_success(self) -> None:
        """正常修改返回 200"""
        client, service = _make_app()
        service.update_entry = AsyncMock(return_value=_make_mock_entry(term="BLM", entity_type="STRATEGY", version=2))

        resp = client.put(
            "/api/v1/documents/dictionary/entries/BLM",
            json={"entity_type": "STRATEGY", "version": 1},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "STRATEGY"

    def test_update_entry_not_found(self) -> None:
        """修改不存在的词条返回 404"""
        client, service = _make_app()
        service.update_entry = AsyncMock(side_effect=DictionaryNotFoundError(term="不存在的词"))

        resp = client.put(
            "/api/v1/documents/dictionary/entries/不存在的词",
            json={"entity_type": "CONCEPT", "version": 1},
        )

        assert resp.status_code == 404
        data = resp.json()
        assert "EXCEPTION_270" in str(data["error"]["code"])


# ===================================================================
# DELETE /entries/{term}
# ===================================================================


class TestDeleteEntry:
    """删除词条测试"""

    def test_delete_entry_success(self) -> None:
        """正常删除返回 204 No Content"""
        client, service = _make_app()
        service.delete_entry = AsyncMock()

        resp = client.delete("/api/v1/documents/dictionary/entries/BLM")

        assert resp.status_code == 204
        assert not resp.content  # 204 无响应体

    def test_delete_entry_not_found(self) -> None:
        """删除不存在的词条返回 404"""
        client, service = _make_app()
        service.delete_entry = AsyncMock(side_effect=DictionaryNotFoundError(term="不存在的词"))

        resp = client.delete("/api/v1/documents/dictionary/entries/不存在的词")

        assert resp.status_code == 404


# ===================================================================
# POST /refresh
# ===================================================================


class TestRefreshDictionary:
    """热更新测试"""

    def test_refresh_success(self) -> None:
        """触发热更新返回 200"""
        client, service = _make_app()
        service.refresh_dictionary = AsyncMock()

        resp = client.post("/api/v1/documents/dictionary/refresh")

        assert resp.status_code == 200
        data = resp.json()
        assert "热更新" in data["message"]


# ===================================================================
# POST /snapshots
# ===================================================================


class TestCreateSnapshot:
    """创建快照测试"""

    def test_create_snapshot_success(self) -> None:
        """创建快照返回 201"""
        client, service = _make_app()
        service.create_snapshot = AsyncMock(return_value=_make_mock_snapshot(snapshot_id="snap-001", version=1))

        resp = client.post("/api/v1/documents/dictionary/snapshots")

        assert resp.status_code == 201
        data = resp.json()
        assert data["snapshot_id"] == "snap-001"
        assert data["version"] == 1


# ===================================================================
# POST /rollback/{version}
# ===================================================================


class TestRollback:
    """回滚测试"""

    def test_rollback_success(self) -> None:
        """回滚成功返回 200"""
        client, service = _make_app()
        service.rollback = AsyncMock()

        resp = client.post("/api/v1/documents/dictionary/rollback/1")

        assert resp.status_code == 200
        data = resp.json()
        assert "回滚" in data["message"]

    def test_rollback_not_found(self) -> None:
        """回滚到不存在版本返回 404"""
        client, service = _make_app()
        service.rollback = AsyncMock(side_effect=DictionaryNotFoundError(version=99))

        resp = client.post("/api/v1/documents/dictionary/rollback/99")

        assert resp.status_code == 404


# ===================================================================
# 401 Unauthorized (override 为 None)
# ===================================================================


class TestAuth:
    """认证测试"""

    def test_no_auth_override_returns_401(self) -> None:
        """无认证覆盖返回 401"""
        from src.interfaces.api.domain_dictionary import create_document_dictionary_router

        app = FastAPI()
        app.add_middleware(ExceptionContextMiddleware)
        register_exception_handlers(app)

        router = create_document_dictionary_router(
            dictionary_service=AsyncMock(),
            get_current_user_override=None,
        )
        app.include_router(router)
        client = TestClient(app)

        resp = client.get("/api/v1/documents/dictionary/entries")
        assert resp.status_code == 401


# ===================================================================
# Helpers
# ===================================================================


def _make_mock_entry(
    term: str = "BLM",
    entity_type: str = "CONCEPT",
    category: str = "general",
    active: bool = True,
    version: int = 1,
) -> object:
    """创建 mock 词条对象"""
    from types import SimpleNamespace

    return SimpleNamespace(
        term=term,
        entity_type=entity_type,
        category=category,
        active=active,
        version=version,
        created_by="testuser",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )


def _make_mock_snapshot(
    snapshot_id: str = "snap-001",
    version: int = 1,
) -> object:
    """创建 mock 快照对象"""
    from types import SimpleNamespace

    return SimpleNamespace(
        snapshot_id=snapshot_id,
        version=version,
        entries=(),
        created_by="testuser",
        created_at="2026-01-01T00:00:00",
        change_summary={},
    )
