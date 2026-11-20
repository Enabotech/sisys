"""表格输出格式化器

纯标准库两遍法渲染（agent_cli ``_print_checkpoint_summary_table`` :1495-1518
先例）：第一遍收集列宽（``len`` 口径——中文列宽先例同款），第二遍
``str.ljust`` 对齐输出，`` | `` 分隔。空态契约：空列表输出空串（零表头
零数据行）、空 dict 输出表头+零数据行。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_SEPARATOR = " | "
_FIELD_HEADER = ("字段", "值")


def _stringify(value: Any) -> str:
    """列值转字符串（UUID/Decimal/嵌套值经 str 展平——f-string 内建转展语义等价）。"""
    if isinstance(value, str):
        return value
    return str(value)


def _render_rows(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """两遍法渲染：先求各列宽（含表头），再 ljust 对齐输出（行尾悬挂分隔符修剪）。"""
    widths = [len(column) for column in header]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))
    lines = [_trim_row(_SEPARATOR.join(column.ljust(widths[idx]) for idx, column in enumerate(header)))]
    for row in rows:
        lines.append(_trim_row(_SEPARATOR.join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))))
    return "\n".join(lines)


def _trim_row(line: str) -> str:
    """修剪行尾空白与悬挂列分隔符（尾部空值 cell 留下的 ' | ' 残留）。"""
    return line.rstrip().rstrip(_SEPARATOR.strip()).rstrip()


def render(payload: Any) -> str:
    """将载荷渲染为人类可读表格。

    Args:
        payload: dict 载荷（键值两列表）或 list[dict] 载荷（表头=全行键并集保序，
            缺失键渲染空串）；空列表输出空串，空 dict 输出表头+零数据行

    Returns:
        表格字符串（列宽自适应，中文按 len 口径——agent_cli 先例）
    """
    if isinstance(payload, Mapping):
        rows: list[Sequence[str]] = [(key, _stringify(value)) for key, value in payload.items()]
        return _render_rows(_FIELD_HEADER, rows)
    if isinstance(payload, Sequence):
        records = [item for item in payload if isinstance(item, Mapping)]
        if not records:
            return ""
        header: list[str] = []
        for record in records:
            for key in record.keys():
                if key not in header:
                    header.append(key)
        list_rows: list[Sequence[str]] = [tuple(_stringify(record.get(key, "")) for key in header) for record in records]
        return _render_rows(header, list_rows)
    return _stringify(payload)
