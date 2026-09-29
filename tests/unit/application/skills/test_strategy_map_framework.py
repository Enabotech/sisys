"""Story 4.1e Task 5: strategy-map Skill 成熟化单元测试（结构型范本 + bsc 分工映射）

TDD 循环覆盖（AC-1 / AC-2 / AC-3）：
- [A] frontmatter 声明契约：data_sources == ()（纯内部型一等不变量，D1）
      + IO Schema 契约（yaml 逐字相等）+ domain catalog 兼容（required 零删除）
      + input 根键锚定 bsc_indicators（禁用 bsc-scorecard 的 strategic_objectives——D13）
- [B] SOP 成熟化：9 章节 / input_examples 非 placeholder / ≤500 行 / 失败处理
      双关键词（207 + INSUFFICIENT_DATA——D3）/ 结构型三件套 + references 内容锚点 /
      因果箭头编码规范 + 负向触发双向跳转 + bsc 互查映射表
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == 声明集合 == ∅（空集语义）
- [D] 模板字段 ↔ input_schema 叶子键双向对应（5 叶子 + 单分区标题 +
      结构型第三段）+ 示例三方一致（模板 ↔ §8）

真实加载真实 SKILL.md（InMemorySkillLoader，范本 test_value_proposition_canvas_framework.py），禁止 mock。
"""

from __future__ import annotations

import pytest

from src.application.ports.skill_loader import SkillDocument
from src.application.skills.loader import InMemorySkillLoader
from src.application.skills.skill_manifest import TOOL_ID_TO_SLUG
from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG
from tests.unit.application.skills.skill_framework_contracts import (
    SKILLS_ROOT,
    assert_cross_consistency,
    assert_framework_data_sources_empty,
    assert_io_schema_contract,
    assert_reference_content_anchors,
    assert_sop_maturity,
    assert_template_schema_alignment,
)

