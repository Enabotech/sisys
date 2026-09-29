"""Story 4.1e Task 8: gantt-chart Skill 成熟化单元测试（结构型 + 时长编码 CPM）

TDD 循环覆盖（AC-1 / AC-2 / AC-3）：
- [A] frontmatter 声明契约：data_sources == ()（纯内部型一等不变量，D1）
      + IO Schema 契约（yaml 逐字相等）+ domain catalog 兼容（required 零删除）
- [B] SOP 成熟化：9 章节 / input_examples 非 placeholder / ≤500 行 / 失败处理
      双关键词（207 + INSUFFICIENT_DATA——D3）/ 结构型三件套 + references 内容锚点 /
      时长编码与归一基准 + 里程碑编码 + CPM 前推后推 + 负向触发分工
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == 声明集合 == ∅（空集语义）
- [D] 模板字段 ↔ input_schema 叶子键双向对应（4 叶子 + project_plan 单分区 +
      结构型第三段）+ 正则三方同文本（SKILL.md ↔ validation_rules）

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

SLUG = "gantt-chart"

# 时长格式正则（数据契约表钉死——与 yaml description / validation_rules / 模板同文本）
DURATION_PATTERN = r"^\d+ *[天周月]$"


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 gantt-chart 的 L2 SkillDocument"""
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
    """[B] SOP 内容成熟化（9 章节 + 结构型三件套 + 内容锚点 + 时长编码/CPM 语义）"""

    def test_sop_sections_and_resources(self, document: SkillDocument) -> None:
        """9 章节完备 + input_examples 非 placeholder + ≤500 行 + 分型三件套 + 模板齐备"""
        assert_sop_maturity(SLUG, document)

    def test_reference_content_anchors(self, document: SkillDocument) -> None:
        """references 内容要素字面锚点（编号步骤 + 英文键名 + 逐条规则 + 关键字 + 工作坊三要素）"""
        assert_reference_content_anchors(SLUG, document)

    def test_failure_keywords_documented(self, document: SkillDocument) -> None:
        """失败处理双关键词显式断言（207 标记误用守护 + INSUFFICIENT_DATA 缺数据引导——D3）"""
        failure_section = document.body.split("失败处理", 1)[-1]
        assert "207" in failure_section, "失败处理章节缺少 207 标记误用守护说明"
        assert "INSUFFICIENT_DATA" in failure_section, "失败处理章节缺少 INSUFFICIENT_DATA 数据缺口引导"

    def test_duration_coding_convention(self, document: SkillDocument) -> None:
        """时长编码断言（D10）：正则表述 + 归一基准（周＝5 工作日 / 月＝20 工作日）入 body"""
        assert DURATION_PATTERN in document.body, "§5/§6 缺少时长格式正则表述 ^\\d+ *[天周月]$"
        assert "个月" in document.body and "禁" in document.body, "缺少「禁『个月』与英文单位」约束说明"
        assert "5 工作日" in document.body, "缺少周归一基准（周＝5 工作日）说明"
        assert "20 工作日" in document.body, "缺少月归一基准（月＝20 工作日）说明"

    def test_milestone_encoding_documented(self, document: SkillDocument) -> None:
        """里程碑输入编码（R2-8）：durations 值「0 天」零时长任务即里程碑（ES=EF）"""
        assert "0 天" in document.body, "缺少里程碑编码说明（durations 值「0 天」）"

    def test_cpm_semantics_documented(self, document: SkillDocument) -> None:
        """CPM 断言：前推/后推（ES/EF/LS/LF）+ 零浮动关键路径语义入 body 或 validation_rules"""
        validation_rules = (SKILLS_ROOT / SLUG / "references" / "validation_rules.md").read_text(encoding="utf-8")
        corpus = document.body + validation_rules
        assert "ES/EF" in corpus and "LS/LF" in corpus, "缺少前推/后推（ES/EF 与 LS/LF）表述"
        assert "零浮动" in corpus, "缺少零浮动关键路径语义（LS-ES=0 链）"
        assert "CPM" in corpus, "缺少 CPM 关键字"

    def test_negative_trigger_dependency_graph(self, document: SkillDocument) -> None:
        """负向触发分工（D13）：§2 含 dependency-graph 字面串（纯拓扑 vs 含时间排程双向闭环）"""
        section = document.body.split("负向触发", 1)[-1].split("输入字段", 1)[0]
        assert "dependency-graph" in section, "§2 负向触发未指向 dependency-graph（分工跳转缺失）"

    def test_duration_pattern_threeway_consistency(self, document: SkillDocument) -> None:
        """正则三方同文本抽查（R7）：时长正则字面串在 SKILL.md body 与 validation_rules 同现"""
        validation_rules = (SKILLS_ROOT / SLUG / "references" / "validation_rules.md").read_text(encoding="utf-8")
        assert DURATION_PATTERN in validation_rules, "validation_rules 缺少时长格式正则（与 SKILL.md 同文本）"


class TestCrossConsistency:
    """[C] 跨循环一致性（空集语义——SOP 标记 == 声明 == ∅）"""

    def test_no_markers_in_sop(self, document: SkillDocument) -> None:
        """纯内部型 SOP 引导代码零 $DATA_SOURCE 标记（空集语义双向守护）"""
        assert_cross_consistency(SLUG, document)


class TestTemplateAlignment:
    """[D] 模板字段 ↔ input_schema 叶子键双向对应（4 叶子 + 单分区 + 结构型第三段）"""

    def test_template_fields_match_schema_leaf_keys(self, document: SkillDocument) -> None:
        """采集模板字段 == input_schema 4 叶子（tasks/dependencies/durations/resources）"""
        assert_template_schema_alignment(SLUG, document)

    def test_template_milestone_example_present(self, document: SkillDocument) -> None:
        """模板 durations 示例含「0 天」里程碑条目（采集端-解析端双端验证——4-1d R3 教训）"""
        template = (SKILLS_ROOT / SLUG / "templates" / "gantt_project_plan.md").read_text(encoding="utf-8")
        assert "0 天" in template, "模板 durations 示例缺少「0 天」里程碑条目（编码可采集性）"
        assert DURATION_PATTERN in template, "模板校验规则段缺少时长格式正则表述（三方同文本）"
