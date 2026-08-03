"""领域层 列类型推断服务

列类型推断领域服务，使用正则模式匹配（日期/货币/百分比/布尔）+ 类型转换试探（数字）
推断表格列的数据类型。纯 Python 实现，零外部依赖。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from src.domain.value_objects.parsed_document import ColumnInfo, ColumnType


def classify_columns(
    rows: list[list[str]],
    sample_size: int = 50,
    column_names: list[str] | None = None,
) -> list[ColumnInfo]:
    """推断表格各列的数据类型

    Args:
        rows: 表格数据行（不含表头行）
        sample_size: 采样行数（前 N 行 + 随机采样）
        column_names: 列名列表（来自表头，用于填充 ColumnInfo.name）

    Returns:
        list[ColumnInfo]: 每列的类型推断结果
    """
    if not rows:
        return []

    num_cols = max(len(row) for row in rows) if rows else 0
    if num_cols == 0:
        return []

    # 采样行（前 sample_size 行）
    sampled_rows = rows[:sample_size]

    results: list[ColumnInfo] = []
    for col_idx in range(num_cols):
        col_values = [row[col_idx].strip() for row in sampled_rows if col_idx < len(row) and row[col_idx].strip()]

        col_name = column_names[col_idx] if column_names and col_idx < len(column_names) else f"col_{col_idx}"
        col_type, confidence = _infer_column_type(col_values)
        # 空值比率使用全量 rows 计算，确保统计准确性
        nullable_ratio = _calc_nullable_ratio(col_idx, rows)

        results.append(
            ColumnInfo(
                name=col_name,
                col_type=col_type,
                confidence=confidence,
                nullable_ratio=nullable_ratio,
                sample_values=col_values[:5],
            )
        )

    return results


def _infer_column_type(values: list[str]) -> tuple[ColumnType, float]:
    """推断单列的数据类型

    Args:
        values: 非空采样值列表

    Returns:
        tuple[ColumnType, float]: 推断类型和置信度
    """
    if not values:
        return ColumnType.UNKNOWN, 0.0

    # 按优先级依次检测类型
    type_scores: dict[ColumnType, float] = {}

    for value in values:
        detected = _detect_single_value_type(value)
        type_scores[detected] = type_scores.get(detected, 0) + 1

    total = len(values)
    best_type = max(type_scores, key=lambda t: type_scores[t])
    best_count = type_scores[best_type]
    confidence = best_count / total

    # 如果最佳类型占比不足 60%，降级为 STRING
    if confidence < 0.6:
        return ColumnType.STRING, confidence

    return best_type, confidence


def _detect_single_value_type(value: str) -> ColumnType:
    """检测单个值的类型

    Args:
        value: 单元格文本值

    Returns:
        ColumnType: 推断的列类型
    """
    # 布尔值检测（仅匹配文本布尔值，"1"/"0" 交由 NUMBER 检测处理）
    if value.lower() in ("true", "false", "是", "否", "yes", "no"):
        return ColumnType.BOOLEAN

    # 百分比检测
    if re.match(r"^-?\d+\.?\d*\s*%$", value):
        return ColumnType.PERCENTAGE

    # 货币检测
    if re.match(r"^[¥$€£]\s*-?\d[\d,]*\.?\d*$", value):
        return ColumnType.CURRENCY

    # 日期检测（ISO / 中文格式）
    if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", value):
        return ColumnType.DATE
    if re.match(r"^\d{4}年\d{1,2}月\d{1,2}日?$", value):
        return ColumnType.DATE

    # 数字检测
    try:
        float(value.replace(",", ""))
        return ColumnType.NUMBER
    except ValueError:
        pass

    return ColumnType.STRING


def _calc_nullable_ratio(col_idx: int, rows: list[list[str]]) -> float:
    """计算列的空值比率

    Args:
        col_idx: 列索引
        rows: 数据行列表

    Returns:
        float: 空值比率（0.0~1.0）
    """
    if not rows:
        return 0.0

    empty_count = sum(1 for row in rows if col_idx >= len(row) or not row[col_idx].strip())
    return empty_count / len(rows)
