"""Story 4.1d Task 2: swot-tows Skill 成熟化单元测试（Task 2-11 实施范本）

TDD 循环覆盖（AC-1 / AC-2 / AC-3）：
- [A] frontmatter 声明契约：data_sources 全字段 == SSOT 2 源（newsapi+tavily 双敏感）
      + IO Schema 契约（yaml 逐字相等）+ domain catalog 兼容（required 零删除）
- [B] SOP 成熟化：9 章节 / input_examples 非 placeholder / ≤500 行 /
      references 三件套（data_fusion/scoring_anchors/workshop_guide）+ templates
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == frontmatter 声明集合（双向）
- [D] 模板字段 ↔ input_schema 叶子键双向对应（嵌套展开：四象限叶子键 +
      四段式微格式 + 必填标注一致）

真实加载真实 SKILL.md（InMemorySkillLoader，范本 4-1c test_disruptive_innovation_
data_collection.py），禁止 mock。
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

SLUG = "swot-tows"


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 swot-tows 的 L2 SkillDocument"""
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
    """[B] SOP 内容成熟化（9 章节 + 三件套 + 模板 + 行数 + Key 敏感降级话术）"""

    def test_sop_sections_and_resources(self, document: SkillDocument) -> None:
        """9 章节完备 + input_examples 非 placeholder + ≤500 行 + references/templates 齐备"""
        assert_sop_maturity(SLUG, document)

    def test_dual_key_sensitive_degradation_documented(self, document: SkillDocument) -> None:
        """双 Key 敏感源（newsapi+tavily）降级话术：未注册 + 数据缺口（内部数据继续分析）"""
        failure_section = document.body.split("失败处理", 1)[-1]
        assert "未注册" in failure_section, "缺少 Key 缺失「未注册」降级话术"
        assert "数据缺口" in failure_section, "缺少「数据缺口」标注话术"


class TestCrossConsistency:
    """[C] 跨循环一致性（SOP 标记 ↔ frontmatter 声明双向）"""

    def test_markers_match_declared_sources(self, document: SkillDocument) -> None:
        """SOP body $DATA_SOURCE 标记 name 集合 == frontmatter 声明集合"""
        assert_cross_consistency(SLUG, document)


class TestTemplateAlignment:
    """[D] 模板字段 ↔ input_schema 叶子键双向对应（AC-3 核心）"""

    def test_template_fields_match_schema_leaf_keys(self, document: SkillDocument) -> None:
        """采集模板字段 == input_schema 叶子键（strengths/weaknesses/opportunities/threats）"""
        assert_template_schema_alignment(SLUG, document)
