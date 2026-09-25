"""Story 4.1b — ToolMetadata.data_sources 扩展单元测试

验证：
- ToolMetadata 新增 data_sources 字段（默认空 tuple，向后兼容）
- frontmatter 解析器支持可选 data_sources 键（YAML list of dict → tuple[DataSourceRef]）
- 既有 23 个 SKILL.md 解析零回归（未声明 data_sources 时默认空 tuple）
- 非法 data_sources 项抛 FrontmatterParseError（含字段路径）
"""

from __future__ import annotations

import pytest

from src.application.ports.skill_loader import ToolMetadata
from src.application.skills.frontmatter import (
    FrontmatterParseError,
    normalize_metadata,
    parse_frontmatter,
)
from src.domain.value_objects.data_source import DataSourceApiType, DataSourceRef


def _frontmatter_with_data_sources(data_sources_yaml: str) -> str:
    """构造含 data_sources 键的合法 frontmatter 文本。"""
    return f"---\nslug: test-skill\nname: 测试工具\nversion: 1.0.0\n{data_sources_yaml}---\n# Body\n正文\n"


class TestToolMetadataDataSourcesField:
    """ToolMetadata.data_sources 字段（向后兼容）。"""

    def test_default_empty_tuple(self) -> None:
        meta = ToolMetadata(tool_name="t", slug="t", category="c", input_schema={}, output_schema={})
        assert meta.data_sources == ()

    def test_explicit_data_sources(self) -> None:
        ref = DataSourceRef(name="world-bank", url="https://api.worldbank.org/v2", api_type=DataSourceApiType.REST_JSON)
        meta = ToolMetadata(
            tool_name="t",
            slug="t",
            category="c",
            input_schema={},
            output_schema={},
            data_sources=(ref,),
        )
        assert meta.data_sources == (ref,)


class TestFrontmatterDataSourcesParsing:
    """frontmatter data_sources 键解析。"""

    def test_parse_data_sources_full_fields(self) -> None:
        raw = _frontmatter_with_data_sources(
            "data_sources:\n"
            "  - name: world-bank\n"
            "    url: https://api.worldbank.org/v2\n"
            "    ttl_seconds: 86400\n"
            "    required_fields: [value, country]\n"
            "    api_type: rest_json\n"
        )
        meta_dict, _body = parse_frontmatter(raw)
        metadata = normalize_metadata(meta_dict)
        assert len(metadata.data_sources) == 1
        ref = metadata.data_sources[0]
        assert ref.name == "world-bank"
        assert ref.url == "https://api.worldbank.org/v2"
        assert ref.ttl_seconds == 86400
        assert ref.required_fields == ("value", "country")
        assert ref.api_type == DataSourceApiType.REST_JSON

    def test_parse_data_sources_minimal_defaults(self) -> None:
        raw = _frontmatter_with_data_sources(
            "data_sources:\n  - name: imf\n    url: https://imf.org/api\n    api_type: sdmx_json\n"
        )
        metadata = normalize_metadata(parse_frontmatter(raw)[0])
        ref = metadata.data_sources[0]
        assert ref.ttl_seconds == 86400
        assert ref.required_fields == ()

    def test_absent_data_sources_defaults_empty(self) -> None:
        raw = "---\nslug: test-skill\nname: 测试工具\nversion: 1.0.0\n---\n# Body\n"
        metadata = normalize_metadata(parse_frontmatter(raw)[0])
        assert metadata.data_sources == ()

    def test_invalid_data_source_item_raises(self) -> None:
        """非法项（缺 url）抛 FrontmatterParseError 且 context 含字段路径。"""
        raw = _frontmatter_with_data_sources("data_sources:\n  - name: world-bank\n    api_type: rest_json\n")
        with pytest.raises(FrontmatterParseError) as exc_info:
            normalize_metadata(parse_frontmatter(raw)[0])
        assert "data_sources" in str(exc_info.value.context.get("field", ""))

    def test_invalid_api_type_raises(self) -> None:
        raw = _frontmatter_with_data_sources(
            "data_sources:\n  - name: imf\n    url: https://imf.org/api\n    api_type: graphql\n"
        )
        with pytest.raises(FrontmatterParseError):
            normalize_metadata(parse_frontmatter(raw)[0])


class TestExistingSkillsRegression:
    """既有 23 个 SKILL.md 解析零回归（未声明 data_sources → 默认空 tuple）。"""

    @pytest.mark.asyncio
    async def test_all_23_skills_parse_without_data_sources(self) -> None:
        from src.application.skills.loader import InMemorySkillLoader
        from src.application.skills.skill_manifest import SLUG_TO_TOOL_ID

        loader = InMemorySkillLoader()
        for tool_name in SLUG_TO_TOOL_ID:
            metadata = await loader.load_metadata(tool_name)
            assert isinstance(metadata.data_sources, tuple)
