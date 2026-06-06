"""DocumentParserPort Protocol 行为验证测试

验证文档解析端口的运行时类型检查、同步方法签名和返回类型契约
"""

from __future__ import annotations

import asyncio

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.value_objects.parsed_document import ParsedDocument


class TestDocumentParserPortRuntimeCheckable:
    """DocumentParserPort 结构化子类型检查"""

    def test_compatible_class_passes_isinstance(self) -> None:
        """实现 parse 方法的类应通过 isinstance 检查"""

        class FakeParser:
            def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
                return ParsedDocument(document_id="doc-1", mime_type=mime_type)

        assert isinstance(FakeParser(), DocumentParserPort)

    def test_incompatible_class_fails_isinstance(self) -> None:
        """不实现 parse 方法的类不应通过 isinstance 检查"""

        class Incompatible:
            def other(self) -> None:
                pass

        assert not isinstance(Incompatible(), DocumentParserPort)

    def test_partial_impl_without_parse_fails(self) -> None:
        """仅实现部分方法的类不应通过 isinstance"""

        class Partial:
            file_path: str = ""

        assert not isinstance(Partial(), DocumentParserPort)


class TestDocumentParserPortMethodSignature:
    """DocumentParserPort 方法签名验证"""

    def test_parse_is_synchronous(self) -> None:
        """parse 应为同步方法"""
        assert not asyncio.iscoroutinefunction(DocumentParserPort.parse)

    def test_parse_returns_parsed_document(self) -> None:
        """parse 应返回 ParsedDocument"""

        class FakeParser:
            def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
                return ParsedDocument(document_id="doc-1", mime_type=mime_type)

        parser = FakeParser()
        result = parser.parse("/docs/test.pdf", "application/pdf")
        assert isinstance(result, ParsedDocument)
        assert result.document_id == "doc-1"
        assert result.mime_type == "application/pdf"

    def test_parse_receives_file_path_and_mime_type(self) -> None:
        """parse 应正确接收 file_path 和 mime_type 参数"""
        received: dict[str, str] = {}

        class SpyParser:
            def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
                received["file_path"] = file_path
                received["mime_type"] = mime_type
                return ParsedDocument(document_id="doc-1", mime_type=mime_type)

        parser = SpyParser()
        parser.parse("/data/report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert received["file_path"] == "/data/report.docx"
        assert "openxmlformats" in received["mime_type"]

    def test_parse_with_different_mime_types(self) -> None:
        """parse 应接受不同 MIME 类型"""
        mime_types = [
            "application/pdf",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]

        class FakeParser:
            def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
                return ParsedDocument(document_id="doc-1", mime_type=mime_type)

        parser = FakeParser()
        for mime in mime_types:
            result = parser.parse("/test", mime)
            assert result.mime_type == mime
