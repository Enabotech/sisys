"""Story 7-1 — CLI 三态输出格式化器单元测试（Task 1 TDD 红阶段）。

覆盖 AC-4 契约：json 合法性+UUID/Decimal 序列化（default=str 策略锚——
R2-1）/表格列宽中文对齐（agent_cli 两遍法先例口径）/pretty 分组缩进/
空态契约三格式冻结（json=[]/table=表头+零数据行/pretty=空态提示语——R2-6）。

Run with:
    poetry run pytest tests/unit/interfaces/cli/test_cli_formatters.py -v
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

# ===================================================================
# json_formatter
# ===================================================================


class TestJsonFormatter:
    """JSON 格式化器（序列化策略冻结：json.dumps(payload, default=str, ensure_ascii=False)）。"""

    def test_render_dict_valid_json(self) -> None:
        """dict 载荷渲染为合法 JSON 单文档。"""
        from src.interfaces.cli.formatters.json_formatter import render

        output = render({"document_id": "doc-1", "status": "uploaded"})
        assert json.loads(output) == {"document_id": "doc-1", "status": "uploaded"}

    def test_render_list_valid_json(self) -> None:
        """list 载荷渲染为合法 JSON 数组。"""
        from src.interfaces.cli.formatters.json_formatter import render

        output = render([{"name": "pestel"}, {"name": "swot"}])
        parsed = json.loads(output)
        assert isinstance(parsed, list) and len(parsed) == 2

    def test_uuid_decimal_datetime_serialized_via_default_str(self) -> None:
        """UUID/Decimal/datetime 字段经 default=str 降维（UUID→hex 串、Decimal→十进制串——R2-1 冻结）。"""
        from src.interfaces.cli.formatters.json_formatter import render

        payload: dict[str, Any] = {
            "plan_id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "cost_budget": Decimal("1.50"),
            "created_at": datetime(2026, 11, 20, 10, 30, 0),
        }
        parsed = json.loads(render(payload))
        assert parsed["plan_id"] == "12345678-1234-5678-1234-567812345678"
        assert parsed["cost_budget"] == "1.50"
        assert parsed["created_at"] == "2026-11-20 10:30:00"

    def test_chinese_not_escaped(self) -> None:
        """中文 ensure_ascii=False（原样输出非 \\u 转义——LLM 直接消费可读性）。"""
        from src.interfaces.cli.formatters.json_formatter import render

        output = render({"task": "分析市场趋势"})
        assert "分析市场趋势" in output

    def test_empty_list_renders_empty_array(self) -> None:
        """空列表契约：json=空 JSON 数组 []（R2-6 冻结）。"""
        from src.interfaces.cli.formatters.json_formatter import render

        assert render([]) == "[]"

    def test_nested_payload_serialized(self) -> None:
        """嵌套结构（嵌套 dict/list/混合非原生类型）完整序列化。"""
        from src.interfaces.cli.formatters.json_formatter import render

        payload = {
            "session": "s-1",
            "nested": {"ids": [uuid.UUID(int=1), uuid.UUID(int=2)], "budget": Decimal("9.99")},
        }
        parsed = json.loads(render(payload))
        assert parsed["nested"]["budget"] == "9.99"
        assert len(parsed["nested"]["ids"]) == 2


# ===================================================================
# table_formatter
# ===================================================================


class TestTableFormatter:
    """表格格式化器（agent_cli 两遍法先例：str.ljust 列宽 + ' | ' 分隔）。"""

    def test_render_dict_as_field_value_table(self) -> None:
        """dict 载荷渲染键值两列表（字段 | 值 表头 + 每键一行）。"""
        from src.interfaces.cli.formatters.table_formatter import render

        output = render({"document_id": "doc-1", "mime_type": "text/markdown"})
        lines = output.splitlines()
        assert lines[0].startswith("字段") and "值" in lines[0]
        assert any("document_id" in line and "doc-1" in line for line in lines)
        assert any("mime_type" in line and "text/markdown" in line for line in lines)

    def test_render_list_aligns_columns_with_chinese(self) -> None:
        """list[dict] 载荷：表头=键并集保序 + 两遍法列宽（中文列宽 len 口径——agent_cli 先例）。"""
        from src.interfaces.cli.formatters.table_formatter import render

        rows = [
            {"checkpoint_no": "CP-1", "stage_id": "market_insight", "summary": "市场洞察"},
            {"checkpoint_no": "CP-10", "stage_id": "strategic_selection", "summary": "战略选择"},
        ]
        output = render(rows)
        lines = output.splitlines()
        assert len(lines) == 3  # 表头 + 2 数据行
        header = lines[0]
        for key in ("checkpoint_no", "stage_id", "summary"):
            assert key in header
        assert "CP-1" in lines[1] and "市场洞察" in lines[1]
        assert "CP-10" in lines[2] and "战略选择" in lines[2]
        # 两遍法列宽：同列不同宽度值（CP-1/CP-10）起始列位置一致（列宽扩展可观测——
        # 变异判别力锚：列宽不增长时 CP-10 行整体右移，起始位错开）
        cp1_idx = lines[1].index("CP-1")
        cp10_idx = lines[2].index("CP-10")
        assert cp1_idx == cp10_idx, "同列值应左对齐（两遍法列宽一致）"
        # 值宽超过表头宽时列宽扩展（数据行 CP-10 宽于表头 checkpoint_no 时不截断）
        stage1_idx = lines[1].index("market_insight")
        stage2_idx = lines[2].index("strategic_selection")
        assert stage1_idx == stage2_idx, "第二列起始位置应一致（首列列宽按最宽值扩展）"
        # 第三列起始受第二列最宽值（strategic_selection=20 > stage_id=8）扩展传播——
        # 变异判别力锚：列宽不增长时 market_insight 行的 summary 起始位提前、两行错开
        sum1_idx = lines[1].index("市场洞察")
        sum2_idx = lines[2].index("战略选择")
        assert sum1_idx == sum2_idx, "第三列起始应一致（第二列列宽按最宽值扩展传播）"

    def test_render_list_union_headers_missing_keys_as_empty(self) -> None:
        """行键不齐时键并集保序，缺失键渲染空串。"""
        from src.interfaces.cli.formatters.table_formatter import render

        rows = [{"a": "1"}, {"a": "2", "b": "3"}]
        lines = render(rows).splitlines()
        assert "a" in lines[0] and "b" in lines[0]
        assert lines[1].rstrip().endswith("1")

    def test_empty_list_renders_no_rows(self) -> None:
        """空列表契约：table=零数据行（无行无表头——空态不报错，R2-6）。"""
        from src.interfaces.cli.formatters.table_formatter import render

        assert render([]) == ""

    def test_empty_dict_renders_header_only(self) -> None:
        """空 dict 契约：表头+零数据行（R2-6 冻结）。"""
        from src.interfaces.cli.formatters.table_formatter import render

        output = render({})
        assert output.strip() != ""
        assert len(output.splitlines()) == 1  # 仅表头行

    def test_non_native_values_stringified(self) -> None:
        """UUID/Decimal/嵌套值经 str() 展平入表（f-string 内建转展语义等价——R2-1 裁定注记）。"""
        from src.interfaces.cli.formatters.table_formatter import render

        payload = {"plan_id": uuid.UUID(int=42), "budget": Decimal("3.14")}
        output = render(payload)
        assert str(uuid.UUID(int=42)) in output
        assert "3.14" in output


# ===================================================================
# pretty_formatter
# ===================================================================


class TestPrettyFormatter:
    """美化格式化器（分组+缩进终端输出）。"""

    def test_render_dict_grouped_lines(self) -> None:
        """dict 载荷：每键一行分组（键: 值）。"""
        from src.interfaces.cli.formatters.pretty_formatter import render

        output = render({"document_id": "doc-1", "status": "uploaded"})
        assert "document_id" in output and "doc-1" in output
        assert "status" in output and "uploaded" in output

    def test_nested_dict_indented(self) -> None:
        """嵌套 dict 缩进呈现（分组+缩进——AC-4）。"""
        from src.interfaces.cli.formatters.pretty_formatter import render

        output = render({"outer": {"inner": "value"}})
        outer_line_idx = output.splitlines()[0].index("outer") if "outer" in output.splitlines()[0] else -1
        assert "outer" in output and "inner" in output and "value" in output
        inner_lines = [line for line in output.splitlines() if "inner" in line]
        assert inner_lines, "嵌套键应有独立行"
        assert inner_lines[0].startswith("  ") or outer_line_idx >= 0, "嵌套层应缩进"

    def test_render_list_items_separated(self) -> None:
        """list 载荷：每条独立分组呈现（多条可辨）。"""
        from src.interfaces.cli.formatters.pretty_formatter import render

        rows = [{"checkpoint_no": "CP-1"}, {"checkpoint_no": "CP-2"}]
        output = render(rows)
        assert "CP-1" in output and "CP-2" in output
        assert len(output.splitlines()) >= 2

    def test_render_list_with_scalar_items(self) -> None:
        """list 含非 dict 项：标量条目独立分组呈现（str 展平）。"""
        from src.interfaces.cli.formatters.pretty_formatter import render

        output = render(["pestel", "swot-tows"])
        assert "pestel" in output and "swot-tows" in output
        assert "第 1 条" in output and "第 2 条" in output

    def test_empty_list_renders_hint_message(self) -> None:
        """空列表契约：pretty=空态提示语（R2-6 冻结）。"""
        from src.interfaces.cli.formatters.pretty_formatter import render

        output = render([])
        assert output.strip() != ""
        assert "无" in output or "空" in output, f"空态提示语缺失: {output!r}"

    def test_empty_dict_renders_hint_message(self) -> None:
        """空 dict 契约：空态提示语。"""
        from src.interfaces.cli.formatters.pretty_formatter import render

        output = render({})
        assert "无" in output or "空" in output


# ===================================================================
# formatters 包分发
# ===================================================================


class TestFormattersDispatch:
    """格式化器包入口：按 format 值分发（Task 1.4 重构锚）。"""

    @pytest.mark.parametrize("fmt", ["json", "table", "pretty"])
    def test_get_formatter_returns_render_callable(self, fmt: str) -> None:
        """get_formatter 按 format 值返回对应渲染函数（可调用且签名 render(payload)->str）。"""
        from src.interfaces.cli.formatters import get_formatter

        formatter = get_formatter(fmt)
        assert callable(formatter)
        output = formatter({"key": "值"})
        assert isinstance(output, str) and output != ""

    def test_get_formatter_unknown_raises_value_error_like_domain_error(self) -> None:
        """未知 format 值拒绝（typer choice 守卫为第一道防线——包入口为第二道）。"""
        from src.domain.exceptions import ValidationError
        from src.interfaces.cli.formatters import get_formatter

        with pytest.raises(ValidationError):
            get_formatter("yaml")
