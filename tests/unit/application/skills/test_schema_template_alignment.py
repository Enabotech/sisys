"""模板字段 ↔ input_schema 叶子键双向对应专项测试（10 Skill 参数化汇总）

Story AC-3 核心断言的汇总层（Task 2-11 [D] 循环在各 Skill 单测内逐个验证，
本文件以契约库断言函数统一参数化复跑——契约库 assert_template_schema_alignment
单一来源，含四段式微格式 + 叶子键双向 + 必填标注一致性全链断言）。

真实加载真实 SKILL.md（InMemorySkillLoader），禁止 mock。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.application.ports.skill_loader import SkillDocument
from src.application.skills.loader import InMemorySkillLoader
from tests.unit.application.skills.skill_mixed_data_contracts import (
    MIXED_SKILL_DATA_SOURCES,
    TEMPLATE_FILES,
    assert_template_schema_alignment,
)

ALL_MIXED_SLUGS: tuple[str, ...] = tuple(MIXED_SKILL_DATA_SOURCES.keys())


@pytest.fixture
async def document(slug: str) -> SkillDocument:
    """真实加载参数化 slug 的 L2 SkillDocument"""
    loader = InMemorySkillLoader()
    return await loader.load_sop(slug)


@pytest.mark.parametrize("slug", ALL_MIXED_SLUGS)
async def test_template_fields_match_schema_leaf_keys(slug: str, document: SkillDocument) -> None:
    """采集模板字段集合 == input_schema 递归叶子键集合（双向）+ 四段式微格式 + 必填标注。"""
    assert_template_schema_alignment(slug, document)


@pytest.mark.parametrize("slug", ALL_MIXED_SLUGS)
def test_template_file_registered(slug: str) -> None:
    """模板文件名登记完备（契约库 TEMPLATE_FILES 覆盖全部 10 Skill 且文件存在）。"""
    assert slug in TEMPLATE_FILES, f"{slug} 未登记模板文件名"
    skills_root = Path(__file__).resolve().parents[4] / "src" / "application" / "skills"
    template_path = skills_root / slug / "templates" / TEMPLATE_FILES[slug]
    assert template_path.is_file(), f"{slug}: 模板文件不存在 {template_path}"
