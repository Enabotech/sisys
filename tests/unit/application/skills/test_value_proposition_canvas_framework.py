"""Story 4.1e Task 2: value-proposition-canvas Skill 成熟化单元测试（Task 2-8 评分型范本）

TDD 循环覆盖（AC-1 / AC-2 / AC-3）：
- [A] frontmatter 声明契约：data_sources == ()（纯内部型一等不变量，D1）
      + IO Schema 契约（yaml 逐字相等）+ domain catalog 兼容（required 零删除）
- [B] SOP 成熟化：9 章节 / input_examples 非 placeholder / ≤500 行 / 失败处理
      双关键词（207 + INSUFFICIENT_DATA——D3）/ 评分型三件套 + references 内容锚点 /
      编码规范四方同步抽查（双侧分值语义 + 解析锚点）
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == 声明集合 == ∅（空集语义）
- [D] 模板字段 ↔ input_schema 叶子键双向对应（6 叶子 + 双分区标题 +
      评分型第三段）+ 示例三方一致（模板 ↔ §8 ↔ scoring_anchors）

真实加载真实 SKILL.md（InMemorySkillLoader，范本 4-1d test_swot_tows_mixed_data.py），禁止 mock。
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

SLUG = "value-proposition-canvas"


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 value-proposition-canvas 的 L2 SkillDocument"""
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
        """编码规范四方同步抽查（D10）：§3 输入字段表 + §8 示例均含双侧分值语义与解析锚点"""
        body = document.body
        assert "严重度" in body and "重要性" in body, "§3 缺少 customer 侧分值语义（严重度/重要性）"
        assert "匹配强度" in body, "§3 缺少 value 侧分值语义（匹配强度——挂 value_map 侧）"
        assert "首个『 —— 』" in body, "缺少确定性解析锚点半句（首个『 —— 』之前前缀中的独立 1-5 整数）"
        examples_section = body.split("input_examples", 1)[-1]
        assert " —— " in examples_section, "§8 示例缺少「分值 —— 描述」微格式条目"

    def test_fit_score_aggregation_documented(self, document: SkillDocument) -> None:
        """输出聚合语义（R2-7）：fit_score 木桶最小值原则在 SOP 中文档化"""
        assert "最小值" in document.body, "缺少 fit_score = 三对匹配分值最小值（木桶原则）说明"
        assert "木桶" in document.body, "缺少木桶原则表述"

    def test_jobs_analysis_startpoint(self, document: SkillDocument) -> None:
        """customer jobs 为分析起点（R1-18：jobs→pains→gains 序入 framework_logic）"""
        framework_logic = (SKILLS_ROOT / SLUG / "references" / "framework_logic.md").read_text(encoding="utf-8")
        assert "jobs" in framework_logic, "framework_logic 缺少 jobs 分析起点表述"
        assert "起点" in framework_logic, "framework_logic 缺少「分析起点」说明"


class TestCrossConsistency:
    """[C] 跨循环一致性（空集语义——SOP 标记 == 声明 == ∅）"""

    def test_no_markers_in_sop(self, document: SkillDocument) -> None:
        """纯内部型 SOP 引导代码零 $DATA_SOURCE 标记（空集语义双向守护）"""
        assert_cross_consistency(SLUG, document)


class TestTemplateAlignment:
    """[D] 模板字段 ↔ input_schema 叶子键双向对应 + 示例三方一致"""

    def test_template_fields_match_schema_leaf_keys(self, document: SkillDocument) -> None:
        """采集模板字段 == input_schema 6 叶子（pains/gains/jobs/products/pain_relievers/gain_creators）"""
        assert_template_schema_alignment(SLUG, document)

    def test_example_threeway_consistency(self, document: SkillDocument) -> None:
        """示例三方一致（R7）：模板示例行 ↔ SKILL.md §8 JSON 同文本同分值"""
        template = (SKILLS_ROOT / SLUG / "templates" / "vpc_canvas_matching.md").read_text(encoding="utf-8")
        anchors = (SKILLS_ROOT / SLUG / "references" / "scoring_anchors.md").read_text(encoding="utf-8")
        # 抽查锚点：同一痛点示例在模板、§8、scoring_anchors 三处以同分值出现
        witness = "充电等待"
        assert witness in template, "模板示例缺少锚点见证条目（充电等待）"
        assert witness in document.body, "SKILL.md §8 示例缺少锚点见证条目（充电等待）"
        assert witness in anchors, "scoring_anchors 锚点示例缺少见证条目（充电等待）"
        template_score = _extract_score(template, witness)
        body_score = _extract_score(document.body, witness)
        assert template_score == body_score, f"模板与 §8 见证条目分值不一致: {template_score} != {body_score}"

    def test_example_threeway_consistency_intersection(self, document: SkillDocument) -> None:
        """同文本同分值交集全量（R2 守护·R1-F3 bug 类防线）：§8 与模板全部同文本条目必同分"""
        template = (SKILLS_ROOT / SLUG / "templates" / "vpc_canvas_matching.md").read_text(encoding="utf-8")
        examples_section = document.body.split("input_examples", 1)[-1]
        template_scores = _scored_entries(template)
        body_scores = _scored_entries(examples_section)
        common = set(template_scores) & set(body_scores)
        assert len(common) >= 12, (
            f"§8 与模板同文本条目交集异常（{len(common)} < 12——单侧删改条目或提取器失效，请核对两侧示例条目）"
        )
        for desc in sorted(common):
            assert template_scores[desc] == body_scores[desc], (
                f"同文本条目分值不一致: {desc!r} 模板 {template_scores[desc]} vs §8 {body_scores[desc]}"
            )

    def test_customer_side_score_role_documented(self, document: SkillDocument) -> None:
        """客户侧分值职能守护（R1-F5）：「不参与 fit_score」排序依据职能显式声明"""
        framework_logic = (SKILLS_ROOT / SLUG / "references" / "framework_logic.md").read_text(encoding="utf-8")
        assert "不参与 fit_score" in framework_logic, "framework_logic 缺少客户侧分值「不参与 fit_score」职能声明（R1-F5）"


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


def _scored_entries(text: str) -> dict[str, str]:
    """提取全部「N —— 描述」条目为 {描述: 分值}（交集全量比对用）。

    全文匹配（同 JSON 行多条目逐一提取）；模板表格行在闭合 | 处截断（防依据列
    尾巴污染描述）、§8 JSON 行在闭合引号/方括号处截断。
    """
    entries: dict[str, str] = {}
    for match in re.finditer(r"(\d+)\s*——\s*([^\"|\[\]{}\n]+)", text):
        desc = match.group(2).strip().strip("，,").strip()
        if desc:
            entries.setdefault(desc, match.group(1))
    return entries
