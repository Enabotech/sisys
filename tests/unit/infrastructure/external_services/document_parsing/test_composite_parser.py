"""组合解析器单元测试

TDD 红阶段：测试 CompositeDocumentParser 的 MIME 类型路由和未知 MIME 拒绝。
"""

from __future__ import annotations

import os
import tempfile

from pypdf import PdfWriter

# MIME 类型常量（与 composition_root 保持一致）
MIME_PDF = "application/pdf"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_DOC = "application/msword"
MIME_TXT = "text/plain"


def _create_minimal_pdf() -> str:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    writer.write(tmp.name)
    tmp.close()
    return tmp.name


def _create_minimal_docx() -> str:
    from docx import Document

    doc = Document()
    doc.add_paragraph("test")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc.save(tmp.name)
    tmp.close()
    return tmp.name


def _create_minimal_txt() -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    tmp.write(b"hello world")
    tmp.close()
    return tmp.name


def _build_composite():
    """构造使用 dict 注入的 CompositeDocumentParser（与 composition_root 一致）"""
    from src.infrastructure.external_services.document_parsing.composite_parser import (
        CompositeDocumentParser,
    )
    from src.infrastructure.external_services.document_parsing.pdf_parser import (
        PDFParser,
    )
    from src.infrastructure.external_services.document_parsing.text_parser import (
        TextParser,
    )
    from src.infrastructure.external_services.document_parsing.word_parser import (
        WordParser,
    )

    return CompositeDocumentParser(
        parsers={
            MIME_PDF: PDFParser(),
            MIME_DOCX: WordParser(),
            MIME_DOC: WordParser(),  # DOC 格式由 WordParser 返回友好拒绝消息
            MIME_TXT: TextParser(),
        },
    )


class TestCompositeParserRouting:
    """MIME 类型路由测试"""

    def test_pdf_mime_routes_to_pdf_parser(self) -> None:
        parser = _build_composite()
        path = _create_minimal_pdf()
        try:
            result = parser.parse(path, MIME_PDF)
            assert result.parse_status == "completed"
            assert result.mime_type == "application/pdf"
        finally:
            os.unlink(path)

    def test_docx_mime_routes_to_word_parser(self) -> None:
        parser = _build_composite()
        path = _create_minimal_docx()
        try:
            result = parser.parse(path, MIME_DOCX)
            assert result.parse_status == "completed"
        finally:
            os.unlink(path)

    def test_txt_mime_routes_to_text_parser(self) -> None:
        parser = _build_composite()
        path = _create_minimal_txt()
        try:
            result = parser.parse(path, MIME_TXT)
            assert result.parse_status == "completed"
            assert result.mime_type == "text/plain"
        finally:
            os.unlink(path)


class TestCompositeParserUnknownMime:
    """未知 MIME 类型拒绝测试"""

    def test_unknown_mime_returns_failed(self) -> None:
        """不支持的 MIME 类型返回 failed 状态（与其他解析器错误处理策略一致）"""
        parser = _build_composite()
        path = _create_minimal_txt()
        try:
            result = parser.parse(path, "application/unknown")
            assert result.parse_status == "failed"
            assert result.error_message is not None
            assert "不支持的 MIME 类型" in result.error_message
        finally:
            os.unlink(path)


class TestCompositeParserDocRouting:
    """DOC 格式路由测试 — 验证 AC-2 友好拒绝消息"""

    def test_doc_mime_routes_to_word_parser(self) -> None:
        """验证 DOC 格式路由到 WordParser，返回友好中文错误消息"""
        parser = _build_composite()
        # 创建一个非 DOCX 格式文件（模拟 DOC）
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".doc")
        tmp.write(b"not a valid docx")
        tmp.close()
        try:
            result = parser.parse(tmp.name, MIME_DOC)
            assert result.parse_status == "failed"
            assert result.error_message is not None
            assert "DOCX" in result.error_message or "DOC" in result.error_message
        finally:
            os.unlink(tmp.name)


class TestCompositeParserPortContract:
    """验证 CompositeDocumentParser 满足 DocumentParserPort 协议"""

    def test_satisfies_protocol(self) -> None:
        from src.domain.ports.document_parser import DocumentParserPort

        parser = _build_composite()
        assert isinstance(parser, DocumentParserPort)
