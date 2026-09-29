"""Story 4.1e Task 6: dependency-graph Skill 成熟化单元测试（结构型 + 顶层 array 形态）

TDD 循环覆盖（AC-1 / AC-2 / AC-3）：
- [A] frontmatter 声明契约：data_sources == ()（纯内部型一等不变量，D1）
      + IO Schema 契约（yaml 逐字相等）+ domain catalog 兼容（required 零删除）
- [B] SOP 成熟化：9 章节 / input_examples 非 placeholder / ≤500 行 / 失败处理
      双关键词（207 + INSUFFICIENT_DATA——D3）/ 结构型三件套 + references 内容锚点 /
      依赖边编码语法（顿号分隔 + 任务名字符约束）
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == 声明集合 == ∅（空集语义）
- [D] 模板字段 ↔ input_schema 叶子键双向对应（task_list 顶层 array-of-objects——
      name/dependencies 两叶子 + task_list 分区标题承载 + 结构型第三段）

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

SLUG = "dependency-graph"


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 dependency-graph 的 L2 SkillDocument"""
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
    """[B] SOP 内容成熟化（9 章节 + 结构型三件套 + 内容锚点 + 依赖边编码）"""

    def test_sop_sections_and_resources(self, document: SkillDocument) -> None:
        """9 章节完备 + input_examples 非 placeholder + ≤500 行 + 分型三件套 + 模板齐备"""
        assert_sop_maturity(SLUG, document)

    def test_reference_content_anchors(self, document: SkillDocument) -> None:
        """references 内容要素字面锚点（编号步骤 + 英文键名 + 编号规则 + DAG 关键字）"""
        assert_reference_content_anchors(SLUG, document)

    def test_failure_keywords_documented(self, document: SkillDocument) -> None:
        """失败处理双关键词显式断言（207 标记误用守护 + INSUFFICIENT_DATA 缺数据引导——D3）"""
        failure_section = document.body.split("失败处理", 1)[-1]
        assert "207" in failure_section, "失败处理章节缺少 207 标记误用守护说明"
        assert "INSUFFICIENT_DATA" in failure_section, "失败处理章节缺少 INSUFFICIENT_DATA 数据缺口引导"

    def test_dependency_edge_coding_declared(self, document: SkillDocument) -> None:
        """依赖边编码语法声明（D10）：「任务名 ← 前置任务列表」+ 顿号分隔 + 任务名字符约束"""
        body = document.body
        assert "任务名 ← 前置任务列表" in body, "§3/§5 缺少依赖边语法「任务名 ← 前置任务列表」声明"
        assert "顿号" in body, "缺少模板行内前置列表顿号分隔说明"
        assert "「、」" in body and "「←」" in body, "缺少任务名禁含「、」与「←」字符约束声明"

    def test_negative_trigger_to_gantt(self, document: SkillDocument) -> None:
        """负向触发跳转（D13）：含时间排程 → gantt-chart（纯拓扑 vs 含时间分工，本侧单向）"""
        section = document.body.split("负向触发", 1)[-1]
        assert "gantt-chart" in section, "§2 负向触发未指向 gantt-chart（时间排程分工跳转缺失）"

    def test_critical_path_semantics_documented(self, document: SkillDocument) -> None:
        """critical_path 语义分工：跳数最长链的无时长结构代理（vs gantt-chart 真 CPM）"""
        assert "跳数最长链" in document.body, "body 缺少「跳数最长链」结构代理表述"
        validation_rules = (SKILLS_ROOT / SLUG / "references" / "validation_rules.md").read_text(encoding="utf-8")
        assert "跳数最长链" in validation_rules, "validation_rules 缺少关键路径结构代理规则表述"
        assert "gantt-chart" in validation_rules, "validation_rules 缺少与 gantt-chart 的 CPM 语义分工说明"


class TestCrossConsistency:
    """[C] 跨循环一致性（空集语义——SOP 标记 == 声明 == ∅）"""

    def test_no_markers_in_sop(self, document: SkillDocument) -> None:
        """纯内部型 SOP 引导代码零 $DATA_SOURCE 标记（空集语义双向守护）"""
        assert_cross_consistency(SLUG, document)


class TestTemplateAlignment:
    """[D] 模板字段 ↔ input_schema 叶子键双向对应（task_list 顶层 array 形态）"""

    def test_template_fields_match_schema_leaf_keys(self, document: SkillDocument) -> None:
        """采集模板字段 == input_schema 叶子（name/dependencies——task_list 分区标题承载顶层键）"""
        assert_template_schema_alignment(SLUG, document)

    def test_template_dependency_row_uses_delimiter(self, document: SkillDocument) -> None:
        """模板 dependencies 行值列以顿号分隔前置任务（依赖边编码模板行内形态——采集端可产性）"""
        from tests.unit.application.skills.skill_mixed_data_contracts import _collection_section

        template = (SKILLS_ROOT / SLUG / "templates" / "dependency_task_inventory.md").read_text(encoding="utf-8")
        collection = _collection_section(template)
        assert collection is not None, "模板缺少「采集表格」区"
        dependency_rows = [line for line in collection.splitlines() if line.strip().startswith("|") and "dependencies" in line]
        assert dependency_rows, "模板采集表格缺少 dependencies 字段行"
        assert any("、" in row for row in dependency_rows), (
            "dependencies 字段行值列缺少顿号分隔的前置任务列表形态（采集端-解析端双端验证——4-1d R3 教训）"
        )
