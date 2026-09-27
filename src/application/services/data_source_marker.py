"""应用层 $DATA_SOURCE 标记解析器（Story 4.1b — Skills 数据采集基础设施）

职责：在宿主机侧解析 LLM 生成代码中的 `$DATA_SOURCE(name, "query")` 标记，
将采集结果以 Python 字面量前言（preamble）形式内联注入代码，并把标记原位
替换为 `DATA_SOURCES["<name>"]` 数据引用表达式（标记即表达式语义，与
4-1c SKILL.md 的赋值形态 `gdp = $DATA_SOURCE(...)` 消费约定兼容）。

安全约束：
- 参数仅经 ast.literal_eval 安全解析（**禁止** eval/exec 动态执行）
- 字符串字面量与行注释内的 $DATA_SOURCE 文本不识别为标记（`_string_literal_spans`
  纯字符级扫描掩码：双引号/单引号/三引号 + 转义字符 + `#` 行注释；未闭合字符串
  保守登记到文件末尾——4-1b Round 1 P0-5 修复，弃用 tokenize 因其 TokenError
  降级会漏边界；第二周期 R2-P1-3 修复补注释识别，注释撇号不再吞掉后续标记）
- 注入产物恒为合法 Python：preamble 用 repr 序列化（ast.literal_eval 可逆，
  杜绝 json.dumps 的 null/true/false NameError）；标记原位替换（杜绝 `$`
  非法字符 SyntaxError）——第二周期 R2-P0-1 修复
- 语法错误抛 ValidationError（EXCEPTION_201），不泄露内部实现细节
"""

from __future__ import annotations

import ast
import json
import re
from datetime import UTC, datetime

from src.domain.exceptions import ValidationError
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import DataSourceResult

# 完整标记模式：$DATA_SOURCE( "name", "query" )（引号支持单/双引号 + 转义）
_STRING_LITERAL = r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''
_MARKER_PATTERN = re.compile(r"\$DATA_SOURCE\(\s*(" + _STRING_LITERAL + r")\s*,\s*(" + _STRING_LITERAL + r")\s*\)")


def _string_literal_spans(code: str) -> list[tuple[int, int]]:
    """返回代码中需掩码的绝对偏移区间（字符串字面量 + 行注释，纯字符级扫描，不依赖 tokenize 完整性）

    为什么不使用 tokenize：未闭合字符串（如 code = '"abc' 单引号风格）会触发 tokenize.TokenError，
    在 except 分支降级返回部分区间，会导致字符串内的 $DATA_SOURCE 文本误识别为标记。
    本函数手写三种引号（双引号、单引号、三引号双/单）+ 转义字符 + `#` 行注释解析，
    即使 tokenize 失败也能给出完整稳健的边界集合。注释识别遵循 Python 词法规范：
    字符串外的 `#` 才是注释起点（字符串内的 `#` 按串内容消费），注释到物理行尾即止。
    """
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c == "#":
            # 行注释：登记区间并跳至行尾（注释撇号不得触发字符串模式——R2-P1-3 修复）
            newline = code.find("\n", i)
            if newline == -1:
                spans.append((i, n))
                break
            spans.append((i, newline))
            i = newline
        elif c in ('"', "'"):
            # 优先匹配三引号（Python 允许三引号在源码中独立成字符串）
            triple = c * 3
            if code[i : i + 3] == triple:
                quote = triple
                step = 3
            else:
                quote = c
                step = 1
            start = i
            i += step
            end = i
            # 在 code 中寻找匹配的结束引号序列
            matched = False
            while i < n:
                if code[i] == "\\" and i + step < n:
                    i += 2  # 跳过转义序列
                    continue
                if code[i : i + step] == quote:
                    i += step
                    end = i
                    spans.append((start, end))
                    matched = True
                    break
                i += 1
            if not matched:
                # 未闭合的字符串字面量：保守登记到文件末尾
                # 下游裸 $ 后置校验会兜底标记语法错误
                spans.append((start, n))
                break
        else:
            i += 1
    return spans


def _inside_span(offset: int, spans: list[tuple[int, int]]) -> bool:
    """判断偏移是否落在任一掩码区间（字符串字面量/行注释）内"""
    return any(start <= offset < end for start, end in spans)


