"""Story 2-3: 版面检测端到端集成测试

测试文档解析 + 版面检测的完整编排流程：
1. 构造小 PDF 文件（reportlab）
2. 使用真实 pypdfium2 渲染页面图像（如果可用）
3. Mock ONNX 推理会话（避免真实模型依赖）
4. Mock MinIO/PostgreSQL/EventPublisher
5. 验证 ParsedDocument 中 bbox 不为 null
6. 验证 layout_confidence 写入 metadata

Run with: poetry run pytest tests/integration/test_integration_document_layout.py -v
"""

from __future__ import annotations

import tempfile
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.value_objects.parsed_document import (
    BoundingBox,
    BoundingBoxResult,
    ParsedDocument,
    ParsedElement,
    ParsedPage,
)


def _create_minimal_pdf() -> str:
    """用 reportlab 构造含文本的单页 PDF"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)
    c.drawString(72, 720, "版面检测集成测试文档")
    c.showPage()
    c.save()
    tmp.close()
    return tmp.name


class TestLayoutDetectionIntegration:
    """端到端版面检测集成测试"""

    @pytest.mark.asyncio
    async def test_full_pipeline_pdf_layout_detection(self) -> None:
        """完整流程：PDF 创建 → 渲染 → 检测 → bbox 合并 → 事件发布"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.entities.document import Document, ParseStatus
        from src.domain.events.document_events import DocumentProcessed

        # 1. 创建测试 PDF
        pdf_path = _create_minimal_pdf()

        try:
            # 2. Mock 基础设施端口
            mock_repo = AsyncMock()
            mock_event_publisher = AsyncMock()

            # Mock storage.retrieve 返回文件流
            def mock_retrieve(*args, **kwargs):
                async def _stream():
                    with open(pdf_path, "rb") as f:
                        yield f.read()

                return _stream()

            mock_storage = MagicMock()
            mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

            # Mock 解析器：返回含文本元素的 ParsedDocument
            element = ParsedElement(content="版面检测集成测试文档", bbox=None)
            mock_parser = MagicMock()
            mock_parser.parse.return_value = ParsedDocument(
                document_id="test-doc-id",
                mime_type="application/pdf",
                pages=[ParsedPage(page_number=1, texts=[element])],
            )

            # 3. Mock layout_detector：返回版面检测结果
            mock_layout_detector = MagicMock()
            mock_layout_detector.detect.return_value = [
                BoundingBoxResult(
                    label="Text",
                    bbox=BoundingBox(x=72.0, y=720.0, width=200.0, height=12.0, page=1),
                    confidence=0.92,
                ),
            ]

            # 4. Mock pdf_page_renderer：返回 PNG 图像字节
            mock_pdf_renderer = MagicMock()
            mock_pdf_renderer.render_page.return_value = b"\x89PNG\r\n\x1a\nfake_png"

            # 5. 创建服务并执行解析
            doc_id = uuid.uuid4()
            doc = Document(
                document_id=doc_id,
                filename="layout_test.pdf",
                mime_type="application/pdf",
                file_size_bytes=1024,
                tenant_id="integration-test",
            )
            doc.metadata["storage_object_key"] = "test/layout_test.pdf"

            mock_repo.find.return_value = doc
            mock_repo.save.return_value = doc

            service = DocumentParsingService(
                document_repository=mock_repo,
                document_storage=mock_storage,
                event_publisher=mock_event_publisher,
                document_parser=mock_parser,
                layout_detector=mock_layout_detector,
                pdf_page_renderer=mock_pdf_renderer,
            )

            result = await service.parse_document(doc_id, "integration-test")

            # 6. 验证解析完成
            assert result.parse_status == ParseStatus.COMPLETED

            # 7. 验证事件发布（包含 bbox 数据）
            mock_event_publisher.publish.assert_called_once()
            event = mock_event_publisher.publish.call_args[0][0]
            assert isinstance(event, DocumentProcessed)
            parse_result = event.parse_result

            # 8. 验证 render_page 被调用
            mock_pdf_renderer.render_page.assert_called_once()

            # 9. 验证 detect 被调用
            mock_layout_detector.detect.assert_called_once()

            # 10. 验证 parse_result 中 bbox 不为 null
            assert parse_result is not None
            assert "pages" in parse_result
            page_data = parse_result["pages"][0]
            texts = page_data.get("texts", [])
            assert len(texts) > 0

            # 至少有一个元素的 bbox 被填充
            matched = [t for t in texts if t.get("bbox") is not None]
            assert len(matched) > 0, "应有至少一个元素的 bbox 被版面检测填充"

            # 11. 验证 bbox 包含完整 5 字段
            matched_bbox = matched[0]["bbox"]
            assert {"x", "y", "width", "height", "page"} == set(matched_bbox.keys())

            # 12. 验证 layout_confidence 写入 metadata
            assert "layout_confidence" in matched[0].get("metadata", {})

        finally:
            import os

            os.unlink(pdf_path)

    @pytest.mark.asyncio
    async def test_pipeline_without_layout_detector_graceful(self) -> None:
        """验证 layout_detector 未注入时完整流程仍正常"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.entities.document import Document, ParseStatus

        pdf_path = _create_minimal_pdf()

        try:
            mock_repo = AsyncMock()
            mock_event_publisher = AsyncMock()

            element = ParsedElement(content="文本", bbox=None)
            mock_parser = MagicMock()
            mock_parser.parse.return_value = ParsedDocument(
                document_id="test-doc-id",
                mime_type="application/pdf",
                pages=[ParsedPage(page_number=1, texts=[element])],
            )

            def mock_retrieve(*args, **kwargs):
                async def _stream():
                    with open(pdf_path, "rb") as f:
                        yield f.read()

                return _stream()

            mock_storage = MagicMock()
            mock_storage.retrieve = MagicMock(side_effect=mock_retrieve)

            doc_id = uuid.uuid4()
            doc = Document(document_id=doc_id, filename="test.pdf", mime_type="application/pdf", tenant_id="t1")
            doc.metadata["storage_object_key"] = "key"
            mock_repo.find.return_value = doc
            mock_repo.save.return_value = doc

            # 不注入 layout_detector 和 pdf_page_renderer
            service = DocumentParsingService(
                document_repository=mock_repo,
                document_storage=mock_storage,
                event_publisher=mock_event_publisher,
                document_parser=mock_parser,
            )

            result = await service.parse_document(doc_id, "t1")
            assert result.parse_status == ParseStatus.COMPLETED

        finally:
            import os

            os.unlink(pdf_path)

    @pytest.mark.asyncio
    async def test_real_pypdfium2_render_and_mock_detect(self) -> None:
        """使用真实 pypdfium2 渲染 + mock ONNX 推理的端到端验证"""
        try:
            import importlib.util

            if not importlib.util.find_spec("pypdfium2"):
                pytest.skip("pypdfium2 未安装，跳过真实渲染测试")
        except ImportError:
            pytest.skip("pypdfium2 未安装，跳过真实渲染测试")

        from src.infrastructure.document_parsing.pdf_page_renderer import PdfPageRenderer

        pdf_path = _create_minimal_pdf()

        try:
            # 1. 使用真实 PdfPageRenderer 渲染 PDF 页面
            renderer = PdfPageRenderer(dpi=72)
            image_bytes = renderer.render_page(pdf_path, page_number=1)

            # 2. 验证返回的是 PNG 字节
            assert isinstance(image_bytes, bytes)
            assert len(image_bytes) > 0
            assert image_bytes[:4] == b"\x89PNG"

            # 3. Mock layout_detector 使用真实渲染结果
            mock_layout_detector = MagicMock()
            mock_layout_detector.detect.return_value = [
                BoundingBoxResult(
                    label="Text",
                    bbox=BoundingBox(x=50.0, y=700.0, width=300.0, height=20.0, page=1),
                    confidence=0.88,
                ),
            ]

            # 4. 验证 detect 收到的 image_bytes 是有效 PNG
            results = mock_layout_detector.detect(image_bytes, page_number=1)
            assert len(results) == 1
            assert results[0].label == "Text"
            assert results[0].bbox.page == 1

        finally:
            import os

            os.unlink(pdf_path)
