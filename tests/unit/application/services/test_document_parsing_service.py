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
            document_id="random-parser-uuid",
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
        assert call_args.document_id == doc_id
        assert call_args.tenant_id == "tenant-1"
        assert call_args.parse_result["document_id"] == str(doc_id)

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
        # 使用 side_effect 捕获每次 save 时的 parse_status 快照
        capture: dict[str, list] = {"statuses": []}

        async def capture_save(d):
            capture["statuses"].append(d.parse_status)
            return d

        mock_repo.save.side_effect = capture_save

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

        # 验证 save 调用顺序：PENDING → IN_PROGRESS → COMPLETED
        # 实际只显式 2 次 save（IN_PROGRESS + COMPLETED），PENDING 是初始状态
        # 使用 side_effect 捕获每次 save 时的 parse_status 快照（避免 mutable doc 引用问题）
        captured_statuses = capture["statuses"]
        assert len(captured_statuses) == 2
        # 第一次 save 应是 IN_PROGRESS
        assert captured_statuses[0] == ParseStatus.IN_PROGRESS
        # 第二次 save 应是 COMPLETED
        assert captured_statuses[1] == ParseStatus.COMPLETED


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


class TestDocumentParsingServiceDownloadTemp:
    """_download_to_temp 防御逻辑测试"""

    @pytest.mark.asyncio
    async def test_stream_aclose_called_on_success(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        """验证正常下载完成后 stream.aclose() 被调用"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="t.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "key"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        mock_stream = AsyncMock()
        mock_stream.__aiter__ = MagicMock(return_value=mock_stream)
        mock_stream.__anext__ = AsyncMock(side_effect=[b"data", StopAsyncIteration])
        mock_stream.aclose = AsyncMock()
        mock_storage.retrieve = MagicMock(return_value=mock_stream)
        mock_parser.parse.return_value = ParsedDocument(document_id=str(doc_id), mime_type="application/pdf")

        service = DocumentParsingService(mock_repo, mock_storage, mock_event_publisher, mock_parser)
        await service.parse_document(doc_id, "t1")

        mock_stream.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_aclose_called_on_exception(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        """验证下载中断时 stream.aclose() 仍被调用"""
        from src.application.services.document_parsing_service import DocumentParsingService

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="t.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "key"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        mock_stream = AsyncMock()
        mock_stream.__aiter__ = MagicMock(return_value=mock_stream)
        mock_stream.__anext__ = AsyncMock(side_effect=RuntimeError("connection lost"))
        mock_stream.aclose = AsyncMock()
        mock_storage.retrieve = MagicMock(return_value=mock_stream)

        service = DocumentParsingService(mock_repo, mock_storage, mock_event_publisher, mock_parser)
        result = await service.parse_document(doc_id, "t1")

        assert result.parse_status == ParseStatus.FAILED
        mock_stream.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_suffix_fallback_to_tmp(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        """验证非白名单后缀回退到 .tmp"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="malware.exe", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "path/to/malware.exe"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"data"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)
        mock_parser.parse.return_value = ParsedDocument(document_id=str(doc_id), mime_type="application/pdf")

        service = DocumentParsingService(mock_repo, mock_storage, mock_event_publisher, mock_parser)
        result = await service.parse_document(doc_id, "t1")

        assert result.parse_status == ParseStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_parser_returns_failed_status(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        """验证解析器返回 failed 状态时 Service 正确处理"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="encrypted.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "key"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"encrypted content"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)
        mock_parser.parse.return_value = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            parse_status="failed",
            error_message="PDF 已加密",
        )

        service = DocumentParsingService(mock_repo, mock_storage, mock_event_publisher, mock_parser)
        result = await service.parse_document(doc_id, "t1")

        assert result.parse_status == ParseStatus.FAILED
        assert "加密" in doc.metadata.get("parse_error", "")
        mock_event_publisher.publish.assert_not_called()


class TestDocumentParsingServiceStatusGuard:
    """乐观锁与状态守卫测试"""

    @pytest.mark.asyncio
    async def test_non_pending_status_skips_processing(
        self, mock_repo, mock_storage, mock_event_publisher, mock_parser
    ) -> None:
        """非 PENDING 状态的文档应直接跳过处理"""
        from src.application.services.document_parsing_service import DocumentParsingService

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="done.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.parse_status = ParseStatus.COMPLETED
        doc.metadata["storage_object_key"] = "key"

        mock_repo.find.return_value = doc

        service = DocumentParsingService(mock_repo, mock_storage, mock_event_publisher, mock_parser)
        result = await service.parse_document(doc_id, "t1")

        assert result.parse_status == ParseStatus.COMPLETED
        mock_repo.save.assert_not_called()
        mock_event_publisher.publish.assert_not_called()


class TestDocumentParsingServiceDistributedLock:
    """Redis 分布式锁测试"""

    @pytest.mark.asyncio
    async def test_lock_acquired_processes_document(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        """获取锁成功时正常处理文档"""
        import asyncio
        from unittest.mock import patch

        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="t.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "key"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"data"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)
        mock_parser.parse.return_value = ParsedDocument(document_id=str(doc_id), mime_type="application/pdf")

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch("src.application.services.document_parsing_service.asyncio") as mock_asyncio:
            mock_asyncio.wait_for = asyncio.wait_for
            mock_asyncio.to_thread = asyncio.to_thread
            mock_asyncio.TimeoutError = asyncio.TimeoutError

            service = DocumentParsingService(mock_repo, mock_storage, mock_event_publisher, mock_parser, mock_redis)
            result = await service.parse_document(doc_id, "t1")

        assert result.parse_status == ParseStatus.COMPLETED
        mock_redis.set.assert_called_once()
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_not_acquired_skips_processing(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        """锁获取失败时跳过处理"""
        from src.application.services.document_parsing_service import DocumentParsingService

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="t.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "key"

        mock_repo.find.return_value = doc

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=None)

        service = DocumentParsingService(mock_repo, mock_storage, mock_event_publisher, mock_parser, mock_redis)
        await service.parse_document(doc_id, "t1")

        mock_repo.save.assert_not_called()
        mock_redis.delete.assert_not_called()


class TestDocumentParsingServiceTimeout:
    """超时场景测试"""

    @pytest.mark.asyncio
    async def test_download_timeout_returns_failed(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        """下载超时时文档状态设为 FAILED"""
        import asyncio

        from src.application.services.document_parsing_service import DocumentParsingService

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="big.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "key"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        service = DocumentParsingService(mock_repo, mock_storage, mock_event_publisher, mock_parser)

        from unittest.mock import patch

        with patch.object(service, "_download_to_temp", AsyncMock(side_effect=asyncio.TimeoutError())):
            result = await service.parse_document(doc_id, "t1")

        assert result.parse_status == ParseStatus.FAILED
        assert "超时" in doc.metadata.get("parse_error", "")
        mock_event_publisher.publish.assert_not_called()
        mock_repo.save.assert_called()


class TestDocumentParsingServiceCancellation:
    """CancelledError 场景测试"""

    @pytest.mark.asyncio
    async def test_cancelled_sets_failed_and_persists(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        """CancelledError 传播前持久化 FAILED 状态"""
        import asyncio
        from unittest.mock import patch

        from src.application.services.document_parsing_service import DocumentParsingService

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="t.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "key"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        service = DocumentParsingService(mock_repo, mock_storage, mock_event_publisher, mock_parser)

        with patch.object(service, "_download_to_temp", AsyncMock(side_effect=asyncio.CancelledError())):
            with pytest.raises(asyncio.CancelledError):
                await service.parse_document(doc_id, "t1")

        assert doc.parse_status == ParseStatus.FAILED
        assert "取消" in doc.metadata.get("parse_error", "")
        mock_event_publisher.publish.assert_not_called()


class TestDocumentParsingServiceLayoutDetection:
    """Story 2-3: 版面检测编排测试

    验证 layout_detector 和 pdf_page_renderer 可选注入后的编排行为：
    PDF 格式触发版面检测，非 PDF 格式跳过，layout_detector 缺失时降级。
    """

    @pytest.mark.asyncio
    async def test_layout_detector_injected_and_pdf_triggers_detection(
        self, mock_repo, mock_storage, mock_event_publisher, mock_parser
    ) -> None:
        """验证 PDF 格式 + layout_detector 注入时触发版面检测"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import (
            BoundingBox,
            BoundingBoxResult,
            ParsedDocument,
            ParsedElement,
            ParsedPage,
        )

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="layout.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "path/to/layout.pdf"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"fake pdf content"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        # 解析器返回含文本元素的 ParsedDocument（bbox=None）
        element = ParsedElement(content="标题文本", bbox=None)
        parsed_doc = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1, texts=[element])],
        )
        mock_parser.parse.return_value = parsed_doc

        # Mock layout_detector 和 pdf_page_renderer
        mock_layout_detector = MagicMock()
        mock_layout_detector.detect.return_value = [
            BoundingBoxResult(
                label="Title",
                bbox=BoundingBox(x=10.0, y=20.0, width=500.0, height=30.0, page=1),
                confidence=0.95,
            ),
        ]
        mock_pdf_renderer = MagicMock()
        mock_pdf_renderer.render_page.return_value = b"\x89PNG_fake_image_bytes"

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
            layout_detector=mock_layout_detector,
            pdf_page_renderer=mock_pdf_renderer,
        )

        result = await service.parse_document(doc_id, "t1")

        assert result.parse_status == ParseStatus.COMPLETED
        # 验证 pdf_page_renderer 被调用
        mock_pdf_renderer.render_page.assert_called()
        # 验证 layout_detector 被调用
        mock_layout_detector.detect.assert_called()

    @pytest.mark.asyncio
    async def test_non_pdf_skips_layout_detection(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        """验证非 PDF 格式不触发版面检测（降级策略）"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="test.txt", mime_type="text/plain", tenant_id="t1")
        doc.metadata["storage_object_key"] = "path/to/test.txt"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"plain text"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        element = ParsedElement(content="纯文本", bbox=None)
        mock_parser.parse.return_value = ParsedDocument(
            document_id=str(doc_id),
            mime_type="text/plain",
            pages=[ParsedPage(page_number=1, texts=[element])],
        )

        mock_layout_detector = MagicMock()
        mock_pdf_renderer = MagicMock()

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
            layout_detector=mock_layout_detector,
            pdf_page_renderer=mock_pdf_renderer,
        )

        result = await service.parse_document(doc_id, "t1")

        assert result.parse_status == ParseStatus.COMPLETED
        # 验证非 PDF 不触发版面检测
        mock_layout_detector.detect.assert_not_called()
        mock_pdf_renderer.render_page.assert_not_called()

    @pytest.mark.asyncio
    async def test_layout_detector_none_graceful_degradation(
        self, mock_repo, mock_storage, mock_event_publisher, mock_parser
    ) -> None:
        """验证 layout_detector=None 时正常解析（降级策略）"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="test.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "path/to/test.pdf"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"pdf content"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        element = ParsedElement(content="文本", bbox=None)
        mock_parser.parse.return_value = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1, texts=[element])],
        )

        # layout_detector=None（默认值），不注入版面检测
        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
        )

        result = await service.parse_document(doc_id, "t1")

        assert result.parse_status == ParseStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_layout_detection_error_does_not_fail_parsing(
        self, mock_repo, mock_storage, mock_event_publisher, mock_parser
    ) -> None:
        """验证版面检测运行时错误不影响解析结果（优雅降级）"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="error.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "path/to/error.pdf"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"pdf data"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        element = ParsedElement(content="文本", bbox=None)
        mock_parser.parse.return_value = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1, texts=[element])],
        )

        # Mock layout_detector 抛出运行时错误
        mock_layout_detector = MagicMock()
        mock_layout_detector.detect.side_effect = RuntimeError("ONNX 推理失败")
        mock_pdf_renderer = MagicMock()
        mock_pdf_renderer.render_page.return_value = b"\x89PNG_fake"

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
            layout_detector=mock_layout_detector,
            pdf_page_renderer=mock_pdf_renderer,
        )

        result = await service.parse_document(doc_id, "t1")

        # 版面检测失败不应导致解析失败
        assert result.parse_status == ParseStatus.COMPLETED
