"""PDF 格式处理器单元测试

验证 PdfFormatHandler 元数据提取、内容标题提取、垃圾标题过滤

"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from plugins.crawler.core.format.handlers.pdf_handler import PdfFormatHandler
from plugins.crawler.core.value_objects import FileMetadata


class TestPdfFormatHandler:
    """PdfFormatHandler 测试"""

    def setup_method(self) -> None:
        self.handler = PdfFormatHandler()

    def _create_pdf_with_text(
        self,
        first_page_text: str,
        title: str = "",
        author: str = "",
    ) -> str:
        """创建带文本内容的测试 PDF 文件

        Args:
            first_page_text: 首页文本内容
            title: PDF 元数据标题
            author: PDF 元数据作者

        Returns:
            临时文件路径
        """
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        c.drawString(72, 720, first_page_text)
        c.showPage()
        c.save()
        buf.seek(0)

        reader = PdfReader(buf)
        writer = PdfWriter()
        writer.append_pages_from_reader(reader)

        if title or author:
            metadata = {}
            if title:
                metadata["/Title"] = title
            if author:
                metadata["/Author"] = author
            writer.add_metadata(metadata)

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        writer.write(tmp)
        tmp.close()
        return tmp.name

    def _create_blank_pdf(self, title: str = "", author: str = "") -> str:
        """创建空白 PDF 文件

        Args:
            title: PDF 元数据标题
            author: PDF 元数据作者

        Returns:
            临时文件路径
        """
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)

        if title or author:
            metadata = {}
            if title:
                metadata["/Title"] = title
            if author:
                metadata["/Author"] = author
            writer.add_metadata(metadata)

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        writer.write(tmp)
        tmp.close()
        return tmp.name

    def test_can_handle_pdf_extension(self) -> None:
        """应识别 .pdf 扩展名"""
        assert self.handler.can_handle("test.pdf", "")

    def test_can_handle_pdf_mime(self) -> None:
        """应识别 application/pdf MIME"""
        assert self.handler.can_handle("test.bin", "application/pdf")

    def test_cannot_handle_non_pdf(self) -> None:
        """不应处理非 PDF 文件"""
        assert not self.handler.can_handle("test.docx", "application/msword")

    def test_extract_metadata_with_title(self) -> None:
        """应提取 PDF 元数据标题"""
        path = self._create_blank_pdf(title="测试报告", author="张三")
        try:
            meta = self.handler.extract_metadata(path)
            assert isinstance(meta, FileMetadata)
            assert meta.title == "测试报告"
            assert meta.author == "张三"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_extract_metadata_empty_returns_default(self) -> None:
        """无元数据时应返回空 FileMetadata"""
        path = self._create_blank_pdf()
        try:
            meta = self.handler.extract_metadata(path)
            assert isinstance(meta, FileMetadata)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_content_title_from_first_page(self) -> None:
        """无大纲时应从首页文本提取标题"""
        path = self._create_pdf_with_text(first_page_text="2024 Annual Report")
        try:
            meta = self.handler.extract_metadata(path)
            assert "Annual Report" in meta.content_title
        finally:
            Path(path).unlink(missing_ok=True)

    def test_content_title_garbage_filtered(self) -> None:
        """应过滤工具生成的垃圾标题"""
        path = self._create_pdf_with_text(first_page_text="Microsoft Word")
        try:
            meta = self.handler.extract_metadata(path)
            assert meta.content_title == ""
        finally:
            Path(path).unlink(missing_ok=True)

    def test_is_garbage_title(self) -> None:
        """应识别常见垃圾标题"""
        assert self.handler._is_garbage_title("Microsoft Word")
        assert self.handler._is_garbage_title("Acrobat Distiller")
        assert self.handler._is_garbage_title("PDFCreator")
        assert not self.handler._is_garbage_title("Annual Report 2024")
