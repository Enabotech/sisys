"""Story 4.1c Task 2: pestel-analysis Skill 成熟化单元测试

TDD 循环覆盖（AC-1 / AC-3）：
- [A] frontmatter 声明契约：data_sources 全字段 == SSOT 6 源集合 + IO Schema 契约
- [B] SOP 成熟化：必备章节 / input_examples 非 placeholder / ≤500 行 / references+templates
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == frontmatter 声明集合（双向）
- 既有资产整合：references/scoring_matrix.json + scripts/aggregate_scores.py 保留并被 SOP 引用
- 23 Skills 全量解析回归 + 7 个非目标 Skill data_sources 空 tuple 不变量
  （4-1d Task 1.4 预调整：10 个混合数据型 Skill 移出非目标清单——4-1d 声明守护
  由 skill_mixed_data_contracts.py 承载，此处仅守护 4-1e 目标）

真实加载真实 SKILL.md（InMemorySkillLoader，范本 test_skills_loader.py），禁止 mock。
"""

from __future__ import annotations

import pytest

from src.application.ports.skill_loader import SkillDocument
from src.application.skills.loader import InMemorySkillLoader
from src.application.skills.skill_manifest import SLUG_TO_TOOL_ID
from tests.unit.application.skills.skill_data_collection_contracts import (
    SKILLS_ROOT,
    assert_cross_consistency,
    assert_data_sources_contract,
    assert_io_schema_contract,
    assert_sop_maturity,
)
from tests.unit.application.skills.skill_framework_contracts import NO_EXTERNAL_SOURCE_SLUGS

SLUG = "pestel-analysis"

# 无外部源型 Skill（23 全量 − 4-1c 声明源 − 4-1d 声明源，派生自 4-1e 契约库
# NO_EXTERNAL_SOURCE_SLUGS——D2 收敛，字面清单零复制）：data_sources 恒空不变量
NON_TARGET_SLUGS: tuple[str, ...] = NO_EXTERNAL_SOURCE_SLUGS


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 pestel-analysis 的 L2 SkillDocument"""
    loader = InMemorySkillLoader()
    return await loader.load_sop(SLUG)


class TestFrontmatterDataSources:
    """[A] frontmatter data_sources 白名单声明契约"""

    async def test_data_sources_match_ssot(self, document: SkillDocument) -> None:
        assert_data_sources_contract(SLUG, document.frontmatter)

    async def test_io_schema_match_contract(self, document: SkillDocument) -> None:
        assert_io_schema_contract(SLUG, document.frontmatter)


class TestSopMaturity:
    """[B] SOP 内容成熟化"""

    async def test_sop_sections_and_resources(self, document: SkillDocument) -> None:
        assert_sop_maturity(SLUG, document)

    async def test_existing_assets_preserved_and_referenced(self, document: SkillDocument) -> None:
        """既有资产整合：scoring_matrix.json + aggregate_scores.py 保留且被新 SOP 引用"""
        skill_dir = SKILLS_ROOT / SLUG
        assert (skill_dir / "references" / "scoring_matrix.json").is_file()
        assert (skill_dir / "scripts" / "aggregate_scores.py").is_file()
        assert "scoring_matrix.json" in document.body
        assert "aggregate_scores.py" in document.body


class TestCrossConsistency:
    """[C] 跨循环一致性（白名单 ↔ SOP 标记双向断言）"""

    async def test_markers_match_declared_sources(self, document: SkillDocument) -> None:
        assert_cross_consistency(SLUG, document)


class TestAllSkillsRegression:
    """23 Skills 全量解析回归 + 7 个非目标 Skill 空 tuple 不变量（AC-1；4-1d Task 1.4 预调整）"""

    async def test_all_23_skills_parse_regression(self) -> None:
        """23 Skills 全量解析回归（R1-F6 名实恢复：枚举源改 SLUG_TO_TOOL_ID 生产 SSOT——
        NON_TARGET_SLUGS 缩水不再静默缩减覆盖面，新 Story 成熟化即自动纳入回归）。"""
        loader = InMemorySkillLoader()
        for slug in SLUG_TO_TOOL_ID:
            document = await loader.load_sop(slug)
            assert document.frontmatter.slug == slug
            assert isinstance(document.frontmatter.data_sources, tuple)

    async def test_non_target_skills_empty_data_sources(self) -> None:
        """无外部源型 Skill data_sources 恒空不变量（纯内部框架型分类学守护——D2）。"""
        loader = InMemorySkillLoader()
        for slug in NON_TARGET_SLUGS:
            document = await loader.load_sop(slug)
            assert document.frontmatter.data_sources == (), f"无外部源型 Skill {slug} 的 data_sources 恒空不变量被破坏"
