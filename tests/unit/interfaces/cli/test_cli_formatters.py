"""格式化器三件单测（Task 1 循环 B——AC-2 输出格式面）。

覆盖面（Task 0.3 信封契约冻结表同源）：
    - build_envelope 信封骨架（ok/command/data/mock 四键 + mock 时 echo）
    - render_json 单行紧凑（ensure_ascii=False）+ json.loads 往返
    - render_table 两遍法动态列宽（_print_checkpoint_summary_table 先例形态）
    - render_pretty 人类可读多行中文
    - format_result 三态分发 + 非法格式值 ValidationError(201) 守卫
    - 命令级 dispatch json/table 态零 ``_print_*`` 归 Task 2 循环 C/Task 6.4
      架构位承载（OD-14——Task 1 时点真命令尚未挂载）
"""

from __future__ import annotations

import json

import pytest

from src.domain.exceptions import ValidationError
from src.interfaces.cli.formatters import (
    build_envelope,
    format_result,
    render_json,
    render_pretty,
    render_table,
)


class TestBuildEnvelope:
    """统一信封构造（Task 0.3 冻结表骨架）。"""

    def test_envelope_has_four_base_keys(self) -> None:
        """基本信封含 ok/command/data/mock 四键。"""
        envelope = build_envelope(command="sisys document upload", data={"document_id": "d1"})
        assert envelope["ok"] is True
        assert envelope["command"] == "sisys document upload"
        assert envelope["data"] == {"document_id": "d1"}
        assert envelope["mock"] is False

    def test_mock_envelope_contains_echo(self) -> None:
        """mock 信封含 mock=true 与 echo 参数回显。"""
        envelope = build_envelope(
            command="sisys document upload",
            data={},
            mock=True,
            echo={"file": "a.md", "tenant_id": "t1"},
        )
        assert envelope["mock"] is True
        assert envelope["echo"] == {"file": "a.md", "tenant_id": "t1"}

    def test_failure_envelope_ok_false(self) -> None:
        """失败态信封 ok=False。"""
        envelope = build_envelope(command="sisys tool run", data={}, ok=False)
        assert envelope["ok"] is False


class TestRenderJson:
    """JSON 渲染（单行紧凑 ensure_ascii=False——AC-2 钦定）。"""

    def test_single_line_compact(self) -> None:
        """单行无换行（pipe 消费友好）。"""
        envelope = build_envelope(command="sisys tool list", data={"total": 2})
        rendered = render_json(envelope)
        assert "\n" not in rendered, f"JSON 输出应单行: {rendered!r}"

    def test_ensure_ascii_false_keeps_chinese(self) -> None:
        """中文原样保留（ensure_ascii=False）。"""
        envelope = build_envelope(command="sisys document search", data={"query": "战略规划"})
        rendered = render_json(envelope)
        assert "战略规划" in rendered, f"中文被转义: {rendered!r}"

    def test_json_loads_roundtrip(self) -> None:
        """json.loads 往返等价（机器可解析契约）。"""
        envelope = build_envelope(
            command="sisys tool run", data={"tool_id": "t", "status": "ok"}, mock=True, echo={"input": "{}"}
        )
        parsed = json.loads(render_json(envelope))
        assert parsed == envelope


class TestRenderTable:
    """表格渲染（两遍法动态列宽——agent_cli.py:1495-1518 先例形态）。"""

    def test_two_pass_dynamic_column_width(self) -> None:
        """列宽=max(表头, 数据行)——中文宽字符列不截断。"""
        headers = ["checkpoint_no", "stage"]
        rows = [["1", "market_insight_超长阶段名"], ["2", "共识"]]
        rendered = render_table(headers, rows)
        lines = [line for line in rendered.splitlines() if line.strip()]
        assert len(lines) == 3, f"应含表头+2 数据行: {rendered!r}"
        header_line, row1, _ = lines
        assert "checkpoint_no" in header_line
        assert "market_insight_超长阶段名" in row1, "长值被截断（两遍法失效）"

    def test_precedent_form_no_separator_line(self) -> None:
        """先例形态：表头行直接跟数据行（无分隔线——:1495-1518 钦定）。"""
        rendered = render_table(["a", "b"], [["1", "2"]])
        lines = [line for line in rendered.splitlines() if line.strip()]
        assert len(lines) == 2, f"表头+数据行两行（无分隔线）: {rendered!r}"
        assert "a" in lines[0] and "1" in lines[1]

    def test_empty_rows_only_header(self) -> None:
        """空数据行仅表头（空态语义）。"""
        rendered = render_table(["a", "b"], [])
        lines = [line for line in rendered.splitlines() if line.strip()]
        assert len(lines) == 1, f"空数据应仅表头: {rendered!r}"


