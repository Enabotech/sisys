"""Story 4.1b — $DATA_SOURCE 标记解析器单元测试

验证 data_source_marker 模块：
- parse：单标记/多标记/嵌套引号/参数空白/重复标记去重/大小写敏感
- parse：语法错误 → ValidationError(201)（缺引号/缺参数/多余参数/未闭合括号/裸 `$`）
- parse：注释识别（注释撇号不吞后续标记、注释内标记文本忽略）
- inject：preamble 单行 Python 字面量（repr，ast.literal_eval 可逆）+ 标记原位替换
  为 DATA_SOURCES["name"] 表达式（注入产物必须 compile 可执行——R2-P0-1 闸门）
- inject：部分失败位标记替换 None（保 SOP 部分失败降级语义）
- 安全：参数经 ast.literal_eval 安全解析（禁止 eval/exec 动态执行）
"""

from __future__ import annotations

import ast
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


def _make_result(source_name: str, value: float = 1.0, payload: str | None = None) -> DataSourceResult:
    now = datetime.now(UTC)
    return DataSourceResult(
        source_name=source_name,
        payload=payload if payload is not None else json.dumps({"value": value}),
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
            '$DATA_SOURCE ("a", "b")',  # 标记名与括号间空白（有意收紧：显式报错而非静默忽略）
            "$DATA_SRC",  # 裸 $ 拼写错误（沙箱 SyntaxError 前置为宿主机 201）
            "price = $100",  # 裸 $ 非标记场景（Python 非法字符前置拦截）
        ],
    )
    def test_syntax_error_raises_validation_error(self, bad_code: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_data_source_markers(bad_code)
        assert exc_info.value.code == "EXCEPTION_201"


class TestCommentHandling:
    """注释识别专项（R2-P1-3：注释撇号吞标记 / 注释内标记文本误报）"""

    def test_apostrophe_in_comment_does_not_swallow_marker(self) -> None:
        """注释中未闭合撇号（don't）不影响后续真实标记解析。"""
        code = '# don\'t fetch twice\nx = $DATA_SOURCE("world-bank", "GDP")\nprint(x)'
        markers = parse_data_source_markers(code)
        assert len(markers) == 1
        assert markers[0].source_name == "world-bank"

    def test_marker_text_in_comment_ignored(self) -> None:
        """注释内的标记文本不识别为标记、不触发语法校验。"""
        code = '# $DATA_SOURCE("a", "b") 示例\nx = 1'
        assert parse_data_source_markers(code) == ()

    def test_dollar_in_comment_ignored(self) -> None:
        """注释内的裸 $（如价格说明）不触发语法校验。"""
        code = "# 价格 $100 起步\nx = 1"
        assert parse_data_source_markers(code) == ()

    def test_hash_inside_string_not_treated_as_comment(self) -> None:
        """字符串内的 # 不作为注释起点（其后的撇号仍在字符串内）。"""
        code = 'text = "a # don\'t"\n$DATA_SOURCE("imf", "WEO")'
        markers = parse_data_source_markers(code)
        assert len(markers) == 1

    def test_coordinate_regression_marker_before_string_mention(self) -> None:
        """R2-P1-2 坐标系回归：有效标记在前时，字符串内的标记文本不误报语法错误。"""
        code = 'x = $DATA_SOURCE("world-bank", "gdp")\nnote = "see $DATA_SOURCE( syntax"\n'
        markers = parse_data_source_markers(code)
        assert len(markers) == 1
        assert markers[0].source_name == "world-bank"


class TestStringLiteralSpanBoundaries:
    """Story 4.1c Task 8.5 — _string_literal_spans 字符级扫描边界专项（4-1b 推迟项收敛）

    覆盖 4-1b Round 1 P0-5 修复（tokenize → 纯字符级扫描）的四类边界场景：
    未闭合字符串降级 / 三引号字面量 / 转义字符边界 / 字符串字面量内伪标记不触发。
    """

    def test_unterminated_string_swallows_following_marker(self) -> None:
        """未闭合字符串保守登记到文件末尾：其后标记文本被吞（不误识别、不抛错）。"""
        code = 'text = \'未闭合\n$DATA_SOURCE("world-bank", "GDP")\n'
        assert parse_data_source_markers(code) == ()

    def test_marker_before_unterminated_string_parsed(self) -> None:
        """未闭合字符串之前的合法标记不受影响（降级不扩大误伤）。"""
        code = '$DATA_SOURCE("world-bank", "GDP")\ntext = \'未闭合\n'
        markers = parse_data_source_markers(code)
        assert len(markers) == 1
        assert markers[0].source_name == "world-bank"

    def test_marker_inside_triple_double_quotes_not_matched(self) -> None:
        """三引号（双）字符串字面量内的标记文本不触发。"""
        code = 'doc = """\n$DATA_SOURCE("world-bank", "GDP")\n"""\nprint(doc)'
        assert parse_data_source_markers(code) == ()

    def test_marker_inside_triple_single_quotes_not_matched(self) -> None:
        """三引号（单）字符串字面量内的标记文本不触发。"""
        code = "doc = '''\n$DATA_SOURCE(\"world-bank\", \"GDP\")\n'''\nprint(doc)"
        assert parse_data_source_markers(code) == ()

    def test_marker_after_triple_quoted_string_parsed(self) -> None:
        """三引号字符串闭合后的合法标记正常解析。"""
        code = 'doc = """说明"""\n$DATA_SOURCE("imf", "WEO")'
        markers = parse_data_source_markers(code)
        assert len(markers) == 1
        assert markers[0].source_name == "imf"

    def test_escaped_quote_in_query(self) -> None:
        """query 内转义引号经 ast.literal_eval 正确还原。"""
        code = '$DATA_SOURCE("newsapi", "He said \\"hi\\" loudly")'
        markers = parse_data_source_markers(code)
        assert len(markers) == 1
        assert markers[0].query == 'He said "hi" loudly'

    def test_escaped_backslash_before_closing_quote(self) -> None:
        """转义反斜杠结尾的字符串：闭合引号边界判定正确，后续标记不受影响。"""
        code = 'path = "C:\\\\data\\\\"\n$DATA_SOURCE("imf", "WEO")'
        markers = parse_data_source_markers(code)
        assert len(markers) == 1
        assert markers[0].source_name == "imf"

    def test_marker_inside_single_quoted_string_not_matched(self) -> None:
        """单引号字符串字面量内的伪标记不触发（既有仅覆盖双引号场景）。"""
        code = 'text = \'$DATA_SOURCE("a", "b")\'\nprint(text)'
        assert parse_data_source_markers(code) == ()


class TestInjectDataSources:
    def test_inject_preamble_python_literal_and_marker_replaced(self) -> None:
        """preamble 为 repr Python 字面量（ast.literal_eval 可逆）；标记原位替换为 DATA_SOURCES 引用。"""
        code = 'gdp = $DATA_SOURCE("world-bank", "GDP")\nprint(gdp)'
        markers = parse_data_source_markers(code)
        results = (_make_result("world-bank", 2.5),)
        injected = inject_data_sources(code, markers, results)
        lines = injected.split("\n", 1)
        assert lines[0].startswith("DATA_SOURCES = ")
        data = ast.literal_eval(lines[0][len("DATA_SOURCES = ") :])
        assert "world-bank" in data
        assert data["world-bank"]["payload"] == {"value": 2.5}
        assert data["world-bank"]["freshness_score"] > 0
        assert data["world-bank"]["confidence"] == 0.9
        # 标记原位替换（不再保留 $DATA_SOURCE 文本）
        assert "$DATA_SOURCE" not in lines[1]
        assert 'gdp = DATA_SOURCES["world-bank"]' in lines[1]
        # 闸门：注入产物必须是可编译的合法 Python（R2-P0-1 根因防护）
        compile(injected, "<sandbox>", "exec")

    def test_inject_payload_with_null_bool_unicode_executable(self) -> None:
        """payload 含 null/bool/unicode 时注入产物可执行且 DATA_SOURCES 可取（json.dumps NameError 回归）。"""
        code = 'v = $DATA_SOURCE("imf", "WEO")\nprint(v)'
        markers = parse_data_source_markers(code)
        payload = json.dumps({"value": None, "ok": True, "name": "中国"}, ensure_ascii=False)
        injected = inject_data_sources(code, markers, (_make_result("imf", payload=payload),))
        namespace: dict[str, object] = {}
        exec(compile(injected, "<sandbox>", "exec"), namespace)  # 测试沙箱语义验证
        data = namespace["DATA_SOURCES"]
        assert isinstance(data, dict)
        assert data["imf"]["payload"] == {"value": None, "ok": True, "name": "中国"}
        assert namespace["v"] == data["imf"]

    def test_inject_non_finite_float_payload_mapped_to_literal_string(self) -> None:
        """payload 含 NaN/Infinity（非标准 JSON 扩展）时映射为字面字符串（杜绝 repr 非法名称）。"""
        code = 'v = $DATA_SOURCE("imf", "WEO")'
        markers = parse_data_source_markers(code)
        injected = inject_data_sources(code, markers, (_make_result("imf", payload='{"v": NaN}'),))
        compile(injected, "<sandbox>", "exec")
        data = ast.literal_eval(injected.split("\n", 1)[0][len("DATA_SOURCES = ") :])
        assert data["imf"]["payload"] == {"v": "NaN"}

    def test_inject_partial_failure_replaces_none(self) -> None:
        """部分失败位标记替换为 None，成功源正常注入；产物可编译（保 SOP 降级语义）。"""
        code = 'a = $DATA_SOURCE("world-bank", "GDP")\nb = $DATA_SOURCE("eurostat", "EU")\nprint(a, b)'
        markers = parse_data_source_markers(code)
        results = (_make_result("world-bank", 1.0), None)  # eurostat 采集失败
        injected = inject_data_sources(code, markers, results)
        assert "eurostat" not in injected.split("\n", 1)[0]  # preamble 不含失败源键
        assert "b = None" in injected
        namespace: dict[str, object] = {}
        exec(compile(injected, "<sandbox>", "exec"), namespace)  # 测试沙箱语义验证
        assert namespace["b"] is None
        data = namespace["DATA_SOURCES"]
        assert isinstance(data, dict)
        assert namespace["a"] == data["world-bank"]

    def test_inject_same_name_different_query_numbered_keys(self) -> None:
        """同源异 query 按去重出现次序分配 name / name#2 键（零数据覆盖）。"""
        code = 'g = $DATA_SOURCE("imf", "WEO GDP")\nc = $DATA_SOURCE("imf", "WEO CPI")'
        markers = parse_data_source_markers(code)
        results = (_make_result("imf", 1.0), _make_result("imf", 2.0))
        injected = inject_data_sources(code, markers, results)
        data = ast.literal_eval(injected.split("\n", 1)[0][len("DATA_SOURCES = ") :])
        assert set(data.keys()) == {"imf", "imf#2"}
        assert data["imf"]["payload"] == {"value": 1.0}
        assert data["imf#2"]["payload"] == {"value": 2.0}
        assert 'g = DATA_SOURCES["imf"]' in injected
        assert 'c = DATA_SOURCES["imf#2"]' in injected
        compile(injected, "<sandbox>", "exec")

    def test_inject_marker_inside_string_not_replaced(self) -> None:
        """字符串字面量内的标记文本不替换（掩码保护）。"""
        code = 'note = "$DATA_SOURCE(语法示例"\ng = $DATA_SOURCE("imf", "WEO")'
        markers = parse_data_source_markers(code)
        injected = inject_data_sources(code, markers, (_make_result("imf", 1.0),))
        assert 'note = "$DATA_SOURCE(语法示例"' in injected
        compile(injected, "<sandbox>", "exec")

    def test_inject_empty_markers_returns_code(self) -> None:
        code = "print(1)"
        assert inject_data_sources(code, (), ()) == code

    def test_no_eval_no_exec(self) -> None:
        """安全审查：注入产物不含 eval/exec 调用，参数仅经 ast.literal_eval 安全解析。"""
        import inspect

        import src.application.services.data_source_marker as marker_module

        source = inspect.getsource(marker_module)
        assert "eval(" not in source.replace("ast.literal_eval(", "")
        assert "exec(" not in source
