"""Story 4.1e Task 4: org-design-framework Skill 成熟化单元测试（catalog 增强范本）

TDD 循环覆盖（AC-1 / AC-2 / AC-3）：
- [A] frontmatter 声明契约：data_sources == ()（纯内部型一等不变量，D1）
      + IO Schema 契约（yaml 逐字相等）+ domain catalog 兼容（既有三字段零删除）
      + **D10 catalog 四维增强断言**（strategy/processes/rewards/people 子容器）
- [B] SOP 成熟化：9 章节 / input_examples 非 placeholder / ≤500 行 / 失败处理
      双关键词（207 + INSUFFICIENT_DATA——D3）/ 评分型三件套 + references 内容锚点 /
      编码规范四方同步抽查 + Galbraith 五维 + org_structure 名实注记
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == 声明集合 == ∅（空集语义）
- [D] 模板字段 ↔ input_schema 叶子键双向对应（7 叶子单分区）+ 示例三方一致

真实加载真实 SKILL.md（InMemorySkillLoader，范本 test_value_proposition_canvas_framework.py），禁止 mock。
"""

from __future__ import annotations

import re

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

SLUG = "org-design-framework"


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 org-design-framework 的 L2 SkillDocument"""
    loader = InMemorySkillLoader()
    return await loader.load_sop(SLUG)


class TestFrontmatterDeclaration:
    """[A] frontmatter 空声明一等不变量 + IO Schema 契约 + catalog 兼容与 D10 增强"""

    def test_data_sources_empty_tuple(self, document: SkillDocument) -> None:
        """纯内部型一等不变量：data_sources == ()（不声明任何外部源——D1）"""
        assert_framework_data_sources_empty(SLUG, document)

    def test_io_schema_match_contract(self, document: SkillDocument) -> None:
        """input_schema/output_schema 与 IO 契约 yaml 逐字相等（双写一致）"""
        assert_io_schema_contract(SLUG, document.frontmatter)

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

    def test_catalog_enhanced_with_four_dimensions(self, document: SkillDocument) -> None:
        """D10 catalog 四维增强（唯一预期生产 .py 增强——只加不改删）：
        org_structure properties 新增 strategy/processes/rewards/people 子容器，
        与 frontmatter（yaml SSOT）四维结构逐字一致。"""
        slug_to_tool = {TOOL_ID_TO_SLUG.get(t.tool_id): t for t in TOOL_CATALOG}
        catalog_tool = slug_to_tool[SLUG]
        catalog_org = catalog_tool.input_schema["properties"]["org_structure"]
        actual_org = document.frontmatter.input_schema["properties"]["org_structure"]
        # 既有三字段零删除
        for legacy in ("functions", "reporting_lines", "decentralization_level"):
            assert legacy in catalog_org["properties"], f"catalog 既有字段 {legacy} 被删除"
        # 四维子容器新增且与 frontmatter 逐字一致
        for dimension in ("strategy", "processes", "rewards", "people"):
            assert dimension in catalog_org["properties"], f"catalog 缺少 D10 四维扩展子容器 {dimension}"
            assert catalog_org["properties"][dimension] == actual_org["properties"][dimension], (
                f"catalog 四维子容器 {dimension} 与 frontmatter（yaml SSOT）不一致"
            )
        # 嵌套 required 同步增强（org_structure.required 含七键）
        assert set(catalog_org.get("required", [])) == set(actual_org.get("required", [])), (
            "catalog org_structure 嵌套 required 未同步增强"
        )


class TestSopMaturity:
    """[B] SOP 内容成熟化（9 章节 + 评分型三件套 + 内容锚点 + Galbraith 五维）"""

    def test_sop_sections_and_resources(self, document: SkillDocument) -> None:
        """9 章节完备 + input_examples 非 placeholder + ≤500 行 + 分型三件套 + 模板齐备"""
        assert_sop_maturity(SLUG, document)

    def test_reference_content_anchors(self, document: SkillDocument) -> None:
        """references 内容要素字面锚点（编号步骤 + 英文键名 + 分档含义 + 正反例独立字样）"""
        assert_reference_content_anchors(SLUG, document)

    def test_failure_keywords_documented(self, document: SkillDocument) -> None:
        """失败处理双关键词显式断言（207 标记误用守护 + INSUFFICIENT_DATA 缺数据引导——D3）"""
        failure_section = document.body.split("失败处理", 1)[-1]
        assert "207" in failure_section, "失败处理章节缺少 207 标记误用守护说明"
        assert "INSUFFICIENT_DATA" in failure_section, "失败处理章节缺少 INSUFFICIENT_DATA 数据缺口引导"

    def test_coding_convention_declared_in_sections(self, document: SkillDocument) -> None:
        """编码规范四方同步抽查（D10）：§3 输入字段表 + §8 示例均含维度对齐度分值语义与解析锚点"""
        body = document.body
        assert "维度对齐度分值" in body, "§3 缺少编码规范表述（维度对齐度分值（1-5）—— 条目描述）"
        assert "首个『 —— 』" in body, "缺少确定性解析锚点半句（首个『 —— 』之前前缀中的独立 1-5 整数）"
        examples_section = body.split("input_examples", 1)[-1]
        assert " —— " in examples_section, "§8 示例缺少「分值 —— 描述」微格式条目"

    def test_galbraith_five_dimensions_documented(self, document: SkillDocument) -> None:
        """Galbraith 五维断言：framework_logic 提及五维英文键名 ≥3（R6/D10）"""
        framework_logic = (SKILLS_ROOT / SLUG / "references" / "framework_logic.md").read_text(encoding="utf-8")
        dimension_keys = ("org_structure", "strategy", "processes", "rewards", "people")
        mentioned = [key for key in dimension_keys if key in framework_logic]
        assert len(mentioned) >= 3, f"framework_logic 提及五维英文键名不足 3 个（实际 {mentioned}）"

    def test_root_key_name_semantics_documented(self, document: SkillDocument) -> None:
        """org_structure 名实注记（D10）：历史根键承载 Galbraith Star 全五维的说明在位"""
        framework_logic = (SKILLS_ROOT / SLUG / "references" / "framework_logic.md").read_text(encoding="utf-8")
        assert "历史根键" in document.body or "历史根键" in framework_logic, "缺少 org_structure 历史根键名实注记"
        assert "Galbraith" in document.body or "Galbraith" in framework_logic, "缺少 Galbraith Star Model 表述"


class TestCrossConsistency:
    """[C] 跨循环一致性（空集语义——SOP 标记 == 声明 == ∅）"""

    def test_no_markers_in_sop(self, document: SkillDocument) -> None:
        """纯内部型 SOP 引导代码零 $DATA_SOURCE 标记（空集语义双向守护）"""
        assert_cross_consistency(SLUG, document)


class TestTemplateAlignment:
    """[D] 模板字段 ↔ input_schema 叶子键双向对应 + 示例三方一致"""

    def test_template_fields_match_schema_leaf_keys(self, document: SkillDocument) -> None:
        """采集模板字段 == input_schema 7 叶子（单分区 org_structure）"""
        assert_template_schema_alignment(SLUG, document)

    def test_example_threeway_consistency(self, document: SkillDocument) -> None:
        """示例三方一致（R7）：模板示例行 ↔ SKILL.md §8 JSON 同文本同分值"""
        template = (SKILLS_ROOT / SLUG / "templates" / "org_star_model_assessment.md").read_text(encoding="utf-8")
        anchors = (SKILLS_ROOT / SLUG / "references" / "scoring_anchors.md").read_text(encoding="utf-8")
        # 抽查锚点：同一汇报线条目在模板、§8、scoring_anchors 三处以同分值出现
        witness = "区域总经理"
        assert witness in template, "模板示例缺少锚点见证条目（区域总经理）"
        assert witness in document.body, "SKILL.md §8 示例缺少锚点见证条目（区域总经理）"
        assert witness in anchors, "scoring_anchors 锚点示例缺少见证条目（区域总经理）"
        template_score = _extract_score(template, witness)
        body_score = _extract_score(document.body, witness)
        assert template_score == body_score, f"模板与 §8 见证条目分值不一致: {template_score} != {body_score}"


def _extract_score(text: str, witness: str) -> str | None:
    """提取见证条目所在行的「N —— 」分值前缀（三方一致比对用）。

    兼容模板表格行（| 字段 | 5 —— 描述 |）与 §8 JSON 行（"5 —— 描述"）两种形态，
    取分隔符前缀中最后一个独立整数。
    """
    for line in text.splitlines():
        if witness in line and "——" in line:
            prefix = line.split("——", 1)[0]
            matches = re.findall(r"\d+", prefix)
            if matches:
                return str(matches[-1])
    return None