SLUG = "strategy-map"


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 strategy-map 的 L2 SkillDocument"""
    loader = InMemorySkillLoader()
    return await loader.load_sop(SLUG)


class TestFrontmatterDeclaration:
    """[A] frontmatter 空声明一等不变量 + IO Schema 契约 + catalog 兼容 + 根键锚定"""

    def test_data_sources_empty_tuple(self, document: SkillDocument) -> None:
        """纯内部型一等不变量：data_sources == ()（不声明任何外部源——D1）"""
        assert_framework_data_sources_empty(SLUG, document)

    def test_io_schema_match_contract(self, document: SkillDocument) -> None:
        """input_schema/output_schema 与 IO 契约 yaml 逐字相等（双写一致）"""
        assert_io_schema_contract(SLUG, document.frontmatter)

    def test_input_root_key_anchored_to_bsc_indicators(self, document: SkillDocument) -> None:
        """根键锚定（D13/R9）：input 顶层为 bsc_indicators，禁用 bsc-scorecard 的 strategic_objectives"""
        properties = document.frontmatter.input_schema.get("properties", {})
        assert "bsc_indicators" in properties, "input 根键应为 bsc_indicators（strategy-map 契约锚）"
        assert "strategic_objectives" not in properties, (
            "strategy-map 禁用 bsc-scorecard 的 strategic_objectives 键名（D13 分工——定性因果链 vs 定量计分卡）"
        )

    def test_domain_catalog_required_preserved(self, document: SkillDocument) -> None:
        """domain catalog 既有 required/properties 零删除（R5：frontmatter 增强兼容约束）"""
        slug_to_tool = {TOOL_ID_TO_SLUG.get(t.tool_id): t for t in TOOL_CATALOG}
        catalog_tool = slug_to_tool[SLUG]
        catalog_input = catalog_tool.input_schema
        actual_input = document.frontmatter.input_schema
        assert set(catalog_input.get("required", [])) <= set(actual_input.get("required", [])), (
            "catalog 既有 input required 字段被删除"
        )
        assert set(catalog_input.get("properties", {})) <= set(actual_input.get("properties", {})), (
            "catalog 既有 input properties 键被删除"
        )
        catalog_output = catalog_tool.output_schema
        actual_output = document.frontmatter.output_schema
        assert set(catalog_output.get("properties", {})) <= set(actual_output.get("properties", {})), (
            "catalog 既有 output properties 键被删除"
        )


class TestSopMaturity:
    """[B] SOP 内容成熟化（9 章节 + 结构型三件套 + 内容锚点 + 因果箭头编码 + 分工映射）"""

    def test_sop_sections_and_resources(self, document: SkillDocument) -> None:
        """9 章节完备 + input_examples 非 placeholder + ≤500 行 + 分型三件套 + 模板齐备"""
        assert_sop_maturity(SLUG, document)

    def test_reference_content_anchors(self, document: SkillDocument) -> None:
        """references 内容要素字面锚点（编号步骤 + 英文键名 + 编号规则 + 关键字）"""
        assert_reference_content_anchors(SLUG, document)

    def test_failure_keywords_documented(self, document: SkillDocument) -> None:
        """失败处理双关键词显式断言（207 标记误用守护 + INSUFFICIENT_DATA 缺数据引导——D3）"""
        failure_section = document.body.split("失败处理", 1)[-1]
        assert "207" in failure_section, "失败处理章节缺少 207 标记误用守护说明"
        assert "INSUFFICIENT_DATA" in failure_section, "失败处理章节缺少 INSUFFICIENT_DATA 数据缺口引导"
        assert "warning" in failure_section or "不硬失败" in failure_section, (
            "失败处理章节缺少逆向或同层箭头 warning 级处置说明（不硬失败）"
        )

    def test_causal_arrow_coding_declared(self, document: SkillDocument) -> None:
        """因果箭头编码规范（D10）：§3/§5 声明「原因维度 → 结果维度」语法 + 标准方向示例"""
        body = document.body
        assert "原因维度 → 结果维度" in body, "缺少因果箭头语法声明（原因维度 → 结果维度：假设描述）"
        assert "learning_growth → internal_process" in body, "缺少标准方向示例条目（自下而上 Kaplan-Norton）"
        examples_section = body.split("input_examples", 1)[-1]
        assert "→" in examples_section, "§8 示例缺少因果箭头条目"

    def test_negative_trigger_points_to_bsc_scorecard(self, document: SkillDocument) -> None:
        """负向触发（D13）：§2 指向 bsc-scorecard（KPI 量化跳转）与 kpi-tree"""
        section = document.body.split("负向触发", 1)[-1].split("##", 1)[0]
        assert "bsc-scorecard" in section, "§2 负向触发未指向 bsc-scorecard（定量计分卡分工）"
        assert "kpi-tree" in section, "§2 负向触发未指向 kpi-tree（单 KPI 分解分工）"

    def test_bsc_scorecard_back_reference_established(self) -> None:
        """bsc 侧回跳（Subtask 5.7）：bsc-scorecard §2 负向触发含 strategy-map 字面串。"""
        bsc_skill = (SKILLS_ROOT / "bsc-scorecard" / "SKILL.md").read_text(encoding="utf-8")
        section = bsc_skill.split("负向触发", 1)[-1].split("##", 1)[0]
        assert "strategy-map" in section, (
            "bsc-scorecard §2 负向触发未回跳 strategy-map（定性因果链分工——D13 双向跳转的 bsc 侧）"
        )

    def test_cross_check_mapping_table_in_framework_logic(self, document: SkillDocument) -> None:
        """互查映射表（D13）：framework_logic 含键名对照（bsc_indicators ↔ strategic_objectives）
        与 bsc-scorecard 字面串 + 传递规则（定性先行、量化移交）。"""
        framework_logic = (SKILLS_ROOT / SLUG / "references" / "framework_logic.md").read_text(encoding="utf-8")
        assert "bsc_indicators" in framework_logic, "互查映射表缺少本侧键名 bsc_indicators"
        assert "strategic_objectives" in framework_logic, "互查映射表缺少 bsc-scorecard 侧键名 strategic_objectives"
        assert "bsc-scorecard" in framework_logic, "互查映射表缺少 bsc-scorecard 字面串"
        assert "移交" in framework_logic, "互查映射表缺少传递规则（量化验证移交 bsc-scorecard）"


class TestCrossConsistency:
    """[C] 跨循环一致性（空集语义——SOP 标记 == 声明 == ∅）"""

    def test_no_markers_in_sop(self, document: SkillDocument) -> None:
        """纯内部型 SOP 引导代码零 $DATA_SOURCE 标记（空集语义双向守护）"""
        assert_cross_consistency(SLUG, document)


class TestTemplateAlignment:
    """[D] 模板字段 ↔ input_schema 叶子键双向对应 + 示例三方一致"""

    def test_template_fields_match_schema_leaf_keys(self, document: SkillDocument) -> None:
        """采集模板字段 == input_schema 5 叶子（financial/customer/internal_process/learning_growth/causal_relationships）"""
        assert_template_schema_alignment(SLUG, document)

    def test_example_threeway_consistency(self, document: SkillDocument) -> None:
        """示例三方一致（R7）：模板因果条目 ↔ SKILL.md §8 JSON 同文本（见证条目：订单处理周期）"""
        template = (SKILLS_ROOT / SLUG / "templates" / "strategy_map_causal_links.md").read_text(encoding="utf-8")
        rules = (SKILLS_ROOT / SLUG / "references" / "validation_rules.md").read_text(encoding="utf-8")
        witness = "订单处理周期"
        assert witness in template, "模板示例缺少锚点见证条目（订单处理周期）"
        assert witness in document.body, "SKILL.md §8 示例缺少锚点见证条目（订单处理周期）"
        assert witness in rules, "validation_rules 校验示例缺少见证条目（订单处理周期）"
