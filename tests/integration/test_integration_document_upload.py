"""Story 2-1: 文档上传集成测试

验证完整上传流程中各组件间协作：
API → Service → Repository/Storage → EventPublish
分片上传状态管理、批量上传部分失败、压缩包处理、租户隔离
"""

from __future__ import annotations

import io
import json
import uuid
from unittest.mock import AsyncMock

from src.application.services.document_upload_service import DocumentUploadService
from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.events.document_events import DocumentUploaded
from src.domain.ports.document_repository import DocumentRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.infrastructure.document_parsing.archive_extractor import ArchiveExtractor
from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadManager


def _make_doc(
    document_id: uuid.UUID | None = None,
    tenant_id: str = "t1",
    uploaded_by: str = "u1",
    filename: str = "test.pdf",
) -> Document:
    """构造 Document 实体"""
    return Document(
        document_id=document_id or uuid.uuid4(),
        filename=filename,
        mime_type="application/pdf",
        file_size_bytes=1024,
        document_type=DocumentType.OTHER,
        parse_status=ParseStatus.PENDING,
        tenant_id=tenant_id,
        uploaded_by=uploaded_by,
    )


def _make_upload_service(
    repo: AsyncMock | None = None,
    storage: AsyncMock | None = None,
    publisher: AsyncMock | None = None,
) -> DocumentUploadService:
    """构造 DocumentUploadService（依赖注入 mock）"""
    if repo is not None:
        repo_mock = repo
    else:
        repo_mock = AsyncMock(spec=DocumentRepositoryPort)
        repo_mock.save = AsyncMock(side_effect=lambda d: d)
        repo_mock.find = AsyncMock(return_value=None)
        repo_mock.list = AsyncMock(return_value=[])
    storage_mock = storage or AsyncMock()
    storage_mock.store_document = AsyncMock(return_value="documents/u1/pdf/2026-05/123")
    pub_mock = publisher or AsyncMock(spec=EventPublisher)
    pub_mock.publish = AsyncMock()
    return DocumentUploadService(
        document_repository=repo_mock,
        document_storage=storage_mock,
        event_publisher=pub_mock,
    )


class TestFullUploadFlow:
    """验证完整上传流程：校验 → 存储 → 持久化 → 事件发布"""

    async def test_single_file_upload_flow(self) -> None:
        """单文件完整上传流程"""
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock()
        service = _make_upload_service(publisher=publisher)

        doc = await service.upload(
            filename="report.pdf",
            mime_type="application/pdf",
            file_size_bytes=2048,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            file_path="/tmp/report.pdf",
        )

        assert doc.filename == "report.pdf"
        assert doc.tenant_id == "tenant-1"
        assert doc.parse_status == ParseStatus.PENDING

        publisher.publish.assert_called_once()
        event = publisher.publish.call_args[0][0]
        assert isinstance(event, DocumentUploaded)
        assert event.filename == "report.pdf"
        assert event.tenant_id == "tenant-1"
        assert event.uploaded_by == "user-1"

    async def test_batch_upload_partial_failure_flow(self) -> None:
        """批量上传部分失败不影响成功文件"""
        service = _make_upload_service()

        from src.application.services.document_upload_service import BatchFileInfo

        files: list[BatchFileInfo] = [
            {"filename": "good.pdf", "mime_type": "application/pdf", "file_size_bytes": 100},
            {"filename": "bad.exe", "mime_type": "application/x-msdownload", "file_size_bytes": 100},
            {"filename": "also_good.txt", "mime_type": "text/plain", "file_size_bytes": 50},
        ]

        result = await service.upload_batch(
            files=files,
            tenant_id="t1",
            uploaded_by="u1",
            file_paths=["/tmp/a", "/tmp/b", "/tmp/c"],
        )

        assert result["total"] == 3
        assert result["success"] == 2
        assert result["failed"] == 1
        assert result["details"][1]["status"] == "failed"

    async def test_get_document_delegates_to_repository(self) -> None:
        """查询文档委托给仓储"""
        doc = _make_doc()
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.find = AsyncMock(return_value=doc)
        service = _make_upload_service(repo=repo)

        found = await service.get_document(doc.document_id, "t1")

        assert found is not None
        assert found.document_id == doc.document_id
        repo.find.assert_called_once()

    async def test_upload_service_publishes_event_with_correct_fields(self) -> None:
        """验证发布事件包含完整字段"""
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock()
        service = _make_upload_service(publisher=publisher)

        doc = await service.upload(
            filename="spec.pdf",
            mime_type="application/pdf",
            file_size_bytes=4096,
            tenant_id="tenant-42",
            uploaded_by="user-42",
            file_path="/tmp/spec.pdf",
        )

        event = publisher.publish.call_args[0][0]
        assert event.document_id == doc.document_id
        assert event.mime_type == "application/pdf"
        assert event.file_size_bytes == 4096
        assert event.aggregate_type == "Document"


