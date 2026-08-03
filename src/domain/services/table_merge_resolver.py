"""领域层 合并单元格还原服务（V1）

合并单元格还原领域服务，接收原始表格行数据和合并范围列表，
生成 MergedCell 值对象列表。纯 Python 实现，零外部依赖。

V1 版本：仅处理合并范围的元数据生成，不修改原始 rows 数据。
实际合并单元格值填充由基础设施层的 PdfTableDetector / ExcelParser 执行。
"""

from __future__ import annotations

from src.domain.value_objects.parsed_document import MergedCell


def resolve_merged_cells(
    rows: list[list[str]],
    merge_ranges: list[tuple[int, int, int, int]],
) -> list[MergedCell]:
    """还原合并单元格语义

    Args:
        rows: 原始表格行数据（二维字符串数组）
        merge_ranges: 合并范围列表，每个元素为
            (row_start, row_end, col_start, col_end) 四元组

    Returns:
        list[MergedCell]: 合并单元格值对象列表
    """
    if not rows:
        return []

    max_row = len(rows) - 1
    max_col = max(len(row) for row in rows) - 1 if rows else 0

    result: list[MergedCell] = []
    for row_start, row_end, col_start, col_end in merge_ranges:
        # 边界检查：确保合并范围在有效区域内，超界时裁剪到边界
        if row_start < 0:
            row_start = 0
        if row_end > max_row:
            row_end = max_row
        if col_start < 0:
            col_start = 0
        if col_end > max_col:
            col_end = max_col

        if row_start > row_end or col_start > col_end:
            continue
        if row_start > max_row or col_start > max_col:
            continue

        # 取左上角单元格的值
        value = rows[row_start][col_start]

        result.append(
            MergedCell(
                row_start=row_start,
                row_end=row_end,
                col_start=col_start,
                col_end=col_end,
                value=value,
            )
        )

    return result
