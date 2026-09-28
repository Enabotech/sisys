"""Story 4.1d Task 1.1 — 契约库永久自检测试。

断言 `skill_mixed_data_contracts.py` 的 SSOT 常量与 Story「端口与数据契约」
声明表逐字一致，防实施期擅改 SSOT（永久断言，有长期判别价值——Round 1 D2-B 勘正：
原稿「临时导入断言」未定去向，改为永久自检测试）。

测试内的独立硬编码基准表与契约库常量双向比对——任何一侧被擅改即红
（变异演示判别力来源：改契约库任一条目 → 本测试红）。
"""

from __future__ import annotations

import inspect
from typing import Any

import tests.unit.application.skills.skill_data_collection_contracts as contracts_41c
import tests.unit.application.skills.skill_mixed_data_contracts as contracts_41d

# Story 4.1d「端口与数据契约」SSOT 声明表逐字基准（独立副本，与契约库比对）
STORY_SSOT: dict[str, tuple[str, ...]] = {
    "swot-tows": ("newsapi", "tavily"),
    "ansoff-matrix": ("world-bank", "imf"),
    "value-curve-analysis": ("tavily", "newsapi"),
    "ge-mckinsey-matrix": ("world-bank", "tavily"),
    "space-matrix": ("world-bank", "imf"),
    "value-chain-analysis": ("tavily", "china-nbs"),
    "vrio-framework": ("uspto", "tavily"),
    "bsc-scorecard": ("china-nbs", "world-bank"),
    "kpi-tree": ("china-nbs", "newsapi"),
    "change-management": ("newsapi", "tavily"),
}


class TestMixedSkillDataSources:
    """MIXED_SKILL_DATA_SOURCES 常量与 Story SSOT 表逐字一致（防擅改）。"""

    def test_entries_match_story_ssot_verbatim(self) -> None:
        """10 条目 slug 集合 + 每条目有序源元组与 Story 声明表逐字一致。"""
        assert contracts_41d.MIXED_SKILL_DATA_SOURCES == STORY_SSOT

    def test_exactly_ten_skills(self) -> None:
        """恰好 10 个条目（4-1d 目标集固定）。"""
        assert len(contracts_41d.MIXED_SKILL_DATA_SOURCES) == 10

    def test_all_sources_are_registered_adapters(self) -> None:
        """全部声明源 ∈ 8 个注册适配器集合（合法值约束）。"""
        for slug, sources in contracts_41d.MIXED_SKILL_DATA_SOURCES.items():
            for name in sources:
                assert name in contracts_41c.ADAPTER_SSOT, f"{slug}: 源 {name} 不在 8 个注册适配器中"

    def test_unified_two_source_policy(self) -> None:
        """统一 2 源策略（决策 D2）：每个 Skill 恰好声明 2 个源且不重复。"""
        for slug, sources in contracts_41d.MIXED_SKILL_DATA_SOURCES.items():
            assert len(sources) == 2, f"{slug}: 声明源数 {len(sources)} != 2（统一 2 源策略 D2）"
            assert len(set(sources)) == 2, f"{slug}: 声明源重复 {sources}"

    def test_key_sensitive_skills_count(self) -> None:
        """Key 敏感 Skill 恰好 7 个（4 单敏感 + 3 双敏感），交叉核算 SSOT 表。"""
        sensitive = contracts_41c.KEY_SENSITIVE_SOURCES
        sensitive_skills = {
            slug: sum(1 for s in sources if s in sensitive) for slug, sources in contracts_41d.MIXED_SKILL_DATA_SOURCES.items()
        }
        dual = {slug for slug, n in sensitive_skills.items() if n == 2}
        single = {slug for slug, n in sensitive_skills.items() if n == 1}
        assert dual == {"swot-tows", "value-curve-analysis", "change-management"}, (
            f"双敏感 Skill 应为 swot-tows/value-curve-analysis/change-management，实际 {dual}"
        )
        assert single == {"ge-mckinsey-matrix", "value-chain-analysis", "vrio-framework", "kpi-tree"}, (
            f"单敏感 Skill 集合不符，实际 {single}"
        )
        assert len(dual) + len(single) == 7, "Key 敏感 Skill 总数应为 7（SOP 降级话术覆盖面核算）"

    def test_slug_set_matches_yaml_contracts(self) -> None:
        """契约库 slug 集合 == IO 契约 yaml 中 4-1d 10 条目集合（两 SSOT 互锁）。"""
        yaml_slugs = set(contracts_41d.load_io_contract_keys())
        mixed_slugs = set(contracts_41d.MIXED_SKILL_DATA_SOURCES)
        assert mixed_slugs <= yaml_slugs, f"契约库 slug 未全部登记 yaml: {mixed_slugs - yaml_slugs}"
        # yaml = 4-1c 6 条 + 4-1d 10 条
        assert yaml_slugs == mixed_slugs | set(contracts_41c.SKILL_DATA_SOURCES), (
            "yaml 条目集合应恰好等于 4-1c ∪ 4-1d 两契约库并集"
        )


