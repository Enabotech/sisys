"""内部框架型 Skills 模板字段 ↔ input_schema 叶子键双向对应专项测试（7 Skill 参数化汇总）

与 4-1d 既有 test_schema_template_alignment.py 的区别（多 framework_ 一段）：
- 分型四段式（评分型「评分锚点」/ 结构型「校验规则」第三段——D5）
- references 内容锚点断言参数化全覆盖（assert_reference_content_anchors——AC-2
  验证标准调用位，7 个真实 references 全覆盖）

本文件以契约库断言函数统一参数化复跑——skill_framework_contracts.py 单一来源。
"""

from __future__ import annotations

import pytest

from src.application.ports.skill_loader import SkillDocument
from src.application.skills.loader import InMemorySkillLoader
from tests.unit.application.skills.skill_framework_contracts import (
    FRAMEWORK_SKILL_SLUGS,
    SKILLS_ROOT,
    TEMPLATE_FILES,
    assert_reference_content_anchors,
    assert_template_schema_alignment,
)

ALL_FRAMEWORK_SLUGS: tuple[str, ...] = tuple(FRAMEWORK_SKILL_SLUGS)


@pytest.fixture
async def document(slug: str) -> SkillDocument:
    """真实加载目标 Skill 的 L2 SkillDocument。"""
    loader = InMemorySkillLoader()
    return await loader.load_sop(slug)


@pytest.mark.parametrize("slug", ALL_FRAMEWORK_SLUGS)
async def test_template_fields_match_schema_leaf_keys(slug: str, document: SkillDocument) -> None:
    """模板字段 ↔ Schema 叶子键双向断言（分型四段式 + 分区标题 + 必填标注）。"""
    assert_template_schema_alignment(slug, document)


@pytest.mark.parametrize("slug", ALL_FRAMEWORK_SLUGS)
async def test_reference_content_anchors_covered(slug: str, document: SkillDocument) -> None:
    """references 内容要素字面锚点全覆盖（编号步骤 + 英文键名 + 分档含义/正反例或
    编号规则/关键字 + workshop 三要素——「文件存在但要素残缺」的假一致防线）。"""
    assert_reference_content_anchors(slug, document)


@pytest.mark.parametrize("slug", ALL_FRAMEWORK_SLUGS)
def test_template_file_registered(slug: str) -> None:
    """模板文件登记与存在（TEMPLATE_FILES 映射 + 文件实体）。"""
    assert slug in TEMPLATE_FILES, f"{slug} 未登记模板文件名"
    assert (SKILLS_ROOT / slug / "templates" / TEMPLATE_FILES[slug]).is_file(), f"{slug}: 缺少 templates/{TEMPLATE_FILES[slug]}"
