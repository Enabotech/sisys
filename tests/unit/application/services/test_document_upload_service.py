"""Tests for DocumentUploadService — 上传编排逻辑"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from src.domain.entities.document import ParseStatus
from src.domain.events.document_events import DocumentUploaded
from src.domain.ports.document_repository import DocumentRepositoryPort
from src.domain.ports.event_publisher import EventPublisher


def _make_upload_service(
    repo_mock: AsyncMock | None = None,
    storage_mock: AsyncMock | None = None,
    publisher_mock: AsyncMock | None = None,
):
    """创建 DocumentUploadService 实例（依赖注入 mock）"""
    from src.application.services.document_upload_service import DocumentUploadService

    repo = repo_mock or AsyncMock(spec=DocumentRepositoryPort)
    repo.save = AsyncMock(side_effect=lambda d: d)
    repo.find = AsyncMock(return_value=None)
    repo.list = AsyncMock(return_value=[])
    storage = storage_mock or AsyncMock()
    publisher = publisher_mock or AsyncMock(spec=EventPublisher)
    publisher.publish = AsyncMock()
    return DocumentUploadService(
        document_repository=repo,
        document_storage=storage,
        event_publisher=publisher,
    )


class TestDocumentUploadServiceUploadSingleFile:
    """验证单文件上传编排"""

    def test_upload_success(self) -> None:
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.save = AsyncMock(side_effect=lambda d: d)
        storage = AsyncMock()
        storage.store_document = AsyncMock(return_value="documents/u1/pdf/2026-05/123")
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock()

        service = _make_upload_service(repo, storage, publisher)

        doc = asyncio.run(
            service.upload(
                filename="test.pdf",
                mime_type="application/pdf",
                file_size_bytes=1024,
                tenant_id="t1",
                uploaded_by="u1",
                file_path="/tmp/test.pdf",
            )
        )

        assert doc is not None
        assert doc.filename == "test.pdf"
        assert doc.tenant_id == "t1"
        assert doc.uploaded_by == "u1"
        assert doc.parse_status == ParseStatus.PENDING

        saved_doc = repo.save.call_args[0][0]
        assert saved_doc.filename == "test.pdf"
        assert saved_doc.tenant_id == "t1"

        storage.store_document.assert_called_once_with(
            user_id="u1",
            doc_type="other",
            file_path="/tmp/test.pdf",
            content_type="application/pdf",
        )
        publisher.publish.assert_called_once()

    def test_upload_unsupported_format_raises(self) -> None:
        service = _make_upload_service()
        with pytest.raises(ValueError, match="不支持的格式"):
            asyncio.run(
                service.upload(
                    filename="malware.exe",
                    mime_type="application/x-msdownload",
                    file_size_bytes=100,
                    tenant_id="t1",
                    uploaded_by="u1",
                    file_path="/tmp/malware.exe",
                )
            )

    def test_upload_mime_mismatch_raises(self) -> None:
        service = _make_upload_service()
        with pytest.raises(ValueError, match="MIME"):
            asyncio.run(
                service.upload(
                    filename="test.pdf",
                    mime_type="text/plain",
                    file_size_bytes=100,
                    tenant_id="t1",
                    uploaded_by="u1",
                    file_path="/tmp/test.pdf",
                )
            )

    def test_upload_empty_file_raises(self) -> None:
        service = _make_upload_service()
        with pytest.raises(ValueError, match="空文件"):
            asyncio.run(
                service.upload(
                    filename="empty.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=0,
                    tenant_id="t1",
                    uploaded_by="u1",
                    file_path="/tmp/empty.pdf",
                )
            )

    def test_upload_file_too_large_raises(self) -> None:
        service = _make_upload_service()
        with pytest.raises(ValueError, match="超过"):
            asyncio.run(
                service.upload(
                    filename="huge.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=20 * 1024 * 1024 * 1024 + 1,
                    tenant_id="t1",
                    uploaded_by="u1",
                    file_path="/tmp/huge.pdf",
                )
            )

    def test_upload_filename_too_long_raises(self) -> None:
        service = _make_upload_service()
        with pytest.raises(ValueError, match="文件名"):
            asyncio.run(
                service.upload(
                    filename="a" * 256 + ".pdf",
                    mime_type="application/pdf",
                    file_size_bytes=100,
                    tenant_id="t1",
                    uploaded_by="u1",
                    file_path="/tmp/long.pdf",
                )
            )

    def test_upload_invalid_filename_chars_raises(self) -> None:
        service = _make_upload_service()
        for bad_name in ["bad\\file.pdf", "bad/file.pdf", "bad\x00file.pdf"]:
            with pytest.raises(ValueError, match="文件名"):
                asyncio.run(
                    service.upload(
                        filename=bad_name,
                        mime_type="application/pdf",
                        file_size_bytes=100,
                        tenant_id="t1",
                        uploaded_by="u1",
                        file_path="/tmp/bad.pdf",
                    )
                )

    def test_upload_publishes_document_uploaded_event(self) -> None:
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.save = AsyncMock(side_effect=lambda d: d)
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock()

        service = _make_upload_service(repo_mock=repo, publisher_mock=publisher)

        asyncio.run(
            service.upload(
                filename="test.pdf",
                mime_type="application/pdf",
                file_size_bytes=1024,
                tenant_id="t1",
                uploaded_by="u1",
                file_path="/tmp/test.pdf",
            )
        )

        publisher.publish.assert_called_once()
        event = publisher.publish.call_args[0][0]
        assert isinstance(event, DocumentUploaded)
        assert event.filename == "test.pdf"
        assert event.tenant_id == "t1"
        assert event.uploaded_by == "u1"


class TestDocumentUploadServiceUploadBatch:
    """验证批量上传编排"""

    def test_upload_batch_success(self) -> None:
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.save = AsyncMock(side_effect=lambda d: d)
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock()

        service = _make_upload_service(repo_mock=repo, publisher_mock=publisher)

        files = [
            {"filename": "a.pdf", "mime_type": "application/pdf", "file_size_bytes": 100},
            {"filename": "b.txt", "mime_type": "text/plain", "file_size_bytes": 50},
        ]

        result = asyncio.run(
            service.upload_batch(files=files, tenant_id="t1", uploaded_by="u1", file_paths=["/tmp/a", "/tmp/b"])
        )

        assert result["total"] == 2
        assert result["success"] == 2
        assert result["failed"] == 0

    def test_upload_batch_empty_raises(self) -> None:
        service = _make_upload_service()
        with pytest.raises(ValueError, match="空批量"):
            asyncio.run(service.upload_batch(files=[], tenant_id="t1", uploaded_by="u1", file_paths=[]))

    def test_upload_batch_partial_failure(self) -> None:
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.save = AsyncMock(side_effect=lambda d: d)
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock()

        service = _make_upload_service(repo_mock=repo, publisher_mock=publisher)

        files = [
            {"filename": "good.pdf", "mime_type": "application/pdf", "file_size_bytes": 100},
            {"filename": "bad.exe", "mime_type": "application/x-msdownload", "file_size_bytes": 100},
        ]

        result = asyncio.run(
            service.upload_batch(files=files, tenant_id="t1", uploaded_by="u1", file_paths=["/tmp/a", "/tmp/b"])
        )

        assert result["total"] == 2
        assert result["success"] == 1
        assert result["failed"] == 1


class TestDocumentUploadServiceGetDocument:
    """验证 get_document 查询方法"""

    def test_get_document_found(self) -> None:
        from src.application.services.document_upload_service import DocumentUploadService
        from src.domain.entities.document import Document

        doc = Document(
            document_id=uuid.uuid4(),
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="t1",
            uploaded_by="u1",
        )
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.find = AsyncMock(return_value=doc)
        publisher = AsyncMock(spec=EventPublisher)
        service = DocumentUploadService(
            document_repository=repo,
            document_storage=AsyncMock(),
            event_publisher=publisher,
        )

        result = asyncio.run(service.get_document(doc.document_id, "t1"))

        assert result is not None
        assert result.document_id == doc.document_id
        assert result.tenant_id == "t1"
        repo.find.assert_called_once()

    def test_get_document_not_found(self) -> None:
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.find = AsyncMock(return_value=None)
        service = _make_upload_service(repo_mock=repo)

        result = asyncio.run(service.get_document(uuid.uuid4(), "t1"))

        assert result is None


class TestDocumentUploadServiceEdgeCases:
    """验证边界值和异常路径"""

    def test_upload_empty_filename_raises(self) -> None:
        service = _make_upload_service()
        with pytest.raises(ValueError, match="文件名"):
            asyncio.run(
                service.upload(
                    filename="",
                    mime_type="application/pdf",
                    file_size_bytes=100,
                    tenant_id="t1",
                    uploaded_by="u1",
                    file_path="/tmp/test.pdf",
                )
            )

    def test_upload_whitespace_filename_raises(self) -> None:
        service = _make_upload_service()
        with pytest.raises(ValueError, match="文件名"):
            asyncio.run(
                service.upload(
                    filename="   ",
                    mime_type="application/pdf",
                    file_size_bytes=100,
                    tenant_id="t1",
                    uploaded_by="u1",
                    file_path="/tmp/test.pdf",
                )
            )

    def test_upload_storage_failure_propagates(self) -> None:
        storage = AsyncMock()
        storage.store_document = AsyncMock(side_effect=OSError("MinIO 不可用"))
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.save = AsyncMock(side_effect=lambda d: d)

        service = _make_upload_service(repo_mock=repo, storage_mock=storage)

        with pytest.raises(OSError, match="MinIO"):
            asyncio.run(
                service.upload(
                    filename="test.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=100,
                    tenant_id="t1",
                    uploaded_by="u1",
                    file_path="/tmp/test.pdf",
                )
            )

    def test_upload_repository_failure_propagates(self) -> None:
        from src.application.services.document_upload_service import DocumentUploadService

        storage = AsyncMock()
        storage.store_document = AsyncMock(return_value="path")
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.save = AsyncMock(side_effect=RuntimeError("PG 连接断开"))
        publisher = AsyncMock(spec=EventPublisher)

        service = DocumentUploadService(
            document_repository=repo,
            document_storage=storage,
            event_publisher=publisher,
        )

        with pytest.raises(RuntimeError, match="PG"):
            asyncio.run(
                service.upload(
                    filename="test.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=100,
                    tenant_id="t1",
                    uploaded_by="u1",
                    file_path="/tmp/test.pdf",
                )
            )

    def test_upload_event_publish_failure_propagates(self) -> None:
        from src.application.services.document_upload_service import DocumentUploadService

        storage = AsyncMock()
        storage.store_document = AsyncMock(return_value="path")
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.save = AsyncMock(side_effect=lambda d: d)
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock(side_effect=RuntimeError("RabbitMQ 不可用"))

        service = DocumentUploadService(
            document_repository=repo,
            document_storage=storage,
            event_publisher=publisher,
        )

        with pytest.raises(RuntimeError, match="RabbitMQ"):
            asyncio.run(
                service.upload(
                    filename="test.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=100,
                    tenant_id="t1",
                    uploaded_by="u1",
                    file_path="/tmp/test.pdf",
                )
            )
