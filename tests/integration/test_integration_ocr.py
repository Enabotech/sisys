"""Story 2-5: OCR 集成测试

使用真实 OCR 服务进行端到端集成测试。
OCR 服务不可用时 pytest.skip() 动态跳过。

遵循集成测试规范：
- 真实服务优先（OCR 已在本地环境运行）
- 自包含生命周期：创建临时文件 → 调用 OCR → 清理
- 服务不可用时动态跳过，禁止 @pytest.mark.skip 写死
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from src.domain.value_objects.ocr_result import OCRPageResult
from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage

# ===================================================================
# Helpers
# ===================================================================


def _ocr_adapter_available() -> bool:
    """检查本地 RapidOCR 引擎是否可用"""
    try:
        from rapidocr import RapidOCR  # noqa: F401

        return True
    except ImportError:
        return False


def _create_temp_file(content: str = "test", suffix: str = ".pdf") -> str:
    """创建临时测试文件"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content.encode())
    tmp.close()
    return tmp.name


def _create_blank_pdf(num_pages: int = 1) -> str:
    """用 pypdf 创建空白 PDF"""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    writer.write(tmp.name)
    tmp.close()
    return tmp.name


def _create_pdf_with_text(text: str = "Hello World") -> str:
    """用 reportlab 创建含文本的 PDF"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    tmp.close()
    return tmp.name


def _cleanup(path: str) -> None:
    """安全清理临时文件"""
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture(scope="module")
def event_loop():
    """模块级事件循环（遵循验收测试模式）"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ===================================================================
# 测试类
# ===================================================================


class TestRapidOCRAdapterIntegration:
    """RapidOCR 本地适配器集成测试

    使用本地 RapidOCR 引擎，通过 OCRPort 接口测试端到端流程。
    """

    @pytest.mark.asyncio
    async def test_image_ocr(self) -> None:
        """RapidOCR 识别图像"""
        if not _ocr_adapter_available():
            pytest.skip("RapidOCR 不可用")

        from PIL import Image

        from src.infrastructure.document_parsing.rapidocr_adapter import RapidOCRAdapter

        adapter = RapidOCRAdapter()
        img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        try:
            img = Image.new("RGB", (100, 30), color="white")
            img.save(img_path)

            results = await adapter.recognize(img_path)
            assert len(results) == 1
            assert isinstance(results[0], OCRPageResult)
        finally:
            _cleanup(img_path)


class TestOCRServiceIntegration:
    """OCR 在 DocumentParsingService 中的集成测试

    使用真实 RapidOCR 引擎，通过 DocumentParsingService._apply_ocr() 测试编排流程。
    """

    @pytest.mark.asyncio
    async def test_apply_ocr_with_real_engine(self) -> None:
        """_apply_ocr() 使用真实 RapidOCR 引擎"""
        if not _ocr_adapter_available():
            pytest.skip("RapidOCR 不可用")

        from unittest.mock import MagicMock

        from src.application.services.document_parsing_service import DocumentParsingService
        from src.infrastructure.document_parsing.rapidocr_adapter import RapidOCRAdapter

        ocr_adapter = RapidOCRAdapter()
        service = DocumentParsingService(
            document_repository=MagicMock(),
            document_storage=MagicMock(),
            event_publisher=MagicMock(),
            document_parser=MagicMock(),
            ocr=ocr_adapter,
        )

        pdf_path = _create_blank_pdf(1)
        try:
            pages = [
                ParsedPage(
                    page_number=1,
                    texts=[ParsedElement(content="x" * 5, confidence=1.0)],  # < 50 字符 → 扫描页
                ),
            ]
            doc = ParsedDocument(
                document_id="test-doc",
                mime_type="application/pdf",
                pages=pages,
                parse_status="completed",
                parse_timestamp="2026-07-30T00:00:00",
            )

            result = await service._apply_ocr(doc, pdf_path, "application/pdf")

            # 验证 OCR 已执行：第 1 页内容被替换（即使 RapidOCR 可能返回空结果）
            assert result[0] is not doc  # OCR 已执行，返回新文档

            # 验证置信度标记
            for page in result[0].pages:
                for elem in page.texts:
                    assert 0.0 <= elem.confidence <= 1.0
        finally:
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_ocr_high_density_text_page_skipped(self) -> None:
        """高密度文本页跳过 OCR"""

        from unittest.mock import AsyncMock, MagicMock

        from src.application.services.document_parsing_service import DocumentParsingService

        # 使用 Mock OCR 验证扫描页检测逻辑
        ocr_mock = AsyncMock()
        ocr_mock.recognize.return_value = []

        service = DocumentParsingService(
            document_repository=MagicMock(),
            document_storage=MagicMock(),
            event_publisher=MagicMock(),
            document_parser=MagicMock(),
            ocr=ocr_mock,
        )

        pdf_path = _create_pdf_with_text("A" * 200)
        try:
            pages = [
                ParsedPage(
                    page_number=1,
                    texts=[ParsedElement(content="A" * 200, confidence=1.0)],  # > 50 字符 → 文本页
                ),
            ]
            doc = ParsedDocument(
                document_id="test-doc",
                mime_type="application/pdf",
                pages=pages,
                parse_status="completed",
                parse_timestamp="2026-07-30T00:00:00",
            )

            result = await service._apply_ocr(doc, pdf_path, "application/pdf")

            # 文本页不触发 OCR
            ocr_mock.recognize.assert_not_called()
            assert result[0] is doc
        finally:
            _cleanup(pdf_path)
