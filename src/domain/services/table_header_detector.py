"""领域层 表头检测服务

表头检测领域服务，使用多特征加权策略识别表格中的表头行索引。

多特征加权策略（三特征）：
1. 首行类型差异法（权重 40%）：首行是否为纯文本且后续行含数据类型
2. 格式特征法（权重 35%）：首行是否具有表头格式特征（全大写/较短/特殊字符）
3. 空值模式法（权重 25%）：首行空值密度 vs 后续行空值密度

纯 Python 实现，零外部依赖。

MVP 限制：
- 仅支持单行表头识别（多行表头标记为 V2 扩展）
- 不依赖外部训练数据或 ML 模型
"""

from __future__ import annotations

import re

# 多特征加权系数
WEIGHT_TYPE_DIFF = 0.40  # 首行类型差异法权重
WEIGHT_FORMAT = 0.35  # 格式特征法权重
WEIGHT_NULL_PATTERN = 0.25  # 空值模式法权重


def detect_header(rows: list[list[str]]) -> tuple[int | None, float]:
    """检测表格表头行索引

    使用多特征加权策略识别表头：

    1. 类型差异法（40%）：首行全文本 + 后续行含数据类型 → 高概率表头
    2. 格式特征法（35%）：首行具有表头格式特征（全大写、较短、含冒号等）
    3. 空值模式法（25%）：首行空值密度显著低于后续行

    Args:
        rows: 表格行数据（二维字符串数组）

    Returns:
        tuple[int | None, float]: 表头行索引（无表头时为 None）和置信度
    """
    if not rows or not rows[0]:
        return None, 0.0

    # 单行表格：无法区分表头与数据，判定为无表头
    if len(rows) < 2:
        return None, 0.3

    first_row = rows[0]
    subsequent_rows = rows[1:]

    # 首行全空：无有效表头
    if all(not cell.strip() for cell in first_row):
        return None, 0.2

    # 1. 类型差异法评分（40%）
    type_diff_score = _calc_type_diff_score(first_row, subsequent_rows)

    # 2. 格式特征法评分（35%）
    format_score = _calc_format_features(first_row)

    # 3. 空值模式法评分（25%）
    null_pattern_score = _calc_null_pattern(first_row, subsequent_rows)

    # 加权综合置信度
    confidence = type_diff_score * WEIGHT_TYPE_DIFF + format_score * WEIGHT_FORMAT + null_pattern_score * WEIGHT_NULL_PATTERN

    # 阈值判断：置信度 >= 0.5 判定为有表头
    if confidence >= 0.5:
        return 0, round(confidence, 4)

    # 置信度不足，判定为无表头
    return None, round(confidence, 4)


def _calc_type_diff_score(
    first_row: list[str],
    subsequent_rows: list[list[str]],
) -> float:
    """计算首行类型差异得分

    首行全文本 + 后续行含数据类型 → 高分（表头信号）
    首行含数据类型 → 低分（非表头信号）
    首行全文本但后续行也全文本 → 中低分（不典型）

    Args:
        first_row: 首行单元格列表
        subsequent_rows: 后续数据行列表

    Returns:
        float: 类型差异得分（0.0~1.0）
    """
    has_data_in_first = any(_is_data_type(cell) for cell in first_row)

    if has_data_in_first:
        # 首行含数据类型，强烈信号为非表头
        return 0.0

    # 首行全文本，检查后续行是否含数据类型
    has_data_in_subsequent = any(_is_data_type(cell) for row in subsequent_rows for cell in row)

    if has_data_in_subsequent:
        # 首行文本 + 后续行含数据 → 典型表头模式
        return 1.0

    # 首行文本 + 后续行也是文本 → 弱信号
    return 0.3


