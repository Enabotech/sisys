"""领域层 表头检测服务

表头检测领域服务，使用多特征加权策略（首行类型差异 + 格式特征 + 空值模式）
识别表格中的表头行索引。纯 Python 实现，零外部依赖。
"""

from __future__ import annotations


def detect_header(rows: list[list[str]]) -> tuple[int | None, float]:
    """检测表格表头行索引

    Args:
        rows: 表格行数据（二维字符串数组）

    Returns:
        tuple[int | None, float]: 表头行索引（无表头时为 None）和置信度

    Note:
        MVP 实现使用首行类型差异法：
        - 单行表格无法区分表头与数据，判定为无表头
        - 首行全为空单元格，判定为无表头
        - 首行全为文本类型且后续行含数字/日期 → 判定为表头（高置信度）
        - 首行含数字/日期等数据类型 → 判定为无表头
    """
    if not rows or not rows[0]:
        return None, 0.0

    # 单行表格：无法区分表头与数据，判定为无表头
    if len(rows) < 2:
        return None, 0.3

    first_row = rows[0]

    # 首行全空：无有效表头
    if all(not cell.strip() for cell in first_row):
        return None, 0.2

    has_data_types_in_first_row = any(_is_data_type(cell) for cell in first_row)

    if has_data_types_in_first_row:
        # 首行含数据类型，判定为无表头
        return None, 0.3

    # 首行全为文本类型，判定为表头
    return 0, 0.8


def _is_data_type(cell: str) -> bool:
    """判断单元格是否为数据类型（数字/日期/货币等）

    Args:
        cell: 单元格文本

    Returns:
        bool: 是否为数据类型
    """
    cell = cell.strip()
    if not cell:
        return False

    # 数字检测
    try:
        float(cell.replace(",", ""))
        return True
    except ValueError:
        pass

    # 日期检测（ISO 格式）
    if len(cell) >= 10 and "-" in cell:
        parts = cell.split("-")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            return True

    # 货币检测
    if cell.startswith("¥") or cell.startswith("$") or cell.startswith("€"):
        return True

    return False
