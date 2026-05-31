"""组合解析器单元测试

TDD 红阶段：测试 CompositeDocumentParser 的 MIME 类型路由和未知 MIME 拒绝。
"""

from __future__ import annotations

import os
import tempfile

import pytest
from pypdf import PdfWriter


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


class TestCompositeParserRouting:
    """MIME 类型路由测试"""

    def test_pdf_mime_routes_to_pdf_parser(self) -> None:
        from src.infrastructure.external_services.document_parsing.composite_parser import CompositeDocumentParser
        from src.infrastructure.external_services.document_parsing.pdf_parser import PDFParser
        from src.infrastructure.external_services.document_parsing.text_parser import TextParser
        from src.infrastructure.external_services.document_parsing.word_parser import WordParser

        parser = CompositeDocumentParser(
            pdf_parser=PDFParser(),
            word_parser=WordParser(),
            text_parser=TextParser(),
        )
        path = _create_minimal_pdf()
        try:
            result = parser.parse(path, "application/pdf")
            assert result.parse_status == "completed"
            assert result.mime_type == "application/pdf"
        finally:
            os.unlink(path)

    def test_docx_mime_routes_to_word_parser(self) -> None:
        from src.infrastructure.external_services.document_parsing.composite_parser import CompositeDocumentParser
        from src.infrastructure.external_services.document_parsing.pdf_parser import PDFParser
        from src.infrastructure.external_services.document_parsing.text_parser import TextParser
        from src.infrastructure.external_services.document_parsing.word_parser import WordParser

        parser = CompositeDocumentParser(
            pdf_parser=PDFParser(),
            word_parser=WordParser(),
            text_parser=TextParser(),
        )
        path = _create_minimal_docx()
        try:
            result = parser.parse(path, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            assert result.parse_status == "completed"
        finally:
            os.unlink(path)

    def test_txt_mime_routes_to_text_parser(self) -> None:
        from src.infrastructure.external_services.document_parsing.composite_parser import CompositeDocumentParser
        from src.infrastructure.external_services.document_parsing.pdf_parser import PDFParser
        from src.infrastructure.external_services.document_parsing.text_parser import TextParser
        from src.infrastructure.external_services.document_parsing.word_parser import WordParser

        parser = CompositeDocumentParser(
            pdf_parser=PDFParser(),
            word_parser=WordParser(),
            text_parser=TextParser(),
        )
        path = _create_minimal_txt()
        try:
            result = parser.parse(path, "text/plain")
            assert result.parse_status == "completed"
            assert result.mime_type == "text/plain"
        finally:
            os.unlink(path)


class TestCompositeParserUnknownMime:
    """未知 MIME 类型拒绝测试"""

    def test_unknown_mime_raises_value_error(self) -> None:
        from src.infrastructure.external_services.document_parsing.composite_parser import CompositeDocumentParser
        from src.infrastructure.external_services.document_parsing.pdf_parser import PDFParser
        from src.infrastructure.external_services.document_parsing.text_parser import TextParser
        from src.infrastructure.external_services.document_parsing.word_parser import WordParser

        parser = CompositeDocumentParser(
            pdf_parser=PDFParser(),
            word_parser=WordParser(),
            text_parser=TextParser(),
        )
        path = _create_minimal_txt()
        try:
            with pytest.raises(ValueError, match="不支持的 MIME"):
                parser.parse(path, "application/unknown")
        finally:
            os.unlink(path)


class TestCompositeParserPortContract:
    """验证 CompositeDocumentParser 满足 DocumentParserPort 协议"""

    def test_satisfies_protocol(self) -> None:
        from src.domain.ports.document_parser import DocumentParserPort
        from src.infrastructure.external_services.document_parsing.composite_parser import CompositeDocumentParser
        from src.infrastructure.external_services.document_parsing.pdf_parser import PDFParser
        from src.infrastructure.external_services.document_parsing.text_parser import TextParser
        from src.infrastructure.external_services.document_parsing.word_parser import WordParser

        parser = CompositeDocumentParser(
            pdf_parser=PDFParser(),
            word_parser=WordParser(),
            text_parser=TextParser(),
        )
        assert isinstance(parser, DocumentParserPort)
