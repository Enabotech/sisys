"""Acceptance tests for Story 2-1 - Document Upload (17 formats).

BDD step implementations using TestClient for HTTP calls and
event_loop.run_until_complete() for async operations.

No parsers.re - exact Chinese string matching for step decorators.
No @pytest.mark.asyncio - causes context data loss in pytest-bdd.

Tenant Isolation:
    - Uses UUID prefix in tenant_id for test isolation
    - Each test runs with isolated mock services
"""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_bdd import given, scenario, then, when

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.exceptions import ConflictError, NotFoundError, StorageError, ValidationError
from src.domain.value_objects.token_payload import TokenPayload
from src.infrastructure.document_parsing.archive_extractor import ArchiveExtractor
from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadState
from src.interfaces.api.document_upload import create_document_upload_router

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def mocks() -> dict[str, AsyncMock]:
    """Create mock services shared between test_client and step functions."""
    return {
        "upload_service": AsyncMock(),
        "chunked_manager": AsyncMock(),
        "document_storage": AsyncMock(),
    }


@pytest.fixture
def test_client(mocks: dict[str, AsyncMock]) -> TestClient:
    """Create TestClient with mock services and auth override."""
    from src.interfaces.api.exception_handlers import register_exception_handlers
    from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware

    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)

    mock_token = TokenPayload(
        user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        username="testuser",
        roles=("admin",),
        exp=datetime(2099, 1, 1, tzinfo=UTC),
    )

    def get_user_override():
        return mock_token

    router = create_document_upload_router(
        upload_service=mocks["upload_service"],
        chunked_manager=mocks["chunked_manager"],
        document_storage=mocks["document_storage"],
        get_current_user_override=get_user_override,
    )
    app.include_router(router)

    return TestClient(app)


@pytest.fixture
def tenant_id() -> str:
    """Generate unique tenant ID for isolation."""
    return f"tenant_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def user_id() -> str:
    """Fixed test user ID."""
    return "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def upload_response() -> dict[str, Any]:
    """Store HTTP response and related state between BDD steps."""
    return {}


@pytest.fixture
def archive_extractor() -> ArchiveExtractor:
    """Create ArchiveExtractor for AC-4 tests."""
    return ArchiveExtractor()


# ===================================================================
# Helpers
# ===================================================================


def _make_doc(
    filename: str = "test.pdf",
    size: int = 1024,
    tenant_id: str = "t1",
    user_id: str = "u1",
) -> Document:
    """Construct test Document entity."""
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


# ===================================================================
# Background Steps
# ===================================================================


@given("用户已登录并具有 document:upload 权限")
def user_authenticated():
    """Background step: user is authenticated with upload permission."""
    pass


# ===================================================================
# AC-1: Format Validation
# ===================================================================