def _calc_format_features(first_row: list[str]) -> float:
    """计算首行格式特征得分

    表头行常见格式特征：
    - 全大写（英文表头）
    - 字符串较短（表头通常比数据简洁）
    - 含特殊字符（冒号、括号、问号）

    Args:
        first_row: 首行单元格列表

    Returns:
        float: 格式特征得分（0.0~1.0）
    """
    if not first_row:
        return 0.0

    score = 0.0
    feature_count = 3  # 三个子特征

    # 子特征 1：全大写检测
    uppercase_count = 0
    text_count = 0
    for cell in first_row:
        stripped = cell.strip()
        if stripped and not _is_data_type(stripped):
            text_count += 1
            if stripped == stripped.upper():
                uppercase_count += 1

    if text_count > 0:
        uppercase_ratio = uppercase_count / text_count
        # 超过 50% 的文本列全大写 → 表头信号
        if uppercase_ratio >= 0.5:
            score += 1.0
        elif uppercase_ratio > 0:
            score += uppercase_ratio * 0.5

    # 子特征 2：字符串长度较短（表头通常 ≤ 15 字符）
    short_count = sum(1 for cell in first_row if len(cell.strip()) <= 15 and cell.strip())
    if short_count > 0:
        score += short_count / len(first_row)
    else:
        score += 0.0

    # 子特征 3：含表头特殊字符（冒号、括号、问号）
    special_chars_pattern = re.compile(r"[:：（）()?？]")
    special_count = sum(1 for cell in first_row if special_chars_pattern.search(cell))
    if special_count > 0:
        score += min(special_count / len(first_row) * 0.5, 0.5)

    return score / feature_count


def _calc_null_pattern(
    first_row: list[str],
    subsequent_rows: list[list[str]],
) -> float:
    """计算空值模式得分

    表头行通常没有空值（列名齐全），数据行可能含空值。
    通过对比首行与后续行的空值密度来识别表头。

    Args:
        first_row: 首行单元格列表
        subsequent_rows: 后续数据行列表

    Returns:
        float: 空值模式得分（0.0~1.0）
    """
    # 首行空值密度
    first_empty = sum(1 for cell in first_row if not cell.strip())
    first_empty_ratio = first_empty / len(first_row) if first_row else 1.0

    if first_empty_ratio > 0.3:
        # 首行空值太多，不太可能是表头
        return 0.0

    if not subsequent_rows:
        return 0.5

    # 后续行平均空值密度
    subsequent_empty_total = 0
    subsequent_cell_total = 0
    for row in subsequent_rows:
        subsequent_empty_total += sum(1 for cell in row if not cell.strip())
        subsequent_cell_total += len(row)

    avg_subsequent_empty_ratio = subsequent_empty_total / subsequent_cell_total if subsequent_cell_total > 0 else 0.0

    # 首行空值密度显著低于后续行 → 表头信号
    if first_empty_ratio == 0 and avg_subsequent_empty_ratio > 0:
        return 1.0
    if first_empty_ratio < avg_subsequent_empty_ratio:
        return 0.7
    if first_empty_ratio == avg_subsequent_empty_ratio:
        return 0.5

    return 0.3


def _is_data_type(cell: str) -> bool:
    """判断单元格是否为数据类型（数字/日期/货币等）

    检测顺序：先日期正则 → 再数字转换（避免逗号日期被 float() 误判）。
    货币检测使用正则校验（避免纯数字被误判为货币）。

    与 table_column_classifier._detect_single_value_type 保持一致的检测逻辑。

    Args:
        cell: 单元格文本

    Returns:
        bool: 是否为数据类型
    """
    cell = cell.strip()
    if not cell:
        return False

    # 日期检测（ISO 格式、中文格式、欧美格式）
    # 必须在数字检测之前执行，避免 "2024,01,15" 等逗号日期被 float() 误判
    if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", cell):
        return True
    if re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}$", cell):
        return True
    if re.match(r"^\d{4}年\d{1,2}月\d{1,2}日?$", cell):
        return True

    # 货币检测（正则校验，必须在数字检测之前）
    if re.match(r"^-?[¥$€£]\s*\d[\d,]*\.?\d*$", cell):
        return True

    # 数字检测（排除 NaN/Infinity 等 IEEE 754 特殊值）
    try:
        value = float(cell.replace(",", ""))
        import math

        if math.isfinite(value):
            return True
    except ValueError:
        pass

    return False
