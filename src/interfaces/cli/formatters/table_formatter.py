"""表格格式化器（Story 7-1——AC-2 输出格式面 table 态）。

两遍法动态列宽表格（agent_cli.py:1495-1518 ``_print_checkpoint_summary_table``
先例形态）：第一遍计算各列最大显示宽度（表头与数据行取 max），第二遍
str.ljust 对齐拼接——表头行直接跟数据行（先例无分隔线、无 ASCII 边框；
显示宽度感知为中文增强——英文场景与先例 len() 语义等价）。
"""

from __future__ import annotations


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    """渲染两遍法动态列宽表格（先例形态：表头行+数据行，" | " 连接）。

    Args:
        headers: 表头单元格列表
        rows: 数据行单元格列表的列表（外层行序=展示序）

    Returns:
        多行表格文本（表头 + 数据行——先例无分隔线）
    """
    column_count = len(headers)
    widths = [_display_width(cell) for cell in headers]
    for row in rows:
        for index in range(column_count):
            cell_width = _display_width(row[index]) if index < len(row) else 0
            widths[index] = max(widths[index], cell_width)

    def _format_line(cells: list[str]) -> str:
        padded = [
            _pad(cells[index], widths[index]) if index < len(cells) else " " * widths[index] for index in range(column_count)
        ]
        return " | ".join(padded).rstrip()

    lines = [_format_line(headers)]
    lines.extend(_format_line(row) for row in rows)
    return "\n".join(lines)


def _display_width(text: str) -> int:
    """计算显示宽度（中日韩宽字符计 2——终端对齐语义）。"""
    return sum(2 if ord(char) > 0x2E80 else 1 for char in text)


def _pad(text: str, width: int) -> str:
    """按显示宽度右补空格（宽字符感知的 ljust）。"""
    padding = width - _display_width(text)
    return text + " " * max(padding, 0)
