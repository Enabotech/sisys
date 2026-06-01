"""组合文档解析器

按 MIME 类型路由到具体解析器（PDF/Word/TXT）的组合模式实现。
"""

from __future__ import annotations

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.value_objects.parsed_document import ParsedDocument
from src.infrastructure.external_services.document_parsing.pdf_parser import PDFParser
from src.infrastructure.external_services.document_parsing.text_parser import TextParser
from src.infrastructure.external_services.document_parsing.word_parser import WordParser

# MIME 类型 → 解析器映射
_MIME_PDF = "application/pdf"
_MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MIME_DOC = "application/msword"
_MIME_TXT = "text/plain"


class CompositeDocumentParser(DocumentParserPort):
    """组合文档解析器 — 按 MIME 类型路由

    内部持有 PDFParser、WordParser、TextParser 实例，
    根据 mime_type 参数路由到对应解析器。
    """

    def __init__(
        self,
        pdf_parser: PDFParser,
        word_parser: WordParser,
        text_parser: TextParser,
    ) -> None:
        self._parsers: dict[str, DocumentParserPort] = {
            _MIME_PDF: pdf_parser,
            _MIME_DOCX: word_parser,
            _MIME_DOC: word_parser,  # DOC 格式由 WordParser 返回友好拒绝消息
            _MIME_TXT: text_parser,
        }

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """按 MIME 类型路由解析

        Args:
            file_path: 本地文件路径
            mime_type: MIME 类型（用于路由决策）

        Returns:
            结构化解析结果

        Raises:
            ValueError: 不支持的 MIME 类型
        """
        parser = self._parsers.get(mime_type)
        if parser is None:
            raise ValueError(f"不支持的 MIME 类型: {mime_type}")
        return parser.parse(file_path, mime_type)
