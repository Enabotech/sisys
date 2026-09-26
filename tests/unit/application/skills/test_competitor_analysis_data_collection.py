"""Story 4.1c Task 5: competitor-analysis Skill 成熟化单元测试

TDD 循环覆盖（AC-1 / AC-3）：
- [A] frontmatter 声明契约：data_sources 全字段 == SSOT 4 源集合（newsapi/uspto/tavily/china-nbs）+ IO Schema 契约
- [B] SOP 成熟化：必备章节 / input_examples 非 placeholder / ≤500 行 / references+templates
- [C] 跨循环一致性：SOP body $DATA_SOURCE 标记集合 == frontmatter 声明集合（双向）

真实加载真实 SKILL.md（InMemorySkillLoader，范本 test_skills_loader.py），禁止 mock。
"""

from __future__ import annotations

import pytest

from src.application.skills.loader import InMemorySkillLoader
from tests.unit.application.skills.skill_data_collection_contracts import (
    assert_cross_consistency,
    assert_data_sources_contract,
    assert_io_schema_contract,
    assert_sop_maturity,
)

SLUG = "competitor-analysis"


@pytest.fixture
async def document():  # type: ignore[no-untyped-def]
    """真实加载 competitor-analysis 的 L2 SkillDocument"""
    loader = InMemorySkillLoader()
    return await loader.load_sop(SLUG)


class TestFrontmatterDataSources:
    """[A] frontmatter data_sources 白名单声明契约"""

    async def test_data_sources_match_ssot(self, document) -> None:  # type: ignore[no-untyped-def]
        assert_data_sources_contract(SLUG, document.frontmatter)

    async def test_io_schema_match_contract(self, document) -> None:  # type: ignore[no-untyped-def]
        assert_io_schema_contract(SLUG, document.frontmatter)


class TestSopMaturity:
    """[B] SOP 内容成熟化"""

    async def test_sop_sections_and_resources(self, document) -> None:  # type: ignore[no-untyped-def]
        assert_sop_maturity(SLUG, document)


class TestCrossConsistency:
    """[C] 跨循环一致性（白名单 ↔ SOP 标记双向断言）"""

    async def test_markers_match_declared_sources(self, document) -> None:  # type: ignore[no-untyped-def]
        assert_cross_consistency(SLUG, document)
