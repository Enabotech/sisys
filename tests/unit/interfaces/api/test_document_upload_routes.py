"""Tests for document upload API routes — 文档上传接口层路由"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.value_objects.token_payload import TokenPayload


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


def _make_doc(
    document_id: str = "22222222-2222-2222-2222-222222222222",
    filename: str = "test.pdf",
) -> Document:
    """构造测试用 Document 实体"""
    return Document(
        document_id=uuid.UUID(document_id),
        filename=filename,
        mime_type="application/pdf",
        file_size_bytes=1024,
        document_type=DocumentType.OTHER,
        parse_status=ParseStatus.PENDING,
        tenant_id="t1",
        uploaded_by="11111111-1111-1111-1111-111111111111",
    )


def _make_app() -> tuple[TestClient, AsyncMock, AsyncMock]:
    """创建带文档上传路由的测试 FastAPI 应用"""
    from src.interfaces.api.document_upload import create_document_upload_router

    app = FastAPI()

    upload_service = AsyncMock()
    chunked_manager = AsyncMock()

    mock_user = _make_token()

    def get_user_override():
        return mock_user

    router = create_document_upload_router(
        upload_service=upload_service,
        chunked_manager=chunked_manager,
        get_current_user_override=get_user_override,
    )
    app.include_router(router)

    return TestClient(app), upload_service, chunked_manager


class TestSingleUpload:
    """验证单文件上传端点 POST /api/v1/documents"""

    def test_upload_success(self) -> None:
        """正常上传返回 201"""
        client, service, _ = _make_app()
        service.upload = AsyncMock(return_value=_make_doc())

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(b"%PDF content"), "application/pdf")},
            headers={"X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "test.pdf"
        assert data["document_id"] == "22222222-2222-2222-2222-222222222222"

    def test_upload_response_has_required_fields(self) -> None:
        """响应包含所有必需字段"""
        client, service, _ = _make_app()
        service.upload = AsyncMock(return_value=_make_doc())

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
            headers={"X-Tenant-ID": "t1"},
        )

        data = resp.json()
        for field in ("document_id", "filename", "mime_type", "file_size_bytes", "parse_status", "created_at"):
            assert field in data

    def test_upload_unsupported_format_returns_400(self) -> None:
        """不支持格式返回 400"""
        client, service, _ = _make_app()
        service.upload = AsyncMock(side_effect=ValueError("不支持的格式: test.exe"))

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.exe", io.BytesIO(b"content"), "application/x-msdownload")},
            headers={"X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 400

    def test_upload_empty_file_returns_400(self) -> None:
        """空文件返回 400"""
        client, service, _ = _make_app()
        service.upload = AsyncMock(side_effect=ValueError("空文件"))

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
            headers={"X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 400

    def test_upload_missing_tenant_header(self) -> None:
        """缺少 X-Tenant-ID 头返回 422"""
        client, service, _ = _make_app()
        service.upload = AsyncMock(return_value=_make_doc())

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
        )

        assert resp.status_code == 422


class TestBatchUpload:
    """验证批量上传端点 POST /api/v1/documents/batch"""

    def test_batch_upload_success(self) -> None:
        """批量上传返回 200"""
        client, service, _ = _make_app()
        service.upload_batch = AsyncMock(
            return_value={
                "total": 2,
                "success": 2,
                "failed": 0,
                "details": [],
            }
        )

        resp = client.post(
            "/api/v1/documents/batch",
            files=[
                ("files", ("a.pdf", io.BytesIO(b"pdf-a"), "application/pdf")),
                ("files", ("b.txt", io.BytesIO(b"txt-b"), "text/plain")),
            ],
            headers={"X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["success"] == 2

    def test_batch_upload_response_format(self) -> None:
        """响应包含 total/success/failed/details"""
        client, service, _ = _make_app()
        service.upload_batch = AsyncMock(
            return_value={
                "total": 1,
                "success": 1,
                "failed": 0,
                "details": [{"filename": "a.pdf", "status": "success"}],
            }
        )

        resp = client.post(
            "/api/v1/documents/batch",
            files=[("files", ("a.pdf", io.BytesIO(b"content"), "application/pdf"))],
            headers={"X-Tenant-ID": "t1"},
        )

        data = resp.json()
        for field in ("total", "success", "failed", "details"):
            assert field in data


class TestChunkedUpload:
    """验证分片上传端点"""

    def test_chunked_init_success(self) -> None:
        """初始化分片上传返回 200"""
        client, _, manager = _make_app()
        manager.init_upload = AsyncMock(
            return_value={
                "upload_id": "abc123",
                "chunk_size": 10485760,
                "total_parts": 50,
            }
        )

        resp = client.post(
            "/api/v1/documents/chunked/init",
            json={"filename": "big.pdf", "file_size": 500 * 1024 * 1024},
            headers={"X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "upload_id" in data
        assert "chunk_size" in data
        assert "total_parts" in data

    def test_chunked_upload_part_success(self) -> None:
        """上传分片返回 200"""
        client, _, manager = _make_app()
        manager.upload_part = AsyncMock(return_value={"uploaded_parts": 1})

        resp = client.put(
            "/api/v1/documents/chunked/abc123/parts/1",
            content=b"binary data",
            headers={"Content-Type": "application/octet-stream", "X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 200
        assert resp.json()["uploaded_parts"] == 1

    def test_chunked_complete_success(self) -> None:
        """完成分片上传返回 200"""
        client, service, manager = _make_app()
        from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadState

        state = ChunkedUploadState(
            upload_id="abc123",
            filename="big.pdf",
            file_size=500 * 1024 * 1024,
            chunk_size=10 * 1024 * 1024,
            uploaded_parts=[{"part_number": 1, "etag": "e1"}],
        )
        manager.complete_upload = AsyncMock(return_value=state)
        service.upload = AsyncMock(return_value=_make_doc())

        resp = client.post(
            "/api/v1/documents/chunked/abc123/complete",
            headers={"X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 200

    def test_chunked_expired_upload_id_returns_410(self) -> None:
        """过期 upload_id 返回 410 Gone"""
        client, _, manager = _make_app()
        manager.complete_upload = AsyncMock(side_effect=ValueError("upload_id abc123 不存在"))

        resp = client.post(
            "/api/v1/documents/chunked/abc123/complete",
            headers={"X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 410

    def test_chunked_expired_part_returns_410(self) -> None:
        """过期分片上传返回 410 Gone"""
        client, _, manager = _make_app()
        manager.upload_part = AsyncMock(side_effect=ValueError("upload_id expired 不存在"))

        resp = client.put(
            "/api/v1/documents/chunked/expired/parts/1",
            content=b"data",
            headers={"Content-Type": "application/octet-stream", "X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 410


class TestDocumentQuery:
    """验证文档查询端点 GET /api/v1/documents/{document_id}"""

    def test_query_success(self) -> None:
        """查询存在的文档返回 200"""
        client, service, _ = _make_app()
        service.get_document = AsyncMock(return_value=_make_doc())

        doc_id = "22222222-2222-2222-2222-222222222222"
        resp = client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == doc_id

    def test_query_not_found_returns_404(self) -> None:
        """不存在的文档返回 404"""
        client, service, _ = _make_app()
        service.get_document = AsyncMock(return_value=None)

        resp = client.get(
            f"/api/v1/documents/{uuid.uuid4()}",
            headers={"X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 404


class TestAuthRequired:
    """验证认证要求"""

    def test_unauthenticated_returns_401(self) -> None:
        """未认证请求返回 401"""
        from src.interfaces.api.document_upload import create_document_upload_router

        app = FastAPI()
        router = create_document_upload_router(
            upload_service=AsyncMock(),
            chunked_manager=AsyncMock(),
        )
        app.include_router(router)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
            headers={"X-Tenant-ID": "t1"},
        )

        assert resp.status_code == 401
