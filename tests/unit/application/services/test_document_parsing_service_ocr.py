"""DocumentParsingService OCR 集成单元测试

测试 _apply_ocr() 方法的注入、调用、降级和置信度标记逻辑。
使用 Mock OCRPort 模拟 OCR 行为。
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.document_parsing_service import DocumentParsingService
from src.domain.exceptions.ocr_exceptions import OCRConnectionError, OCRProcessingError
from src.domain.value_objects.ocr_result import OCRPageResult
from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage


def _create_temp_file(content: str = "test", suffix: str = ".pdf") -> str:
    """创建临时测试文件"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content.encode())
    tmp.close()
    return tmp.name


def _create_parsing_service(
    ocr_mock: AsyncMock | None = None,
) -> DocumentParsingService:
    """创建带 Mock OCR 的 DocumentParsingService 实例"""
    return DocumentParsingService(
        document_repository=MagicMock(),
        document_storage=MagicMock(),
        event_publisher=MagicMock(),
        document_parser=MagicMock(),
        redis_client=None,
        layout_detector=None,
        pdf_page_renderer=None,
        table_detector=None,
        table_enhancer=None,
        ocr=ocr_mock,
    )


def _create_parsed_doc(
    pages: list[ParsedPage] | None = None,
) -> ParsedDocument:
    """创建测试用 ParsedDocument"""
    if pages is None:
        pages = [
            ParsedPage(
                page_number=1,
                texts=[
                    ParsedElement(content="A" * 100, confidence=1.0),  # 文本页
                ],
            ),
            ParsedPage(
                page_number=2,
                texts=[
                    ParsedElement(content="B" * 5, confidence=1.0),  # 扫描页
                ],
            ),
        ]
    return ParsedDocument(
        document_id="test-doc",
        mime_type="application/pdf",
        pages=pages,
        parse_status="completed",
        parse_timestamp="2026-07-30T00:00:00",
    )


