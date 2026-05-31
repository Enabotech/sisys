"""文档解析服务单元测试

TDD 红阶段：测试 DocumentParsingService 的编排流程、状态更新、事件发布。
使用 AsyncMock 模拟仓储、存储和事件发布端口。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities.document import Document, ParseStatus
from src.domain.events.document_events import DocumentProcessed


@pytest.fixture
def mock_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_storage() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_event_publisher() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_parser() -> MagicMock:
    parser = MagicMock()
    return parser


class TestDocumentParsingServiceCreation:
    """服务构造测试"""

    def test_create_service(self) -> None:
        from src.application.services.document_parsing_service import DocumentParsingService

        service = DocumentParsingService(
            document_repository=AsyncMock(),
            document_storage=AsyncMock(),
            event_publisher=AsyncMock(),
            document_parser=MagicMock(),
        )
        assert service is not None


class TestDocumentParsingServiceSuccess:
    """解析成功场景测试"""

    @pytest.mark.asyncio
    async def test_parse_document_success(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedPage

        doc_id = uuid.uuid4()
        doc = Document(
            document_id=doc_id,
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="tenant-1",
            uploaded_by="user-1",
        )
        doc.metadata["storage_object_key"] = "documents/user-1/other/2026-05/test"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        # 模拟 MinIO 下载流（retrieve 是同步方法返回 AsyncIterator）
        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"fake pdf content"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        parsed_doc = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1)],
            parse_timestamp="2026-05-31T00:00:00Z",
        )
        mock_parser.parse.return_value = parsed_doc

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
        )

        result = await service.parse_document(doc_id, "tenant-1")

        assert result.parse_status == ParseStatus.COMPLETED
        mock_event_publisher.publish.assert_called_once()
        call_args = mock_event_publisher.publish.call_args[0][0]
        assert isinstance(call_args, DocumentProcessed)

    @pytest.mark.asyncio
    async def test_parse_document_updates_status(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument

        doc_id = uuid.uuid4()
        doc = Document(
            document_id=doc_id,
            filename="test.txt",
            mime_type="text/plain",
            file_size_bytes=100,
            tenant_id="tenant-1",
        )
        doc.metadata["storage_object_key"] = "path/to/file"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"hello"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)
        mock_parser.parse.return_value = ParsedDocument(document_id=str(doc_id), mime_type="text/plain")

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
        )

        await service.parse_document(doc_id, "tenant-1")

        # 验证 save 被调用（IN_PROGRESS + COMPLETED 两次 save）
        assert mock_repo.save.call_count == 2


class TestDocumentParsingServiceFailure:
    """解析失败场景测试"""

    @pytest.mark.asyncio
    async def test_parse_document_missing_object_key(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        from src.application.services.document_parsing_service import DocumentParsingService

        doc_id = uuid.uuid4()
        doc = Document(
            document_id=doc_id,
            filename="test.pdf",
            mime_type="application/pdf",
            tenant_id="tenant-1",
        )
        # 不设置 storage_object_key

        mock_repo.find.return_value = doc

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
        )

        result = await service.parse_document(doc_id, "tenant-1")

        # 缺少 object_key 应返回 failed
        assert result.parse_status == ParseStatus.FAILED
        mock_event_publisher.publish.assert_not_called()
        # 验证失败状态被持久化
        mock_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_document_not_found(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        from src.application.services.document_parsing_service import DocumentParsingService

        mock_repo.find.return_value = None

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
        )

        result = await service.parse_document(uuid.uuid4(), "tenant-1")

        assert result.parse_status == ParseStatus.FAILED

    @pytest.mark.asyncio
    async def test_parse_document_parser_failure(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        from src.application.services.document_parsing_service import DocumentParsingService

        doc_id = uuid.uuid4()
        doc = Document(
            document_id=doc_id,
            filename="bad.pdf",
            mime_type="application/pdf",
            tenant_id="tenant-1",
        )
        doc.metadata["storage_object_key"] = "path/to/file"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"bad content"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)
        mock_parser.parse.side_effect = Exception("解析失败")

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
        )

        result = await service.parse_document(doc_id, "tenant-1")

        assert result.parse_status == ParseStatus.FAILED
        mock_event_publisher.publish.assert_not_called()