class TestSharedConstantsSingleSource:
    """跨 Story 共享常量一律 import 4-1c 契约库（R2-F3 单一来源，D6 决策）。"""

    def test_shared_constants_are_imported_not_copied(self) -> None:
        """五共享常量必须与 4-1c 契约库同一对象（identity 断言，防复制漂移）。"""
        assert contracts_41d.ADAPTER_SSOT is contracts_41c.ADAPTER_SSOT
        assert contracts_41d.KEY_SENSITIVE_SOURCES is contracts_41c.KEY_SENSITIVE_SOURCES
        assert contracts_41d.DATA_SOURCE_MARKER_PATTERN is contracts_41c.DATA_SOURCE_MARKER_PATTERN
        assert contracts_41d.REQUIRED_SOP_SECTIONS is contracts_41c.REQUIRED_SOP_SECTIONS
        assert contracts_41d.SKILL_MD_MAX_LINES == contracts_41c.SKILL_MD_MAX_LINES


class TestTemplateContract:
    """模板微格式契约常量（Task 1.2 固化，多 Agent 并行防发散）。"""

    def test_template_required_sections_literal(self) -> None:
        """模板四段标题字面值逐字固化。"""
        assert contracts_41d.TEMPLATE_REQUIRED_SECTIONS == (
            "基本信息",
            "采集表格",
            "评分锚点",
            "数据缺口登记",
        )

    def test_required_references_trio(self) -> None:
        """references 三件套：data_fusion.md 替代 4-1c triangulation.md（决策 D3）。"""
        assert contracts_41d.REQUIRED_REFERENCES == ("data_fusion.md", "scoring_anchors.md", "workshop_guide.md")
        assert "triangulation.md" not in contracts_41d.REQUIRED_REFERENCES

    def test_template_files_table_complete(self) -> None:
        """模板文件名映射表：10 条目齐全且均为 .md（Story「模板文件命名」表固化）。"""
        files = contracts_41d.TEMPLATE_FILES
        assert set(files) == set(STORY_SSOT), "模板文件映射表必须覆盖全部 10 个 Skill"
        assert all(name.endswith(".md") for name in files.values()), "模板文件必须为 Markdown（决策 D1）"
        assert len(set(files.values())) == 10, "模板文件名不得重复"

    def test_scoring_anchor_reference_literal(self) -> None:
        """评分锚点引用字面串常量（模板断言用）。"""
        assert contracts_41d.SCORING_ANCHOR_REFERENCE == "references/scoring_anchors.md"

    def test_gap_register_header_literal(self) -> None:
        """数据缺口登记区表头字面串常量（模板断言用）。"""
        assert contracts_41d.GAP_REGISTER_HEADER == "| 字段 | 缺口描述 | 替代来源 |"

    def test_required_suffix_literal(self) -> None:
        """必填标注统一语法后缀常量（提取器剥离依据）。"""
        assert contracts_41d.REQUIRED_SUFFIX == "（必填）"


class TestSchemaLeafKeysExtraction:
    """叶子键递归展开函数（嵌套 Schema 展开约定，Round 1 D1-B 勘正补定）。"""

    def test_flat_schema_top_keys_are_leaves(self) -> None:
        """平铺 Schema（无嵌套 properties）退化为顶层键即叶子键。"""

        def _leaf(schema: dict[str, Any]) -> dict[str, bool]:
            return dict(contracts_41d.schema_leaf_keys(schema))

        flat = {
            "type": "object",
            "required": ["a"],
            "properties": {"a": {"type": "string"}, "b": {"type": "number"}},
        }
        leaves = _leaf(flat)
        assert set(leaves) == {"a", "b"}
        assert leaves["a"] is True and leaves["b"] is False

    def test_nested_object_expands_to_leaf_keys(self) -> None:
        """嵌套 object 展开为叶子键（顶层键不进比对集，以模板分区标题承载）。"""
        nested = {
            "type": "object",
            "required": ["internal_factors", "external_factors"],
            "properties": {
                "internal_factors": {
                    "type": "object",
                    "required": ["strengths", "weaknesses"],
                    "properties": {"strengths": {"type": "array"}, "weaknesses": {"type": "array"}},
                },
                "external_factors": {
                    "type": "object",
                    "required": ["opportunities", "threats"],
                    "properties": {"opportunities": {"type": "array"}, "threats": {"type": "array"}},
                },
            },
        }
        leaves = dict(contracts_41d.schema_leaf_keys(nested))
        assert set(leaves) == {"strengths", "weaknesses", "opportunities", "threats"}
        assert all(leaves.values()), "全部叶子在 required 链上（swot 四象限必填）"

    def test_array_items_expands_to_item_properties(self) -> None:
        """array 展开为其 items.properties（顶层 array 键不进比对集）。"""
        array_schema = {
            "type": "object",
            "required": ["business_units"],
            "properties": {
                "business_units": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "industry_attractiveness"],
                        "properties": {
                            "name": {"type": "string"},
                            "industry_attractiveness": {"type": "number"},
                            "competitive_strength": {"type": "number"},
                        },
                    },
                }
            },
        }
        leaves = dict(contracts_41d.schema_leaf_keys(array_schema))
        assert set(leaves) == {"name", "industry_attractiveness", "competitive_strength"}
        assert leaves["name"] is True and leaves["competitive_strength"] is False

    def test_double_nested_object_in_array(self) -> None:
        """array items 内嵌 object（vrio vrio_scores 形态）递归展开到底。"""
        vrio_like = {
            "type": "object",
            "required": ["resources"],
            "properties": {
                "resources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "vrio_scores"],
                        "properties": {
                            "name": {"type": "string"},
                            "vrio_scores": {
                                "type": "object",
                                "required": ["value", "rarity"],
                                "properties": {
                                    "value": {"type": "number"},
                                    "rarity": {"type": "number"},
                                    "imitability": {"type": "number"},
                                },
                            },
                        },
                    },
                }
            },
        }
        leaves = dict(contracts_41d.schema_leaf_keys(vrio_like))
        assert set(leaves) == {"name", "value", "rarity", "imitability"}
        assert leaves["value"] is True and leaves["imitability"] is False


