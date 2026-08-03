"""基础设施层 PdfTableDetector 单元测试

TDD 红阶段：验证 PDF 专用表格检测器，mock pdfplumber 测试各种场景。
不依赖真实 PDF 文件，所有 pdfplumber 调用通过 mock 注入。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from src.domain.value_objects.parsed_document import ParsedTable
from src.infrastructure.document_parsing.pdf_table_extractor import PdfTableDetector


class TestPdfTableDetectorStandard:
    """标准 PDF 表格检测测试"""

    @patch("src.infrastructure.document_parsing.pdf_table_extractor._pdfplumber")
    def test_detect_single_table(self, mock_pdfplumber: Any) -> None:
        """检测单页中的单个表格"""
        # mock pdfplumber 返回包含表格的页面
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [[["A", "B"], ["1", "2"]]]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        detector = PdfTableDetector()
        result = detector.detect("/tmp/test.pdf", "application/pdf")

        assert len(result) == 1
        assert isinstance(result[0], ParsedTable)

    @patch("src.infrastructure.document_parsing.pdf_table_extractor._pdfplumber")
    def test_detect_multiple_tables_on_page(self, mock_pdfplumber: Any) -> None:
        """检测单页中的多个表格"""
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [["A", "B"], ["1", "2"]],
            [["X", "Y"], ["3", "4"]],
        ]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        detector = PdfTableDetector()
        result = detector.detect("/tmp/test.pdf", "application/pdf")

        assert len(result) == 2

    @patch("src.infrastructure.document_parsing.pdf_table_extractor._pdfplumber")
    def test_no_tables_on_page(self, mock_pdfplumber: Any) -> None:
        """页面无表格"""
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        detector = PdfTableDetector()
        result = detector.detect("/tmp/test.pdf", "application/pdf")

        assert result == []

    @patch("src.infrastructure.document_parsing.pdf_table_extractor._pdfplumber")
    def test_empty_pdf(self, mock_pdfplumber: Any) -> None:
        """空 PDF（0 页）"""
        mock_pdf = MagicMock()
        mock_pdf.pages = []
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        detector = PdfTableDetector()
        result = detector.detect("/tmp/test.pdf", "application/pdf")

        assert result == []

    @patch("src.infrastructure.document_parsing.pdf_table_extractor._pdfplumber")
    def test_multi_page_pdf_tables(self, mock_pdfplumber: Any) -> None:
        """多页 PDF，每页含表格"""
        mock_page1 = MagicMock()
        mock_page1.extract_tables.return_value = [[["A", "B"], ["1", "2"]]]
        mock_page2 = MagicMock()
        mock_page2.extract_tables.return_value = [[["C", "D"], ["3", "4"]]]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        detector = PdfTableDetector()
        result = detector.detect("/tmp/test.pdf", "application/pdf")

        assert len(result) == 2


class TestPdfTableDetectorDegradation:
    """降级策略测试"""

    @patch("src.infrastructure.document_parsing.pdf_table_extractor._pdfplumber")
    def test_pdfplumber_runtime_exception_returns_empty(self, mock_pdfplumber: Any) -> None:
        """pdfplumber 运行时异常 → 空列表降级"""
        mock_pdfplumber.open.side_effect = RuntimeError("PDF 文件损坏")

        detector = PdfTableDetector()
        result = detector.detect("/tmp/test.pdf", "application/pdf")

        # 运行时异常降级为空列表
        assert result == []

    @patch("src.infrastructure.document_parsing.pdf_table_extractor._pdfplumber")
    def test_extract_tables_exception_degrades(self, mock_pdfplumber: Any) -> None:
        """extract_tables 方法异常 → 降级"""
        mock_page = MagicMock()
        mock_page.extract_tables.side_effect = RuntimeError("解析失败")
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        detector = PdfTableDetector()
        result = detector.detect("/tmp/test.pdf", "application/pdf")

        # 单页异常降级为空列表
        assert result == []

    def test_non_pdf_mime_returns_empty(self) -> None:
        """非 PDF MIME 类型直接返回空"""
        detector = PdfTableDetector()
        result = detector.detect("/tmp/test.txt", "text/plain")
        assert result == []


class TestPdfTableDetectorProtocol:
    """Protocol 合规性测试"""

    def test_implements_table_detector_port(self) -> None:
        """验证 PdfTableDetector 满足 TableDetectorPort Protocol"""
        from src.domain.ports.table_detector import TableDetectorPort

        detector = PdfTableDetector()
        assert isinstance(detector, TableDetectorPort)


class TestPdfTableDetectorReturnValues:
    """返回值结构测试"""

    @patch("src.infrastructure.document_parsing.pdf_table_extractor._pdfplumber")
    def test_returned_table_has_correct_rows(self, mock_pdfplumber: Any) -> None:
        """返回的 ParsedTable.rows 与 pdfplumber 返回的数据一致"""
        mock_page = MagicMock()
        table_data = [["姓名", "年龄"], ["张三", "30"]]
        mock_page.extract_tables.return_value = [table_data]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        detector = PdfTableDetector()
        result = detector.detect("/tmp/test.pdf", "application/pdf")

        assert len(result) == 1
        assert result[0].rows == table_data
