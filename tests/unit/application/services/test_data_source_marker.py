"""Story 4.1b — $DATA_SOURCE 标记解析器单元测试

验证 data_source_marker 模块：
- parse：单标记/多标记/嵌套引号/参数空白/重复标记去重/大小写敏感
- parse：语法错误 → ValidationError(201)（缺引号/缺参数/多余参数/未闭合括号）
- inject：preamble 单行 JSON 字面量内联 + 原始代码保留
- 安全：参数经 ast.literal_eval 安全解析（禁止 eval/exec 动态执行）
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.application.services.data_source_marker import (
    inject_data_sources,
    parse_data_source_markers,
)
from src.domain.exceptions import ValidationError
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceResult,
)


def _make_result(source_name: str, value: float = 1.0) -> DataSourceResult:
    now = datetime.now(UTC)
    return DataSourceResult(
        source_name=source_name,
        payload=json.dumps({"value": value}),
        source_timestamp=now,
        fetched_at=now,
        freshness=DataFreshness(source_timestamp=now, ttl_seconds=3600),
        confidence=0.9,
    )


class TestParseMarkers:
    def test_single_marker(self) -> None:
        code = '$DATA_SOURCE("world-bank", "GDP China 2024")\nprint(1)'
        markers = parse_data_source_markers(code)
        assert len(markers) == 1
        assert markers[0].source_name == "world-bank"
        assert markers[0].query == "GDP China 2024"

    def test_multiple_markers(self) -> None:
        code = '$DATA_SOURCE("world-bank", "GDP")\n$DATA_SOURCE("eurostat", "unemployment")\n'
        markers = parse_data_source_markers(code)
        assert [m.source_name for m in markers] == ["world-bank", "eurostat"]

    def test_no_marker_returns_empty(self) -> None:
        assert parse_data_source_markers("print('hello')") == ()

    def test_duplicate_markers_deduplicated(self) -> None:
        code = '$DATA_SOURCE("imf", "WEO")\n$DATA_SOURCE("imf", "WEO")\n'
        markers = parse_data_source_markers(code)
        assert len(markers) == 1

    def test_same_name_different_query_kept(self) -> None:
        code = '$DATA_SOURCE("imf", "WEO GDP")\n$DATA_SOURCE("imf", "WEO CPI")\n'
        markers = parse_data_source_markers(code)
        assert len(markers) == 2

    def test_query_with_nested_quotes_and_punctuation(self) -> None:
        code = "$DATA_SOURCE('newsapi', '中国 \"双碳\" 政策, 2026')\n"
        markers = parse_data_source_markers(code)
        assert markers[0].query == '中国 "双碳" 政策, 2026'

    def test_whitespace_tolerated(self) -> None:
        code = '$DATA_SOURCE(  "imf" ,   "WEO"  )'
        markers = parse_data_source_markers(code)
        assert markers[0].source_name == "imf"
        assert markers[0].query == "WEO"

    def test_marker_inside_string_literal_not_matched(self) -> None:
        """字符串字面量内的 $DATA_SOURCE 文本不应被识别为标记（避免误触发）。"""
        code = 'text = "$DATA_SOURCE(not_a_marker)"\nprint(text)'
        assert parse_data_source_markers(code) == ()

    @pytest.mark.parametrize(
        "bad_code",
        [
            '$DATA_SOURCE("world-bank")',  # 缺 query 参数
            "$DATA_SOURCE(world-bank, GDP)",  # 缺引号
            '$DATA_SOURCE("a", "b"',  # 未闭合括号
            '$DATA_SOURCE("a", "b", "c")',  # 多余参数
            '$DATA_SOURCE("", "b")',  # 空 name
            '$DATA_SOURCE("a", "")',  # 空 query
        ],
    )
    def test_syntax_error_raises_validation_error(self, bad_code: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_data_source_markers(bad_code)
        assert exc_info.value.code == "EXCEPTION_201"


class TestInjectDataSources:
    def test_inject_preamble_single_line(self) -> None:
        code = '$DATA_SOURCE("world-bank", "GDP")\nprint(DATA_SOURCES)'
        results = (_make_result("world-bank", 2.5),)
        injected = inject_data_sources(code, results)
        lines = injected.split("\n", 1)
        assert lines[0].startswith("DATA_SOURCES = ")
        # 前言是合法 Python 字面量（单行 JSON）
        prefix = "DATA_SOURCES = "
        data = json.loads(lines[0][len(prefix) :])
        assert "world-bank" in data
        assert data["world-bank"]["payload"]  # payload 内嵌
        assert data["world-bank"]["freshness_score"] > 0
        assert data["world-bank"]["confidence"] == 0.9
        # 原始代码保留（含标记行）
        assert lines[1] == code

    def test_inject_empty_results_no_preamble(self) -> None:
        code = "print(1)"
        assert inject_data_sources(code, ()) == code

    def test_no_eval_no_exec(self) -> None:
        """安全审查：注入产物不含 eval/exec 调用，参数仅经 ast.literal_eval 安全解析。"""
        import inspect

        import src.application.services.data_source_marker as marker_module

        source = inspect.getsource(marker_module)
        assert "eval(" not in source.replace("ast.literal_eval(", "")
        assert "exec(" not in source