class TestTemplateFieldExtractor:
    """模板字段提取器（Markdown 表格字段列 + 「（必填）」后缀剥离）。"""

    def test_extracts_fields_with_required_suffix_stripped(self) -> None:
        """采集表格区表格行字段列提取 + 后缀剥离 + 必填标记记录。"""
        template = """# SWOT 四象限采集矩阵

## 基本信息

| 字段 | 说明 |
| --- | --- |
| 分析对象 | 目标企业 |

## 采集表格

### internal_factors

| 字段 | 评分/描述 | 证据来源 |
| --- | --- | --- |
| strengths（必填） | 内部优势 | 工作坊 |
| weaknesses（必填） | 内部劣势 | 工作坊 |

### external_factors

| 字段 | 评分/描述 | 证据来源 |
| --- | --- | --- |
| opportunities（必填） | 外部机会 | 外部印证 |
| threats（必填） | 外部威胁 | 外部印证 |

## 评分锚点

评分标准见 references/scoring_anchors.md。

## 数据缺口登记

| 字段 | 缺口描述 | 替代来源 |
| --- | --- | --- |
"""
        fields = contracts_41d.extract_template_fields(template)
        assert fields == {
            "strengths": True,
            "weaknesses": True,
            "opportunities": True,
            "threats": True,
        }

    def test_basic_info_section_not_collected(self) -> None:
        """基本信息区表格字段不进入比对集（仅采集表格区参与叶子键比对）。"""
        template = """# 模板

## 基本信息

| 字段 | 说明 |
| --- | --- |
| 分析对象 | 目标企业 |

## 采集表格

### internal_factors

| 字段 | 描述 |
| --- | --- |
| strengths（必填） | 优势 |

## 评分锚点

见 references/scoring_anchors.md。

## 数据缺口登记

| 字段 | 缺口描述 | 替代来源 |
| --- | --- | --- |
"""
        fields = contracts_41d.extract_template_fields(template)
        assert "分析对象" not in fields, "基本信息区字段不得进入比对集"
        assert fields == {"strengths": True}

    def test_non_required_field_without_suffix(self) -> None:
        """非 required 字段无后缀（后缀语法统一，有/无不匹配 required 链均失败）。"""
        template = """# 模板

## 基本信息

## 采集表格

### data

| 字段 | 描述 |
| --- | --- |
| objectives（必填） | 目标 |
| baseline_data | 基线 |

## 评分锚点

见 references/scoring_anchors.md。

## 数据缺口登记

| 字段 | 缺口描述 | 替代来源 |
| --- | --- | --- |
"""
        fields = contracts_41d.extract_template_fields(template)
        assert fields == {"objectives": True, "baseline_data": False}


class TestAssertionFunctions:
    """契约断言函数存在性与签名（10 个 Skill 单测统一 import 入口）。"""

    def test_assert_functions_exist_with_expected_signature(self) -> None:
        """五个断言函数存在且签名一致（slug + metadata/document）。"""
        for func_name in (
            "assert_data_sources_contract",
            "assert_io_schema_contract",
            "assert_sop_maturity",
            "assert_cross_consistency",
            "assert_template_schema_alignment",
        ):
            func = getattr(contracts_41d, func_name, None)
            assert callable(func), f"缺少断言函数 {func_name}"
            params = tuple(inspect.signature(func).parameters)
            assert params in (("slug", "metadata"), ("slug", "document")), f"{func_name} 签名异常: {params}"
