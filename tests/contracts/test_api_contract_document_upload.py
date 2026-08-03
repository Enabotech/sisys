"""Story 2-1: API 契约测试 — 文档上传端点

验证 REST API 端点的存在性、请求格式和响应结构。
端点定义：
- POST /api/v1/documents — 单文件上传
- POST /api/v1/documents/batch — 批量上传
- POST /api/v1/documents/chunked/init — 分片上传初始化
- PUT /api/v1/documents/chunked/{upload_id}/parts/{part_number} — 分片上传
- POST /api/v1/documents/chunked/{upload_id}/complete — 分片上传完成
- GET /api/v1/documents/{document_id} — 上传结果确认查询
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.exceptions.storage_exceptions import MetadataValidationError
from src.domain.value_objects.token_payload import TokenPayload
from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadState
from src.interfaces.api.document_upload import create_document_upload_router
from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware


def _make_token() -> TokenPayload:
    return TokenPayload(
        user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        username="testuser",
        roles=("admin",),
        exp=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _make_doc() -> Document:
    return Document(
        document_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        filename="test.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        document_type=DocumentType.OTHER,
        parse_status=ParseStatus.PENDING,
        tenant_id="t1",
        uploaded_by="11111111-1111-1111-1111-111111111111",
    )


def _make_client() -> tuple[TestClient, AsyncMock, AsyncMock, AsyncMock]:
    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)
    service = AsyncMock()
    manager = AsyncMock()
    storage = AsyncMock()

    def override():
        return _make_token()

    router = create_document_upload_router(
        upload_service=service,
        chunked_manager=manager,
        document_storage=storage,
        get_current_user_override=override,
    )
    app.include_router(router)
    return TestClient(app), service, manager, storage


TENANT = {"X-Tenant-ID": "t1"}


class TestDocumentUploadAPIContract:
    """API 契约测试：验证端点定义和响应格式"""

    def test_single_upload_endpoint_exists(self) -> None:
        """验证 POST /api/v1/documents 端点存在"""
        client, service, _, _ = _make_client()
        service.upload = AsyncMock(return_value=_make_doc())

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
            headers=TENANT,
        )
        assert resp.status_code == 201

    def test_batch_upload_endpoint_exists(self) -> None:
        """验证 POST /api/v1/documents/batch 端点存在"""
        client, service, _, _ = _make_client()
        service.upload_batch = AsyncMock(return_value={"total": 1, "success": 1, "failed": 0, "details": []})

        resp = client.post(
            "/api/v1/documents/batch",
            files=[("files", ("a.pdf", io.BytesIO(b"x"), "application/pdf"))],
            headers=TENANT,
        )
        assert resp.status_code == 200

    def test_chunked_init_endpoint_exists(self) -> None:
        """验证 POST /api/v1/documents/chunked/init 端点存在"""
        client, _, manager, storage = _make_client()
        storage.init_multipart_upload = AsyncMock(return_value=("minio-id", "docs/key"))
        manager.init_upload = AsyncMock(return_value={"upload_id": "abc", "chunk_size": 10, "total_parts": 1})

        resp = client.post(
            "/api/v1/documents/chunked/init",
            json={"filename": "big.pdf", "file_size": 1000},
            headers=TENANT,
        )
        assert resp.status_code == 200

    def test_chunked_upload_part_endpoint_exists(self) -> None:
        """验证 PUT /api/v1/documents/chunked/{upload_id}/parts/{part_number} 端点存在"""
        client, _, manager, storage = _make_client()
        manager.get_multipart_info = AsyncMock(return_value={"minio_upload_id": "minio-123", "object_key": "docs/key"})
        storage.upload_part = AsyncMock(return_value="etag-1")
        manager.upload_part = AsyncMock(return_value={"uploaded_parts": 1})

        resp = client.put(
            "/api/v1/documents/chunked/abc/parts/1",
            files={"part": ("part.bin", io.BytesIO(b"data"), "application/octet-stream")},
            headers=TENANT,
        )
        assert resp.status_code == 200

    def test_chunked_complete_endpoint_exists(self) -> None:
        """验证 POST /api/v1/documents/chunked/{upload_id}/complete 端点存在"""
        client, service, manager, storage = _make_client()
        state = ChunkedUploadState(
            upload_id="abc",
            filename="big.pdf",
            file_size=1000,
            chunk_size=500,
            minio_upload_id="minio-123",
            object_key="docs/key",
        )
        manager.complete_upload = AsyncMock(return_value=state)
        storage.complete_multipart_upload = AsyncMock(return_value="version-1")
        service.register_document = AsyncMock(return_value=_make_doc())

        resp = client.post("/api/v1/documents/chunked/abc/complete", headers=TENANT)
        assert resp.status_code == 200

    def test_document_query_endpoint_exists(self) -> None:
        """验证 GET /api/v1/documents/{document_id} 端点存在"""
        client, service, _, _ = _make_client()
        service.get_document = AsyncMock(return_value=_make_doc())

        resp = client.get(
            f"/api/v1/documents/{uuid.uuid4()}",
            headers=TENANT,
        )
        assert resp.status_code == 200

    def test_single_upload_response_format(self) -> None:
        """验证单文件上传响应格式：扁平 JSON"""
        client, service, _, _ = _make_client()
        service.upload = AsyncMock(return_value=_make_doc())

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
            headers=TENANT,
        )
        data = resp.json()
        assert isinstance(data["document_id"], str)
        assert isinstance(data["filename"], str)
        assert isinstance(data["mime_type"], str)
        assert isinstance(data["file_size_bytes"], int)
        assert isinstance(data["parse_status"], str)
        assert isinstance(data["created_at"], str)

    def test_batch_upload_response_format(self) -> None:
        """验证批量上传响应格式"""
        client, service, _, _ = _make_client()
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
            files=[("files", ("a.pdf", io.BytesIO(b"x"), "application/pdf"))],
            headers=TENANT,
        )
        data = resp.json()
        assert isinstance(data["total"], int)
        assert isinstance(data["success"], int)
        assert isinstance(data["failed"], int)
        assert isinstance(data["details"], list)

    def test_chunked_init_response_format(self) -> None:
        """验证分片上传初始化响应格式"""
        client, _, manager, storage = _make_client()
        storage.init_multipart_upload = AsyncMock(return_value=("minio-id", "docs/key"))
        manager.init_upload = AsyncMock(return_value={"upload_id": "abc", "chunk_size": 10, "total_parts": 5})

        resp = client.post(
            "/api/v1/documents/chunked/init",
            json={"filename": "big.pdf", "file_size": 1000},
            headers=TENANT,
        )
        data = resp.json()
        assert isinstance(data["upload_id"], str)
        assert isinstance(data["chunk_size"], int)
        assert isinstance(data["total_parts"], int)

    def test_document_query_response_format(self) -> None:
        """验证文档查询响应格式"""
        client, service, _, _ = _make_client()
        service.get_document = AsyncMock(return_value=_make_doc())

        resp = client.get(
            "/api/v1/documents/22222222-2222-2222-2222-222222222222",
            headers=TENANT,
        )
        data = resp.json()
        assert data["document_id"] == "22222222-2222-2222-2222-222222222222"
        assert data["filename"] == "test.pdf"
        assert data["parse_status"] == "pending"

    def test_404_for_nonexistent_document(self) -> None:
        """验证不存在的 document_id 返回 404"""
        client, service, _, _ = _make_client()
        service.get_document = AsyncMock(return_value=None)

        resp = client.get(
            f"/api/v1/documents/{uuid.uuid4()}",
            headers=TENANT,
        )
        assert resp.status_code == 404

    def test_400_for_invalid_uuid_format(self) -> None:
        """验证无效 UUID 格式返回 400（统一异常处理器处理）"""
        client, service, _, _ = _make_client()
        service.get_document = AsyncMock(return_value=None)

        resp = client.get(
            "/api/v1/documents/not-a-uuid",
            headers=TENANT,
        )
        assert resp.status_code == 400

    def test_404_for_expired_upload_id(self) -> None:
        """验证过期 upload_id 返回 404"""
        client, _, manager, _ = _make_client()
        manager.complete_upload = AsyncMock(side_effect=NotFoundError(message="upload_id expired 不存在或已过期"))

        resp = client.post("/api/v1/documents/chunked/expired/complete", headers=TENANT)
        assert resp.status_code == 404

    def test_400_for_unsupported_format(self) -> None:
        """验证不支持格式返回 400"""
        client, service, _, _ = _make_client()
        service.upload = AsyncMock(side_effect=ValidationError(message="不支持的格式"))

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.exe", io.BytesIO(b"x"), "application/x-msdownload")},
            headers=TENANT,
        )
        assert resp.status_code == 400

    def test_400_for_empty_file(self) -> None:
        """验证空文件返回 400"""
        client, service, _, _ = _make_client()
        service.upload = AsyncMock(side_effect=ValidationError(message="空文件"))

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
            headers=TENANT,
        )
        assert resp.status_code == 400

    def test_auth_required_for_all_endpoints(self) -> None:
        """验证所有端点需要认证"""
        app = FastAPI()
        app.add_middleware(ExceptionContextMiddleware)
        register_exception_handlers(app)
        router = create_document_upload_router(
            upload_service=AsyncMock(),
            chunked_manager=AsyncMock(),
        )
        app.include_router(router)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(b"x"), "application/pdf")},
            headers=TENANT,
        )
        assert resp.status_code == 401

    # ===================================================================
    # Story 2-7: 元数据标准化校验 — API 契约
    # ===================================================================

    def test_single_upload_response_contains_metadata_field(self) -> None:
        """验证单文件上传响应包含 metadata 字段"""
        client, service, _, _ = _make_client()
        doc = _make_doc()
        doc.metadata = {"creator": "test-user", "source": "internal"}
        service.upload = AsyncMock(return_value=doc)

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
            headers=TENANT,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "metadata" in data
        assert data["metadata"] is not None
        assert data["metadata"]["source"] == "internal"

    def test_single_upload_accepts_metadata_form_param(self) -> None:
        """验证单文件上传可传递 metadata Form 参数（JSON 字符串）"""
        client, service, _, _ = _make_client()
        service.upload = AsyncMock(return_value=_make_doc())

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
            data={"metadata": '{"source": "internal", "license": "confidential", "business_domain": "finance"}'},
            headers=TENANT,
        )
        assert resp.status_code == 201
        # 验证 metadata 参数被传递给了 upload 服务
        call_kwargs = service.upload.call_args.kwargs
        assert "metadata" in call_kwargs
        assert call_kwargs["metadata"]["source"] == "internal"

    def test_single_upload_422_for_metadata_validation_error(self) -> None:
        """验证元数据校验失败时返回 422 且含 EXCEPTION_217 响应格式"""
        from uuid import uuid4

        client, service, _, _ = _make_client()
        service.upload = AsyncMock(
            side_effect=MetadataValidationError(
                document_id=uuid4(),
                missing_fields=["source", "license", "business_domain"],
                tenant_id="t1",
            )
        )

        resp = client.post(
            "/api/v1/documents",
            files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
            headers=TENANT,
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "EXCEPTION_217"
        assert "missing_fields" in data["error"]["context"]
        assert "source" in data["error"]["context"]["missing_fields"]

    def test_chunked_init_accepts_metadata_field(self) -> None:
        """验证分片上传初始化请求可携带 metadata 字段"""
        client, _, manager, storage = _make_client()
        storage.init_multipart_upload = AsyncMock(return_value=("minio-id", "docs/key"))
        manager.init_upload = AsyncMock(return_value={"upload_id": "abc", "chunk_size": 10, "total_parts": 1})

        resp = client.post(
            "/api/v1/documents/chunked/init",
            json={
                "filename": "big.pdf",
                "file_size": 1000,
                "metadata": '{"source": "internal", "license": "confidential", "business_domain": "finance"}',
            },
            headers=TENANT,
        )
        assert resp.status_code == 200
        # 验证 metadata 参数被传递给了 init_upload
        call_kwargs = manager.init_upload.call_args.kwargs
        assert "metadata" in call_kwargs
        assert call_kwargs["metadata"] is not None
        assert "source" in call_kwargs["metadata"]

    def test_chunked_complete_response_contains_metadata(self) -> None:
        """验证分片上传完成响应包含 metadata 字段"""
        client, service, manager, storage = _make_client()
        state = ChunkedUploadState(
            upload_id="abc",
            filename="big.pdf",
            file_size=1000,
            chunk_size=500,
            minio_upload_id="minio-123",
            object_key="docs/key",
            metadata='{"source": "internal", "license": "confidential", "business_domain": "finance"}',
        )
        manager.complete_upload = AsyncMock(return_value=state)
        storage.complete_multipart_upload = AsyncMock(return_value="version-1")
        doc = _make_doc()
        doc.metadata = {"source": "internal", "license": "confidential", "business_domain": "finance"}
        service.register_document = AsyncMock(return_value=doc)

        resp = client.post("/api/v1/documents/chunked/abc/complete", headers=TENANT)
        assert resp.status_code == 200
        data = resp.json()
        assert "metadata" in data
        assert data["metadata"]["source"] == "internal"

    def test_batch_upload_accepts_metadata_form_param(self) -> None:
        """验证批量上传可传递 metadata Form 参数（JSON 字符串数组）"""
        client, service, _, _ = _make_client()
        service.upload_batch = AsyncMock(return_value={"total": 1, "success": 1, "failed": 0, "details": []})

        resp = client.post(
            "/api/v1/documents/batch",
            files=[("files", ("a.pdf", io.BytesIO(b"x"), "application/pdf"))],
            data={"metadata": '[{"source": "internal", "license": "confidential", "business_domain": "finance"}]'},
            headers=TENANT,
        )
        assert resp.status_code == 200
        # 验证 metadata_list 参数被传递给了 upload_batch
        call_kwargs = service.upload_batch.call_args.kwargs
        assert "metadata_list" in call_kwargs
        assert call_kwargs["metadata_list"] is not None
        assert len(call_kwargs["metadata_list"]) == 1
        assert call_kwargs["metadata_list"][0]["source"] == "internal"

    def test_document_query_response_contains_metadata_field(self) -> None:
        """验证文档查询响应包含 metadata 字段"""
        client, service, _, _ = _make_client()
        doc = _make_doc()
        doc.metadata = {"creator": "test-user", "source": "internal"}
        service.get_document = AsyncMock(return_value=doc)

        resp = client.get(
            "/api/v1/documents/22222222-2222-2222-2222-222222222222",
            headers=TENANT,
        )
        data = resp.json()
        assert "metadata" in data
        assert data["metadata"]["source"] == "internal"