def _masked_code(code: str, spans: list[tuple[int, int]]) -> str:
    """构造等长掩码串（区间内容替换为空格、保留换行），坐标系与原 code 严格一致

    用于后置语法校验：在掩码串上检索残留非法字符时坐标不漂移（R2-P1-2 修复，
    弃用 residual sub 删除后检索的错位方案）。
    """
    chars = list(code)
    for start, end in spans:
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def parse_data_source_markers(code: str) -> tuple[DataSourceQuery, ...]:
    """解析代码中的全部 $DATA_SOURCE 标记（去重，保序）

    Args:
        code: LLM 生成的沙箱代码

    Returns:
        DataSourceQuery 元组（tenant_id 为 None，由调用方在采集时注入）

    Raises:
        ValidationError: 标记语法错误（EXCEPTION_201：缺参数/缺引号/未闭合/多余参数/空值/
            字符串与注释外的裸 `$`——Python 中 `$` 恒为非法字符，统一前置为宿主机校验）
    """
    # 掩码区间识别走纯字符级扫描（_string_literal_spans），不依赖 tokenize 完整性
    # 即使代码含未闭合字符串（语法错误），spans 集合仍可正确反映已识别的字面量边界，
    # 由下游裸 $ 后置校验兜底标记语法错误 → ValidationError
    spans = _string_literal_spans(code)

    markers: list[DataSourceQuery] = []
    marker_spans: list[tuple[int, int]] = []
    seen: set[tuple[str, str]] = set()
    for match in _MARKER_PATTERN.finditer(code):
        if _inside_span(match.start(), spans):
            continue  # 字符串字面量/行注释内的文本不识别为标记
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
        marker_spans.append((match.start(), match.end()))
        key = (name, query)
        if key not in seen:
            seen.add(key)
            markers.append(DataSourceQuery(source_name=name, query=query))

    # 语法错误检测：掩码（字符串/注释/有效标记）后的裸 `$` 恒为非法 Python 字符
    # （有意收紧：覆盖 $DATA_SOURCE 无括号/空白/拼写错误变体，沙箱 SyntaxError 全部前置）
    idx = _masked_code(code, [*spans, *marker_spans]).find("$")
    if idx != -1:
        raise ValidationError(
            message='$DATA_SOURCE 标记语法错误（期望 $DATA_SOURCE("name", "query")）',
            context={"stage": "parse_marker", "position": idx},
        )

    return tuple(markers)


def inject_data_sources(
    code: str,
    markers: tuple[DataSourceQuery, ...],
    results: tuple[DataSourceResult | None, ...],
) -> str:
    """将采集结果以单行 Python 字面量前言内联注入，并把标记原位替换为数据引用表达式

    Args:
        code: 原始代码（engine 已在 execution.code 存证注入前版本，审计不受影响）
        markers: parse_data_source_markers 解析的标记元组（调用方解析一次传入，杜绝二次扫描漂移）
        results: 与 markers 等长对齐的采集结果（None 位为采集失败——fetch_many 部分成功语义）

    Returns:
        注入后的代码：`DATA_SOURCES = {...repr 字面量...}\n` + 标记替换后的代码。
        成功标记替换为 `DATA_SOURCES["<name>"]`（同源第 k 个不同 query 键为 `name#k`，
        单源场景键为裸 name，向后兼容 4-1c SKILL.md 消费约定）；失败位标记替换为
        `None`（保 SOP「部分失败不中断分析」降级语义，失败信息由 DataSourceFetchFailed
        事件承载）。注入产物恒为可编译的合法 Python（R2-P0-1 修复闸门）。
    """
    if not markers:
        return code
    now = datetime.now(UTC)

    # 键分配：去重后 (name, query) 出现次序，同源第 k 个不同 query → name#k
    key_of: dict[tuple[str, str], str] = {}
    name_count: dict[str, int] = {}
    success: dict[tuple[str, str], bool] = {}
    data: dict[str, dict[str, object]] = {}
    for marker, result in zip(markers, results, strict=True):
        pair = (marker.source_name, marker.query)
        if pair not in key_of:
            ordinal = name_count.get(marker.source_name, 0) + 1
            name_count[marker.source_name] = ordinal
            key_of[pair] = marker.source_name if ordinal == 1 else f"{marker.source_name}#{ordinal}"
        success[pair] = result is not None
        if result is None:
            continue
        payload: object
        try:
            # parse_constant 将 NaN/Infinity/-Infinity（非标准 JSON 扩展）映射为字面字符串，
            # 杜绝 repr 产出 inf/nan 非法名称导致沙箱 NameError（R2-P0-1 边界闭合）
            payload = json.loads(result.payload, parse_constant=lambda constant: constant)
        except ValueError:
            payload = result.payload
        data[key_of[pair]] = {
            "payload": payload,
            "source_timestamp": result.source_timestamp.isoformat(),
            "freshness_score": result.freshness.score(now),
            "confidence": result.confidence,
            "cache_hit": result.cache_hit,
        }

    # 标记原位替换（掩码区间内的标记文本不替换）；替换表达式键经 json.dumps 生成
    # （JSON 字符串字面量是合法 Python 字面量子集，键含引号/unicode 均安全）
    spans = _string_literal_spans(code)
    parts: list[str] = []
    last = 0
    for match in _MARKER_PATTERN.finditer(code):
        if _inside_span(match.start(), spans):
            continue
        pair = (ast.literal_eval(match.group(1)), ast.literal_eval(match.group(2)))
        key = key_of.get(pair)
        if key is None:
            continue  # 与传入 markers 不一致的标记（理论不可达）保守保留
        parts.append(code[last : match.start()])
        parts.append(f"DATA_SOURCES[{json.dumps(key, ensure_ascii=False)}]" if success[pair] else "None")
        last = match.end()
    parts.append(code[last:])
    body = "".join(parts)

    if not data:
        return body  # 全部失败（fetch_many 契约下不可达，防御性保护）：无 preamble
    return f"DATA_SOURCES = {repr(data)}\n{body}"


__all__ = ["inject_data_sources", "parse_data_source_markers"]
