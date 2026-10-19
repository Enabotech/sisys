"""SkillSelector 单元测试（Story 5-2 — GAP-CRITICAL-08b 交付）

双分支覆盖（真实服务优先 + Mock 行为注入）：
- 真实分支：InMemorySkillLoader 直构组合（本地静态文件只读、无连接）——
  23 条全 active / 与 get_all_slugs() 清单同序（零排序副作用）/ tuple 返回类型
- Mock 分支：AsyncMock(spec=SkillLoaderPort)——deprecated 过滤行为 /
  SkillNotFoundError 传播不静默

权威口径：interface-design.md §5.5——SkillSelector 仅查询接口（ACTIVE 纯过滤），
触发由 LLM 基于 L1 description 自主判断（5.3）；禁止关键词打分/语义检索/Top-K。

Run with:
    poetry run pytest tests/unit/application/skills/test_skill_selector.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


def _make_real_selector():
    """真实分支工厂：InMemorySkillLoader 直构组合（构造期同步读 TOOLS.md 一次）。"""
    from src.application.skills.loader import InMemorySkillLoader
    from src.application.skills.registry.selector import SkillSelector

    return SkillSelector(skill_loader=InMemorySkillLoader())


# ===================================================================
# 真实分支：全量 23 条 ACTIVE + 稳定序
# ===================================================================


class TestRealLoaderBranch:
    """真实 InMemorySkillLoader 组合（23 个 SKILL.md 全 active 实测基线）。"""

    async def test_returns_23_active_skills(self) -> None:
        """条目数 23（Skills 资产 tripwire——SKILL.md status 演进时同步更新）。"""
        selector = _make_real_selector()
        skills = await selector.list_active_skills()
        assert len(skills) == 23, f"期望 23 个活跃技能，实际 {len(skills)}"

    async def test_all_status_active(self) -> None:
        """全部条目 status=="active"。"""
        selector = _make_real_selector()
        skills = await selector.list_active_skills()
        assert all(meta.status == "active" for meta in skills)

    async def test_order_matches_slug_manifest(self) -> None:
        """零排序副作用：返回顺序与 get_all_slugs() 清单一致。"""
        from src.application.skills.skill_manifest import get_all_slugs

        selector = _make_real_selector()
        skills = await selector.list_active_skills()
        assert [meta.slug for meta in skills] == get_all_slugs()

    async def test_returns_tuple_type(self) -> None:
        """返回类型为 tuple（端口契约）。"""
        selector = _make_real_selector()
        skills = await selector.list_active_skills()
        assert isinstance(skills, tuple)

    async def test_metadata_fields_present(self) -> None:
        """条目含 slug/tool_name/description/when_to_use/tags 元数据（AC-3 清单）。"""
        selector = _make_real_selector()
        skills = await selector.list_active_skills()
        for meta in skills:
            assert meta.slug
            assert meta.tool_name
            assert isinstance(meta.description, str)
            assert isinstance(meta.when_to_use, tuple)
            assert isinstance(meta.tags, tuple)


# ===================================================================
# Mock 分支：过滤行为与异常传播
# ===================================================================


class TestMockLoaderBranch:
    """AsyncMock(spec=SkillLoaderPort) 注入——过滤行为断言。"""

    @staticmethod
    def _make_metadata(slug: str, status: str):
        """构造带指定 status 的 ToolMetadata（其余字段最小合法）。"""
        from src.application.ports.skill_loader import ToolMetadata

        return ToolMetadata(
            tool_name=f"工具 {slug}",
            slug=slug,
            category="strategic_selection",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            description=f"{slug} 描述",
            status=status,
        )

    async def test_deprecated_filtered_out(self) -> None:
        """某 slug 元数据 status="deprecated" → 结果不含该条（过滤行为断言）。"""
        from src.application.ports.skill_loader import SkillLoaderPort
        from src.application.skills.registry.selector import SkillSelector
        from src.application.skills.skill_manifest import get_all_slugs

        slugs = get_all_slugs()
        metadata_map = {slug: self._make_metadata(slug, "active") for slug in slugs}
        metadata_map[slugs[5]] = self._make_metadata(slugs[5], "deprecated")  # 第 6 个降级

        loader = AsyncMock(spec=SkillLoaderPort)
        loader.load_metadata = AsyncMock(side_effect=lambda slug: metadata_map[slug])
        selector = SkillSelector(skill_loader=loader)

        skills = await selector.list_active_skills()
        returned_slugs = [meta.slug for meta in skills]
        assert slugs[5] not in returned_slugs, "deprecated 条目应被过滤"
        assert len(returned_slugs) == len(slugs) - 1

    async def test_experimental_filtered_out(self) -> None:
        """status="experimental" 同样被过滤（仅 active 通过）。"""
        from src.application.ports.skill_loader import SkillLoaderPort
        from src.application.skills.registry.selector import SkillSelector
        from src.application.skills.skill_manifest import get_all_slugs

        slugs = get_all_slugs()
        loader = AsyncMock(spec=SkillLoaderPort)
        loader.load_metadata = AsyncMock(
            side_effect=lambda slug: self._make_metadata(slug, "active" if slug != slugs[0] else "experimental")
        )
        selector = SkillSelector(skill_loader=loader)

        skills = await selector.list_active_skills()
        assert slugs[0] not in [meta.slug for meta in skills]

    async def test_skill_not_found_propagates(self) -> None:
        """skill_loader 抛 SkillNotFoundError → 传播不静默（缺档案是资产缺陷）。"""
        from src.application.ports.skill_loader import SkillLoaderPort
        from src.application.skills.registry.selector import SkillSelector
        from src.domain.exceptions import SkillNotFoundError

        loader = AsyncMock(spec=SkillLoaderPort)
        loader.load_metadata = AsyncMock(side_effect=SkillNotFoundError(tool_name="missing", slug="missing"))
        selector = SkillSelector(skill_loader=loader)

        with pytest.raises(SkillNotFoundError):
            await selector.list_active_skills()