class TestDocumentParsingServiceOCR:
    """DocumentParsingService OCR 步骤测试"""

    @pytest.mark.asyncio
    async def test_ocr_not_injected_skips(self) -> None:
        """OCR 端口未注入（ocr=None）→ 整个 OCR 步骤跳过"""
        service = _create_parsing_service(ocr_mock=None)
        doc = _create_parsed_doc()
        result = await service._apply_ocr(doc, "/tmp/test.pdf", "application/pdf")
        # 文档不变
        assert result[0] is doc

    @pytest.mark.asyncio
    async def test_ocr_injected_scanned_pages_triggered(self) -> None:
        """OCR 端口注入 → 扫描页触发 OCR → ParsedElement.confidence 更新"""
        ocr_mock = AsyncMock()
        ocr_mock.recognize.return_value = [
            OCRPageResult(
                page_number=2,
                elements=[
                    ParsedElement(content="OCR 识别结果", confidence=0.95),
                ],
            ),
        ]

        temp_path = _create_temp_file(content="x" * 1000, suffix=".pdf")
        try:
            service = _create_parsing_service(ocr_mock=ocr_mock)
            doc = _create_parsed_doc()
            result = await service._apply_ocr(doc, temp_path, "application/pdf")

            # 第 1 页（文本页）不变
            assert len(result[0].pages[0].texts) == 1
            assert result[0].pages[0].texts[0].content == "A" * 100
            assert result[0].pages[0].texts[0].confidence == 1.0

            # 第 2 页（扫描页）被 OCR 替换
            assert len(result[0].pages[1].texts) == 1
            assert result[0].pages[1].texts[0].content == "OCR 识别结果"
            assert result[0].pages[1].texts[0].confidence == 0.95

            # 验证 OCR 元数据已返回
            assert result[1]["ocr_engine"] == "paddleocr-vl"
            assert result[1]["ocr_scanned_pages"] == [2]
            assert result[1]["ocr_processed_pages"] == [2]

            ocr_mock.recognize.assert_called_once()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_ocr_injected_text_pages_skipped(self) -> None:
        """OCR 端口注入 → 文本页不触发 OCR → ParsedElement.confidence 保持 1.0"""
        ocr_mock = AsyncMock()

        # 全部为文本页
        pages = [
            ParsedPage(
                page_number=1,
                texts=[ParsedElement(content="A" * 100, confidence=1.0)],
            ),
            ParsedPage(
                page_number=2,
                texts=[ParsedElement(content="B" * 200, confidence=1.0)],
            ),
        ]

        temp_path = _create_temp_file(content="x" * 1000, suffix=".pdf")
        try:
            service = _create_parsing_service(ocr_mock=ocr_mock)
            doc = _create_parsed_doc(pages=pages)
            result = await service._apply_ocr(doc, temp_path, "application/pdf")

            # OCR 未被调用
            ocr_mock.recognize.assert_not_called()
            # 文档不变
            assert result[0] is doc
            assert result[0].pages[0].texts[0].confidence == 1.0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_ocr_connection_error_fallback(self) -> None:
        """OCR 调用抛出 OCRConnectionError → 返回 FAILED 状态 + 脱敏错误信息"""
        ocr_mock = AsyncMock()
        ocr_mock.recognize.side_effect = OCRConnectionError(
            message="服务不可达",
            service_url="http://test:8080",
        )

        temp_path = _create_temp_file(content="x" * 1000, suffix=".pdf")
        try:
            service = _create_parsing_service(ocr_mock=ocr_mock)
            doc = _create_parsed_doc()
            result = await service._apply_ocr(doc, temp_path, "application/pdf")

            # 返回 FAILED 状态
            assert result[0].is_failed()
            assert result[0].error_message is not None
            # 错误信息不泄露内部 URL
            assert "localhost" not in result[0].error_message
            assert "8080" not in result[0].error_message
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_ocr_processing_error_fallback(self) -> None:
        """OCR 调用抛出 OCRProcessingError → 返回 FAILED 状态 + 脱敏错误信息"""
        ocr_mock = AsyncMock()
        ocr_mock.recognize.side_effect = OCRProcessingError(
            message="处理失败",
            service_url="http://test:8080",
            status_code=500,
        )

        temp_path = _create_temp_file(content="x" * 1000, suffix=".pdf")
        try:
            service = _create_parsing_service(ocr_mock=ocr_mock)
            doc = _create_parsed_doc()
            result = await service._apply_ocr(doc, temp_path, "application/pdf")

            # 返回 FAILED 状态
            assert result[0].is_failed()
            assert result[0].error_message is not None
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_low_confidence_marked(self) -> None:
        """置信度 < 0.85 的元素 → metadata[\"needs_review\"] = True"""
        ocr_mock = AsyncMock()
        ocr_mock.recognize.return_value = [
            OCRPageResult(
                page_number=2,
                elements=[
                    ParsedElement(content="模糊文本", confidence=0.45),
                    ParsedElement(content="清晰文本", confidence=0.95),
                ],
            ),
        ]

        temp_path = _create_temp_file(content="x" * 1000, suffix=".pdf")
        try:
            service = _create_parsing_service(ocr_mock=ocr_mock)
            doc = _create_parsed_doc()
            result = await service._apply_ocr(doc, temp_path, "application/pdf")

            # 低置信度元素
            assert result[0].pages[1].texts[0].metadata.get("needs_review") is True
            # 高置信度元素
            assert result[0].pages[1].texts[1].metadata.get("needs_review") is None
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_empty_ocr_result(self) -> None:
        """OCR 返回空结果 → 页面保持原始状态"""
        ocr_mock = AsyncMock()
        ocr_mock.recognize.return_value = []

        temp_path = _create_temp_file(content="x" * 1000, suffix=".pdf")
        try:
            service = _create_parsing_service(ocr_mock=ocr_mock)
            doc = _create_parsed_doc()
            result = await service._apply_ocr(doc, temp_path, "application/pdf")

            # 文档不变
            assert result[0] is doc
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_ocr_unexpected_exception_fallback(self) -> None:
        """OCR 调用抛出未预期异常 → 返回 FAILED 状态 + 脱敏错误信息"""
        ocr_mock = AsyncMock()
        ocr_mock.recognize.side_effect = RuntimeError("unexpected")

        temp_path = _create_temp_file(content="x" * 1000, suffix=".pdf")
        try:
            service = _create_parsing_service(ocr_mock=ocr_mock)
            doc = _create_parsed_doc()
            result = await service._apply_ocr(doc, temp_path, "application/pdf")

            # 返回 FAILED 状态（不再静默降级）
            assert result[0].is_failed()
            assert result[0].error_message is not None
            assert "unexpected" not in result[0].error_message  # 脱敏
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_mark_low_confidence(self) -> None:
        """_mark_low_confidence 静态方法测试"""
        elements = [
            ParsedElement(content="a", confidence=0.5),
            ParsedElement(content="b", confidence=0.9),
            ParsedElement(content="c", confidence=0.84),
            ParsedElement(content="d", confidence=0.85),
        ]
        result = DocumentParsingService._mark_low_confidence(elements)

        assert result[0].metadata.get("needs_review") is True  # 0.5 < 0.85
        assert result[1].metadata.get("needs_review") is None  # 0.9 >= 0.85
        assert result[2].metadata.get("needs_review") is True  # 0.84 < 0.85
        assert result[3].metadata.get("needs_review") is None  # 0.85 >= 0.85