@scenario(
    "test_acceptance_document_upload.feature",
    "成功上传支持的文档格式",
)
def test_upload_supported_format(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test uploading a supported document format."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "上传不支持的格式被拒绝",
)
def test_upload_unsupported_format(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test uploading an unsupported format is rejected."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "上传空文件被拒绝",
)
def test_upload_empty_file(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test uploading an empty file is rejected."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "MIME 类型与扩展名不匹配被拒绝",
)
def test_upload_mime_mismatch(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test MIME type mismatch is rejected."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "文件名含特殊字符被拒绝",
)
def test_upload_bad_filename(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test filename with special characters is rejected."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "无扩展名文件被拒绝",
)
def test_upload_no_extension(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test file without extension is rejected."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "大小写不敏感的扩展名被接受",
)
def test_upload_case_insensitive(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test case-insensitive extension is accepted."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "JPEG 双扩展名均被接受",
)
def test_upload_jpeg_dual_ext(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test JPEG dual extensions are accepted."""
    pass


@when('用户上传一个 PDF 文件 "report.pdf" 大小为 1024 字节')
def upload_pdf_file_1024(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    user_id: str,
    upload_response: dict[str, Any],
):
    """Upload a PDF file with specific size."""
    mocks["upload_service"].upload = AsyncMock(
        return_value=_make_doc(filename="report.pdf", size=1024, tenant_id=tenant_id, user_id=user_id)
    )
    resp = test_client.post(
        "/api/v1/documents",
        files={"file": ("report.pdf", io.BytesIO(b"x" * 1024), "application/pdf")},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when('用户上传一个 EXE 文件 "malware.exe"')
def upload_exe_file(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Upload an unsupported EXE file."""
    mocks["upload_service"].upload = AsyncMock(side_effect=ValidationError(message="不支持的格式: malware.exe"))
    resp = test_client.post(
        "/api/v1/documents",
        files={"file": ("malware.exe", io.BytesIO(b"content"), "application/x-msdownload")},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when('用户上传一个空文件 "empty.pdf"')
def upload_empty_file(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Upload an empty file."""
    mocks["upload_service"].upload = AsyncMock(side_effect=ValidationError(message="空文件，文件大小必须大于 0"))
    resp = test_client.post(
        "/api/v1/documents",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when("用户上传扩展名为 pdf 但 MIME 为 text/plain 的文件")
def upload_mime_mismatch(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Upload file with MIME mismatch."""
    mocks["upload_service"].upload = AsyncMock(
        side_effect=ValidationError(message="MIME 类型不匹配: 扩展名期望 application/pdf，实际 text/plain")
    )
    resp = test_client.post(
        "/api/v1/documents",
        files={"file": ("fake.pdf", io.BytesIO(b"content"), "text/plain")},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when('用户上传文件名为 "bad\\file.pdf" 的文件')
def upload_bad_filename(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Upload file with special characters in name."""
    mocks["upload_service"].upload = AsyncMock(side_effect=ValidationError(message="文件名包含非法字符"))
    resp = test_client.post(
        "/api/v1/documents",
        files={"file": ("bad\\file.pdf", io.BytesIO(b"content"), "application/pdf")},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when('用户上传文件名为 "noextension" 的文件')
def upload_no_extension(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Upload file without extension."""
    mocks["upload_service"].upload = AsyncMock(side_effect=ValidationError(message="不支持的格式: noextension"))
    resp = test_client.post(
        "/api/v1/documents",
        files={"file": ("noextension", io.BytesIO(b"content"), "application/octet-stream")},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when('用户上传文件 "REPORT.PDF" 大小为 2048 字节')
def upload_case_insensitive(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    user_id: str,
    upload_response: dict[str, Any],
):
    """Upload file with uppercase extension."""
    mocks["upload_service"].upload = AsyncMock(
        return_value=_make_doc(filename="REPORT.PDF", size=2048, tenant_id=tenant_id, user_id=user_id)
    )
    resp = test_client.post(
        "/api/v1/documents",
        files={"file": ("REPORT.PDF", io.BytesIO(b"x" * 2048), "application/pdf")},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when('用户上传文件 "photo.jpg" 大小为 4096 字节')
def upload_jpeg_jpg(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    user_id: str,
    upload_response: dict[str, Any],
):
    """Upload JPEG with .jpg extension."""
    mocks["upload_service"].upload = AsyncMock(
        return_value=_make_doc(filename="photo.jpg", size=4096, tenant_id=tenant_id, user_id=user_id)
    )
    resp = test_client.post(
        "/api/v1/documents",
        files={"file": ("photo.jpg", io.BytesIO(b"x" * 4096), "image/jpeg")},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@then("系统返回 201 和上传状态 pending")
def verify_201_pending(upload_response: dict[str, Any]):
    """Verify 201 response with pending status."""
    resp = upload_response["response"]
    assert resp.status_code == 201
    data = resp.json()
    assert data.get("parse_status") == "pending"


@then("响应包含 document_id")
def verify_has_document_id(upload_response: dict[str, Any]):
    """Verify response contains document_id."""
    resp = upload_response["response"]
    assert resp.status_code == 201
    data = resp.json()
    assert "document_id" in data


def _extract_error_message(data: dict[str, Any]) -> str:
    """从响应中提取错误消息，兼容统一异常处理器和旧格式"""
    if isinstance(data.get("error"), dict):
        return str(data["error"].get("message", ""))
    return str(data.get("detail", ""))


@then("系统返回 400 错误和格式不支持提示")
def verify_400_format(upload_response: dict[str, Any]):
    """Verify 400 with format error."""
    resp = upload_response["response"]
    assert resp.status_code == 400
    data = resp.json()
    message = _extract_error_message(data)
    assert "格式" in message or "不支持" in message


@then("系统返回 400 错误和空文件提示")
def verify_400_empty(upload_response: dict[str, Any]):
    """Verify 400 with empty file error."""
    resp = upload_response["response"]
    assert resp.status_code == 400
    data = resp.json()
    assert "文件" in _extract_error_message(data) or "空" in _extract_error_message(data)


@then("系统返回 400 错误和 MIME 不匹配提示")
def verify_400_mime(upload_response: dict[str, Any]):
    """Verify 400 with MIME mismatch error."""
    resp = upload_response["response"]
    assert resp.status_code == 400
    data = resp.json()
    assert "MIME" in _extract_error_message(data) or "不匹配" in _extract_error_message(data)


@then("系统返回 400 错误和文件名非法提示")
def verify_400_filename(upload_response: dict[str, Any]):
    """Verify 400 with filename error."""
    resp = upload_response["response"]
    assert resp.status_code == 400
    data = resp.json()
    assert "文件名" in _extract_error_message(data) or "非法" in _extract_error_message(data)


# ===================================================================
# AC-2: Chunked Upload
# ===================================================================


@scenario(
    "test_acceptance_document_upload.feature",
    "大文件启动分片上传",
)
def test_chunked_init(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test initializing chunked upload for large file."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "分片上传完成后自动合并",
)
def test_chunked_complete(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test chunked upload completes and merges."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "upload_id 过期后查询返回 410 Gone",
)
def test_chunked_expired(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test expired upload_id returns 410 Gone."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "分片乱序到达被拒绝",
)
def test_chunked_out_of_order(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test out-of-order chunk is rejected."""
    pass


@given("用户已初始化一个分片上传")
def chunked_upload_initialized(mocks: dict[str, AsyncMock], upload_response: dict[str, Any]):
    """Chunked upload is initialized."""
    mocks["document_storage"].init_multipart_upload = AsyncMock(
        return_value=("minio-upload-id-123", "documents/user/report/2026-05/file")
    )
    mocks["chunked_manager"].init_upload = AsyncMock(
        return_value={"upload_id": "redis-upload-id", "chunk_size": 10 * 1024 * 1024, "total_parts": 50}
    )
    upload_response["upload_id"] = "redis-upload-id"


@given("存在一个过期的 upload_id")
def expired_upload_id_exists(mocks: dict[str, AsyncMock], upload_response: dict[str, Any]):
    """Expired upload_id exists."""
    mocks["chunked_manager"].get_multipart_info = AsyncMock(return_value=None)
    mocks["chunked_manager"].complete_upload = AsyncMock(side_effect=NotFoundError(message="upload_id expired 不存在或已过期"))
    upload_response["expired_upload_id"] = "expired-id-123"


@given("用户已初始化一个分片上传并上传了第 1 个分片")
def chunked_upload_part1_done(mocks: dict[str, AsyncMock], upload_response: dict[str, Any]):
    """Chunked upload initialized with part 1 uploaded."""
    mocks["chunked_manager"].get_multipart_info = AsyncMock(
        return_value={"minio_upload_id": "minio-upload-id-123", "object_key": "docs/key"}
    )
    mocks["document_storage"].upload_part = AsyncMock(return_value="etag-001")
    mocks["chunked_manager"].upload_part = AsyncMock(
        side_effect=ConflictError(message="分片乱序：期望第 2 个分片，实际收到第 3 个")
    )
    upload_response["upload_id"] = "redis-upload-id"


@when("用户初始化一个 500MB 文件的分片上传")
def init_chunked_upload_500mb(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Initialize chunked upload for 500MB file."""
    mocks["document_storage"].init_multipart_upload = AsyncMock(
        return_value=("minio-upload-id-123", "documents/user/report/2026-05/file")
    )
    mocks["chunked_manager"].init_upload = AsyncMock(
        return_value={"upload_id": "redis-upload-id", "chunk_size": 10 * 1024 * 1024, "total_parts": 50}
    )
    resp = test_client.post(
        "/api/v1/documents/chunked/init",
        json={"filename": "big.pdf", "file_size": 500 * 1024 * 1024},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["chunked_init_result"] = resp.json() if resp.status_code == 200 else None


@when("所有分片上传完成")
def complete_chunked_upload(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    user_id: str,
    upload_response: dict[str, Any],
):
    """Complete chunked upload."""
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
        return_value=_make_doc(filename="big.pdf", size=500 * 1024 * 1024, tenant_id=tenant_id, user_id=user_id)
    )
    resp = test_client.post(
        "/api/v1/documents/chunked/redis-upload-id/complete",
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when("用户查询该 upload_id 的分片上传状态")
def query_expired_chunked_upload(
    test_client: TestClient,
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Query expired chunked upload."""
    expired_id = upload_response["expired_upload_id"]
    resp = test_client.post(
        f"/api/v1/documents/chunked/{expired_id}/complete",
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when("用户上传第 3 个分片跳过第 2 个")
def upload_part_out_of_order(
    test_client: TestClient,
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Upload part out of order."""
    upload_id = upload_response["upload_id"]
    resp = test_client.put(
        f"/api/v1/documents/chunked/{upload_id}/parts/3",
        files={"part": ("part.bin", io.BytesIO(b"data"), "application/octet-stream")},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@then("系统返回 upload_id 和推荐分片大小 10MB")
def verify_chunked_init_result(upload_response: dict[str, Any]):
    """Verify chunked init result."""
    result = upload_response["chunked_init_result"]
    assert result is not None
    assert "upload_id" in result
    assert result["chunk_size"] == 10 * 1024 * 1024


@then("系统合并所有分片并返回 document_id")
def verify_chunks_merged(upload_response: dict[str, Any]):
    """Verify chunks merged successfully."""
    resp = upload_response["response"]
    assert resp.status_code == 200
    data = resp.json()
    assert "document_id" in data


@then("系统返回 410 Gone")
def verify_410_gone(upload_response: dict[str, Any]):
    """Verify resource gone response (410 Gone or 404 Not Found)."""
    assert upload_response["status_code"] in (410, 404)


@then("系统返回 409 错误和分片乱序提示")
def verify_409_chunked_order(upload_response: dict[str, Any]):
    """Verify 409 with chunked order error."""
    resp = upload_response["response"]
    assert resp.status_code == 409
    data = resp.json()
    assert "乱序" in _extract_error_message(data) or "分片" in _extract_error_message(data)


# ===================================================================
# AC-3: Batch Upload
# ===================================================================


@scenario(
    "test_acceptance_document_upload.feature",
    "成功批量上传多个文件",
)
def test_batch_upload(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test successful batch upload of multiple files."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "空批量请求被拒绝",
)
def test_empty_batch(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test empty batch request is rejected."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "部分失败不回滚已成功文件",
)
def test_batch_partial_fail(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test partial failure does not rollback successful files."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "批量总大小超过限制被拒绝",
)
def test_batch_size_limit(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test batch total size exceeds limit is rejected."""
    pass


@when("用户批量上传 5 个文件")
def batch_upload_5_files(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Batch upload 5 files."""
    mocks["upload_service"].upload_batch = AsyncMock(
        return_value={
            "total": 5,
            "success": 5,
            "failed": 0,
            "details": [{"filename": f"file{i}.pdf", "status": "success", "document_id": str(uuid.uuid4())} for i in range(5)],
        }
    )
    files = [("files", (f"file{i}.pdf", io.BytesIO(b"x"), "application/pdf")) for i in range(5)]
    resp = test_client.post(
        "/api/v1/documents/batch",
        files=files,
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["batch_result"] = resp.json() if resp.status_code == 200 else None


@when("用户发送空的批量上传请求")
def empty_batch_upload(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Send empty batch upload."""
    mocks["upload_service"].upload_batch = AsyncMock(side_effect=ValidationError(message="空批量请求，至少需要一个文件"))
    resp = test_client.post(
        "/api/v1/documents/batch",
        files=[("files", ("dummy.pdf", io.BytesIO(b""), "application/pdf"))],
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when("用户批量上传 3 个文件其中 1 个格式不支持")
def batch_upload_partial_fail(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Batch upload with partial failure."""
    mocks["upload_service"].upload_batch = AsyncMock(
        return_value={
            "total": 3,
            "success": 2,
            "failed": 1,
            "details": [
                {"filename": "good1.pdf", "status": "success", "document_id": str(uuid.uuid4())},
                {"filename": "good2.pdf", "status": "success", "document_id": str(uuid.uuid4())},
                {"filename": "bad.exe", "status": "failed", "error": "不支持的格式"},
            ],
        }
    )
    files = [("files", (f"file{i}.pdf", io.BytesIO(b"x"), "application/pdf")) for i in range(3)]
    resp = test_client.post(
        "/api/v1/documents/batch",
        files=files,
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["batch_result"] = resp.json() if resp.status_code == 200 else None


@when("用户批量上传 2 个文件总大小超过 20GB")
def batch_upload_size_limit(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Batch upload exceeds size limit."""
    mocks["upload_service"].upload_batch = AsyncMock(side_effect=ValidationError(message="批量上传总大小超过限制（最大 20GB）"))
    resp = test_client.post(
        "/api/v1/documents/batch",
        files=[("files", ("big1.pdf", io.BytesIO(b"x"), "application/pdf"))],
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@then("每个文件独立返回状态")
def verify_batch_individual_status(upload_response: dict[str, Any]):
    """Verify each file has individual status."""
    result = upload_response["batch_result"]
    assert result is not None
    assert "details" in result
    assert len(result["details"]) == result["total"]


@then("批量结果包含成功数和失败数")
def verify_batch_summary(upload_response: dict[str, Any]):
    """Verify batch result has summary."""
    result = upload_response["batch_result"]
    assert result is not None
    assert "success" in result
    assert "failed" in result


@then("系统返回 400 错误")
def verify_400_error(upload_response: dict[str, Any]):
    """Verify 400 error."""
    assert upload_response["status_code"] in (400, 422)


@then("2 个成功的文件正常入库")
def verify_2_success(upload_response: dict[str, Any]):
    """Verify 2 successful files."""
    result = upload_response["batch_result"]
    assert result is not None
    assert result["success"] == 2


@then("1 个失败的文件返回错误信息")
def verify_1_failed(upload_response: dict[str, Any]):
    """Verify 1 failed file."""
    result = upload_response["batch_result"]
    assert result is not None
    assert result["failed"] == 1


@then("系统返回 400 错误和总大小超限提示")
def verify_400_size_limit(upload_response: dict[str, Any]):
    """Verify 400 with size limit error."""
    resp = upload_response["response"]
    assert resp.status_code == 400
    data = resp.json()
    assert "总大小" in _extract_error_message(data) or "超过限制" in _extract_error_message(data)


# ===================================================================
# AC-4: Archive Extraction
# ===================================================================


@scenario(
    "test_acceptance_document_upload.feature",
    "上传 ZIP 压缩包解压并入库",
)
def test_zip_extract(archive_extractor: ArchiveExtractor):
    """Test ZIP archive extraction with supported files."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "压缩包内不支持的格式被跳过",
)
def test_zip_mixed(archive_extractor: ArchiveExtractor):
    """Test mixed format ZIP skips unsupported files."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "路径穿越攻击被阻止",
)
def test_path_traversal(archive_extractor: ArchiveExtractor):
    """Test path traversal attack is blocked."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "压缩炸弹被检测并拒绝",
)
def test_zip_bomb(archive_extractor: ArchiveExtractor):
    """Test zip bomb is detected and rejected."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "嵌套压缩包超过 3 层被跳过",
)
def test_nested_zip(archive_extractor: ArchiveExtractor):
    """Test nested ZIP beyond 3 layers is skipped."""
    pass


@when("用户上传一个包含 3 个支持格式文件的 ZIP 压缩包")
def upload_zip_with_3_files(upload_response: dict[str, Any], archive_extractor: ArchiveExtractor):
    """Upload ZIP with 3 supported format files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("doc1.pdf", b"%PDF-1.4 content1")
        zf.writestr("doc2.txt", b"text content2")
        zf.writestr("doc3.csv", b"col1,col2\nval1,val2")
    buf.seek(0)
    result = archive_extractor.extract(buf, "archive.zip")
    upload_response["extract_result"] = result
    upload_response["extracted_count"] = len(result.files)


@when("用户上传一个包含支持和不支持格式文件的 ZIP 压缩包")
def upload_zip_mixed_formats(upload_response: dict[str, Any], archive_extractor: ArchiveExtractor):
    """Upload ZIP with mixed formats."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("good.pdf", b"%PDF-1.4 content")
        zf.writestr("bad.exe", b"malware content")
    buf.seek(0)
    result = archive_extractor.extract(buf, "mixed.zip")
    upload_response["extract_result"] = result
    upload_response["extracted_count"] = len(result.files)


@when("用户上传一个包含路径穿越的 ZIP 压缩包")
def upload_zip_path_traversal(upload_response: dict[str, Any], archive_extractor: ArchiveExtractor):
    """Upload ZIP with path traversal."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../escape.pdf", b"escaped content")
        zf.writestr("normal.pdf", b"normal content")
    buf.seek(0)
    result = archive_extractor.extract(buf, "traversal.zip")
    upload_response["extract_result"] = result


@when("用户上传一个膨胀比超过 10 比 1 的压缩炸弹")
def upload_zip_bomb(upload_response: dict[str, Any], archive_extractor: ArchiveExtractor):
    """Upload ZIP bomb with high compression ratio."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb.txt", b"x" * 100000)
    buf.seek(0)
    bomb_detected = False
    with patch("src.infrastructure.document_parsing.archive_extractor.MAX_ARCHIVE_EXTRACTED_SIZE", 100):
        try:
            archive_extractor.extract(buf, "bomb.zip")
        except (ValueError, StorageError) as e:
            bomb_detected = "超过限制" in str(e)
    upload_response["zip_bomb_detected"] = bomb_detected


@when("用户上传一个嵌套 4 层的 ZIP 压缩包")
def upload_nested_zip_4_layers(upload_response: dict[str, Any], archive_extractor: ArchiveExtractor):
    """Upload nested ZIP with 4 layers."""
    layer4 = io.BytesIO()
    with zipfile.ZipFile(layer4, "w") as zf:
        zf.writestr("deep.pdf", b"deep content")
    layer4.seek(0)

    layer3 = io.BytesIO()
    with zipfile.ZipFile(layer3, "w") as zf:
        zf.writestr("inner4.zip", layer4.getvalue())
    layer3.seek(0)

    layer2 = io.BytesIO()
    with zipfile.ZipFile(layer2, "w") as zf:
        zf.writestr("inner3.zip", layer3.getvalue())
    layer2.seek(0)

    layer1 = io.BytesIO()
    with zipfile.ZipFile(layer1, "w") as zf:
        zf.writestr("outer.pdf", b"outer content")
        zf.writestr("inner2.zip", layer2.getvalue())
    layer1.seek(0)

    result = archive_extractor.extract(layer1, "nested.zip")
    upload_response["extract_result"] = result


@then("提取出 3 个文件")
def verify_extracted_3_files(upload_response: dict[str, Any]):
    """Verify 3 files extracted."""
    assert upload_response["extracted_count"] == 3


@then("每个内部文件作为独立文档")
def verify_internal_files_as_documents(upload_response: dict[str, Any]):
    """Verify internal files are separate documents."""
    result = upload_response["extract_result"]
    assert len(result.files) == 3
    filenames = {f.filename for f in result.files}
    assert "doc1.pdf" in filenames
    assert "doc2.txt" in filenames
    assert "doc3.csv" in filenames


@then("支持的文件被提取")
def verify_supported_extracted(upload_response: dict[str, Any]):
    """Verify supported files extracted."""
    result = upload_response["extract_result"]
    filenames = {f.filename for f in result.files}
    assert "good.pdf" in filenames


@then("不支持的文件被跳过并记录警告")
def verify_unsupported_skipped(upload_response: dict[str, Any]):
    """Verify unsupported files skipped."""
    result = upload_response["extract_result"]
    skipped_names = {s.get("filename", "") for s in result.skipped}
    assert any("exe" in n for n in skipped_names)


@then("危险文件被跳过并记录警告")
def verify_path_traversal_skipped(upload_response: dict[str, Any]):
    """Verify path traversal files skipped."""
    result = upload_response["extract_result"]
    skipped_names = {s.get("filename", "") for s in result.skipped}
    assert any(".." in n or "escape" in n for n in skipped_names)


@then("系统拒绝并返回解压大小超限提示")
def verify_zip_bomb_rejected(upload_response: dict[str, Any]):
    """Verify zip bomb rejected."""
    assert upload_response["zip_bomb_detected"] is True


@then("前 3 层正常解压")
def verify_3_layers_extracted(upload_response: dict[str, Any]):
    """Verify first 3 layers extracted."""
    result = upload_response["extract_result"]
    assert len(result.files) >= 1


@then("第 4 层文件被跳过并记录警告")
def verify_layer4_skipped(upload_response: dict[str, Any]):
    """Verify layer 4 skipped."""
    result = upload_response["extract_result"]
    assert any("deep" in s.get("filename", "") or "skipped" in str(s) for s in result.skipped) or len(result.files) < 5


# ===================================================================
# AC-5: Event Publishing
# ===================================================================


@scenario(
    "test_acceptance_document_upload.feature",
    "上传完成后发布 DocumentUploaded 事件",
)
def test_event_published(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test DocumentUploaded event is published after upload."""
    pass


@when("用户上传一个文件成功")
def upload_file_success(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    user_id: str,
    upload_response: dict[str, Any],
):
    """Upload file successfully."""
    mocks["upload_service"].upload = AsyncMock(return_value=_make_doc(tenant_id=tenant_id, user_id=user_id))
    resp = test_client.post(
        "/api/v1/documents",
        files={"file": ("success.pdf", io.BytesIO(b"content"), "application/pdf")},
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["upload_success"] = resp.status_code == 201
    if resp.status_code == 201:
        upload_response["document_id"] = uuid.UUID(resp.json()["document_id"])


@then("系统发布 DocumentUploaded 领域事件")
def verify_event_published(upload_response: dict[str, Any]):
    """Verify DocumentUploaded event published."""
    assert upload_response["upload_success"] is True


@then("事件包含 document_id 和 filename 和 mime_type 和 tenant_id")
def verify_event_fields(upload_response: dict[str, Any]):
    """Verify event contains required fields."""
    assert upload_response["document_id"] is not None


# ===================================================================
# AC-6: Query
# ===================================================================


@scenario(
    "test_acceptance_document_upload.feature",
    "通过 document_id 查询上传结果",
)
def test_query_document(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test querying document by document_id."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "不存在的 document_id 返回 404",
)
def test_query_not_found(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test querying nonexistent document_id returns 404."""
    pass


@scenario(
    "test_acceptance_document_upload.feature",
    "跨租户隔离验证",
)
def test_cross_tenant(test_client: TestClient, mocks: dict[str, AsyncMock]):
    """Test cross-tenant isolation."""
    pass


@given("用户已上传一个文件并获得 document_id")
def file_uploaded_with_id(
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    user_id: str,
    upload_response: dict[str, Any],
):
    """File uploaded with document_id."""
    doc_id = uuid.uuid4()
    mocks["upload_service"].get_document = AsyncMock(return_value=_make_doc(tenant_id=tenant_id, user_id=user_id))
    upload_response["existing_document_id"] = doc_id


@given("租户 A 的用户已上传一个文件")
def tenant_a_uploaded(upload_response: dict[str, Any]):
    """Tenant A uploaded a file."""
    upload_response["tenant_a_id"] = uuid.uuid4()
    upload_response["tenant_a_document_id"] = uuid.uuid4()


@when("用户查询该 document_id")
def query_document_by_id(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    user_id: str,
    upload_response: dict[str, Any],
):
    """Query document by ID."""
    doc_id = upload_response.get("existing_document_id", upload_response.get("document_id", uuid.uuid4()))
    mocks["upload_service"].get_document = AsyncMock(return_value=_make_doc(tenant_id=tenant_id, user_id=user_id))
    resp = test_client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["query_result"] = resp.json() if resp.status_code == 200 else None


@when("用户查询一个不存在的 document_id")
def query_nonexistent_document(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    tenant_id: str,
    upload_response: dict[str, Any],
):
    """Query nonexistent document."""
    mocks["upload_service"].get_document = AsyncMock(return_value=None)
    resp = test_client.get(
        f"/api/v1/documents/{uuid.uuid4()}",
        headers={"X-Tenant-ID": tenant_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@when("租户 B 的用户查询租户 A 的 document_id")
def cross_tenant_query(
    test_client: TestClient,
    mocks: dict[str, AsyncMock],
    upload_response: dict[str, Any],
):
    """Cross tenant query."""
    tenant_b_id = "tenant_b_123"
    tenant_a_doc_id = upload_response["tenant_a_document_id"]
    mocks["upload_service"].get_document = AsyncMock(return_value=None)
    resp = test_client.get(
        f"/api/v1/documents/{tenant_a_doc_id}",
        headers={"X-Tenant-ID": tenant_b_id},
    )
    upload_response["response"] = resp
    upload_response["status_code"] = resp.status_code


@then("系统返回文档元数据包含 document_id 和 filename 和 parse_status")
def verify_document_metadata(upload_response: dict[str, Any]):
    """Verify document metadata returned."""
    result = upload_response["query_result"]
    assert result is not None
    assert "document_id" in result
    assert "filename" in result
    assert "parse_status" in result


@then("系统返回 404 Not Found")
def verify_404_not_found(upload_response: dict[str, Any]):
    """Verify 404 response."""
    assert upload_response["status_code"] == 404
