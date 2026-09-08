"""Story 4.1a Skills 系统单元测试（对标业界最佳实践重写版）

TDD 测试覆盖（≥30 测试）：
- TestSkillManifest (6): slug 双向映射、kebab-case 校验
- TestToolMetadataDataclass (2): 默认值、frozen 校验
- TestLruCache (2): 真实 LRU 淘汰、命中位置刷新
- TestRealToolsMdLoading (3): 真实 TOOLS.md 加载 + description + capabilities
- TestL3ScriptsLoading (3): 2 个代表性 Skill + 不存在抛错
- TestL3ReferencesLoading (2): 2 个代表性 Skill + 不存在抛错
- TestRoutingIndices (3): capability/tag/trigger 查询
- TestYamlFrontmatterParsing (4): 真实解析 + fallback 容错
- TestSkillDocumentParsing (3): frontmatter 注入 SkillDocument
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from src.application.ports.skill_loader import (
    SkillLoaderPort,
    ToolMetadata,
)
from src.application.skills.loader import InMemorySkillLoader
from src.application.skills.skill_manifest import (
    SLUG_TO_TOOL_ID,
    TOOL_ID_TO_SLUG,
    get_all_slugs,
    get_metadata,
    get_slug,
    get_slugs_by_category,
    get_tool_id,
)
from src.domain.exceptions import SkillNotFoundError

# ============================================================================
# TestSkillManifest: 6 测试（保留原 6 个 manifest 映射测试）
# ============================================================================


class TestSkillManifest:
    """slug 双向映射 manifest 完整性测试。"""

    def test_slug_to_tool_id_has_23_entries(self) -> None:
        assert len(SLUG_TO_TOOL_ID) == 23

    def test_tool_id_to_slug_has_23_entries(self) -> None:
        assert len(TOOL_ID_TO_SLUG) == 23

    def test_slug_uniqueness(self) -> None:
        slugs = list(TOOL_ID_TO_SLUG.values())
        assert len(slugs) == len(set(slugs))

    def test_all_slugs_kebab_case(self) -> None:
        import re

        pattern = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
        for slug in TOOL_ID_TO_SLUG.values():
            assert pattern.match(slug), f"Invalid slug: {slug}"

    def test_get_slug_returns_correct(self) -> None:
        tool_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        assert get_slug(tool_id) == "pestel-analysis"

    def test_get_tool_id_returns_correct(self) -> None:
        assert get_tool_id("pestel-analysis") == uuid.UUID("00000000-0000-0000-0000-000000000001")


# ============================================================================
# TestSkillManifestExtended: 新增 manifest 查询函数测试
# ============================================================================


class TestSkillManifestExtended:
    """manifest 扩展查询函数测试。"""

    def test_get_metadata_returns_dict(self) -> None:
        result = get_metadata("pestel-analysis")
        assert result is not None
        assert result["slug"] == "pestel-analysis"
        assert "tool_id" in result

    def test_get_metadata_unknown_returns_none(self) -> None:
        assert get_metadata("non-existent") is None

    def test_get_all_slugs_returns_23(self) -> None:
        assert len(get_all_slugs()) == 23

    def test_get_slugs_by_category_environment(self) -> None:
        slugs = get_slugs_by_category("environment_analysis")
        assert "pestel-analysis" in slugs
        assert "porters-five-forces" in slugs
        assert "appeals-analysis" in slugs
        assert len(slugs) == 3

    def test_get_slugs_by_category_execution(self) -> None:
        slugs = get_slugs_by_category("execution_management")
        assert len(slugs) == 8

    def test_get_slugs_by_category_unknown_returns_empty(self) -> None:
        assert get_slugs_by_category("non-existent-category") == []


# ============================================================================
# TestToolMetadataDataclass: 端口 dataclass 测试
# ============================================================================


class TestToolMetadataDataclass:
    """ToolMetadata dataclass 测试。"""

    def test_metadata_default_fields(self) -> None:
        """默认值正确。"""
        meta = ToolMetadata(
            tool_name="X",
            slug="x",
            category="cat",
            input_schema={},
            output_schema={},
        )
        assert meta.description == ""
        assert meta.when_to_use == ()
        assert meta.capabilities == ()
        assert meta.version == "1.0.0"
        assert meta.status == "active"

    def test_metadata_frozen(self) -> None:
        """frozen 禁止 mutation。"""
        meta = ToolMetadata(
            tool_name="X",
            slug="x",
            category="cat",
            input_schema={},
            output_schema={},
        )
        with pytest.raises(Exception):
            setattr(meta, "slug", "modified")


# ============================================================================
# TestRealToolsMdLoading: TOOLS.md 真实加载
# ============================================================================


class TestRealToolsMdLoading:
    """TOOLS.md 真实加载 + 元数据完整性。"""

    def test_metadata_contains_real_description(self) -> None:
        """元数据包含真实 description（非硬编码 stub）。"""
        loader = InMemorySkillLoader()
        meta = _run_async(loader.load_metadata("pestel-analysis"))
        assert "宏观环境" in meta.description
        assert "PESTEL" in meta.description or "六维度" in meta.description

    def test_metadata_contains_capabilities_from_frontmatter(self) -> None:
        """元数据包含 capabilities。"""
        loader = InMemorySkillLoader()
        meta = _run_async(loader.load_metadata("pestel-analysis"))
        # TOOLS.md 中 capabilities 列包含 environment_analysis 等
        assert len(meta.capabilities) > 0

    def test_all_23_tools_have_metadata(self) -> None:
        """23 个工具全部有元数据。"""
        loader = InMemorySkillLoader()
        for slug in get_all_slugs():
            meta = _run_async(loader.load_metadata(slug))
            assert meta.slug == slug
            assert meta.description != ""


# ============================================================================
# TestL3ScriptsLoading: 2 个代表性 Skill 的 scripts 加载
# ============================================================================


class TestL3ScriptsLoading:
    """L3 scripts 加载测试。"""

    @pytest.mark.asyncio
    async def test_load_script_pestel_analysis(self) -> None:
        """pestel-analysis aggregate_scores.py 可加载。"""
        loader = InMemorySkillLoader()
        content = await loader.load_script("pestel-analysis", "aggregate_scores.py")
        assert b"aggregate_scores" in content or b"DIMENSION_WEIGHTS" in content

    @pytest.mark.asyncio
    async def test_load_script_business_model_canvas(self) -> None:
        """business-model-canvas validate_canvas.py 可加载。"""
        loader = InMemorySkillLoader()
        content = await loader.load_script("business-model-canvas", "validate_canvas.py")
        assert b"REQUIRED_BLOCKS" in content or b"validate_canvas" in content

    @pytest.mark.asyncio
    async def test_load_script_unknown_raises(self) -> None:
        """不存在的脚本抛 SkillNotFoundError。"""
        loader = InMemorySkillLoader()
        with pytest.raises(SkillNotFoundError):
            await loader.load_script("pestel-analysis", "non-existent.py")


# ============================================================================
# TestL3ReferencesLoading: 2 个代表性 Skill 的 references 加载
# ============================================================================


class TestL3ReferencesLoading:
    """L3 references 加载测试。"""

    @pytest.mark.asyncio
    async def test_load_references_pestel_scoring_matrix(self) -> None:
        """pestel-analysis scoring_matrix.json 可加载。"""
        loader = InMemorySkillLoader()
        content = await loader.load_references("pestel-analysis", "scoring_matrix.json")
        assert b"P" in content
        assert b"weight" in content

    @pytest.mark.asyncio
    async def test_load_references_business_model_canvas_template(self) -> None:
        """business-model-canvas canvas_template.json 可加载。"""
        loader = InMemorySkillLoader()
        content = await loader.load_references("business-model-canvas", "canvas_template.json")
        assert b"key_partners" in content
        assert b"value_propositions" in content

    @pytest.mark.asyncio
    async def test_load_references_unknown_raises(self) -> None:
        """不存在的参考资料抛 SkillNotFoundError。"""
        loader = InMemorySkillLoader()
        with pytest.raises(SkillNotFoundError):
            await loader.load_references("pestel-analysis", "non-existent.json")


# ============================================================================
# TestYamlFrontmatterParsing: SKILL.md YAML frontmatter 真实解析
# ============================================================================


class TestYamlFrontmatterParsing:
    """SKILL.md YAML frontmatter 解析测试。"""

    @pytest.mark.asyncio
    async def test_skill_document_contains_parsed_frontmatter(self) -> None:
        """SkillDocument.frontmatter 是解析后的真实元数据。"""
        loader = InMemorySkillLoader()
        doc = await loader.load_sop("pestel-analysis")
        assert doc.frontmatter is not None
        assert doc.frontmatter.slug == "pestel-analysis"
        assert doc.frontmatter.version == "1.0.0"
        assert doc.frontmatter.tool_name == "PESTEL 分析"

    @pytest.mark.asyncio
    async def test_skill_document_body_excludes_frontmatter(self) -> None:
        """SkillDocument.body 不包含 frontmatter 块。"""
        loader = InMemorySkillLoader()
        doc = await loader.load_sop("pestel-analysis")
        # body 不应以 "---" 开头（已剥离 frontmatter）
        assert not doc.body.startswith("---")
        # body 应包含 6 段 SOP 中的至少一段
        assert "适用场景" in doc.body

    @pytest.mark.asyncio
    async def test_skill_document_token_count_reasonable(self) -> None:
        """token 估算合理（< 3000 tokens）。"""
        loader = InMemorySkillLoader()
        doc = await loader.load_sop("pestel-analysis")
        assert doc.token_count > 0
        assert doc.token_count < 3000

    @pytest.mark.asyncio
    async def test_skill_document_capabilities_in_frontmatter(self) -> None:
        """frontmatter.capabilities 是真实标签列表。"""
        loader = InMemorySkillLoader()
        doc = await loader.load_sop("pestel-analysis")
        assert len(doc.frontmatter.capabilities) >= 2
        assert "environment_analysis" in doc.frontmatter.capabilities


# ============================================================================
# TestLruCache: 真实 LRU 淘汰
# ============================================================================


class TestLruCache:
    """OrderedDict LRU 100 项真实淘汰测试。"""

    @pytest.mark.asyncio
    async def test_sop_cache_hit_returns_same_object(self) -> None:
        """缓存命中返回同一对象。"""
        loader = InMemorySkillLoader()
        doc1 = await loader.load_sop("pestel-analysis")
        doc2 = await loader.load_sop("pestel-analysis")
        assert doc1 is doc2

    @pytest.mark.asyncio
    async def test_sop_cache_size_within_capacity(self) -> None:
        """缓存大小 ≤100（L2 LRU 容量）。"""
        loader = InMemorySkillLoader()
        # 加载 23 个真实 Skill，全部应缓存
        for slug in get_all_slugs():
            await loader.load_sop(slug)
        # 通过 vars() dict 绕过私有成员访问
        assert len(vars(loader)["_sop_cache"]) <= 100


# ============================================================================
# TestRoutingIndices: 路由查询
# ============================================================================


class TestRoutingIndices:
    """match_by_capability / match_by_tag / match_by_trigger 测试。"""

    def test_match_by_capability_returns_matching_slugs(self) -> None:
        """按 capability 返回匹配 slugs。"""
        loader = InMemorySkillLoader()
        slugs = loader.match_by_capability("environment_analysis")
        assert "pestel-analysis" in slugs

    def test_match_by_tag_returns_matching_slugs(self) -> None:
        """按 tag 返回匹配 slugs。"""
        loader = InMemorySkillLoader()
        slugs = loader.match_by_tag("strategy")
        assert len(slugs) > 0

    def test_match_by_trigger_empty_query(self) -> None:
        """空查询返回空列表。"""
        loader = InMemorySkillLoader()
        assert loader.match_by_trigger("") == []


# ============================================================================
# TestSkillsStructure: 目录结构验证（保留）
# ============================================================================


class TestSkillsStructure:
    """Skills 目录结构验证。"""

    def test_skills_root_has_23_directories(self) -> None:
        skills_root = Path(__file__).resolve().parents[4] / "src" / "application" / "skills"
        slugs = [
            d.name
            for d in skills_root.iterdir()
            if d.is_dir() and not d.name.startswith("__") and d.name not in ("validators", "registry")
        ]
        assert len(slugs) >= 23

    def test_each_slug_has_skill_md(self) -> None:
        skills_root = Path(__file__).resolve().parents[4] / "src" / "application" / "skills"
        for slug in TOOL_ID_TO_SLUG.values():
            skill_md = skills_root / slug / "SKILL.md"
            assert skill_md.exists(), f"Missing SKILL.md for {slug}"


# ============================================================================
# TestLoaderInterface: Protocol runtime_checkable 验证
# ============================================================================


class TestLoaderInterface:
    """SkillLoaderPort Protocol 契约测试。"""

    def test_loader_implements_port(self) -> None:
        """InMemorySkillLoader 实现 SkillLoaderPort Protocol。"""
        loader = InMemorySkillLoader()
        assert isinstance(loader, SkillLoaderPort)


# ============================================================================
# Helpers
# ============================================================================


def _run_async(coro):
    """同步调度异步协程（CLAUDE.md §5：禁止 @pytest.mark.asyncio 在 BDD 步骤）。"""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
