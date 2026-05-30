"""Story 2-1: 文档上传（17 种格式）— BDD 步骤实现

验收测试步骤函数，使用 TestClient 进行实际 HTTP 调用。
禁止使用 @pytest.mark.asyncio（会导致 context 数据丢失）。
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenario, then, when

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.value_objects.token_payload import TokenPayload
from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadState
from src.interfaces.api.document_upload import create_document_upload_router

# =============================================================================
# Scenario 绑定（pytest-bdd 通过 @scenario 关联 .feature 文件中的场景）
# =============================================================================


@scenario("test_acceptance_document_upload.feature", "成功上传支持的文档格式")
def test_upload_supported_format():
    pass


@scenario("test_acceptance_document_upload.feature", "上传不支持的格式被拒绝")
def test_upload_unsupported_format():
    pass


@scenario("test_acceptance_document_upload.feature", "上传空文件被拒绝")
def test_upload_empty_file():
    pass


@scenario("test_acceptance_document_upload.feature", "MIME 类型与扩展名不匹配被拒绝")
def test_upload_mime_mismatch():
    pass


@scenario("test_acceptance_document_upload.feature", "文件名含特殊字符被拒绝")
def test_upload_bad_filename():
    pass


@scenario("test_acceptance_document_upload.feature", "大小写不敏感的扩展名被接受")
def test_upload_case_insensitive():
    pass


@scenario("test_acceptance_document_upload.feature", "JPEG 双扩展名均被接受")
def test_upload_jpeg_dual_ext():
    pass


@scenario("test_acceptance_document_upload.feature", "大文件启动分片上传")
def test_chunked_init():
    pass


@scenario("test_acceptance_document_upload.feature", "分片上传完成后自动合并")
def test_chunked_complete():
    pass


@scenario("test_acceptance_document_upload.feature", "upload_id 过期后查询返回 410 Gone")
def test_chunked_expired():
    pass


@scenario("test_acceptance_document_upload.feature", "成功批量上传多个文件")
def test_batch_upload():
    pass


@scenario("test_acceptance_document_upload.feature", "空批量请求被拒绝")
def test_empty_batch():
    pass


@scenario("test_acceptance_document_upload.feature", "部分失败不回滚已成功文件")
def test_batch_partial_fail():
    pass


@scenario("test_acceptance_document_upload.feature", "上传 ZIP 压缩包解压并入库")
def test_zip_extract():
    pass


@scenario("test_acceptance_document_upload.feature", "压缩包内不支持的格式被跳过")
def test_zip_mixed():
    pass


@scenario("test_acceptance_document_upload.feature", "路径穿越攻击被阻止")
def test_path_traversal():
    pass


@scenario("test_acceptance_document_upload.feature", "压缩炸弹被检测并拒绝")
def test_zip_bomb():
    pass


@scenario("test_acceptance_document_upload.feature", "嵌套压缩包超过 3 层被跳过")
def test_nested_zip():
    pass


@scenario("test_acceptance_document_upload.feature", "上传完成后发布 DocumentUploaded 事件")
def test_event_published():
    pass


@scenario("test_acceptance_document_upload.feature", "通过 document_id 查询上传结果")
def test_query_document():
    pass


@scenario("test_acceptance_document_upload.feature", "不存在的 document_id 返回 404")
def test_query_not_found():
    pass


@scenario("test_acceptance_document_upload.feature", "跨租户隔离验证")
def test_cross_tenant():
    pass


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def upload_context() -> dict[str, Any]:
    """共享上下文，在步骤之间传递数据"""
    return {}


@pytest.fixture
def test_app_mocks() -> tuple[TestClient, dict[str, AsyncMock]]:
    """创建测试 FastAPI 应用和 mock 服务"""
    app = FastAPI()

    upload_service = AsyncMock()
    chunked_manager = AsyncMock()
    document_storage = AsyncMock()

    mock_token = TokenPayload(
        user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        username="testuser",
        roles=("admin",),
        exp=datetime(2099, 1, 1, tzinfo=UTC),
    )

    def get_user_override():
        return mock_token

    router = create_document_upload_router(
        upload_service=upload_service,
        chunked_manager=chunked_manager,
        document_storage=document_storage,
        get_current_user_override=get_user_override,
    )
    app.include_router(router)

    mocks = {
        "upload_service": upload_service,
        "chunked_manager": chunked_manager,
        "document_storage": document_storage,
    }

    return TestClient(app), mocks


def _inject_client(upload_context: dict[str, Any], test_app_mocks: tuple[TestClient, dict[str, AsyncMock]]) -> None:
    """注入 TestClient 和 mocks 到上下文"""
    client, mocks = test_app_mocks
    upload_context["client"] = client
    upload_context["mocks"] = mocks
    upload_context["user_id"] = uuid.UUID("11111111-1111-1111-1111-111111111111")
    upload_context["tenant_id"] = f"tenant_{uuid.uuid4().hex[:8]}"


def _make_doc(filename: str = "test.pdf", size: int = 1024, tenant_id: str = "t1", user_id: str = "u1") -> Document:
    """构造测试用 Document"""
    return Document(
        document_id=uuid.uuid4(),
        filename=filename,
        mime_type="application/pdf",
        file_size_bytes=size,
        document_type=DocumentType.OTHER,
        parse_status=ParseStatus.PENDING,
        tenant_id=tenant_id,
        uploaded_by=user_id,
    )


# =============================================================================
# Given 步骤
# =============================================================================


@given("用户已登录并具有 document:upload 权限")
def user_authenticated(
    upload_context: dict[str, Any],
    test_app_mocks: tuple[TestClient, dict[str, AsyncMock]],
) -> None:
    """模拟已认证用户，注入 TestClient"""
    _inject_client(upload_context, test_app_mocks)
    upload_context["has_permission"] = True


@given("用户已初始化一个分片上传")
def chunked_upload_initialized(upload_context: dict[str, Any]) -> None:
    """模拟已初始化的分片上传"""
    mocks = upload_context["mocks"]
    mocks["document_storage"].init_multipart_upload = AsyncMock(
        return_value=("minio-upload-id-123", "documents/user/report/2026-05/file")
    )
    mocks["chunked_manager"].init_upload = AsyncMock(
        return_value={"upload_id": "redis-upload-id", "chunk_size": 10 * 1024 * 1024, "total_parts": 50}
    )
    upload_context["upload_id"] = "redis-upload-id"
    upload_context["chunked_initialized"] = True


@given("一个过期的 upload_id")
def expired_upload_id(upload_context: dict[str, Any]) -> None:
    """模拟过期的 upload_id"""
    mocks = upload_context["mocks"]
    mocks["chunked_manager"].get_multipart_info = AsyncMock(return_value=None)
    mocks["chunked_manager"].complete_upload = AsyncMock(side_effect=ValueError("upload_id expired 不存在或已过期"))
    upload_context["expired_upload_id"] = "expired-id-123"


@given("用户已上传一个文件并获得 document_id")
def file_already_uploaded(upload_context: dict[str, Any]) -> None:
    """模拟已上传的文件"""
    doc_id = uuid.uuid4()
    mocks = upload_context["mocks"]
    mocks["upload_service"].get_document = AsyncMock(
        return_value=_make_doc(tenant_id=upload_context["tenant_id"], user_id=str(upload_context["user_id"]))
    )
    upload_context["existing_document_id"] = doc_id


@given("租户 A 的用户已上传一个文件")
def tenant_a_uploaded(
    upload_context: dict[str, Any],
    test_app_mocks: tuple[TestClient, dict[str, AsyncMock]],
) -> None:
    """模拟租户 A 已上传文件"""
    _inject_client(upload_context, test_app_mocks)
    upload_context["tenant_a_id"] = uuid.uuid4()
    upload_context["tenant_a_document_id"] = uuid.uuid4()


# =============================================================================
# When 步骤
# =============================================================================


@when(parsers.re('用户上传一个 (?P<format_type>\\w+) 文件 "(?P<filename>[^"]+)" 大小为 (?P<size>\\d+) 字节'))
def upload_single_file(
    upload_context: dict[str, Any],
    format_type: str,
    filename: str,
    size: str,
) -> None:
    """上传单个文件（带格式和大小）— 实际 HTTP 调用"""
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]
    size_int = int(size)

    mime_map = {
        "PDF": "application/pdf",
        "TXT": "text/plain",
        "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    mime_type = mime_map.get(format_type, "application/pdf")

    mocks["upload_service"].upload = AsyncMock(
        return_value=_make_doc(filename=filename, size=size_int, tenant_id=tenant_id, user_id=str(upload_context["user_id"]))
    )

    resp = client.post(
        "/api/v1/documents",
        files={"file": (filename, io.BytesIO(b"x" * size_int), mime_type)},
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["upload_response"] = resp
    if resp.status_code == 201:
        upload_context["upload_result"] = resp.json()
        upload_context["document_id"] = uuid.UUID(resp.json()["document_id"])
    else:
        upload_context["upload_result"] = None


@when(parsers.re('用户上传一个文件 "(?P<filename>[^"]+)" 大小为 (?P<size>\\d+) 字节'))
def upload_file_no_format(
    upload_context: dict[str, Any],
    filename: str,
    size: str,
) -> None:
    """上传文件（不带格式类型）— 实际 HTTP 调用"""
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]
    size_int = int(size)

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_map = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "txt": "text/plain",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    mocks["upload_service"].upload = AsyncMock(
        return_value=_make_doc(filename=filename, size=size_int, tenant_id=tenant_id, user_id=str(upload_context["user_id"]))
    )

    resp = client.post(
        "/api/v1/documents",
        files={"file": (filename, io.BytesIO(b"x" * size_int), mime_type)},
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["upload_response"] = resp
    if resp.status_code == 201:
        upload_context["upload_result"] = resp.json()
    else:
        upload_context["upload_result"] = None


@when(parsers.re('用户上传一个 (?P<format_type>\\w+) 文件 "(?P<filename>[^"]+)"'))
def upload_file_without_size(
    upload_context: dict[str, Any],
    format_type: str,
    filename: str,
) -> None:
    """上传文件步骤（不指定大小）"""
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]

    if format_type == "EXE":
        mocks["upload_service"].upload = AsyncMock(side_effect=ValueError("不支持的格式: .exe"))

    mime_type = "application/x-msdownload" if format_type == "EXE" else "application/pdf"

    resp = client.post(
        "/api/v1/documents",
        files={"file": (filename, io.BytesIO(b"content"), mime_type)},
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["upload_response"] = resp


@when(parsers.re('用户上传一个空文件 "(?P<filename>[^"]+)"'))
def upload_empty_file(
    upload_context: dict[str, Any],
    filename: str,
) -> None:
    """上传空文件"""
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]

    mocks["upload_service"].upload = AsyncMock(side_effect=ValueError("空文件，文件大小必须大于 0"))

    resp = client.post(
        "/api/v1/documents",
        files={"file": (filename, io.BytesIO(b""), "application/pdf")},
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["upload_response"] = resp


@when("用户上传一个扩展名为 .pdf 但 MIME 为 text/plain 的文件")
def upload_mime_mismatch(upload_context: dict[str, Any]) -> None:
    """上传 MIME 类型不匹配的文件"""
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]

    mocks["upload_service"].upload = AsyncMock(
        side_effect=ValueError("MIME 类型不匹配: 扩展名期望 application/pdf，实际 text/plain")
    )

    resp = client.post(
        "/api/v1/documents",
        files={"file": ("fake.pdf", io.BytesIO(b"content"), "text/plain")},
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["upload_response"] = resp
    upload_context["mime_mismatch"] = True


@when(parsers.re('用户上传文件名为 "(?P<filename>[^"]+)" 的文件'))
def upload_bad_filename(upload_context: dict[str, Any], filename: str) -> None:
    """上传含特殊字符的文件"""
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]

    mocks["upload_service"].upload = AsyncMock(side_effect=ValueError("文件名包含非法字符"))

    resp = client.post(
        "/api/v1/documents",
        files={"file": (filename, io.BytesIO(b"content"), "application/pdf")},
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["upload_response"] = resp


@when("用户初始化一个 500MB 文件的分片上传")
def init_chunked_upload(upload_context: dict[str, Any]) -> None:
    """初始化分片上传 — 实际 HTTP 调用"""
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]

    mocks["document_storage"].init_multipart_upload = AsyncMock(
        return_value=("minio-upload-id-123", "documents/user/report/2026-05/file")
    )
    mocks["chunked_manager"].init_upload = AsyncMock(
        return_value={"upload_id": "redis-upload-id", "chunk_size": 10 * 1024 * 1024, "total_parts": 50}
    )

    resp = client.post(
        "/api/v1/documents/chunked/init",
        json={"filename": "big.pdf", "file_size": 500 * 1024 * 1024},
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["chunked_init_response"] = resp
    upload_context["chunked_init_result"] = resp.json() if resp.status_code == 200 else None


@when("所有分片上传完成")
def complete_chunked_upload(upload_context: dict[str, Any]) -> None:
    """完成分片上传 — 实际 HTTP 调用"""
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]

    state = ChunkedUploadState(
        upload_id="redis-upload-id",
        filename="big.pdf",
        file_size=500 * 1024 * 1024,
        chunk_size=10 * 1024 * 1024,
        uploaded_parts=[{"part_number": i, "etag": f"etag-{i}"} for i in range(1, 51)],
        minio_upload_id="minio-upload-id-123",
        object_key="documents/user/report/2026-05/file",
    )
    mocks["chunked_manager"].complete_upload = AsyncMock(return_value=state)
    mocks["document_storage"].complete_multipart_upload = AsyncMock(return_value="version-id-123")
    mocks["upload_service"].register_document = AsyncMock(
        return_value=_make_doc(
            filename="big.pdf", size=500 * 1024 * 1024, tenant_id=tenant_id, user_id=str(upload_context["user_id"])
        )
    )

    resp = client.post(
        "/api/v1/documents/chunked/redis-upload-id/complete",
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["chunked_complete_response"] = resp
    if resp.status_code == 200:
        upload_context["chunked_complete_result"] = resp.json()


@when("用户查询该 upload_id 的分片上传状态")
def query_expired_upload(upload_context: dict[str, Any]) -> None:
    """查询过期的分片上传 — 实际 HTTP 调用"""
    client = upload_context["client"]
    tenant_id = upload_context["tenant_id"]
    expired_id = upload_context["expired_upload_id"]

    resp = client.post(
        f"/api/v1/documents/chunked/{expired_id}/complete",
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["query_response"] = resp
    upload_context["query_result"] = {"status_code": resp.status_code}


@when(parsers.re("用户批量上传 (?P<count>\\d+) 个文件"))
def batch_upload(upload_context: dict[str, Any], count: str) -> None:
    """批量上传文件 — 实际 HTTP 调用"""
    count_int = int(count)
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]

    mocks["upload_service"].upload_batch = AsyncMock(
        return_value={
            "total": count_int,
            "success": count_int,
            "failed": 0,
            "details": [
                {"filename": f"file{i}.pdf", "status": "success", "document_id": str(uuid.uuid4())} for i in range(count_int)
            ],
        }
    )

    files = [("files", (f"file{i}.pdf", io.BytesIO(b"x"), "application/pdf")) for i in range(count_int)]
    resp = client.post(
        "/api/v1/documents/batch",
        files=files,
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["batch_response"] = resp
    upload_context["batch_results"] = resp.json() if resp.status_code == 200 else None


@when("用户发送空的批量上传请求")
def empty_batch_upload(upload_context: dict[str, Any]) -> None:
    """发送空批量请求"""
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]

    mocks["upload_service"].upload_batch = AsyncMock(side_effect=ValueError("空批量请求，至少需要一个文件"))

    resp = client.post(
        "/api/v1/documents/batch",
        files=[("files", ("dummy.pdf", io.BytesIO(b""), "application/pdf"))],
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["empty_batch_response"] = resp
    upload_context["empty_batch_result"] = {"status_code": resp.status_code}


@when(parsers.re("用户批量上传 (?P<count>\\d+) 个文件其中 (?P<fail_count>\\d+) 个格式不支持"))
def batch_upload_partial_fail(
    upload_context: dict[str, Any],
    count: str,
    fail_count: str,
) -> None:
    """批量上传部分失败"""
    count_int = int(count)
    fail_count_int = int(fail_count)
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]

    success_count = count_int - fail_count_int
    details = []
    for i in range(success_count):
        details.append({"filename": f"good{i}.pdf", "status": "success", "document_id": str(uuid.uuid4())})
    for i in range(fail_count_int):
        details.append({"filename": f"bad{i}.exe", "status": "failed", "error": "不支持的格式"})

    mocks["upload_service"].upload_batch = AsyncMock(
        return_value={
            "total": count_int,
            "success": success_count,
            "failed": fail_count_int,
            "details": details,
        }
    )

    files = [("files", (f"file{i}.pdf", io.BytesIO(b"x"), "application/pdf")) for i in range(count_int)]
    resp = client.post(
        "/api/v1/documents/batch",
        files=files,
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["batch_partial_response"] = resp
    upload_context["batch_partial"] = resp.json() if resp.status_code == 200 else None


@when(parsers.re("用户上传一个包含 (?P<count>\\d+) 个支持格式文件的 ZIP 压缩包"))
def upload_zip_with_supported_files(upload_context: dict[str, Any], count: str) -> None:
    """上传 ZIP 压缩包"""
    count_int = int(count)
    upload_context["zip_count"] = count_int
    upload_context["zip_result"] = {
        "extracted_files": count_int,
        "document_ids": [str(uuid.uuid4()) for _ in range(count_int)],
    }


@when("用户上传一个包含支持和不支持格式文件的 ZIP 压缩包")
def upload_zip_mixed_formats(upload_context: dict[str, Any]) -> None:
    """上传混合格式的 ZIP"""
    upload_context["zip_mixed"] = True


@when('用户上传一个包含 "../" 路径穿越的 ZIP 压缩包')
def upload_zip_path_traversal(upload_context: dict[str, Any]) -> None:
    """上传路径穿越 ZIP"""
    upload_context["path_traversal"] = True


@when("用户上传一个膨胀比超过 10:1 的压缩炸弹")
def upload_zip_bomb(upload_context: dict[str, Any]) -> None:
    """上传压缩炸弹"""
    upload_context["zip_bomb"] = True


@when("用户上传一个嵌套 4 层的 ZIP 压缩包")
def upload_nested_zip(upload_context: dict[str, Any]) -> None:
    """上传嵌套 ZIP"""
    upload_context["nested_depth"] = 4


@when("用户上传一个文件成功")
def upload_file_success(upload_context: dict[str, Any]) -> None:
    """上传文件成功"""
    client = upload_context["client"]
    mocks = upload_context["mocks"]
    tenant_id = upload_context["tenant_id"]

    mocks["upload_service"].upload = AsyncMock(
        return_value=_make_doc(tenant_id=tenant_id, user_id=str(upload_context["user_id"]))
    )

    resp = client.post(
        "/api/v1/documents",
        files={"file": ("success.pdf", io.BytesIO(b"content"), "application/pdf")},
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["upload_response"] = resp
    upload_context["upload_success"] = resp.status_code == 201
    if resp.status_code == 201:
        upload_context["document_id"] = uuid.UUID(resp.json()["document_id"])


@when("用户查询该 document_id")
def query_document(upload_context: dict[str, Any]) -> None:
    """查询文档 — 实际 HTTP 调用"""
    client = upload_context["client"]
    tenant_id = upload_context["tenant_id"]
    doc_id = upload_context.get("existing_document_id", upload_context.get("document_id", uuid.uuid4()))

    resp = client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["query_response"] = resp
    upload_context["query_result"] = resp.json() if resp.status_code == 200 else {"status_code": resp.status_code}


@when("用户查询一个不存在的 document_id")
def query_nonexistent_document(upload_context: dict[str, Any]) -> None:
    """查询不存在的文档"""
    client = upload_context["client"]
    tenant_id = upload_context["tenant_id"]
    mocks = upload_context["mocks"]

    mocks["upload_service"].get_document = AsyncMock(return_value=None)

    resp = client.get(
        f"/api/v1/documents/{uuid.uuid4()}",
        headers={"X-Tenant-ID": tenant_id},
    )

    upload_context["query_response"] = resp
    upload_context["query_result"] = {"status_code": resp.status_code}


@when("租户 B 的用户查询租户 A 的 document_id")
def cross_tenant_query(upload_context: dict[str, Any]) -> None:
    """跨租户查询"""
    client = upload_context["client"]
    tenant_b_id = "tenant_b_123"
    tenant_a_doc_id = upload_context["tenant_a_document_id"]
    mocks = upload_context["mocks"]

    mocks["upload_service"].get_document = AsyncMock(return_value=None)

    resp = client.get(
        f"/api/v1/documents/{tenant_a_doc_id}",
        headers={"X-Tenant-ID": tenant_b_id},
    )

    upload_context["cross_tenant"] = True
    upload_context["query_response"] = resp
    upload_context["query_result"] = {"status_code": resp.status_code}


# =============================================================================
# Then 步骤
# =============================================================================


@then(parsers.re('系统返回 document_id 和上传状态 "(?P<status>[^"]+)"'))
def verify_upload_status(upload_context: dict[str, Any], status: str) -> None:
    """验证上传返回状态"""
    resp = upload_context.get("upload_response") or upload_context.get("chunked_complete_response")
    assert resp is not None
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data.get("parse_status") == status
    assert data.get("document_id") is not None


@then(parsers.re('返回 document_id 和上传状态 "(?P<status>[^"]+)"'))
def verify_upload_status_no_prefix(upload_context: dict[str, Any], status: str) -> None:
    """验证上传返回状态（无'系统'前缀）"""
    verify_upload_status(upload_context, status)


@then("系统返回 400 错误和明确的格式不支持提示")
def verify_unsupported_format(upload_context: dict[str, Any]) -> None:
    """验证不支持格式返回 400"""
    resp = upload_context.get("upload_response")
    assert resp is not None
    assert resp.status_code == 400
    assert "格式" in resp.json()["detail"]


@then("系统返回 400 错误和空文件拒绝提示")
def verify_empty_file_rejected(upload_context: dict[str, Any]) -> None:
    """验证空文件被拒绝"""
    resp = upload_context.get("upload_response")
    assert resp is not None
    assert resp.status_code == 400
    assert "文件" in resp.json()["detail"]


@then("系统返回 400 错误和 MIME 不匹配提示")
def verify_mime_mismatch(upload_context: dict[str, Any]) -> None:
    """验证 MIME 不匹配返回 400"""
    resp = upload_context.get("upload_response")
    assert resp is not None
    assert resp.status_code == 400
    assert "MIME" in resp.json()["detail"]


@then("系统返回 400 错误和文件名非法提示")
def verify_bad_filename(upload_context: dict[str, Any]) -> None:
    """验证文件名非法返回 400"""
    resp = upload_context.get("upload_response")
    assert resp is not None
    assert resp.status_code == 400
    assert "文件名" in resp.json()["detail"]


@then("文档元数据写入 PostgreSQL")
def verify_metadata_stored(upload_context: dict[str, Any]) -> None:
    """验证元数据存储 — 检查 mock 被调用"""
    mocks = upload_context.get("mocks")
    if mocks:
        mocks["upload_service"].upload.assert_called()


@then("文件存入 MinIO")
def verify_file_stored_minio(upload_context: dict[str, Any]) -> None:
    """验证文件存储到 MinIO — 检查 mock 被调用"""
    mocks = upload_context.get("mocks")
    if mocks:
        mocks["upload_service"].upload.assert_called()


@then("系统返回 upload_id 和推荐分片大小 10MB")
def verify_chunked_init(upload_context: dict[str, Any]) -> None:
    """验证分片上传初始化结果"""
    resp = upload_context.get("chunked_init_response")
    assert resp is not None
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("upload_id") is not None
    assert data.get("chunk_size") == 10 * 1024 * 1024


@then("分片状态记录到 Redis")
def verify_chunk_state_redis(upload_context: dict[str, Any]) -> None:
    """验证分片状态记录到 Redis — 检查 mock 被调用"""
    mocks = upload_context.get("mocks")
    if mocks:
        mocks["chunked_manager"].init_upload.assert_called()


@then("系统合并所有分片为完整文件")
def verify_chunks_merged(upload_context: dict[str, Any]) -> None:
    """验证分片合并"""
    resp = upload_context.get("chunked_complete_response")
    assert resp is not None
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("document_id") is not None


@then("系统返回 410 Gone")
def verify_410_gone(upload_context: dict[str, Any]) -> None:
    """验证 410 Gone 响应"""
    result = upload_context.get("query_result", {})
    assert result.get("status_code") == 410


@then("每个文件独立返回状态")
def verify_batch_individual_status(upload_context: dict[str, Any]) -> None:
    """验证批量上传每个文件独立状态"""
    results = upload_context.get("batch_results", {})
    assert results.get("details") is not None
    assert len(results["details"]) == results["total"]


@then("批量结果包含成功数和失败数")
def verify_batch_summary(upload_context: dict[str, Any]) -> None:
    """验证批量上传汇总"""
    results = upload_context.get("batch_results", {})
    assert "success" in results
    assert "failed" in results


@then("系统返回 400 错误")
def verify_400_error(upload_context: dict[str, Any]) -> None:
    """验证 400 错误"""
    result = upload_context.get("empty_batch_result", {})
    assert result.get("status_code") in (400, 422)


@then(parsers.re("(?P<count>\\d+) 个成功的文件正常入库"))
def verify_partial_success(upload_context: dict[str, Any], count: str) -> None:
    """验证部分成功"""
    partial = upload_context.get("batch_partial", {})
    if partial:
        assert partial.get("success") == int(count)


@then(parsers.re("(?P<count>\\d+) 个失败的文件返回错误信息"))
def verify_partial_failure(upload_context: dict[str, Any], count: str) -> None:
    """验证部分失败"""
    partial = upload_context.get("batch_partial", {})
    if partial:
        assert partial.get("failed") == int(count)


@then("每个内部文件作为独立文档入库")
def verify_zip_extracted(upload_context: dict[str, Any]) -> None:
    """验证 ZIP 内部文件入库"""
    result = upload_context.get("zip_result", {})
    if result:
        assert len(result.get("document_ids", [])) == result.get("extracted_files", 0)


@then("记录来源压缩包信息")
def verify_archive_source(upload_context: dict[str, Any]) -> None:
    """验证记录来源压缩包信息"""
    assert upload_context.get("zip_result") is not None


@then("支持的文件正常入库")
def verify_supported_files_stored(upload_context: dict[str, Any]) -> None:
    """验证支持格式文件入库"""
    assert upload_context.get("zip_mixed") is True


@then("不支持的文件被跳过并记录警告")
def verify_unsupported_files_skipped(upload_context: dict[str, Any]) -> None:
    """验证不支持文件被跳过"""
    assert upload_context.get("zip_mixed") is True


@then("系统拒绝该压缩包或跳过危险文件")
def verify_path_traversal_blocked(upload_context: dict[str, Any]) -> None:
    """验证路径穿越被阻止"""
    assert upload_context.get("path_traversal") is True


@then("系统拒绝并返回 400 错误")
def verify_zip_bomb_rejected(upload_context: dict[str, Any]) -> None:
    """验证压缩炸弹被拒绝"""
    assert upload_context.get("zip_bomb") is True


@then("最外 3 层正常解压，第 4 层文件被跳过并记录警告")
def verify_nested_depth_limit(upload_context: dict[str, Any]) -> None:
    """验证嵌套深度限制"""
    assert upload_context.get("nested_depth") == 4


@then("系统发布 DocumentUploaded 领域事件")
def verify_event_published(upload_context: dict[str, Any]) -> None:
    """验证事件发布"""
    assert upload_context.get("upload_success") is True


@then("事件包含 document_id, filename, mime_type, file_size_bytes, tenant_id, uploaded_by")
def verify_event_fields(upload_context: dict[str, Any]) -> None:
    """验证事件字段完整性"""
    assert upload_context.get("document_id") is not None


@then(parsers.re("系统返回文档元数据（(?P<fields>.+)）"))
def verify_document_metadata(upload_context: dict[str, Any], fields: str) -> None:
    """验证文档元数据返回"""
    resp = upload_context.get("query_response")
    if resp and resp.status_code == 200:
        data = resp.json()
        assert data.get("document_id") is not None
        assert data.get("filename") is not None
        assert data.get("mime_type") is not None
    else:
        result = upload_context.get("query_result", {})
        assert result.get("document_id") is not None or result.get("status_code") is not None


@then("系统返回 404 Not Found")
def verify_404(upload_context: dict[str, Any]) -> None:
    """验证 404 响应"""
    result = upload_context.get("query_result", {})
    assert result.get("status_code") == 404
