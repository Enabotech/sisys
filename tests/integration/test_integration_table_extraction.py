"""Story 2-4 表格语义提取集成测试

验证端到端表格语义提取流程：解析器产出原始 ParsedTable → TableSemanticExtractor
语义增强 → 增强后的 ParsedTable 含表头/列类型/合并单元格等语义字段。

测试策略：
- 使用 mock 规避真实文件系统和 pdfplumber 依赖
- 验证 TableSemanticExtractor 编排三个领域服务的正确性
- 验证降级路径：table_extractor=None 跳过、运行时异常不阻断
- 验证 DocumentParsingService._apply_table_extraction() 集成行为

Run with: poetry run pytest tests/integration/test_integration_table_extraction.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.domain.value_objects.parsed_document import (
    ColumnType,
    ParsedDocument,
    ParsedPage,
    ParsedTable,
)

# ===================================================================
# 测试数据工厂
# ===================================================================


def _create_sample_table() -> ParsedTable:
    """创建含表头的标准表格"""
    return ParsedTable(
        rows=[
            ["姓名", "年龄", "薪资"],
            ["张三", "30", "50000"],
            ["李四", "25", "35000"],
        ],
    )


def _create_no_header_table() -> ParsedTable:
    """创建无表头的纯数据表格"""
    return ParsedTable(
        rows=[
            ["100", "200", "300"],
            ["400", "500", "600"],
        ],
    )


def _create_empty_table() -> ParsedTable:
    """创建空表格"""
    return ParsedTable(rows=[])


def _create_parsed_doc(
    tables: list[ParsedTable], mime_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
) -> ParsedDocument:
    """创建包含指定表格的 ParsedDocument"""
    return ParsedDocument(
        document_id="test-doc-001",
        mime_type=mime_type,
        pages=[
            ParsedPage(
                page_number=1,
                texts=[],
                tables=tables,
                images=[],
            ),
        ],
    )


# ===================================================================
# 集成测试
# ===================================================================


class TestTableSemanticExtractorIntegration:
    """TableSemanticExtractor 集成测试（mock 领域服务）"""

    @pytest.mark.asyncio
    async def test_extract_enhances_single_table(self) -> None:
        """标准表格语义提取：表头+列类型"""
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        extractor = TableSemanticExtractor()
        table = _create_sample_table()
        result = extractor.extract(
            file_path="/tmp/test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            tables=[table],
        )

        assert len(result) == 1
        enhanced = result[0]
        assert enhanced.header == ["姓名", "年龄", "薪资"]
        assert enhanced.column_types is not None
        assert len(enhanced.column_types) == 3
        assert enhanced.column_types[0].col_type == ColumnType.STRING
        assert enhanced.column_types[1].col_type == ColumnType.NUMBER
        assert enhanced.column_types[2].col_type == ColumnType.NUMBER
        # 原始 rows 保持不变
        assert enhanced.rows == table.rows

    @pytest.mark.asyncio
    async def test_extract_no_header_table(self) -> None:
        """无表头表格：header=None，列类型仍被推断"""
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        extractor = TableSemanticExtractor()
        table = _create_no_header_table()
        result = extractor.extract(
            file_path="/tmp/test.csv",
            mime_type="text/csv",
            tables=[table],
        )

        assert len(result) == 1
        enhanced = result[0]
        assert enhanced.header is None  # 无表头
        assert enhanced.column_types is not None
        assert len(enhanced.column_types) == 3
        # 纯数字 → NUMBER
        assert all(ct.col_type == ColumnType.NUMBER for ct in enhanced.column_types)

    @pytest.mark.asyncio
    async def test_extract_empty_tables(self) -> None:
        """空表格列表返回空"""
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        extractor = TableSemanticExtractor()
        result = extractor.extract(
            file_path="/tmp/test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            tables=[],
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_preserves_multiple_tables(self) -> None:
        """多表格同时增强"""
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        extractor = TableSemanticExtractor()
        tables = [_create_sample_table(), _create_no_header_table()]
        result = extractor.extract(
            file_path="/tmp/test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            tables=tables,
        )

        assert len(result) == 2
        assert result[0].header == ["姓名", "年龄", "薪资"]
        assert result[1].header is None

    @pytest.mark.asyncio
    async def test_extract_semantic_confidence_calculated(self) -> None:
        """语义提取综合置信度被正确计算"""
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        extractor = TableSemanticExtractor()
        table = _create_sample_table()
        result = extractor.extract(
            file_path="/tmp/test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            tables=[table],
        )

        enhanced = result[0]
        assert enhanced.semantic_confidence is not None
        assert 0.0 <= enhanced.semantic_confidence <= 1.0

    @pytest.mark.asyncio
    async def test_extract_to_dict_contains_all_semantic_fields(self) -> None:
        """to_dict() 输出包含所有语义字段"""
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        extractor = TableSemanticExtractor()
        table = _create_sample_table()
        result = extractor.extract(
            file_path="/tmp/test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            tables=[table],
        )

        d = result[0].to_dict()
        assert "header" in d
        assert "column_types" in d
        assert "merged_cells" in d
        assert "semantic_confidence" in d

    @pytest.mark.asyncio
    async def test_individual_table_failure_does_not_affect_others(self) -> None:
        """单个表格增强失败不影响其他表格"""
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        # 注入会抛异常的 mock
        with patch(
            "src.infrastructure.document_parsing.table_semantic_extractor.detect_header",
            side_effect=[RuntimeError("模拟失败"), (0, 0.95)],
        ):
            extractor = TableSemanticExtractor()
            tables = [_create_sample_table(), _create_sample_table()]
            result = extractor.extract(
                file_path="/tmp/test.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                tables=tables,
            )

            assert len(result) == 2
            # 第一个表格失败 → 降级返回原始表格
            assert result[0].header is None  # 原始值未增强
            assert result[0].rows == tables[0].rows
            # 第二个表格正常增强
            assert result[1].header == ["姓名", "年龄", "薪资"]


class TestDocumentParsingServiceTableExtractionIntegration:
    """DocumentParsingService._apply_table_extraction() 集成测试"""

    @pytest.mark.asyncio
    async def test_table_extractor_injected_enhances_tables(self) -> None:
        """table_extractor 注入时，表格被语义增强"""
        from src.application.services.document_parsing_service import (
            DocumentParsingService,
        )
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        service = DocumentParsingService(
            document_repository=MagicMock(),
            document_parser=MagicMock(),
            event_publisher=MagicMock(),
            document_storage=MagicMock(),
            redis_client=MagicMock(),
            table_extractor=TableSemanticExtractor(),
        )

        doc = _create_parsed_doc([_create_sample_table()])
        result = await service._apply_table_extraction(
            parsed_doc=doc,
            file_path="/tmp/test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        assert len(result.pages) == 1
        assert result.pages[0].tables[0].header == ["姓名", "年龄", "薪资"]

    @pytest.mark.asyncio
    async def test_table_extractor_none_skips_enhancement(self) -> None:
        """table_extractor=None 时跳过表格语义增强"""
        from src.application.services.document_parsing_service import (
            DocumentParsingService,
        )

        service = DocumentParsingService(
            document_repository=MagicMock(),
            document_parser=MagicMock(),
            event_publisher=MagicMock(),
            document_storage=MagicMock(),
            redis_client=MagicMock(),
            table_extractor=None,
        )

        doc = _create_parsed_doc([_create_sample_table()])
        result = await service._apply_table_extraction(
            parsed_doc=doc,
            file_path="/tmp/test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # 无增强，原始表格 header 为 None
        assert result.pages[0].tables[0].header is None

    @pytest.mark.asyncio
    async def test_runtime_exception_degrades_gracefully(self) -> None:
        """运行时异常降级：返回原始文档，解析状态不受影响"""
        from src.application.services.document_parsing_service import (
            DocumentParsingService,
        )

        failing_extractor = MagicMock()
        failing_extractor.extract.side_effect = RuntimeError("表格提取失败")

        service = DocumentParsingService(
            document_repository=MagicMock(),
            document_parser=MagicMock(),
            event_publisher=MagicMock(),
            document_storage=MagicMock(),
            redis_client=MagicMock(),
            table_extractor=failing_extractor,
        )

        doc = _create_parsed_doc([_create_sample_table()])
        result = await service._apply_table_extraction(
            parsed_doc=doc,
            file_path="/tmp/test.pdf",
            mime_type="application/pdf",
        )

        # 降级返回原文档
        assert result.pages[0].tables[0].header is None
        assert result.pages[0].tables[0].rows == _create_sample_table().rows

    @pytest.mark.asyncio
    async def test_no_tables_skips_processing(self) -> None:
        """无表格时跳过处理，不调用 extractor"""
        from src.application.services.document_parsing_service import (
            DocumentParsingService,
        )

        mock_extractor = MagicMock()
        service = DocumentParsingService(
            document_repository=MagicMock(),
            document_parser=MagicMock(),
            event_publisher=MagicMock(),
            document_storage=MagicMock(),
            redis_client=MagicMock(),
            table_extractor=mock_extractor,
        )

        doc = _create_parsed_doc([])  # 无表格
        result = await service._apply_table_extraction(
            parsed_doc=doc,
            file_path="/tmp/test.pdf",
            mime_type="application/pdf",
        )

        mock_extractor.extract.assert_not_called()
        assert len(result.pages) == 1
        assert result.pages[0].tables == []


class TestPdfTableExtractorIntegration:
    """PdfTableExtractor 集成测试（mock pdfplumber）"""

    @pytest.mark.asyncio
    async def test_detect_single_table_with_pdfplumber(self) -> None:
        """pdfplumber 检测到单表格"""
        from src.infrastructure.document_parsing.pdf_table_extractor import (
            PdfTableExtractor,
        )

        # Mock pdfplumber 页面（与单元测试同样的 mock 模式）
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [["名称", "数量"], ["项目A", "100"]],
        ]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]

        with patch("src.infrastructure.document_parsing.pdf_table_extractor.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

            extractor = PdfTableExtractor()
            result = extractor.extract(
                file_path="/tmp/test.pdf",
                mime_type="application/pdf",
                tables=[],
            )

            assert len(result) == 1
            assert result[0].rows == [["名称", "数量"], ["项目A", "100"]]

    @pytest.mark.asyncio
    async def test_non_pdf_mime_returns_empty(self) -> None:
        """非 PDF MIME 类型返回空列表"""
        from src.infrastructure.document_parsing.pdf_table_extractor import (
            PdfTableExtractor,
        )

        extractor = PdfTableExtractor()
        result = extractor.extract(
            file_path="/tmp/test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            tables=[],
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_pdfplumber_unavailable_returns_empty(self) -> None:
        """pdfplumber 未安装时降级返回空列表"""
        from src.infrastructure.document_parsing.pdf_table_extractor import (
            PdfTableExtractor,
        )

        with patch.dict("sys.modules", {"pdfplumber": None}):
            extractor = PdfTableExtractor()
            result = extractor.extract(
                file_path="/tmp/test.pdf",
                mime_type="application/pdf",
                tables=[],
            )
            assert result == []


class TestCompositionRootTableExtractor:
    """Composition Root 端口注册验证"""

    @pytest.mark.asyncio
    async def test_table_extractor_port_registered(self) -> None:
        """table_extractor 端口在 composition_root 中注册"""
        from src.domain.ports.registry import _global_registry

        # 检查 table_extractor 是否在注册表中
        assert "table_extractor" in _global_registry._ports, "table_extractor 端口应已注册"

    @pytest.mark.asyncio
    async def test_pdf_table_extractor_port_registered(self) -> None:
        """pdf_table_extractor 端口在 composition_root 中注册"""
        from src.domain.ports.registry import _global_registry

        assert "pdf_table_extractor" in _global_registry._ports, "pdf_table_extractor 端口应已注册"
