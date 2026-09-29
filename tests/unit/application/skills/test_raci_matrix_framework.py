"""Story 4.1e Task 7: raci-matrix Skill 成熟化单元测试（结构型 + 双层编码）

TDD 循环覆盖（AC-1 / AC-2 / AC-3）：
- [A] frontmatter 声明契约：data_sources == ()（纯内部型一等不变量，D1）
      + IO Schema 契约（yaml 逐字相等）+ domain catalog 兼容（required 零删除）
- [B] SOP 成熟化：9 章节 / input_examples 非 placeholder / ≤500 行 / 失败处理
      双关键词（207 + INSUFFICIENT_DATA——D3）/ 结构型三件套 + references 内容锚点 /
      双层编码声明（外层键为任务名，R2-3）+ RACI 规则集（恰 1 A 硬 + ≥1 R 软）
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == 声明集合 == ∅（空集语义）
- [D] 模板字段 ↔ input_schema 叶子键双向对应（roles/tasks/assignments 三叶子 +
      单分区标题）+ 矩阵速查表位于采集表格区外（提取器不污染，第五段承载）

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

SLUG = "raci-matrix"

# 字母组合正则的 16 合法形态（4 单字母 + 12 有序双字母——显式枚举，与 validation_rules 同文本）
RACI_COMBO_PATTERN = r"^(R|A|C|I|R/A|A/R|R/C|C/R|R/I|I/R|A/C|C/A|A/I|I/A|C/I|I/C)$"
# 全部不重复双字母组合（P(4,2)=12——行为锁参数化全集）
_VALID_DOUBLE_COMBOS = ("R/A", "A/R", "R/C", "C/R", "R/I", "I/R", "A/C", "C/A", "A/I", "I/A", "C/I", "I/C")


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 raci-matrix 的 L2 SkillDocument"""
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
    """[B] SOP 内容成熟化（9 章节 + 结构型三件套 + 内容锚点 + 双层编码 + RACI 规则集）"""

    def test_sop_sections_and_resources(self, document: SkillDocument) -> None:
        """9 章节完备 + input_examples 非 placeholder + ≤500 行 + 分型三件套 + 模板齐备"""
        assert_sop_maturity(SLUG, document)

    def test_reference_content_anchors(self, document: SkillDocument) -> None:
        """references 内容要素字面锚点（编号步骤 + 英文键名 + 逐条规则 + RACI 关键字）"""
        assert_reference_content_anchors(SLUG, document)

    def test_failure_keywords_documented(self, document: SkillDocument) -> None:
        """失败处理双关键词显式断言（207 标记误用守护 + INSUFFICIENT_DATA 缺数据引导——D3）"""
        failure_section = document.body.split("失败处理", 1)[-1]
        assert "207" in failure_section, "失败处理章节缺少 207 标记误用守护说明"
        assert "INSUFFICIENT_DATA" in failure_section, "失败处理章节缺少 INSUFFICIENT_DATA 数据缺口引导"

    def test_dual_layer_encoding_declared(self, document: SkillDocument) -> None:
        """双层编码（R2-3）：外层键为任务名（per-task 规则计算粒度）+ 全角化记法声明"""
        body = document.body
        assert "任务名→角色名＝RACI 字母组合" in body, "缺少双层编码全角化记法（任务名→角色名＝RACI 字母组合）"
        assert "外层键为任务名" in body, "缺少「外层键为任务名」粒度说明（恰 1 A 规则计算依据）"

    def test_raci_rules_documented(self, document: SkillDocument) -> None:
        """RACI 规则集：恰 1 A 硬规则 + ≥1 R 软规则 + A/R 计为已承担 R + conflicts 出口"""
        rules = (SKILLS_ROOT / SLUG / "references" / "validation_rules.md").read_text(encoding="utf-8")
        combined = document.body + "\n" + rules
        assert "恰 1" in combined, "缺少「恰 1 个 A」硬规则（per-task 单点问责）"
        assert "≥1" in combined, "缺少「≥1 个 R」软规则"
        assert "A/R" in combined, "缺少斜线组合形态示例（A/R）"
        assert "已承担" in combined, "缺少「A/R 计为已承担 R」说明（业界兼任惯例）"
        assert "conflicts" in combined, "缺少违规经 raci_matrix.conflicts 结构化呈现出口"

    def test_soft_rule_exit_conflicts_locked(self, document: SkillDocument) -> None:
        """软规则出口守护（R1-F1）：规则 2 声明汇入 conflicts，不得回归 suggestions 出口"""
        rules = (SKILLS_ROOT / SLUG / "references" / "validation_rules.md").read_text(encoding="utf-8")
        rule2 = rules.split("规则 2", 1)[1].split("规则 3", 1)[0]
        assert "conflicts" in rule2, "规则 2 软规则违规出口必须为 conflicts（R1-F1 统一裁定）"
        assert "suggestions" not in rule2, "规则 2 不得回归 suggestions 出口（R1-F1 矛盾形态）"

    def test_combo_regex_enumeration_locked(self, document: SkillDocument) -> None:
        """字母组合正则形态锁定（R1-F2 守护）：16 形态显式枚举，拒绝重复字母与三字母组合"""
        rules = (SKILLS_ROOT / SLUG / "references" / "validation_rules.md").read_text(encoding="utf-8")
        assert RACI_COMBO_PATTERN in rules, "validation_rules 缺少 16 形态显式枚举正则（R1-F2 守护——字面锁）"
        for letter in ("R", "A", "C", "I"):
            assert re.fullmatch(RACI_COMBO_PATTERN, letter), f"正则应接受单字母 {letter}"
        for combo in _VALID_DOUBLE_COMBOS:
            assert re.fullmatch(RACI_COMBO_PATTERN, combo), f"正则应接受不重复双字母组合 {combo}"
        assert re.fullmatch(RACI_COMBO_PATTERN, "A/A") is None, "正则不得放行重复字母（A/A——文字规则明禁）"
        assert re.fullmatch(RACI_COMBO_PATTERN, "R/A/C") is None, "正则不得放行三字母组合"
        assert re.fullmatch(RACI_COMBO_PATTERN, "X") is None, "正则不得放行非法字母"

    def test_assignment_slash_combination_in_examples(self, document: SkillDocument) -> None:
        """§8 示例含斜线组合（A/R）形态的 assignments 双层 JSON"""
        examples_section = document.body.split("input_examples", 1)[-1]
        assert "A/R" in examples_section, "§8 assignments 示例缺少斜线组合（A/R）条目"


