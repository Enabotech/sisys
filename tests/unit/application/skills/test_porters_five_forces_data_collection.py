"""Story 4.1c Task 3: porters-five-forces Skill 成熟化单元测试

TDD 循环覆盖（AC-1 / AC-3）：
- [A] frontmatter 声明契约：data_sources 全字段 == SSOT 3 源集合（newsapi/world-bank/eurostat）+ IO Schema 契约
- [B] SOP 成熟化：必备章节 / input_examples 非 placeholder / ≤500 行 / references+templates
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == frontmatter 声明集合（双向）

真实加载真实 SKILL.md（InMemorySkillLoader，范本 test_skills_loader.py），禁止 mock。
23 Skills 全量解析回归集中在 test_pestel_analysis_data_collection.py（TestAllSkillsRegression），本文件不重复。
"""

from __future__ import annotations

import pytest

from src.application.ports.skill_loader import SkillDocument
from src.application.skills.loader import InMemorySkillLoader
from tests.unit.application.skills.skill_data_collection_contracts import (
    assert_cross_consistency,
    assert_data_sources_contract,
    assert_io_schema_contract,
    assert_sop_maturity,
)

SLUG = "porters-five-forces"


@pytest.fixture
async def document() -> SkillDocument:
    """真实加载 porters-five-forces 的 L2 SkillDocument"""
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


class TestCrossConsistency:
    """[C] 跨循环一致性（白名单 ↔ SOP 标记双向断言）"""

    async def test_markers_match_declared_sources(self, document: SkillDocument) -> None:
        assert_cross_consistency(SLUG, document)
