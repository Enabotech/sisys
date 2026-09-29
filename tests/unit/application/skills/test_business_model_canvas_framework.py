"""Story 4.1e Task 3: business-model-canvas Skill 成熟化单元测试（存量资产整合范本）

TDD 循环覆盖（AC-1 / AC-2 / AC-3）：
- [A] frontmatter 声明契约：data_sources == ()（纯内部型一等不变量，D1）
      + IO Schema 契约（yaml 逐字相等）+ domain catalog 兼容（required 零删除）
- [B] SOP 成熟化：9 章节 / input_examples 非 placeholder / ≤500 行 / 失败处理
      双关键词（207 + INSUFFICIENT_DATA——D3）/ 评分型三件套 + references 内容锚点 /
      编码规范四方同步抽查（块成熟度分值 + 解析锚点）+ 存量资产保留引用（D7）
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == 声明集合 == ∅（空集语义）
- [D] 模板字段 ↔ input_schema 叶子键双向对应（9 叶子单分区 + 评分型第三段）+
      示例三方一致（模板 ↔ §8 ↔ scoring_anchors）
- D7 命名收敛：canvas_template.json / validate_canvas.py 收敛为 key_partnerships
  （catalog 锚定名），旧名 key_partners 词边界零残留

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

SLUG = "business-model-canvas"


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 business-model-canvas 的 L2 SkillDocument"""
    loader = InMemorySkillLoader()
    return await loader.load_sop(SLUG)


class TestFrontmatterDeclaration:
    """[A] frontmatter 空声明一等不变量 + IO Schema 契约 + catalog 兼容"""

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
        # catalog 锚定名：business_model 容器内 9 键（含 key_partnerships）零删除
        catalog_bm_keys = set(catalog_input["properties"]["business_model"]["properties"])
        actual_bm_keys = set(actual_input["properties"]["business_model"]["properties"])
        assert catalog_bm_keys <= actual_bm_keys, "catalog business_model 容器内既有叶子键被删除"


class TestSopMaturity:
    """[B] SOP 内容成熟化（9 章节 + 评分型三件套 + 内容锚点 + 编码规范四方同步）"""

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
        """编码规范四方同步抽查（D10）：块成熟度分值语义 + 解析锚点在 SOP 内文档化"""
        body = document.body
        assert "块成熟度分值" in body, "§3/§5 缺少块成熟度分值（1-5）编码语义"
        assert "首个『 —— 』" in body, "缺少确定性解析锚点半句（首个『 —— 』之前前缀中的独立 1-5 整数）"
        examples_section = body.split("input_examples", 1)[-1]
        assert " —— " in examples_section, "§8 示例缺少「分值 —— 描述」微格式条目"

    def test_output_aggregation_documented(self, document: SkillDocument) -> None:
        """输出聚合语义（R2-7）：dimension_scores 九块聚合 + consistency_analysis 双侧对照文档化"""
        body = document.body
        assert "dimension_scores" in body, "缺少 dimension_scores 九块成熟度聚合说明"
        assert "consistency_analysis" in body, "缺少 consistency_analysis 块间一致性说明"
        assert "value_propositions" in body and "customer_segments" in body, (
            "缺少核心匹配 value_propositions↔customer_segments 表述"
        )
        assert "cost_structure" in body and "revenue_streams" in body, "缺少成本-收入对称 cost_structure↔revenue_streams 表述"

    def test_legacy_assets_referenced_in_sop(self, document: SkillDocument) -> None:
        """存量资产保留并被 SOP 引用（D7/pestel 先例）：validate_canvas.py + canvas_template.json"""
        body = document.body
        assert "validate_canvas.py" in body, "§9 References 未引用存量 scripts/validate_canvas.py 九块校验器"
        assert "canvas_template.json" in body, "§9 References 未引用存量 references/canvas_template.json 模板基型"

    def test_framework_logic_nine_blocks_linkage(self, document: SkillDocument) -> None:
        """九块联动系统化思考（framework_logic）：核心匹配 + 成本-收入对称双侧对照"""
        framework_logic = (SKILLS_ROOT / SLUG / "references" / "framework_logic.md").read_text(encoding="utf-8")
        assert "value_propositions" in framework_logic and "customer_segments" in framework_logic, (
            "framework_logic 缺少核心匹配 value_propositions↔customer_segments"
        )
        assert "cost_structure" in framework_logic and "revenue_streams" in framework_logic, (
            "framework_logic 缺少成本-收入对称 cost_structure↔revenue_streams"
        )


class TestCrossConsistency:
    """[C] 跨循环一致性（空集语义——SOP 标记 == 声明 == ∅）"""

    def test_no_markers_in_sop(self, document: SkillDocument) -> None:
        """纯内部型 SOP 引导代码零 $DATA_SOURCE 标记（空集语义双向守护）"""
        assert_cross_consistency(SLUG, document)


class TestTemplateAlignment:
    """[D] 模板字段 ↔ input_schema 叶子键双向对应 + 示例三方一致"""

    def test_template_fields_match_schema_leaf_keys(self, document: SkillDocument) -> None:
        """采集模板字段 == input_schema 9 叶子（九宫格块键 + cost_structure 自由 object 叶子）"""
        assert_template_schema_alignment(SLUG, document)

    def test_example_threeway_consistency(self, document: SkillDocument) -> None:
        """示例三方一致（R7）：模板示例行 ↔ SKILL.md §8 JSON 同文本同分值"""
        template = (SKILLS_ROOT / SLUG / "templates" / "bmc_nine_blocks_canvas.md").read_text(encoding="utf-8")
        anchors = (SKILLS_ROOT / SLUG / "references" / "scoring_anchors.md").read_text(encoding="utf-8")
        # 抽查锚点：同一伙伴示例在模板、§8、scoring_anchors 三处以同分值出现
        witness = "宁德时代"
        assert witness in template, "模板示例缺少锚点见证条目（宁德时代）"
        assert witness in document.body, "SKILL.md §8 示例缺少锚点见证条目（宁德时代）"
        assert witness in anchors, "scoring_anchors 锚点示例缺少见证条目（宁德时代）"
        template_score = _extract_score(template, witness)
        body_score = _extract_score(document.body, witness)
        assert template_score == body_score, f"模板与 §8 见证条目分值不一致: {template_score} != {body_score}"


class TestD7NamingConvergence:
    """D7 命名收敛：canvas_template.json + validate_canvas.py 收敛 catalog 锚定名 key_partnerships"""

    def test_canvas_template_json_uses_key_partnerships(self) -> None:
        """canvas_template.json 块名 == key_partnerships（旧名 key_partners 词边界零残留）"""
        content = (SKILLS_ROOT / SLUG / "references" / "canvas_template.json").read_text(encoding="utf-8")
        assert '"key_partnerships"' in content, "canvas_template.json 未收敛为 key_partnerships"
        assert not re.search(r'"key_partners"', content), "canvas_template.json 残留旧名 key_partners"

    def test_validate_canvas_uses_key_partnerships(self) -> None:
        """validate_canvas.py 的 REQUIRED_BLOCKS == key_partnerships（词边界零残留）"""
        source = (SKILLS_ROOT / SLUG / "scripts" / "validate_canvas.py").read_text(encoding="utf-8")
        assert '"key_partnerships"' in source, "validate_canvas.py REQUIRED_BLOCKS 未收敛为 key_partnerships"
        assert not re.search(r'"key_partners"', source), "validate_canvas.py 残留旧名 key_partners"


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
