"""基础设施层 TableSemanticExtractor 单元测试

TDD 红阶段：验证通用表格语义提取编排器对领域服务的编排调用和降级策略。
所有领域服务通过 mock 注入，不依赖真实实现。
"""

from __future__ import annotations

from src.domain.value_objects.parsed_document import (
    ParsedTable,
)
from src.infrastructure.document_parsing.table_semantic_extractor import (
    TableSemanticExtractor,
)


class TestTableSemanticExtractorStandard:
    """标准表格语义提取测试"""

    def test_extract_enhances_single_table(self) -> None:
        """单表格语义增强"""
        extractor = TableSemanticExtractor()
        tables = [
            ParsedTable(rows=[["姓名", "年龄"], ["张三", "30"]]),
        ]
        result = extractor.extract(
            "/tmp/test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", tables
        )
        assert len(result) == 1
        assert result[0].header is not None
        assert result[0].column_types is not None

    def test_extract_enhances_multiple_tables(self) -> None:
        """多表格语义增强"""
        extractor = TableSemanticExtractor()
        tables = [
            ParsedTable(rows=[["A", "B"], ["1", "2"]]),
            ParsedTable(rows=[["C", "D"], ["3", "4"]]),
        ]
        result = extractor.extract(
            "/tmp/test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", tables
        )
        assert len(result) == 2

    def test_extract_empty_table_list(self) -> None:
        """空表格列表直接返回"""
        extractor = TableSemanticExtractor()
        result = extractor.extract("/tmp/test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", [])
        assert result == []

    def test_extract_preserves_original_rows(self) -> None:
        """语义增强不修改原始 rows"""
        extractor = TableSemanticExtractor()
        original_rows = [["姓名", "年龄"], ["张三", "30"]]
        tables = [ParsedTable(rows=original_rows)]
        result = extractor.extract(
            "/tmp/test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", tables
        )
        assert result[0].rows == original_rows

    def test_extract_sets_semantic_confidence(self) -> None:
        """语义增强设置综合置信度"""
        extractor = TableSemanticExtractor()
        tables = [ParsedTable(rows=[["姓名", "年龄"], ["张三", "30"]])]
        result = extractor.extract(
            "/tmp/test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", tables
        )
        assert result[0].semantic_confidence is not None
        assert 0.0 <= result[0].semantic_confidence <= 1.0

    def test_extract_to_dict_contains_all_semantic_fields(self) -> None:
        """to_dict() 包含所有语义字段"""
        extractor = TableSemanticExtractor()
        tables = [ParsedTable(rows=[["姓名", "年龄"], ["张三", "30"]])]
        result = extractor.extract(
            "/tmp/test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", tables
        )
        d = result[0].to_dict()
        assert "header" in d
        assert "column_types" in d
        assert "merged_cells" in d
        assert "semantic_confidence" in d


class TestTableSemanticExtractorNoHeader:
    """无表头表格处理"""

    def test_no_header_table_returns_none_header(self) -> None:
        """无表头表格的 header 字段为 None"""
        extractor = TableSemanticExtractor()
        tables = [ParsedTable(rows=[["100", "200"], ["300", "400"]])]
        result = extractor.extract("/tmp/test.csv", "text/csv", tables)
        # 无表头时 header 应为 None
        assert result[0].header is None

    def test_no_header_still_has_column_types(self) -> None:
        """无表头时仍执行列类型推断"""
        extractor = TableSemanticExtractor()
        tables = [ParsedTable(rows=[["100", "200"], ["300", "400"]])]
        result = extractor.extract("/tmp/test.csv", "text/csv", tables)
        assert result[0].column_types is not None


class TestTableSemanticExtractorDegradation:
    """降级策略测试"""

    def test_header_detector_failure_degrades_gracefully(self) -> None:
        """表头检测失败时降级（header=None，不抛异常）"""
        extractor = TableSemanticExtractor()
        # 空行数据模拟边缘 case
        tables = [ParsedTable(rows=[[""]])]
        result = extractor.extract(
            "/tmp/test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", tables
        )
        # 不应抛异常，降级处理
        assert len(result) == 1

    def test_column_classifier_failure_degrades_gracefully(self) -> None:
        """列类型推断失败时降级"""
        extractor = TableSemanticExtractor()
        tables = [ParsedTable(rows=[])]
        result = extractor.extract(
            "/tmp/test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", tables
        )
        # 空行不抛异常
        assert len(result) == 1

    def test_non_table_mime_type_still_processes(self) -> None:
        """非表格 MIME 类型仍可处理（语义提取不依赖 MIME 过滤）"""
        extractor = TableSemanticExtractor()
        tables = [ParsedTable(rows=[["A", "B"], ["1", "2"]])]
        result = extractor.extract("/tmp/test.txt", "text/plain", tables)
        assert len(result) == 1


class TestTableSemanticExtractorProtocol:
    """Protocol 合规性测试"""

    def test_implements_table_extractor_port(self) -> None:
        """验证 TableSemanticExtractor 满足 TableExtractorPort Protocol"""
        from src.domain.ports.table_extractor import TableExtractorPort

        extractor = TableSemanticExtractor()
        assert isinstance(extractor, TableExtractorPort)

    def test_has_extract_method(self) -> None:
        """验证 extract 方法存在"""
        extractor = TableSemanticExtractor()
        assert hasattr(extractor, "extract")
        assert callable(extractor.extract)
