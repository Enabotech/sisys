"""领域层 列类型推断服务

列类型推断领域服务，使用正则模式匹配（日期/货币/百分比/布尔）+ 类型转换试探（数字）
推断表格列的数据类型。纯 Python 实现，零外部依赖。
"""

from __future__ import annotations

import re
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from src.domain.value_objects.parsed_document import ColumnInfo, ColumnType


def _secure_sample(population: range, k: int) -> list[int]:
    """从 range 中安全采样 k 个不重复元素

    使用 secrets.randbelow 替代 random.sample，避免伪随机数生成器
    在非加密场景中使用。

    Args:
        population: 采样范围
        k: 采样数量

    Returns:
        采样结果列表（升序排列）
    """
    chosen: set[int] = set()
    max_val = population.stop - population.start
    while len(chosen) < k:
        idx = population.start + secrets.randbelow(max_val)
        chosen.add(idx)
    return sorted(chosen)


def classify_columns(
    rows: list[list[str]],
    sample_size: int = 50,
    column_names: list[str] | None = None,
) -> list[ColumnInfo]:
    """推断表格各列的数据类型

    Args:
        rows: 表格数据行（不含表头行）
        sample_size: 采样行数（前 N/2 行 + 随机采样 N/2 行）
        column_names: 列名列表（来自表头，用于填充 ColumnInfo.name）

    Returns:
        list[ColumnInfo]: 每列的类型推断结果
    """
    if not rows:
        return []

    num_cols = max(len(row) for row in rows) if rows else 0
    if num_cols == 0:
        return []

    # 采样策略：前 N/2 行 + 随机采样 N/2 行（避免顺序偏差）
    if len(rows) > sample_size:
        half = sample_size // 2
        head = rows[:half]
        tail_indices = _secure_sample(range(half, len(rows)), min(half, len(rows) - half))
        tail = [rows[i] for i in sorted(tail_indices)]
        sampled_rows = head + tail
    else:
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

    检测优先级（按 Story 规格）：
    DATE > CURRENCY > PERCENTAGE > BOOLEAN > NUMBER > STRING

    日期优先检测（格式最明确），货币/百分比次之（带符号标记），
    布尔在数字之前（防止 "1"/"0" 直接被转为 NUMBER）。

    Args:
        value: 单元格文本值

    Returns:
        ColumnType: 推断的列类型
    """
    # 日期检测（ISO / 中文格式 / 欧美格式）
    if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", value):
        return ColumnType.DATE
    if re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}$", value):
        return ColumnType.DATE
    if re.match(r"^\d{4}年\d{1,2}月\d{1,2}日?$", value):
        return ColumnType.DATE

    # 货币检测（支持负号在符号前/后、无前导零的小数）
    if re.match(r"^-?[¥$€£]\s*\d*\.?\d+$", value):
        return ColumnType.CURRENCY
    if re.match(r"^[¥$€£]\s*-?\d[\d,]*\.?\d*$", value):
        return ColumnType.CURRENCY

    # 百分比检测（支持千分位格式）
    if re.match(r"^-?\d[\d,]*\.?\d*\s*%$", value):
        return ColumnType.PERCENTAGE

    # 布尔值检测（仅匹配文本布尔值，"1"/"0" 交由 NUMBER 检测处理）
    if value.lower() in ("true", "false", "是", "否", "yes", "no"):
        return ColumnType.BOOLEAN

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
