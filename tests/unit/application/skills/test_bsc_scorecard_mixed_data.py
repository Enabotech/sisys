"""Story 4.1d Task: bsc-scorecard Skill 成熟化单元测试（免 Key + china-nbs crawler 组）

TDD 循环覆盖（AC-1 / AC-2 / AC-3）：
- [A] frontmatter 声明契约：data_sources 全字段 == SSOT 2 源（china-nbs+world-bank 免 Key）
      + IO Schema 契约（yaml 逐字相等）+ domain catalog 兼容（required 零删除）
- [B] SOP 成熟化：9 章节 / input_examples 非 placeholder / ≤500 行 /
      references 三件套（data_fusion/scoring_anchors/workshop_guide）+ templates；
      china-nbs crawler 不可用降级话术 + INSUFFICIENT_DATA 兜底
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == frontmatter 声明集合（双向）
- [D] 模板字段 ↔ input_schema 叶子键双向对应（嵌套展开：四维度叶子键 +
      四段式微格式 + 必填标注一致）

真实加载真实 SKILL.md（InMemorySkillLoader，范本 test_swot_tows_mixed_data.py），
禁止 mock。
"""

from __future__ import annotations

import pytest

from src.application.ports.skill_loader import SkillDocument
from src.application.skills.loader import InMemorySkillLoader
from src.application.skills.skill_manifest import TOOL_ID_TO_SLUG
from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG
from tests.unit.application.skills.skill_mixed_data_contracts import (
    assert_cross_consistency,
    assert_data_sources_contract,
    assert_io_schema_contract,
    assert_sop_maturity,
    assert_template_schema_alignment,
)

SLUG = "bsc-scorecard"


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 bsc-scorecard 的 L2 SkillDocument"""
    loader = InMemorySkillLoader()
    return await loader.load_sop(SLUG)


class TestFrontmatterDataSources:
    """[A] frontmatter data_sources 白名单声明契约 + IO Schema + catalog 兼容"""

    def test_data_sources_match_ssot(self, document: SkillDocument) -> None:
        """data_sources 全字段（name/url/api_type/ttl/required_fields）== SSOT 2 源"""
        assert_data_sources_contract(SLUG, document.frontmatter)

    def test_io_schema_match_contract(self, document: SkillDocument) -> None:
        """input_schema/output_schema 与 IO 契约 yaml 逐字相等"""
        assert_io_schema_contract(SLUG, document.frontmatter)

    def test_domain_catalog_required_preserved(self, document: SkillDocument) -> None:
        """domain catalog 既有 required/properties 零删除（frontmatter 增强兼容约束）"""
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
    """[B] SOP 内容成熟化（9 章节 + 三件套 + 模板 + 行数 + crawler 降级话术）"""

    def test_sop_sections_and_resources(self, document: SkillDocument) -> None:
        """9 章节完备 + input_examples 非 placeholder + ≤500 行 + references/templates 齐备"""
        assert_sop_maturity(SLUG, document)

    def test_crawler_degradation_documented(self, document: SkillDocument) -> None:
        """china-nbs crawler 不可用降级话术 + 内部数据不足 INSUFFICIENT_DATA 兜底"""
        failure_section = document.body.split("失败处理", 1)[-1]
        assert "crawler" in failure_section, "缺少 china-nbs crawler 不可用降级话术"
        assert "INSUFFICIENT_DATA" in failure_section, "缺少内部数据不足 INSUFFICIENT_DATA 降级话术"


class TestCrossConsistency:
    """[C] 跨循环一致性（SOP 标记 ↔ frontmatter 声明双向）"""

    def test_markers_match_declared_sources(self, document: SkillDocument) -> None:
        """SOP body $DATA_SOURCE 标记 name 集合 == frontmatter 声明集合"""
        assert_cross_consistency(SLUG, document)


class TestTemplateAlignment:
    """[D] 模板字段 ↔ input_schema 叶子键双向对应（AC-3 核心）"""

    def test_template_fields_match_schema_leaf_keys(self, document: SkillDocument) -> None:
        """采集模板字段 == input_schema 叶子键（财务/客户/流程/学习四维度目标）"""
        assert_template_schema_alignment(SLUG, document)
