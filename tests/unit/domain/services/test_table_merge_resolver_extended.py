"""table_merge_resolver 单元测试补充。

现有测试覆盖了大部分路径，但需要补充：
- 边界极端情况
- 超大表格
- 行列长度不一致（参差矩阵）
- 多次填充同一单元格后拒绝（已覆盖但加强断言）
"""

from __future__ import annotations

from src.domain.services.table_merge_resolver import resolve_merged_cells


class TestTableMergeResolverEdgeCases:
    """table_merge_resolver 边界用例补充测试。"""

    def test_single_cell_single_range(self) -> None:
        """1x1 表格 + 1 个合并范围 → 正确返回。"""
        rows = [["值"]]
        result = resolve_merged_cells(rows, [(0, 0, 0, 0)])
        assert len(result) == 1
        assert result[0].value == "值"
        assert result[0].row_start == 0
        assert result[0].col_start == 0

    def test_ragged_rows_with_valid_merge(self) -> None:
        """参差矩阵中合法的合并范围应正常处理。"""
        rows = [["a", "b"], ["c"]]
        result = resolve_merged_cells(rows, [(0, 1, 0, 0)])
        assert len(result) == 1
        assert result[0].value == "a"

    def test_large_table_many_ranges(self) -> None:
        """大表格中的多个非重叠合并范围应全部被识别。"""
        size = 100
        rows = [[f"c{r}{c}" for c in range(size)] for r in range(size)]
        ranges = [(r, r, 0, 0) for r in range(size)]
        result = resolve_merged_cells(rows, ranges)
        assert len(result) == size

    def test_overlap_only_first_wins(self) -> None:
        """重叠合并范围，第一个覆盖左上角的胜出。"""
        rows = [["x", "x", "x"], ["x", "x", "x"], ["x", "x", "x"]]
        ranges = [(0, 1, 0, 1), (0, 0, 0, 1)]
        result = resolve_merged_cells(rows, ranges)
        # 第一个范围 (0,1,0,1) 覆盖 (0,0)，第二个 (0,0,0,1) 的左上角已被占
        assert len(result) == 1
        assert result[0].row_start == 0
        assert result[0].col_start == 0
        assert result[0].row_end == 1
        assert result[0].col_end == 1
