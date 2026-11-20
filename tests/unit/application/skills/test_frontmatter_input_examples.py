"""Story 7-1 — frontmatter input_examples 字段单元测试（Task 4 TDD 循环 A）。

P7 承载（AC-6）：skill frontmatter 新增 ``input_examples`` 字段（1-5 条
参数 JSON 示例约束校验——非 list/零条/超 5 条 → ValidationError
EXCEPTION_201 族校验异常——故事异常表钦定；缺省缺字段容忍=空元组不报错、
tool schema 输出空，批量补齐后收紧为全量断言——Subtask 4.4）。

Run with:
    poetry run pytest tests/unit/application/skills/test_frontmatter_input_examples.py -v
"""

from __future__ import annotations

import pytest

from src.application.skills.frontmatter import normalize_metadata, parse_frontmatter
from src.domain.exceptions import ValidationError


def _make_valid_frontmatter(**overrides: object) -> str:
    """构造有效 frontmatter 文本（可覆盖字段——test_frontmatter.py 同款工厂形态）。"""
    base: dict = {
        "slug": "test-skill",
        "name": "测试工具",
        "version": "1.0.0",
        "description": "测试用工具",
    }
    base.update(overrides)
    yaml_lines = ["---"]
    for key, value in base.items():
        if isinstance(value, list):
            yaml_lines.append(f"{key}:")
            for item in value:
                yaml_lines.append(f"  - {item!r}")
        else:
            yaml_lines.append(f"{key}: {value!r}")
    yaml_lines.append("---")
    yaml_lines.append("# Body")
    return "\n".join(yaml_lines)


class TestInputExamplesParsing:
    """input_examples 字段解析与归一化。"""

    def test_valid_list_of_one_to_five_examples(self) -> None:
        """1-5 条示例正常解析为 tuple（list → tuple 归一——LIST_FIELDS 风格）。"""
        raw = _make_valid_frontmatter(input_examples=['{"query": "市场分析"}'])
        meta, _ = parse_frontmatter(raw)
        assert meta["input_examples"] == ('{"query": "市场分析"}',)

    def test_five_examples_upper_bound(self) -> None:
        """5 条上边界合法。"""
        raw = _make_valid_frontmatter(input_examples=["e1", "e2", "e3", "e4", "e5"])
        meta, _ = parse_frontmatter(raw)
        assert len(meta["input_examples"]) == 5

    def test_single_string_tolerated_as_single_element(self) -> None:
        """单值字符串兼容为单元素 tuple（YAML 单值形态——LIST_FIELDS 归一风格）。"""
        raw = _make_valid_frontmatter(input_examples='{"query": "a"}')
        meta, _ = parse_frontmatter(raw)
        assert meta["input_examples"] == ('{"query": "a"}',)

    def test_missing_field_defaults_to_empty_tuple(self) -> None:
        """缺省缺字段容忍：无 input_examples 键 → 不报错（归一为空元组）。"""
        raw = _make_valid_frontmatter()
        meta, _ = parse_frontmatter(raw)
        assert meta.get("input_examples", ()) == ()

    def test_empty_list_rejected_201(self) -> None:
        """零条 → ValidationError EXCEPTION_201（1-5 条约束）。"""
        raw = _make_valid_frontmatter(input_examples=[])
        with pytest.raises(ValidationError) as exc_info:
            parse_frontmatter(raw)
        assert exc_info.value.code == "EXCEPTION_201"
        assert "input_examples" in exc_info.value.message

    def test_six_examples_rejected_201(self) -> None:
        """六条 → ValidationError EXCEPTION_201（上界 5）。"""
        raw = _make_valid_frontmatter(input_examples=["e1", "e2", "e3", "e4", "e5", "e6"])
        with pytest.raises(ValidationError) as exc_info:
            parse_frontmatter(raw)
        assert exc_info.value.code == "EXCEPTION_201"

    def test_non_list_non_str_type_rejected_201(self) -> None:
        """非 list/str 类型（int）→ ValidationError EXCEPTION_201。"""
        raw = _make_valid_frontmatter(input_examples=42)
        with pytest.raises(ValidationError) as exc_info:
            parse_frontmatter(raw)
        assert exc_info.value.code == "EXCEPTION_201"

    def test_list_of_non_str_items_rejected_201(self) -> None:
        """list 内非 str 项 → ValidationError EXCEPTION_201（示例串形态约束）。"""
        raw = _make_valid_frontmatter(input_examples=[1, 2])
        with pytest.raises(ValidationError) as exc_info:
            parse_frontmatter(raw)
        assert exc_info.value.code == "EXCEPTION_201"


class TestInputExamplesNormalization:
    """input_examples 透传 ToolMetadata（tool schema 运行时数据通路——R1-F3）。"""

    def test_normalize_metadata_passes_input_examples(self) -> None:
        """normalize_metadata 透传 input_examples 至 ToolMetadata 字段。"""
        raw = _make_valid_frontmatter(input_examples=['{"query": "x"}', '{"query": "y"}'])
        meta, _ = parse_frontmatter(raw)
        tool_metadata = normalize_metadata(meta)
        assert tool_metadata.input_examples == ('{"query": "x"}', '{"query": "y"}')

    def test_tool_metadata_default_empty_tuple(self) -> None:
        """ToolMetadata 缺省 input_examples=()（向后兼容——尾部默认值惯例）。"""
        raw = _make_valid_frontmatter()
        meta, _ = parse_frontmatter(raw)
        tool_metadata = normalize_metadata(meta)
        assert tool_metadata.input_examples == ()

    def test_validation_context_contains_field(self) -> None:
        """校验异常 context 含 field=input_examples（定位锚）。"""
        raw = _make_valid_frontmatter(input_examples=[])
        with pytest.raises(ValidationError) as exc_info:
            parse_frontmatter(raw)
        assert exc_info.value.context.get("field") == "input_examples"
