"""领域层 表头检测服务单元测试

TDD 红阶段：验证表头检测领域服务的多特征加权策略，
包括标准表头检测、无表头表格、单行表格、空表格等边缘 case。
"""

from __future__ import annotations

from src.domain.services.table_header_detector import detect_header


class TestHeaderDetectionStandard:
    """标准表头检测测试"""

    def test_standard_text_header(self) -> None:
        """首行全文本，后续行含数字 → 检测到表头"""
        rows = [
            ["姓名", "年龄", "城市"],
            ["张三", "30", "北京"],
            ["李四", "25", "上海"],
        ]
        idx, conf = detect_header(rows)
        assert idx == 0
        assert conf >= 0.5

    def test_header_with_mixed_data(self) -> None:
        """首行全文本，后续行含货币/日期 → 检测到表头"""
        rows = [
            ["项目", "金额", "日期"],
            ["A", "¥50,000", "2024-01-01"],
            ["B", "¥30,000", "2024-02-01"],
        ]
        idx, conf = detect_header(rows)
        assert idx == 0
        assert conf >= 0.5

    def test_header_with_chinese_column_names(self) -> None:
        """中文列名检测"""
        rows = [
            ["编号", "名称", "金额"],
            ["001", "项目A", "10000"],
            ["002", "项目B", "20000"],
        ]
        idx, conf = detect_header(rows)
        assert idx == 0

    def test_header_with_english_column_names(self) -> None:
        """英文列名检测"""
        rows = [
            ["Name", "Age", "Salary"],
            ["Alice", "30", "50000"],
            ["Bob", "25", "35000"],
        ]
        idx, conf = detect_header(rows)
        assert idx == 0

    def test_header_detection_confidence_reasonable(self) -> None:
        """表头检测置信度在合理范围"""
        rows = [
            ["列A", "列B", "列C"],
            ["1", "2", "3"],
        ]
        idx, conf = detect_header(rows)
        assert idx is not None
        assert 0.0 <= conf <= 1.0


class TestHeaderDetectionNoHeader:
    """无表头纯数据表格测试"""

    def test_all_numeric_rows(self) -> None:
        """所有行均为数字 → 无表头"""
        rows = [
            ["100", "200", "300"],
            ["400", "500", "600"],
            ["700", "800", "900"],
        ]
        idx, conf = detect_header(rows)
        assert idx is None

    def test_first_row_contains_numbers(self) -> None:
        """首行含数字 → 判定为数据行，无表头"""
        rows = [
            ["100", "名称", "300"],
            ["400", "项目", "600"],
        ]
        idx, _ = detect_header(rows)
        assert idx is None

    def test_first_row_contains_date(self) -> None:
        """首行含日期 → 判定为数据行"""
        rows = [
            ["2024-01-15", "100", "项目A"],
            ["2024-02-20", "200", "项目B"],
        ]
        idx, _ = detect_header(rows)
        assert idx is None

    def test_first_row_contains_currency(self) -> None:
        """首行含货币 → 判定为数据行"""
        rows = [
            ["¥50,000", "100", "A"],
            ["¥30,000", "200", "B"],
        ]
        idx, _ = detect_header(rows)
        assert idx is None


class TestHeaderDetectionEdgeCases:
    """边缘 case 测试"""

    def test_empty_table(self) -> None:
        """空表格 → 无表头，置信度 0"""
        idx, conf = detect_header([])
        assert idx is None
        assert conf == 0.0

    def test_empty_rows(self) -> None:
        """空行列表 → 无表头"""
        idx, conf = detect_header([[]])
        assert idx is None
        assert conf == 0.0

    def test_single_row_table(self) -> None:
        """单行表格 → 无表头（至少需 2 行才能区分表头和数据）"""
        rows = [["名称", "数量", "金额"]]
        idx, conf = detect_header(rows)
        # 单行情况，无法确定是否为表头
        assert idx is None or conf < 0.5

    def test_two_row_table_with_header(self) -> None:
        """两行表格：首行文本，次行数字 → 可能为表头"""
        rows = [
            ["姓名", "年龄"],
            ["张三", "30"],
        ]
        idx, conf = detect_header(rows)
        assert idx == 0
        assert conf >= 0.5

    def test_all_empty_cells(self) -> None:
        """全空单元格行"""
        rows = [
            ["", "", ""],
            ["", "", ""],
        ]
        idx, conf = detect_header(rows)
        assert idx is None or conf < 0.3

    def test_header_with_partial_empty_cells(self) -> None:
        """首行部分空白非全部空白 → 仍检测为表头（blank cell 被 _is_data_type 判为非数据）"""
        rows = [
            ["", "金额", "日期"],
            ["X", "¥1000", "2024-01-01"],
        ]
        idx, conf = detect_header(rows)
        assert idx == 0
        assert conf >= 0.5

    def test_header_with_whitespace(self) -> None:
        """表头含前后空白"""
        rows = [
            ["  姓名  ", " 年龄 ", " 城市 "],
            ["张三", "30", "北京"],
        ]
        idx, conf = detect_header(rows)
        assert idx == 0

    def test_confidence_lower_for_no_header(self) -> None:
        """无表头时置信度应低于有表头"""
        rows_with = [
            ["名称", "数量"],
            ["A", "100"],
        ]
        rows_without = [
            ["100", "200"],
            ["300", "400"],
        ]
        _, conf_with = detect_header(rows_with)
        _, conf_without = detect_header(rows_without)
        assert conf_without < conf_with

    def test_single_column_header(self) -> None:
        """单列表格表头检测"""
        rows = [
            ["序号"],
            ["1"],
            ["2"],
        ]
        idx, conf = detect_header(rows)
        assert idx == 0

    def test_wide_table_header(self) -> None:
        """宽表格（20 列）表头检测"""
        header = [f"列{i}" for i in range(20)]
        data = [[str(j) for j in range(20)] for _ in range(5)]
        rows = [header] + data
        idx, conf = detect_header(rows)
        assert idx == 0

    def test_rows_with_uneven_lengths(self) -> None:
        """行长度不一致的表格"""
        rows = [
            ["名称", "数量", "金额"],
            ["A", "100"],
            ["B", "200", "¥300", "extra"],
        ]
        idx, conf = detect_header(rows)
        assert idx == 0
