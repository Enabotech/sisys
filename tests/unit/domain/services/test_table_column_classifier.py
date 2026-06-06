"""领域层 列类型推断服务单元测试

TDD 红阶段：验证列类型推断领域服务的正则模式匹配和类型转换试探，
覆盖 7 种列类型（STRING/NUMBER/DATE/CURRENCY/PERCENTAGE/BOOLEAN/UNKNOWN）。
"""

from __future__ import annotations

import pytest

from src.domain.services.table_column_classifier import classify_columns
from src.domain.value_objects.parsed_document import ColumnType


class TestColumnTypeInference:
    """列类型推断测试"""

    def test_number_column(self) -> None:
        """纯数字列 → NUMBER"""
        rows = [["100"], ["200"], ["300"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.NUMBER

    def test_float_column(self) -> None:
        """浮点数字列 → NUMBER"""
        rows = [["3.14"], ["2.72"], ["1.41"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.NUMBER

    def test_number_with_comma(self) -> None:
        """千分位数字列 → NUMBER"""
        rows = [["1,000"], ["2,000"], ["10,000"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.NUMBER

    def test_date_iso_column(self) -> None:
        """ISO 日期列 → DATE"""
        rows = [["2024-01-15"], ["2024-02-20"], ["2024-03-10"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.DATE

    def test_date_slash_column(self) -> None:
        """斜杠日期列 → DATE"""
        rows = [["2024/01/15"], ["2024/02/20"], ["2024/03/10"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.DATE

    def test_currency_yen_column(self) -> None:
        """人民币列 → CURRENCY"""
        rows = [["¥50,000"], ["¥30,000"], ["¥80,000"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.CURRENCY

    def test_currency_dollar_column(self) -> None:
        """美元列 → CURRENCY"""
        rows = [["$100"], ["$200"], ["$300"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.CURRENCY

    def test_currency_euro_column(self) -> None:
        """欧元列 → CURRENCY"""
        rows = [["€100"], ["€200"], ["€300"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.CURRENCY

    def test_percentage_column(self) -> None:
        """百分比列 → PERCENTAGE"""
        rows = [["50%"], ["30%"], ["80%"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.PERCENTAGE

    def test_boolean_column(self) -> None:
        """布尔列 → BOOLEAN"""
        rows = [["true"], ["false"], ["true"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.BOOLEAN

    def test_boolean_chinese_column(self) -> None:
        """中文布尔列 → BOOLEAN"""
        rows = [["是"], ["否"], ["是"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.BOOLEAN

    def test_string_column(self) -> None:
        """文本字符串列 → STRING"""
        rows = [["张三"], ["李四"], ["王五"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.STRING

    def test_mixed_column_degrades_to_string(self) -> None:
        """混合类型列降级为 STRING（类型占比不足 60%）"""
        rows = [["文本"], ["100"], ["2024-01-01"], ["¥50"], ["更多文本"]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.STRING

    def test_empty_rows_return_unknown(self) -> None:
        """空行列表 → UNKNOWN"""
        result = classify_columns([])
        assert result == []

    def test_empty_column_return_unknown(self) -> None:
        """全空列 → UNKNOWN"""
        rows = [[""], [""], [""]]
        result = classify_columns(rows)
        assert result[0].col_type == ColumnType.UNKNOWN


class TestColumnInfoOutput:
    """ColumnInfo 输出结构测试"""

    def test_column_name_from_header(self) -> None:
        """列名来自表头"""
        rows = [["100"], ["200"]]
        result = classify_columns(rows, column_names=["数量"])
        assert result[0].name == "数量"

    def test_column_name_auto_generated(self) -> None:
        """无表头时自动生成列名"""
        rows = [["100"], ["200"]]
        result = classify_columns(rows)
        assert result[0].name == "col_0"

    def test_confidence_is_float(self) -> None:
        """置信度为浮点数"""
        rows = [["100"], ["200"], ["300"]]
        result = classify_columns(rows)
        assert isinstance(result[0].confidence, float)
        assert 0.0 <= result[0].confidence <= 1.0

    def test_nullable_ratio_calculation(self) -> None:
        """空值比率计算"""
        rows = [["100"], [""], ["300"]]
        result = classify_columns(rows)
        assert result[0].nullable_ratio == pytest.approx(1 / 3, abs=0.01)

    def test_sample_values_populated(self) -> None:
        """采样值已填充"""
        rows = [["100"], ["200"], ["300"]]
        result = classify_columns(rows)
        assert len(result[0].sample_values) > 0

    def test_sample_values_max_five(self) -> None:
        """采样值最多 5 个"""
        rows = [[str(i)] for i in range(10)]
        result = classify_columns(rows)
        assert len(result[0].sample_values) <= 5

    def test_multi_column_classification(self) -> None:
        """多列同时推断"""
        rows = [
            ["张三", "30", "2024-01-15", "¥50,000"],
            ["李四", "25", "2024-02-20", "¥30,000"],
        ]
        result = classify_columns(rows, column_names=["姓名", "年龄", "入职日期", "薪资"])
        assert result[0].col_type == ColumnType.STRING
        assert result[1].col_type == ColumnType.NUMBER
        assert result[2].col_type == ColumnType.DATE
        assert result[3].col_type == ColumnType.CURRENCY

    def test_sample_size_limit(self) -> None:
        """采样行数限制（sample_size 参数）"""
        rows = [[str(i)] for i in range(100)]
        result = classify_columns(rows, sample_size=10)
        # 仅采样前 10 行
        assert len(result[0].sample_values) <= 10
