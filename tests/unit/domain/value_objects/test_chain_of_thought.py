"""ChainOfThought 值对象单元测试（Story 5-3 — 单 Agent 标准工作流）

覆盖思维链五字段 frozen 值对象的自校验与展示契约：
- 五字段合法构造往返 + frozen 不可变
- 四 str 字段先 isinstance(str) 类型守卫再 strip 判空（5-1 R2-F2 教训防线）
- tools_used 元组类型守卫（元素 str）+ 空元组合法（无工具任务形态——AC-2）
- 校验失败统一 EntityValidationError(EXCEPTION_242)（VO 构造器守卫语义；
  服务端终局组装完整性校验捕获 242 改写 445——异常契约三层次序②）
- to_display() 五段展示形态（Input → 三个 XML 标签段 → JSON 尾段——
  or.md §五.5 L480 展示契约，存储用结构化、展示用标签 DC-2 双形态）

Run with:
    poetry run pytest tests/unit/domain/value_objects/test_chain_of_thought.py -v
"""

from __future__ import annotations

import json

import pytest

from src.domain.exceptions import EntityValidationError


def _make_chain(**kwargs):
    """工厂：构造合法思维链值对象（可覆盖任意字段）。

    Story 5-3 新模块延迟 import 纪律——模块顶部 import 会使收集期整文件炸。
    """
    from src.domain.value_objects.chain_of_thought import ChainOfThought

    defaults: dict = {
        "input_summary": "输入摘要：分析新能源汽车行业进入战略",
        "reflection": "反思：分析覆盖政策、经济与技术三维度",
        "tools_used": ("pestel:v1.2.0", "swot:v1.0.0"),
        "constraints_check": "约束检查：符合 MVP 范围与安全红线",
        "final_answer": json.dumps({"answer": "建议采用三层次进入策略"}, ensure_ascii=False),
    }
    defaults.update(kwargs)
    return ChainOfThought(**defaults)


# ===================================================================
# 合法构造与 frozen
# ===================================================================


class TestValidConstruction:
    """五字段合法构造往返与 frozen 不可变。"""

    def test_full_fields_roundtrip(self) -> None:
        """全字段构造后逐字段读回一致。"""
        chain = _make_chain()
        assert chain.input_summary.startswith("输入摘要")
        assert "三维度" in chain.reflection
        assert chain.tools_used == ("pestel:v1.2.0", "swot:v1.0.0")
        assert chain.constraints_check.startswith("约束检查")
        assert json.loads(chain.final_answer)["answer"].startswith("建议")

    def test_empty_tools_used_is_legal(self) -> None:
        """tools_used 空元组合法——无工具任务的合法形态（AC-2 完整率口径）。"""
        chain = _make_chain(tools_used=())
        assert chain.tools_used == ()

    def test_frozen_dataclass(self) -> None:
        """frozen：setattr 抛异常（思维链为不可变值对象）。"""
        chain = _make_chain()
        with pytest.raises(Exception, match="cannot assign|frozen"):
            setattr(chain, "reflection", "# 篡改")


# ===================================================================
# 字段守卫（先类型后空值——truthy 标量越过判空的防线）
# ===================================================================


class TestFieldGuards:
    """四 str 字段类型守卫 + strip 判空；tools_used 元组类型守卫（242）。"""

    @pytest.mark.parametrize(
        "field_name",
        ["input_summary", "reflection", "constraints_check", "final_answer"],
    )
    def test_non_string_field_rejected(self, field_name: str) -> None:
        """str 字段非 str（如 int/list）→ 242——类型守卫先于判空。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_chain(**{field_name: 12345})
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.parametrize(
        "field_name",
        ["input_summary", "reflection", "constraints_check", "final_answer"],
    )
    def test_empty_string_rejected(self, field_name: str) -> None:
        """空串 → 242。"""
        with pytest.raises(EntityValidationError):
            _make_chain(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name",
        ["input_summary", "reflection", "constraints_check", "final_answer"],
    )
    def test_blank_string_rejected(self, field_name: str) -> None:
        """纯空白串 → 242（strip 校验）。"""
        with pytest.raises(EntityValidationError):
            _make_chain(**{field_name: "   \n\t  "})

    def test_tools_used_must_be_tuple(self) -> None:
        """tools_used 非 tuple（如 list）→ 242——元组形态纪律（frozen 不可变）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_chain(tools_used=["pestel:v1.2.0"])
        assert exc_info.value.code == "EXCEPTION_242"

    def test_tools_used_element_must_be_str(self) -> None:
        """tools_used 元素非 str（如 int）→ 242。"""
        with pytest.raises(EntityValidationError):
            _make_chain(tools_used=(12345,))

    def test_tools_used_empty_str_element_rejected(self) -> None:
        """tools_used 含空串元素 → 242（轨迹条目级非空）。"""
        with pytest.raises(EntityValidationError):
            _make_chain(tools_used=("pestel:v1.2.0", "  "))


# ===================================================================
# to_display 五段展示形态（DC-2 双形态：存储用结构化、展示用标签）
# ===================================================================


class TestToDisplay:
    """to_display() 展示契约：五段形态 + 三个 XML 标签段 + JSON 尾段。"""

    def test_display_contains_five_segments_in_order(self) -> None:
        """五段顺序：Input → Reflection → Tools_Used → Constraints_Check → JSON 尾段。"""
        display = _make_chain().to_display()
        positions = [
            display.index("Input"),
            display.index("<Reflection>"),
            display.index("<Tools_Used>"),
            display.index("<Constraints_Check>"),
        ]
        assert positions == sorted(positions), f"五段顺序异常: {display!r}"

    def test_display_contains_xml_tag_pairs(self) -> None:
        """三个 XML 标签段闭合完整。"""
        display = _make_chain().to_display()
        assert "<Reflection>" in display and "</Reflection>" in display
        assert "<Tools_Used>" in display and "</Tools_Used>" in display
        assert "<Constraints_Check>" in display and "</Constraints_Check>" in display

    def test_display_json_tail_is_final_answer_verbatim(self) -> None:
        """JSON 尾段为 final_answer 原样（最后一段剥分隔符后可解析）。"""
        chain = _make_chain()
        display = chain.to_display()
        json_tail = display.rsplit("→", 1)[-1].strip()
        assert json_tail == chain.final_answer
        assert json.loads(json_tail)["answer"].startswith("建议")

    def test_display_tools_section_lists_trace(self) -> None:
        """Tools_Used 段逐行列出轨迹条目。"""
        display = _make_chain().to_display()
        tools_section = display.split("<Tools_Used>", 1)[1].split("</Tools_Used>", 1)[0]
        assert "pestel:v1.2.0" in tools_section
        assert "swot:v1.0.0" in tools_section

    def test_display_empty_tools_section_placeholder(self) -> None:
        """空元组时 Tools_Used 段有占位内容（段不空——展示形态完整性）。"""
        display = _make_chain(tools_used=()).to_display()
        tools_section = display.split("<Tools_Used>", 1)[1].split("</Tools_Used>", 1)[0]
        assert tools_section.strip(), "空轨迹时 Tools_Used 段应有占位内容"
