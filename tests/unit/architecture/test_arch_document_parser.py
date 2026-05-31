"""Story 2-2a: SDD 架构约束验证测试

验证文档解析功能的架构合规性：
- domain 层零外部依赖
- 解析器位于 infrastructure 层
- DocumentParserPort 位于 domain 层
"""

from __future__ import annotations

import importlib


class TestDomainLayerPurity:
    """验证 domain 层零外部依赖"""

    def test_parsed_document_no_external_deps(self) -> None:
        """parsed_document.py 不依赖外部库"""
        mod = importlib.import_module("src.domain.value_objects.parsed_document")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if hasattr(attr, "__module__") and attr.__module__:
                assert not attr.__module__.startswith(
                    ("pypdf", "docx", "openpyxl", "pytesseract", "pillow", "prefect", "fastapi", "pydantic", "sqlalchemy")
                ), f"domain 层禁止依赖 {attr.__module__}"

    def test_document_parser_port_is_protocol(self) -> None:
        """DocumentParserPort 是 Protocol"""
        from src.domain.ports.document_parser import DocumentParserPort

        assert hasattr(DocumentParserPort, "_is_protocol") or hasattr(DocumentParserPort, "__protocol_attrs__")

    def test_document_parser_port_has_parse_method(self) -> None:
        """DocumentParserPort 定义了 parse 方法"""
        from src.domain.ports.document_parser import DocumentParserPort

        assert hasattr(DocumentParserPort, "parse")


class TestInfrastructureLayerPlacement:
    """验证解析器位于 infrastructure 层"""

    def test_pdf_parser_in_infrastructure(self) -> None:
        from src.infrastructure.external_services.document_parsing.pdf_parser import PDFParser

        assert "infrastructure" in PDFParser.__module__

    def test_word_parser_in_infrastructure(self) -> None:
        from src.infrastructure.external_services.document_parsing.word_parser import WordParser

        assert "infrastructure" in WordParser.__module__

    def test_text_parser_in_infrastructure(self) -> None:
        from src.infrastructure.external_services.document_parsing.text_parser import TextParser

        assert "infrastructure" in TextParser.__module__

    def test_composite_parser_in_infrastructure(self) -> None:
        from src.infrastructure.external_services.document_parsing.composite_parser import CompositeDocumentParser

        assert "infrastructure" in CompositeDocumentParser.__module__


class TestDependencyDirection:
    """验证依赖方向正确"""

    def test_infrastructure_imports_domain(self) -> None:
        """infrastructure 层可以导入 domain 层"""
        from src.domain.ports.document_parser import DocumentParserPort
        from src.domain.value_objects.parsed_document import ParsedDocument
        from src.infrastructure.external_services.document_parsing.composite_parser import CompositeDocumentParser

        # infrastructure 层引用了 domain 层的类型
        assert CompositeDocumentParser is not None
        assert DocumentParserPort is not None
        assert ParsedDocument is not None

    def test_application_imports_domain(self) -> None:
        """application 层可以导入 domain 层"""
        from src.application.services.document_parsing_service import DocumentParsingService

        assert "application" in DocumentParsingService.__module__

    def test_composite_parser_satisfies_protocol(self) -> None:
        """CompositeDocumentParser 满足 DocumentParserPort 协议"""
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
