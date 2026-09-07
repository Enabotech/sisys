"""Story 4.1a: Skills 加载器单元测试

TDD 测试覆盖：
- TOOLS.md L1 元数据加载（<200 tokens）
- SKILL.md × 23 L2 SOP 加载
- skill_manifest 双向映射（23 项）
- 3 级加载触发逻辑
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from src.application.skills.loader import InMemorySkillLoader
from src.application.skills.skill_manifest import (
    SLUG_TO_TOOL_ID,
    TOOL_ID_TO_SLUG,
    get_slug,
    get_tool_id,
)
from src.domain.exceptions import SkillNotFoundError


class TestSkillManifest:
    """skill_manifest.py 双向映射测试"""

    def test_slug_to_tool_id_has_23_entries(self) -> None:
        """slug → tool_id 映射 23 项"""
        assert len(SLUG_TO_TOOL_ID) == 23

    def test_tool_id_to_slug_has_23_entries(self) -> None:
        """tool_id → slug 映射 23 项"""
        assert len(TOOL_ID_TO_SLUG) == 23

    def test_slug_uniqueness(self) -> None:
        """slug 唯一"""
        slugs = list(TOOL_ID_TO_SLUG.values())
        assert len(slugs) == len(set(slugs))

    def test_all_slugs_kebab_case(self) -> None:
        """slug 全部 kebab-case"""
        import re

        pattern = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
        for slug in TOOL_ID_TO_SLUG.values():
            assert pattern.match(slug), f"Invalid slug: {slug}"

    def test_get_slug_returns_correct(self) -> None:
        """get_slug 正向查询"""
        tool_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        assert get_slug(tool_id) == "pestel-analysis"

    def test_get_tool_id_returns_correct(self) -> None:
        """get_tool_id 反向查询"""
        assert get_tool_id("pestel-analysis") == uuid.UUID("00000000-0000-0000-0000-000000000001")


class TestInMemorySkillLoaderMetadata:
    """L1 元数据加载测试"""

    @pytest.mark.asyncio
    async def test_load_metadata_by_slug(self) -> None:
        """通过 slug 加载元数据"""
        loader = InMemorySkillLoader()
        metadata = await loader.load_metadata("pestel-analysis")
        assert metadata.slug == "pestel-analysis"
        assert metadata.tool_name != ""

    @pytest.mark.asyncio
    async def test_load_metadata_unknown_raises(self) -> None:
        """未知 slug 抛 SkillNotFoundError"""
        loader = InMemorySkillLoader()
        with pytest.raises(SkillNotFoundError):
            await loader.load_metadata("non-existent-tool")


class TestInMemorySkillLoaderSOP:
    """L2 SOP 加载测试"""

    @pytest.mark.asyncio
    async def test_load_sop_returns_skill_document(self) -> None:
        """加载 SKILL.md 返回 SkillDocument"""
        loader = InMemorySkillLoader()
        doc = await loader.load_sop("pestel-analysis")
        assert doc.slug == "pestel-analysis"
        assert doc.content != ""
        assert doc.token_count >= 0

    @pytest.mark.asyncio
    async def test_load_sop_caches_result(self) -> None:
        """二次加载命中 LRU 缓存"""
        loader = InMemorySkillLoader()
        doc1 = await loader.load_sop("pestel-analysis")
        doc2 = await loader.load_sop("pestel-analysis")
        assert doc1 is doc2  # 同对象引用（缓存命中）

    @pytest.mark.asyncio
    async def test_load_sop_unknown_raises(self) -> None:
        """未知 slug 抛 SkillNotFoundError"""
        loader = InMemorySkillLoader()
        with pytest.raises(SkillNotFoundError):
            await loader.load_sop("non-existent-tool")


class TestInMemorySkillLoaderReferences:
    """L3 参考资料加载测试"""

    @pytest.mark.asyncio
    async def test_load_references_unknown_file_raises(self) -> None:
        """不存在的参考资料抛 SkillNotFoundError"""
        loader = InMemorySkillLoader()
        with pytest.raises(SkillNotFoundError):
            await loader.load_references("pestel-analysis", "non-existent.json")


class TestSkillsStructure:
    """Skills 目录结构验证"""

    def test_skills_root_has_23_directories(self) -> None:
        """Skills 根目录有 23 个工具子目录"""
        # tests/unit/application/skills/test_skills_loader.py
        # parents[4] = sisys (project root)
        skills_root = Path(__file__).resolve().parents[4] / "src" / "application" / "skills"
        slugs = [
            d.name
            for d in skills_root.iterdir()
            if d.is_dir() and not d.name.startswith("__") and d.name not in ("validators", "registry")
        ]
        assert len(slugs) >= 23

    def test_each_slug_has_skill_md(self) -> None:
        """每个 slug 都有 SKILL.md"""
        skills_root = Path(__file__).resolve().parents[4] / "src" / "application" / "skills"
        for slug in TOOL_ID_TO_SLUG.values():
            skill_md = skills_root / slug / "SKILL.md"
            assert skill_md.exists(), f"Missing SKILL.md for {slug}"
