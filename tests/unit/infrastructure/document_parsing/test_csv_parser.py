"""CSV 文档解析器单元测试

TDD 红阶段：测试 CSVParser 的分隔符自动检测、编码检测、空文件拒绝、大文件分块。
使用 csv 标准库创建 fixture CSV 文件。
"""

from __future__ import annotations

import os
import tempfile


def _create_csv_content(content: str, encoding: str = "utf-8") -> str:
    """创建指定编码的 CSV fixture"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    tmp.write(content.encode(encoding))
    tmp.close()
    return tmp.name


MIME_CSV = "text/csv"


class TestCSVParserCreation:
    """CSVParser 构造和基本功能测试"""

    def test_create_parser(self) -> None:
        from src.infrastructure.document_parsing.csv_parser import CSVParser

        parser = CSVParser()
        assert parser is not None

    def test_parser_implements_document_parser_port(self) -> None:
        from src.domain.ports.document_parser import DocumentParserPort
        from src.infrastructure.document_parsing.csv_parser import CSVParser

        assert isinstance(CSVParser(), DocumentParserPort)


class TestCSVParserBasic:
    """基本 CSV 解析测试"""

    def test_parse_standard_csv(self) -> None:
        """解析标准逗号分隔 CSV"""
        from src.infrastructure.document_parsing.csv_parser import CSVParser

        path = _create_csv_content("姓名,部门,职级\n张三,技术部,P7\n李四,市场部,P6\n")
        try:
            parser = CSVParser()
            result = parser.parse(path, MIME_CSV)

            assert result.is_completed()
            assert len(result.pages) == 1
            tables = result.pages[0].tables
            assert len(tables) == 1
            assert tables[0].rows == [["姓名", "部门", "职级"], ["张三", "技术部", "P7"], ["李四", "市场部", "P6"]]
        finally:
            os.unlink(path)

    def test_parse_semicolon_delimited_csv(self) -> None:
        """解析分号分隔 CSV（Sniffer 自动检测）"""
        from src.infrastructure.document_parsing.csv_parser import CSVParser

        path = _create_csv_content("姓名;部门;职级\n张三;技术部;P7\n")
        try:
            parser = CSVParser()
            result = parser.parse(path, MIME_CSV)

            assert result.is_completed()
            tables = result.pages[0].tables
            assert len(tables[0].rows) >= 2
            assert len(tables[0].rows[0]) == 3, f"应为 3 列，实际: {len(tables[0].rows[0])}"
            assert tables[0].rows[0][0] == "姓名", f"首列首行应为 '姓名'，实际: {tables[0].rows[0][0]}"
        finally:
            os.unlink(path)


class TestCSVParserEncoding:
    """编码检测测试"""

    def test_parse_gbk_encoded_csv(self) -> None:
        """解析 GBK 编码 CSV"""
        from src.infrastructure.document_parsing.csv_parser import CSVParser

        content = "姓名,部门\n张三,技术部\n"
        path = _create_csv_content(content, encoding="gbk")
        try:
            parser = CSVParser()
            result = parser.parse(path, MIME_CSV)

            assert result.is_completed()
            all_text = " ".join(cell for t in result.pages[0].tables for row in t.rows for cell in row)
            assert "张三" in all_text, f"GBK 中文应正确提取，实际: {all_text}"
        finally:
            os.unlink(path)


class TestCSVParserEmptyDocument:
    """空文档检测测试"""

    def test_empty_csv_returns_failed(self) -> None:
        """空 CSV 返回 failed"""
        from src.infrastructure.document_parsing.csv_parser import CSVParser

        path = _create_csv_content("")
        try:
            parser = CSVParser()
            result = parser.parse(path, MIME_CSV)

            assert result.parse_status == "failed"
            assert result.error_message is not None
        finally:
            os.unlink(path)
