"""领域层 合并单元格还原服务单元测试（V1）

TDD 红阶段：验证合并单元格还原领域服务的坐标覆盖计算和值填充。
"""

from __future__ import annotations

from src.domain.services.table_merge_resolver import resolve_merged_cells
from src.domain.value_objects.parsed_document import MergedCell


class TestMergeResolution:
    """合并单元格还原测试"""

    def test_no_merge_ranges(self) -> None:
        """无合并范围 → 返回空列表"""
        rows = [["A", "B"], ["C", "D"]]
        result = resolve_merged_cells(rows, [])
        assert result == []

    def test_single_row_merge(self) -> None:
        """单行跨列合并"""
        rows = [["标题", "", ""], ["A", "B", "C"]]
        merge_ranges = [(0, 0, 0, 2)]  # row_start, row_end, col_start, col_end
        result = resolve_merged_cells(rows, merge_ranges)
        assert len(result) == 1
        assert result[0].value == "标题"
        assert result[0].row_start == 0
        assert result[0].row_end == 0
        assert result[0].col_start == 0
        assert result[0].col_end == 2

    def test_single_column_merge(self) -> None:
        """单列跨行合并"""
        rows = [["分组", "值"], ["A", "1"], ["", "2"], ["", "3"]]
        merge_ranges = [(1, 3, 0, 0)]
        result = resolve_merged_cells(rows, merge_ranges)
        assert len(result) == 1
        assert result[0].value == "A"
        assert result[0].row_start == 1
        assert result[0].row_end == 3

    def test_cross_row_column_merge(self) -> None:
        """跨行跨列合并"""
        rows = [
            ["大标题", "", "C"],
            ["", "", "D"],
            ["E", "F", "G"],
        ]
        merge_ranges = [(0, 1, 0, 1)]
        result = resolve_merged_cells(rows, merge_ranges)
        assert len(result) == 1
        assert result[0].value == "大标题"
        assert result[0].row_start == 0
        assert result[0].row_end == 1
        assert result[0].col_start == 0
        assert result[0].col_end == 1

    def test_multiple_merge_ranges(self) -> None:
        """多个合并范围"""
        rows = [
            ["标题1", "", "标题2", ""],
            ["A", "B", "C", "D"],
        ]
        merge_ranges = [(0, 0, 0, 1), (0, 0, 2, 3)]
        result = resolve_merged_cells(rows, merge_ranges)
        assert len(result) == 2
        assert result[0].value == "标题1"
        assert result[1].value == "标题2"

    def test_empty_rows(self) -> None:
        """空表格"""
        result = resolve_merged_cells([], [(0, 0, 0, 0)])
        # 边界情况：空表格有合并范围时返回空
        assert result == []

    def test_merge_value_from_top_left_cell(self) -> None:
        """合并区域的值取自左上角单元格"""
        rows = [
            ["合并值", ""],
            ["", ""],
        ]
        merge_ranges = [(0, 1, 0, 1)]
        result = resolve_merged_cells(rows, merge_ranges)
        assert result[0].value == "合并值"

    def test_single_cell_merge(self) -> None:
        """1×1 单元格合并（无实际合并效果）"""
        rows = [["A", "B"], ["C", "D"]]
        merge_ranges = [(0, 0, 0, 0)]
        result = resolve_merged_cells(rows, merge_ranges)
        assert len(result) == 1
        assert result[0].value == "A"
        assert result[0].row_start == result[0].row_end
        assert result[0].col_start == result[0].col_end

    def test_merge_with_empty_value(self) -> None:
        """合并区域左上角为空值"""
        rows = [
            ["", "B"],
            ["", "D"],
        ]
        merge_ranges = [(0, 1, 0, 0)]
        result = resolve_merged_cells(rows, merge_ranges)
        assert len(result) == 1
        assert result[0].value == ""

    def test_return_type_is_merged_cell_list(self) -> None:
        """返回类型为 list[MergedCell]"""
        rows = [["A", "B"], ["C", "D"]]
        merge_ranges = [(0, 0, 0, 1)]
        result = resolve_merged_cells(rows, merge_ranges)
        assert isinstance(result, list)
        for cell in result:
            assert isinstance(cell, MergedCell)
