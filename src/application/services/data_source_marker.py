"""应用层 $DATA_SOURCE 标记解析器（Story 4.1b — Skills 数据采集基础设施）

职责：在宿主机侧解析 LLM 生成代码中的 `$DATA_SOURCE(name, "query")` 标记，
并将采集结果以 Python 字面量前言（preamble）形式内联注入代码。

安全约束：
- 参数仅经 ast.literal_eval 安全解析（**禁止** eval/exec 动态执行）
- 字符串字面量内的 $DATA_SOURCE 文本不识别为标记（tokenize 掩码防误触发）
- 语法错误抛 ValidationError（EXCEPTION_201），不泄露内部实现细节
"""

from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from datetime import UTC, datetime

from src.domain.exceptions import ValidationError
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import DataSourceResult

# 完整标记模式：$DATA_SOURCE( "name", "query" )（引号支持单/双引号 + 转义）
_STRING_LITERAL = r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''
_MARKER_PATTERN = re.compile(r"\$DATA_SOURCE\(\s*(" + _STRING_LITERAL + r")\s*,\s*(" + _STRING_LITERAL + r")\s*\)")
# 裸标记起始（用于识别语法错误的标记）
_MARKER_HEAD = "$DATA_SOURCE("


def _string_literal_spans(code: str) -> list[tuple[int, int]]:
    """返回代码中所有字符串字面量的绝对偏移区间（tokenize 实现，容错 ERRORTOKEN）

    $DATA_SOURCE 含非法 Python 字符 `$`，tokenize 将其标记为 ERRORTOKEN 并继续，
    不影响字符串字面量区间的提取。
    """
    spans: list[tuple[int, int]] = []
    line_offsets = [0]
    for line in code.splitlines(keepends=True):
        line_offsets.append(line_offsets[-1] + len(line))
    try:
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        for tok in tokens:
            if tok.type == tokenize.STRING:
                start = line_offsets[tok.start[0] - 1] + tok.start[1]
                end = line_offsets[tok.end[0] - 1] + tok.end[1]
                spans.append((start, end))
    except tokenize.TokenError:
        # 未闭合字符串等词法错误：返回已提取区间（后续语法校验兜底）
        pass
    return spans


def _inside_span(offset: int, spans: list[tuple[int, int]]) -> bool:
    """判断偏移是否落在任一字符串字面量区间内"""
    return any(start <= offset < end for start, end in spans)


def parse_data_source_markers(code: str) -> tuple[DataSourceQuery, ...]:
    """解析代码中的全部 $DATA_SOURCE 标记（去重，保序）

    Args:
        code: LLM 生成的沙箱代码

    Returns:
        DataSourceQuery 元组（tenant_id 为 None，由调用方在采集时注入）

    Raises:
        ValidationError: 标记语法错误（EXCEPTION_201：缺参数/缺引号/未闭合/多余参数/空值）
    """
    spans = _string_literal_spans(code)

    markers: list[DataSourceQuery] = []
    seen: set[tuple[str, str]] = set()
    for match in _MARKER_PATTERN.finditer(code):
        if _inside_span(match.start(), spans):
            continue  # 字符串字面量内的文本不识别为标记
        name = ast.literal_eval(match.group(1))
        query = ast.literal_eval(match.group(2))
        if not name or not name.strip():
            raise ValidationError(
                message="$DATA_SOURCE 标记 name 参数不能为空",
                context={"stage": "parse_marker", "field": "name"},
            )
        if not query or not query.strip():
            raise ValidationError(
                message="$DATA_SOURCE 标记 query 参数不能为空",
                context={"stage": "parse_marker", "field": "query"},
            )
        key = (name, query)
        if key not in seen:
            seen.add(key)
            markers.append(DataSourceQuery(source_name=name, query=query))

    # 语法错误检测：存在未匹配的裸标记起始（且不在字符串内）
    residual = _MARKER_PATTERN.sub("", code)
    idx = 0
    while True:
        idx = residual.find(_MARKER_HEAD, idx)
        if idx == -1:
            break
        if not _inside_span(idx, spans):
            raise ValidationError(
                message='$DATA_SOURCE 标记语法错误（期望 $DATA_SOURCE("name", "query")）',
                context={"stage": "parse_marker", "position": idx},
            )
        idx += len(_MARKER_HEAD)

    return tuple(markers)


def inject_data_sources(code: str, results: tuple[DataSourceResult, ...]) -> str:
    """将采集结果以单行 Python 字面量前言内联注入代码

    Args:
        code: 原始代码（含标记行，原样保留供审计）
        results: 采集成功的 DataSourceResult 元组（空元组时不注入）

    Returns:
        注入后的代码：`DATA_SOURCES = {...json...}\n` + 原始代码
        前言为单行 JSON 字面量，每项含 payload/source_timestamp/freshness_score/confidence/cache_hit
    """
    if not results:
        return code
    now = datetime.now(UTC)
    data: dict[str, dict[str, object]] = {}
    for result in results:
        payload: object
        try:
            payload = json.loads(result.payload)
        except ValueError:
            payload = result.payload
        data[result.source_name] = {
            "payload": payload,
            "source_timestamp": result.source_timestamp.isoformat(),
            "freshness_score": result.freshness.score(now),
            "confidence": result.confidence,
            "cache_hit": result.cache_hit,
        }
    preamble = f"DATA_SOURCES = {json.dumps(data, ensure_ascii=False)}"
    return f"{preamble}\n{code}"


__all__ = ["inject_data_sources", "parse_data_source_markers"]