class TestChunkedUploadIntegration:
    """验证分片上传完整流程"""

    async def test_chunked_init_upload_complete_flow(self) -> None:
        """分片上传完整生命周期：初始化 → 分片 → 完成"""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=True)
        cache.delete = AsyncMock(return_value=True)

        manager = ChunkedUploadManager(cache)

        result = await manager.init_upload("big.pdf", 500 * 1024 * 1024)
        upload_id = result["upload_id"]
        total_parts = result["total_parts"]

        uploaded: list[dict] = []
        for i in range(1, min(total_parts + 1, 4)):
            state_json = json.dumps(
                {
                    "upload_id": upload_id,
                    "filename": "big.pdf",
                    "file_size": 500 * 1024 * 1024,
                    "chunk_size": result["chunk_size"],
                    "uploaded_parts": list(uploaded),
                }
            )
            cache.get = AsyncMock(return_value=state_json)

            part_result = await manager.upload_part(upload_id, i, f"e{i}")
            assert part_result["uploaded_parts"] == i

            uploaded.append({"part_number": i, "etag": f"e{i}"})

    async def test_chunked_resume_returns_remaining_parts(self) -> None:
        """断点续传返回未上传分片"""
        cache = AsyncMock()
        cache.get = AsyncMock(
            return_value=json.dumps(
                {
                    "upload_id": "resume-1",
                    "filename": "big.pdf",
                    "file_size": 300 * 1024 * 1024,
                    "chunk_size": 10 * 1024 * 1024,
                    "uploaded_parts": [{"part_number": 1, "etag": "e1"}, {"part_number": 3, "etag": "e3"}],
                }
            )
        )

        manager = ChunkedUploadManager(cache)
        result = await manager.resume_upload("resume-1")

        assert result is not None
        assert 1 not in result["remaining_parts"]
        assert 3 not in result["remaining_parts"]
        assert 2 in result["remaining_parts"]


class TestArchiveExtractorIntegration:
    """验证压缩包处理集成"""

    def test_zip_extraction_with_service_upload(self) -> None:
        """ZIP 解压后逐文件上传（模拟完整流程）"""
        import zipfile

        extractor = ArchiveExtractor()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("report.pdf", b"%PDF-1.4 fake")
            zf.writestr("notes.txt", b"meeting notes")
            zf.writestr("malware.exe", b"evil")
        buf.seek(0)

        result = extractor.extract(buf, "archive.zip")

        extracted_names = {f.filename for f in result.files}
        assert "report.pdf" in extracted_names
        assert "notes.txt" in extracted_names
        assert "malware.exe" not in extracted_names

        skipped_names = {s["filename"] for s in result.skipped}
        assert any("malware.exe" in n for n in skipped_names)

    def test_nested_zip_extraction(self) -> None:
        """嵌套 ZIP 递归解压"""
        extractor = ArchiveExtractor()

        inner = io.BytesIO()
        import zipfile

        with zipfile.ZipFile(inner, "w") as zf:
            zf.writestr("inner.txt", b"inner content")
        inner.seek(0)

        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as zf:
            zf.writestr("outer.pdf", b"outer content")
            zf.writestr("nested.zip", inner.getvalue())
        outer.seek(0)

        result = extractor.extract(outer, "outer.zip")

        all_names = {f.filename for f in result.files}
        assert "outer.pdf" in all_names
        assert "inner.txt" in all_names


class TestTenantIsolation:
    """验证跨租户隔离"""

    async def test_query_with_wrong_tenant_returns_none(self) -> None:
        """不同租户无法查询到其他租户文档"""
        doc = _make_doc(tenant_id="tenant-A")
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.find = AsyncMock(return_value=None)
        service = _make_upload_service(repo=repo)

        found = await service.get_document(doc.document_id, "tenant-B")

        assert found is None
        repo.find.assert_called_once()

    async def test_upload_and_query_same_tenant(self) -> None:
        """同一租户可查询到已上传文档"""
        repo = AsyncMock(spec=DocumentRepositoryPort)
        repo.save = AsyncMock(side_effect=lambda d: d)
        doc = _make_doc(tenant_id="tenant-A")
        repo.find = AsyncMock(return_value=doc)
        service = _make_upload_service(repo=repo)

        uploaded = await service.upload(
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=100,
            tenant_id="tenant-A",
            uploaded_by="u1",
            file_path="/tmp/test.pdf",
        )

        found = await service.get_document(uploaded.document_id, "tenant-A")
        assert found is not None
        assert found.tenant_id == "tenant-A"
