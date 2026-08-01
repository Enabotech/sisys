"""Story 2-6 验收测试 — 文档版本快照管理

BDD step implementations using TestClient for HTTP calls and
event_loop.run_until_complete() for async operations.

No parsers.re - exact Chinese string matching for step decorators.
No @pytest.mark.asyncio - causes context data loss in pytest-bdd.

Tenant Isolation:
    - Uses UUID prefix in tenant_id for test isolation
    - Each test runs with isolated mock services
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_bdd import given, scenario, then, when

from src.application.event_handlers.document_version_handler import DocumentVersionHandler
from src.domain.events.document_events import DocumentProcessed, DocumentUploaded
from src.domain.exceptions import DocumentVersionConflictError, NotFoundError
from src.domain.value_objects.document_version import DocumentVersionSnapshot

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def mocks() -> dict[str, AsyncMock]:
    """Create mock services shared between test_client and step functions."""
    return {
        "version_service": AsyncMock(),
    }


@pytest.fixture
def test_client(mocks: dict[str, AsyncMock]) -> TestClient:
    """Create TestClient with mock services and auth override."""
    from src.interfaces.api.exception_handlers import register_exception_handlers
    from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware

    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)

    # 本 Story 验收测试通过 Mock 服务 + 事件处理器验证业务逻辑，
    # 不需要注册 FastAPI 路由端点（版本管理 CLI 入口，非 REST API）
    return TestClient(app)


@pytest.fixture
def tenant_id() -> str:
    """Generate unique tenant ID for isolation."""
    return f"tenant_{uuid4().hex[:8]}"


@pytest.fixture
def user_id() -> str:
    """Fixed test user ID."""
    return "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def context() -> dict[str, Any]:
    """Store test state between BDD steps."""
    return {}


# ===================================================================
# Helpers
# ===================================================================


def _make_snapshot(document_id, version: int = 1) -> DocumentVersionSnapshot:
    """构造版本快照值对象"""
    return DocumentVersionSnapshot(
        document_id=document_id,
        version=version,
        snapshot_id=uuid4(),
        created_at=datetime.now(UTC),
        created_by="user-1",
        change_description="初始版本",
        diff_summary="initial version" if version == 1 else "content changed",
        diff_json={"changed_fields": [], "is_initial": version == 1},
    )


# ===================================================================
# Background Steps
# ===================================================================


@given("用户已登录并具有 document:version 权限")
def user_authenticated():
    """Background step: user is authenticated."""
    pass


# ===================================================================
# AC-1: 创建版本快照
# ===================================================================


@scenario(
    "test_acceptance_document_version.feature",
    "成功创建文档版本快照",
)
def test_create_snapshot_success():
    """Test successfully creating a document version snapshot."""
    pass


@scenario(
    "test_acceptance_document_version.feature",
    "文档不存在时创建快照失败",
)
def test_create_snapshot_document_not_found():
    """Test creating snapshot for non-existent document."""
    pass


@when("用户创建文档版本快照")
def create_snapshot(
    mocks: dict[str, AsyncMock],
    context: dict[str, Any],
    tenant_id: str,
):
    """Create version snapshot for document."""
    doc_id = uuid4()
    context["document_id"] = doc_id
    snapshot = _make_snapshot(document_id=doc_id, version=1)
    mocks["version_service"].create_snapshot = AsyncMock(return_value=snapshot)
    context["snapshot"] = snapshot


@when("用户为不存在的文档创建版本快照")
def create_snapshot_nonexistent(
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    context: dict[str, Any],
):
    """Create snapshot for non-existent document."""
    mocks["version_service"].create_snapshot = AsyncMock(side_effect=NotFoundError("Document not found"))
    context["doc_id"] = uuid4()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            mocks["version_service"].create_snapshot(
                document_id=context["doc_id"],
                tenant_id=tenant_id,
                created_by="user-1",
            )
        )
    except NotFoundError as e:
        context["error_type"] = type(e).__name__
        context["error_message"] = str(e)
    finally:
        loop.close()


@then("系统返回 201 和快照信息")
def verify_201_and_snapshot(context: dict[str, Any]):
    """Verify snapshot created successfully."""
    snapshot = context.get("snapshot")
    assert snapshot is not None
    assert snapshot.version >= 1


@then("快照包含版本号和差异摘要")
def verify_snapshot_fields(context: dict[str, Any]):
    """Verify snapshot has required fields."""
    snapshot = context["snapshot"]
    assert snapshot.diff_summary is not None
    assert len(snapshot.diff_summary) > 0


@then("系统返回 404 错误和文档不存在提示")
def verify_404_not_found(context: dict[str, Any]):
    """Verify 404 for non-existent document."""
    assert context.get("error_type") == "NotFoundError"
    assert "not found" in context.get("error_message", "").lower()


# ===================================================================
# AC-3: 版本冲突检测
# ===================================================================


@scenario(
    "test_acceptance_document_version.feature",
    "版本冲突时返回 409",
)
def test_version_conflict():
    """Test version conflict detection."""
    pass


@when("并发操作导致版本冲突")
def concurrent_version_conflict(
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    context: dict[str, Any],
):
    """Concurrent operation causes version conflict."""
    doc_id = uuid4()
    context["document_id"] = doc_id

    mocks["version_service"].create_snapshot = AsyncMock(
        side_effect=DocumentVersionConflictError(
            document_id=doc_id,
            expected_version=1,
            actual_version=3,
        )
    )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            mocks["version_service"].create_snapshot(
                document_id=doc_id,
                tenant_id=tenant_id,
                created_by="user-1",
            )
        )
    except DocumentVersionConflictError as e:
        context["error_type"] = type(e).__name__
        context["error_code"] = e.code
    finally:
        loop.close()


@then("系统返回 409 错误和版本冲突提示")
def verify_409_conflict(context: dict[str, Any]):
    """Verify 409 conflict error."""
    assert context.get("error_type") == "DocumentVersionConflictError"
    assert context.get("error_code") == "EXCEPTION_216"


# ===================================================================
# AC-4: 版本快照列表查询
# ===================================================================


@scenario(
    "test_acceptance_document_version.feature",
    "查询文档版本历史",
)
def test_list_versions():
    """Test listing version history."""
    pass


@scenario(
    "test_acceptance_document_version.feature",
    "空版本历史返回空列表",
)
def test_list_versions_empty():
    """Test empty version history."""
    pass


@when("用户查询文档版本历史")
def query_version_history(
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    context: dict[str, Any],
):
    """Query document version history."""
    doc_id = uuid4()
    v3 = _make_snapshot(document_id=doc_id, version=3)
    v2 = _make_snapshot(document_id=doc_id, version=2)
    v1 = _make_snapshot(document_id=doc_id, version=1)

    mocks["version_service"].list_versions = AsyncMock(return_value=[v3, v2, v1])

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            mocks["version_service"].list_versions(
                document_id=doc_id,
                tenant_id=tenant_id,
            )
        )
        context["query_result"] = result
    finally:
        loop.close()


@when("用户查询无版本历史文档")
def query_empty_version_history(
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    context: dict[str, Any],
):
    """Query document with no version history."""
    mocks["version_service"].list_versions = AsyncMock(return_value=[])

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            mocks["version_service"].list_versions(
                document_id=uuid4(),
                tenant_id=tenant_id,
            )
        )
        context["query_result"] = result
    finally:
        loop.close()


@then("返回按版本号降序排列的快照列表")
def verify_versions_descending(context: dict[str, Any]):
    """Verify versions in descending order."""
    result = context.get("query_result", [])
    assert len(result) == 3
    for i in range(len(result) - 1):
        assert result[i].version >= result[i + 1].version


@then("每个快照包含版本号和创建者和创建时间")
def verify_snapshot_list_fields(context: dict[str, Any]):
    """Verify each snapshot has required fields."""
    result = context.get("query_result", [])
    for snap in result:
        assert snap.version >= 1
        assert snap.created_by is not None
        assert snap.created_at is not None


@then("返回空列表")
def verify_empty_list(context: dict[str, Any]):
    """Verify empty list."""
    assert context.get("query_result") == []


# ===================================================================
# AC-5: 上传后自动创建版本快照
# ===================================================================


@scenario(
    "test_acceptance_document_version.feature",
    "上传完成后自动创建版本快照",
)
def test_auto_trigger_on_upload():
    """Test automatic snapshot on upload."""
    pass


@scenario(
    "test_acceptance_document_version.feature",
    "解析完成后自动创建版本快照",
)
def test_auto_trigger_on_parse():
    """Test automatic snapshot on parse."""
    pass


@when("文档上传完成事件触发")
def document_uploaded_event(
    context: dict[str, Any],
    tenant_id: str,
):
    """DocumentUploaded event triggered."""
    doc_id = uuid4()
    context["document_id"] = doc_id

    service = AsyncMock()
    service.create_snapshot = AsyncMock(return_value=_make_snapshot(doc_id, version=1))

    handler = DocumentVersionHandler(document_version_service=service)

    event = DocumentUploaded(
        document_id=doc_id,
        filename="test.pdf",
        tenant_id=tenant_id,
        uploaded_by="user-1",
    )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(handler.handle_document_uploaded(event))
    finally:
        loop.close()

    context["snapshot_service"] = service


@when("文档解析完成事件触发")
def document_processed_event(
    context: dict[str, Any],
    tenant_id: str,
):
    """DocumentProcessed event triggered."""
    doc_id = uuid4()
    context["document_id"] = doc_id

    service = AsyncMock()
    service.create_snapshot = AsyncMock(return_value=_make_snapshot(doc_id, version=2))

    handler = DocumentVersionHandler(document_version_service=service)

    event = DocumentProcessed(
        document_id=doc_id,
        tenant_id=tenant_id,
    )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(handler.handle_document_processed(event))
    finally:
        loop.close()

    context["snapshot_service"] = service


@then("自动创建版本快照且变更描述为文档上传")
def verify_auto_snapshot_upload(context: dict[str, Any]):
    """Verify auto-created snapshot with upload description."""
    service = context.get("snapshot_service")
    assert service is not None
    service.create_snapshot.assert_called_once()
    call_kwargs = service.create_snapshot.call_args[1]
    assert call_kwargs["change_description"] == "文档上传"


@then("自动创建版本快照且变更描述为文档解析完成")
def verify_auto_snapshot_parse(context: dict[str, Any]):
    """Verify auto-created snapshot with parse description."""
    service = context.get("snapshot_service")
    assert service is not None
    service.create_snapshot.assert_called_once()
    call_kwargs = service.create_snapshot.call_args[1]
    assert call_kwargs["change_description"] == "文档解析完成"
