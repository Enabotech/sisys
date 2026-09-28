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

    @pytest.mark.parametrize(
        ("field", "yaml_value"),
        [
            ("name", "123"),  # YAML 整数 → VO re.match 原生 TypeError
            ("url", "123"),  # → startswith 原生 AttributeError
            ("ttl_seconds", '"604800"'),  # YAML 引号字符串 → 比较原生 TypeError
            ("ttl_seconds", ""),  # YAML 空值 None → int<=None 原生 TypeError
        ],
    )
    def test_scalar_type_confusion_wrapped_as_frontmatter_error(self, field: str, yaml_value: str) -> None:
        """data_sources 子字段标量类型混淆 → FrontmatterParseError（R3-2 G3：
        VO 构造侧 isinstance 门禁后，原以原生 TypeError/AttributeError 逃逸
        load_sop 的 YAML 编排错误统一收敛为领域异常——EntityValidationError ⊂
        DomainError 被 frontmatter 既有 except 自动包裹）"""
        item_lines = {"name": "world-bank", "url": "https://x.local/api", "api_type": "rest_json"}
        item_lines[field] = yaml_value
        raw = _frontmatter_with_data_sources(
            "data_sources:\n  - " + "\n    ".join(f"{k}: {v}" for k, v in item_lines.items()) + "\n"
        )
        with pytest.raises(FrontmatterParseError) as exc_info:
            normalize_metadata(parse_frontmatter(raw)[0])
        assert exc_info.value.context.get("field") == "data_sources[0]"


class TestExistingSkillsRegression:
    """既有 23 个 SKILL.md 解析零回归（4-1d Task 1.4 中间态安全化重构）。

    R3-4 K3v2：锚点改 frontmatter/L2 路径（load_metadata 走 L1/TOOLS.md 表，
    结构性不携带 data_sources——原 isinstance 断言恒真且测错层；白名单的真实
    消费链路是 load_sop(slug).frontmatter）。

    4-1d Task 1.4 重构（Round 2 设计，替代原「DECLARING_SLUGS 静态清单 +
    非声明组空 tuple 断言」——静态清单方案在 4-1d 并行实施期存在必红窗口）：
    - 「凡声明必合法」：物理 data_sources 非空者逐个校验合法性（name/ttl），
      不绑定静态清单（各 Story 声明进程互不干扰）
    - 「物理非空者必 ∈ SSOT 并集」：并集 = 4-1c ∪ 4-1d 两契约库动态派生
      （16 slug）——4-1e 目标误填即 ∉ 并集红，4-1d 目标未填不红（中间态
      两向安全）；最终态 16 全非空由 4-1d 架构测试闭环
    """

    @pytest.mark.asyncio
    async def test_declaring_skills_frontmatter_carries_data_sources(self) -> None:
        """凡物理声明 data_sources 的 Skill，经 L2 frontmatter 路径解析且逐源合法（name/ttl）"""
        from src.application.skills.loader import InMemorySkillLoader
        from src.application.skills.skill_manifest import SLUG_TO_TOOL_ID

        loader = InMemorySkillLoader()
        declared_any = False
        for slug in SLUG_TO_TOOL_ID:
            doc = await loader.load_sop(slug)
            refs = doc.frontmatter.data_sources
            if not refs:
                continue  # 未声明 Skill 不在本用例范围（守卫见下一用例）
            declared_any = True
            assert len(refs) >= 1, f"{slug} 声明的 data_sources 未经 frontmatter 路径解析"
            for ref in refs:
                assert ref.name and ref.ttl_seconds >= 60, f"{slug}.{ref.name} 值对象校验失效"
        assert declared_any, "4-1c 已交付 6 个声明 Skill，物理非空者至少存在"

    @pytest.mark.asyncio
    async def test_physical_declaring_slugs_within_ssot_union(self) -> None:
        """物理 data_sources 非空者必 ∈ SSOT 并集 16（4-1c ∪ 4-1d 契约库动态派生）。

        未声明 Skill 保持空 tuple 不受影响；并集外误填（如 4-1e 目标）即红。
        4-1d 目标 Skill 填写声明后 ∈ 并集（契约库登记）即绿——中间态两向安全。
        """
        from src.application.skills.loader import InMemorySkillLoader
        from src.application.skills.skill_manifest import SLUG_TO_TOOL_ID
        from tests.unit.application.skills.skill_data_collection_contracts import SKILL_DATA_SOURCES
        from tests.unit.application.skills.skill_mixed_data_contracts import MIXED_SKILL_DATA_SOURCES

        ssot_union = set(SKILL_DATA_SOURCES) | set(MIXED_SKILL_DATA_SOURCES)
        assert len(ssot_union) == 16, f"SSOT 并集应为 16（6 外部 + 10 混合），实际 {len(ssot_union)}"

        loader = InMemorySkillLoader()
        for slug in SLUG_TO_TOOL_ID:
            doc = await loader.load_sop(slug)
            if doc.frontmatter.data_sources:
                assert slug in ssot_union, (
                    f"{slug} 物理声明了 data_sources 但不在 SSOT 并集（4-1c ∪ 4-1d）中——误填或契约库未登记"
                )