class TestCrossConsistency:
    """[C] 跨循环一致性（空集语义——SOP 标记 == 声明 == ∅）"""

    def test_no_markers_in_sop(self, document: SkillDocument) -> None:
        """纯内部型 SOP 引导代码零 $DATA_SOURCE 标记（空集语义双向守护）"""
        assert_cross_consistency(SLUG, document)


class TestTemplateAlignment:
    """[D] 模板字段 ↔ input_schema 叶子键双向对应 + 矩阵速查段位置守护"""

    def test_template_fields_match_schema_leaf_keys(self, document: SkillDocument) -> None:
        """采集模板字段 == input_schema 3 叶子（roles/tasks/assignments）+ 单分区标题"""
        assert_template_schema_alignment(SLUG, document)

    def test_matrix_quick_reference_outside_collection_section(self, document: SkillDocument) -> None:
        """矩阵速查表位于采集表格区之外（第五段承载——提取器比对集不污染）"""
        template_path = SKILLS_ROOT / SLUG / "templates" / "raci_roles_tasks.md"
        template = template_path.read_text(encoding="utf-8")
        assert "## RACI 矩阵速查" in template, "模板缺少「## RACI 矩阵速查」第五段"
        # 速查段必须在采集表格区之后（## 校验规则 与 ## 数据缺口登记 均终止采集区）
        collection_start = template.find("## 采集表格")
        matrix_pos = template.find("## RACI 矩阵速查")
        third_section_pos = template.find("## 校验规则")
        assert collection_start != -1 and third_section_pos != -1, "四段式结构缺失（前序断言已覆盖）"
        assert matrix_pos > third_section_pos, "矩阵速查段必须位于采集表格区之外（第三段之后）"
        # 速查矩阵表头含角色列形态（任务\角色 矩阵——工作坊现场承载）
        matrix_section = template.split("## RACI 矩阵速查", 1)[-1]
        assert "任务" in matrix_section.splitlines()[0] or "任务" in matrix_section[:200], "矩阵速查段缺少任务×角色矩阵表头说明"
