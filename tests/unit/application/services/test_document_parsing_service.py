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

    @pytest.mark.asyncio
    async def test_pdf_page_renderer_none_graceful_degradation(
        self, mock_repo, mock_storage, mock_event_publisher, mock_parser
    ) -> None:
        """验证 pdf_page_renderer=None（layout_detector 非 None）时正常解析（降级策略）"""
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

        # layout_detector 非 None 但 pdf_page_renderer=None
        mock_layout_detector = MagicMock()
        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
            layout_detector=mock_layout_detector,
            # pdf_page_renderer=None（未注入）
        )

        result = await service.parse_document(doc_id, "t1")

        assert result.parse_status == ParseStatus.COMPLETED
        # 降级条件下不应调用 detect
        mock_layout_detector.detect.assert_not_called()

    @pytest.mark.asyncio
    async def test_per_page_independent_failure(self, mock_repo, mock_storage, mock_event_publisher, mock_parser) -> None:
        """验证逐页独立降级：某页检测失败不影响其他页"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import (
            BoundingBox,
            BoundingBoxResult,
            ParsedDocument,
            ParsedElement,
            ParsedPage,
        )

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="multi.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "path/to/multi.pdf"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"pdf data"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        # 构造 2 页 ParsedDocument
        elem1 = ParsedElement(content="第一页文本", bbox=None)
        elem2 = ParsedElement(content="第二页文本", bbox=None)
        mock_parser.parse.return_value = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            pages=[
                ParsedPage(page_number=1, texts=[elem1]),
                ParsedPage(page_number=2, texts=[elem2]),
            ],
        )

        # mock renderer 正常返回
        mock_pdf_renderer = MagicMock()
        mock_pdf_renderer.render_page.return_value = b"\x89PNG_fake"

        # mock detector: 第 1 页抛异常，第 2 页正常返回
        mock_layout_detector = MagicMock()
        detection_result = BoundingBoxResult(
            label="Text",
            bbox=BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0, page=2),
            confidence=0.95,
        )
        mock_layout_detector.detect.side_effect = [
            RuntimeError("第 1 页推理失败"),  # 第 1 页抛异常
            [detection_result],  # 第 2 页正常返回
        ]

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=mock_event_publisher,
            document_parser=mock_parser,
            layout_detector=mock_layout_detector,
            pdf_page_renderer=mock_pdf_renderer,
        )

        result = await service.parse_document(doc_id, "t1")

        # 整体解析成功
        assert result.parse_status == ParseStatus.COMPLETED
        parse_result = result.metadata["parse_result"]

        # 第 1 页：检测失败，bbox 保持 None
        page1_texts = parse_result["pages"][0]["texts"]
        assert page1_texts[0]["bbox"] is None

        # 第 2 页：检测成功，bbox 已填充
        page2_texts = parse_result["pages"][1]["texts"]
        assert page2_texts[0]["bbox"] is not None
        assert page2_texts[0]["bbox"]["page"] == 2

    @pytest.mark.asyncio
    async def test_layout_detection_page_with_no_texts(
        self, mock_repo, mock_storage, mock_event_publisher, mock_parser
    ) -> None:
        """验证空 texts 页面直接跳过增强（continue 分支）"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import (
            BoundingBox,
            BoundingBoxResult,
            ParsedDocument,
            ParsedPage,
        )

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="empty.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "path/to/empty.pdf"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"pdf"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        # 构造空 texts 的 ParsedDocument
        mock_parser.parse.return_value = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1, texts=[])],
        )

        mock_layout_detector = MagicMock()
        mock_layout_detector.detect.return_value = [
            BoundingBoxResult(
                label="Text",
                bbox=BoundingBox(x=0.0, y=0.0, width=100.0, height=50.0, page=1),
                confidence=0.9,
            ),
        ]
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
        assert result.parse_status == ParseStatus.COMPLETED
        # 空 texts 页面保持不变
        assert result.metadata["parse_result"]["pages"][0]["texts"] == []

    @pytest.mark.asyncio
    async def test_layout_detection_empty_detections_preserves_page(
        self, mock_repo, mock_storage, mock_event_publisher, mock_parser
    ) -> None:
        """验证 detect 返回空列表时保持原页面不变（continue 分支）"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="blank.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "path/to/blank.pdf"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"pdf"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        element = ParsedElement(content="无版面检测文本", bbox=None)
        mock_parser.parse.return_value = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1, texts=[element])],
        )

        # detect 返回空列表
        mock_layout_detector = MagicMock()
        mock_layout_detector.detect.return_value = []
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
        assert result.parse_status == ParseStatus.COMPLETED
        # 空检测结果 → bbox 保持 None
        page_texts = result.metadata["parse_result"]["pages"][0]["texts"]
        assert page_texts[0]["bbox"] is None

    @pytest.mark.asyncio
    async def test_layout_detection_preserves_images_field(
        self, mock_repo, mock_storage, mock_event_publisher, mock_parser
    ) -> None:
        """验证版面检测增强后 images 字段不丢失"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import (
            BoundingBox,
            BoundingBoxResult,
            ParsedDocument,
            ParsedElement,
            ParsedPage,
        )

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="img.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "path/to/img.pdf"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"pdf"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        image_element = ParsedElement(content="", metadata={"format": "PNG", "width": 800, "height": 600})
        text_element = ParsedElement(content="图片说明", bbox=None)
        mock_parser.parse.return_value = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1, texts=[text_element], images=[image_element])],
        )

        mock_layout_detector = MagicMock()
        mock_layout_detector.detect.return_value = [
            BoundingBoxResult(
                label="Caption",
                bbox=BoundingBox(x=10.0, y=500.0, width=200.0, height=20.0, page=1),
                confidence=0.88,
            ),
        ]
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
        assert result.parse_status == ParseStatus.COMPLETED
        page_data = result.metadata["parse_result"]["pages"][0]
        # images 字段应保留（修复前的 bug 会丢失 images）
        assert len(page_data["images"]) == 1
        assert page_data["images"][0]["metadata"]["format"] == "PNG"

    @pytest.mark.asyncio
    async def test_layout_detection_element_with_existing_bbox_not_overwritten(
        self, mock_repo, mock_storage, mock_event_publisher, mock_parser
    ) -> None:
        """验证已有 bbox 的元素不被版面检测结果覆盖（else 分支）"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import (
            BoundingBox,
            BoundingBoxResult,
            ParsedDocument,
            ParsedElement,
            ParsedPage,
        )

        doc_id = uuid.uuid4()
        doc = Document(document_id=doc_id, filename="bbox.pdf", mime_type="application/pdf", tenant_id="t1")
        doc.metadata["storage_object_key"] = "path/to/bbox.pdf"

        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"pdf"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        # 构造已有 bbox 的元素（bbox 非 None）
        existing_bbox = BoundingBox(x=50.0, y=50.0, width=200.0, height=30.0, page=1)
        element_with_bbox = ParsedElement(content="已有bbox文本", bbox=existing_bbox, confidence=0.99)
        mock_parser.parse.return_value = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1, texts=[element_with_bbox])],
        )

        mock_layout_detector = MagicMock()
        mock_layout_detector.detect.return_value = [
            BoundingBoxResult(
                label="Text",
                bbox=BoundingBox(x=0.0, y=0.0, width=100.0, height=100.0, page=1),
                confidence=0.7,
            ),
        ]
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
        assert result.parse_status == ParseStatus.COMPLETED
        page_texts = result.metadata["parse_result"]["pages"][0]["texts"]
        # 已有 bbox 的元素不应被覆盖
        assert page_texts[0]["bbox"]["x"] == 50.0
        assert page_texts[0]["bbox"]["width"] == 200.0
        assert page_texts[0]["confidence"] == 0.99


class TestDocumentParsingServiceTableExtraction:
    """表格语义提取集成测试

    测试 DocumentParsingService 的 table_extractor 可选注入和 _apply_table_extraction 编排。
    """

    @pytest.mark.asyncio
    async def test_table_extractor_injected_enhances_tables(self) -> None:
        """table_extractor 注入时触发语义增强"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedPage, ParsedTable

        doc_id = uuid.uuid4()
        doc = Document(
            document_id=doc_id,
            filename="test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            tenant_id="t1",
            parse_status=ParseStatus.PENDING,
            metadata={"storage_object_key": "raw-documents/test.xlsx"},
        )

        mock_repo = AsyncMock()
        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        mock_storage = AsyncMock()

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"fake xlsx content"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        mock_parser = MagicMock()
        parsed = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            pages=[ParsedPage(page_number=1, tables=[ParsedTable(rows=[["姓名", "年龄"], ["张三", "30"]])])],
            parse_status="completed",
        )
        mock_parser.parse.return_value = parsed

        # mock table_extractor
        mock_table_extractor = MagicMock()
        enhanced_table = ParsedTable(
            rows=[["姓名", "年龄"], ["张三", "30"]],
            header=["姓名", "年龄"],
            semantic_confidence=0.85,
        )
        mock_table_extractor.extract.return_value = [enhanced_table]

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=AsyncMock(),
            document_parser=mock_parser,
            table_extractor=mock_table_extractor,
        )

        result = await service.parse_document(doc_id, "t1")
        assert result.parse_status == ParseStatus.COMPLETED
        mock_table_extractor.extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_table_extractor_none_skips_enhancement(self) -> None:
        """table_extractor=None 时跳过语义增强"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedPage, ParsedTable

        doc_id = uuid.uuid4()
        doc = Document(
            document_id=doc_id,
            filename="test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            tenant_id="t1",
            parse_status=ParseStatus.PENDING,
            metadata={"storage_object_key": "raw-documents/test.xlsx"},
        )

        mock_repo = AsyncMock()
        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        mock_storage = AsyncMock()

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"fake xlsx content"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        mock_parser = MagicMock()
        parsed = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            pages=[ParsedPage(page_number=1, tables=[ParsedTable(rows=[["A", "B"]])])],
            parse_status="completed",
        )
        mock_parser.parse.return_value = parsed

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=AsyncMock(),
            document_parser=mock_parser,
            table_extractor=None,
        )

        result = await service.parse_document(doc_id, "t1")
        assert result.parse_status == ParseStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_table_extractor_failure_degrades(self) -> None:
        """table_extractor 运行时异常降级（WARNING + 原始 tables）"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedPage, ParsedTable

        doc_id = uuid.uuid4()
        doc = Document(
            document_id=doc_id,
            filename="test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            tenant_id="t1",
            parse_status=ParseStatus.PENDING,
            metadata={"storage_object_key": "raw-documents/test.xlsx"},
        )

        mock_repo = AsyncMock()
        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        mock_storage = AsyncMock()

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"fake xlsx content"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        mock_parser = MagicMock()
        parsed = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            pages=[ParsedPage(page_number=1, tables=[ParsedTable(rows=[["A"]])])],
            parse_status="completed",
        )
        mock_parser.parse.return_value = parsed

        mock_table_extractor = MagicMock()
        mock_table_extractor.extract.side_effect = RuntimeError("表格语义提取失败")

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=AsyncMock(),
            document_parser=mock_parser,
            table_extractor=mock_table_extractor,
        )

        result = await service.parse_document(doc_id, "t1")
        # 降级后解析状态仍为 COMPLETED
        assert result.parse_status == ParseStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_table_extraction_preserves_parse_status(self) -> None:
        """表格提取失败不影响解析状态"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedPage

        doc_id = uuid.uuid4()
        doc = Document(
            document_id=doc_id,
            filename="test.pdf",
            mime_type="application/pdf",
            tenant_id="t1",
            parse_status=ParseStatus.PENDING,
            metadata={"storage_object_key": "raw-documents/test.pdf"},
        )

        mock_repo = AsyncMock()
        mock_repo.find.return_value = doc
        mock_repo.save.return_value = doc

        mock_storage = AsyncMock()

        def mock_retrieve(*args, **kwargs):
            async def _stream():
                yield b"fake pdf content"

            return _stream()

        mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

        mock_parser = MagicMock()
        parsed = ParsedDocument(
            document_id=str(doc_id),
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1)],
            parse_status="completed",
        )
        mock_parser.parse.return_value = parsed

        mock_table_extractor = MagicMock()
        mock_table_extractor.extract.side_effect = RuntimeError("提取失败")

        service = DocumentParsingService(
            document_repository=mock_repo,
            document_storage=mock_storage,
            event_publisher=AsyncMock(),
            document_parser=mock_parser,
            table_extractor=mock_table_extractor,
        )

        result = await service.parse_document(doc_id, "t1")
        assert result.parse_status == ParseStatus.COMPLETED