class TestRenderPretty:
    """人类可读渲染（多行中文——既有形态）。"""

    def test_multiline_human_readable(self) -> None:
        """数据 dict 渲染为多行键值（中文标签友好）。"""
        rendered = render_pretty({"total": 3, "query": "战略"})
        assert "total" in rendered and "3" in rendered
        assert "战略" in rendered

    def test_chinese_not_escaped(self) -> None:
        """中文不转义（非 JSON 形态断言）。"""
        rendered = render_pretty({"name": "工具清单"})
        assert "工具清单" in rendered
        assert "\\u" not in rendered

    def test_nested_list_dict_items(self) -> None:
        """嵌套 list[dict] 清单语义渲染（逐项缩进——R1-T7 该分支原零覆盖）。"""
        rendered = render_pretty(
            {
                "plan_id": "p-1",
                "checkpoints": [{"checkpoint_no": "CP-1", "stage": "trend"}, {"checkpoint_no": "CP-2", "stage": "gap"}],
            }
        )
        lines = rendered.splitlines()
        assert any("checkpoints:" in line for line in lines), f"清单键行缺失: {rendered!r}"
        joined = "\n".join(lines)
        assert "CP-1" in joined and "CP-2" in joined, f"清单项缺失: {rendered!r}"
        assert "- " in joined, f"清单项缩进形态缺失: {rendered!r}"


class TestFormatResult:
    """三态分发器（json/table/pretty——缺省 pretty）。"""

    def test_dispatch_json(self) -> None:
        """json 态返回信封单行 JSON。"""
        rendered = format_result("json", command="sisys tool list", data={"total": 1})
        parsed = json.loads(rendered)
        assert parsed["ok"] is True and parsed["data"] == {"total": 1}

    def test_dispatch_table(self) -> None:
        """table 态返回两遍法表格（rows-of-dicts 转 headers/rows）。"""
        rendered = format_result("table", command="sisys tool list", data={"tools": [{"tool_id": "t1", "name": "swot"}]})
        assert "tool_id" in rendered and "swot" in rendered

    def test_dispatch_pretty(self) -> None:
        """pretty 态返回人类可读多行。"""
        rendered = format_result("pretty", command="sisys tool list", data={"total": 1})
        assert "total" in rendered
        with pytest.raises(json.JSONDecodeError):
            json.loads(rendered)

    def test_dispatch_default_is_pretty(self) -> None:
        """缺省格式=pretty（AC-2 钦定）。"""
        rendered_default = format_result("", command="sisys tool list", data={"total": 1})
        rendered_pretty = format_result("pretty", command="sisys tool list", data={"total": 1})
        assert rendered_default == rendered_pretty

    def test_illegal_format_raises_validation_error(self) -> None:
        """非法格式值 → ValidationError(201)——禁裸 ValueError 逃逸统一异常体系。"""
        with pytest.raises(ValidationError) as exc_info:
            format_result("yaml", command="sisys tool list", data={})
        assert exc_info.value.code == "EXCEPTION_201"


class TestStdoutPurity:
    """stdout 纯净机制（json/table 渲染源=controller result——OD-14 机制位说明）。

    formatter 层契约：render_* 系纯函数返回字符串（调用方 print 到 stdout），
    自身不打印——进度/日志类输出天然不走 formatter 通道（stderr 分流在命令层
    经 logging stderr 配置承载，agent_cli main() 先例 :2635-2639）。
    """

    def test_render_functions_are_pure_no_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        """渲染函数纯返回不打印（capsys 捕获为空）。"""
        envelope = build_envelope(command="c", data={"a": 1})
        render_json(envelope)
        render_table(["h"], [["v"]])
        render_pretty({"a": 1})
        captured = capsys.readouterr()
        assert captured.out == "", f"渲染函数不应打印 stdout: {captured.out!r}"
        assert captured.err == "", f"渲染函数不应打印 stderr: {captured.err!r}"
