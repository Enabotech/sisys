"""Story 4.1d Task 1.1 — 契约库永久自检测试。

断言 `skill_mixed_data_contracts.py` 的 SSOT 常量与 Story「端口与数据契约」
声明表逐字一致，防实施期擅改 SSOT（永久断言，有长期判别价值——Round 1 D2-B 勘正：
原稿「临时导入断言」未定去向，改为永久自检测试）。

测试内的独立硬编码基准表与契约库常量双向比对——任何一侧被擅改即红
（变异演示判别力来源：改契约库任一条目 → 本测试红）。
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from typing import Any

import pytest

import tests.unit.application.skills.skill_data_collection_contracts as contracts_41c
import tests.unit.application.skills.skill_mixed_data_contracts as contracts_41d
from src.application.ports.skill_loader import SkillDocument
from src.application.skills.loader import InMemorySkillLoader

# Story 4.1d「端口与数据契约」SSOT 声明表逐字基准（独立副本，与契约库比对）
STORY_SSOT: dict[str, tuple[str, ...]] = {
    "swot-tows": ("newsapi", "tavily"),
    "ansoff-matrix": ("world-bank", "imf"),
    "value-curve-analysis": ("tavily", "newsapi"),
    "ge-mckinsey-matrix": ("world-bank", "tavily"),
    "space-matrix": ("world-bank", "imf"),
    "value-chain-analysis": ("tavily", "china-nbs"),
    "vrio-framework": ("uspto", "epo-ops", "tavily"),
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
        """全部声明源 ∈ 11 个注册适配器集合（合法值约束——4-1f 三新源入册）。"""
        for slug, sources in contracts_41d.MIXED_SKILL_DATA_SOURCES.items():
            for name in sources:
                assert name in contracts_41c.ADAPTER_SSOT, f"{slug}: 源 {name} 不在 11 个注册适配器中"

    def test_adapter_ssot_quadruple_structure(self) -> None:
        """ADAPTER_SSOT 四元组结构基准（4-1f D6）：11 源 × (url, api_type, ttl, required_fields)。"""
        assert len(contracts_41c.ADAPTER_SSOT) == 11, f"应 11 源（8 既有 + 3 新），实际 {len(contracts_41c.ADAPTER_SSOT)}"
        for name, entry in contracts_41c.ADAPTER_SSOT.items():
            assert len(entry) == 4, f"{name}: SSOT 条目应为四元组，实际 {len(entry)} 元: {entry}"
            url, api_type, ttl, required_fields = entry
            assert url.startswith("http"), f"{name}: url 非法 {url}"
            assert api_type in ("rest_json", "sdmx_json", "csv_download", "crawler"), f"{name}: api_type 非法 {api_type}"
            assert 60 <= ttl <= 2592000, f"{name}: ttl 越界 {ttl}"
            assert isinstance(required_fields, tuple) and required_fields, f"{name}: required_fields 应为非空 tuple"
        assert set(contracts_41c.ADAPTER_SSOT) >= {"epo-ops", "sec-edgar", "comtrade"}, "4-1f 三新源应入册 SSOT"

    def test_unified_two_source_policy(self) -> None:
        """2 源基线 + 4-1f 增补豁免表（D2 修订——epics 4.1f 任务 6 授权）。

        基线：混合数据 Skill 恰好声明 2 个源且不重复；豁免表逐 Skill 登记显式增补
        （未登记的增补即红——防漂移语义保留）。vrio-framework 经 epics 授权增补
        epo-ops（专利域第二口径，3 源）。
        """
        exempted_source_counts = {"vrio-framework": 3}
        for slug, sources in contracts_41d.MIXED_SKILL_DATA_SOURCES.items():
            expected_count = exempted_source_counts.get(slug, 2)
            assert len(sources) == expected_count, (
                f"{slug}: 声明源数 {len(sources)} != {expected_count}（2 源基线 D2 / 4-1f 豁免）"
            )
            assert len(set(sources)) == len(sources), f"{slug}: 声明源重复 {sources}"

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
        # yaml = 4-1c 6 条 + 4-1d 10 条 + 4-1e 7 条（三方并集——4-1e Task 1.4 预调整）
        from tests.unit.application.skills.skill_framework_contracts import FRAMEWORK_SKILL_SLUGS

        assert yaml_slugs == mixed_slugs | set(contracts_41c.SKILL_DATA_SOURCES) | set(FRAMEWORK_SKILL_SLUGS), (
            "yaml 条目集合应恰好等于 4-1c ∪ 4-1d ∪ 4-1e 三契约库并集"
        )


class TestSharedConstantsSingleSource:
    """跨 Story 共享常量一律 import 4-1c 契约库（R2-F3 单一来源，D6 决策）。"""

    def test_shared_constants_are_imported_not_copied(self) -> None:
        """六共享常量必须与 4-1c 契约库同一对象（identity 断言，防复制漂移）。

        SKILL_MD_MAX_LINES 用 ==（int 无对象同一性语义，R2-F2 注记）；
        其余五常量为 tuple/Pattern/Path 对象，is 断言成立。EXPECTED_REQUIRED_FIELDS
        已随 4-1f 四元组化移除（D6——查表断言取代统一比对，双真相源漂移风险消除）。
        """
        assert contracts_41d.ADAPTER_SSOT is contracts_41c.ADAPTER_SSOT
        assert contracts_41d.KEY_SENSITIVE_SOURCES is contracts_41c.KEY_SENSITIVE_SOURCES
        assert contracts_41d.DATA_SOURCE_MARKER_PATTERN is contracts_41c.DATA_SOURCE_MARKER_PATTERN
        assert contracts_41d.REQUIRED_SOP_SECTIONS is contracts_41c.REQUIRED_SOP_SECTIONS
        assert contracts_41d.SKILL_MD_MAX_LINES == contracts_41c.SKILL_MD_MAX_LINES
        assert contracts_41d.SKILLS_ROOT is contracts_41c.SKILLS_ROOT

    def test_required_fields_quadruple_values_locked(self) -> None:
        """required_fields 四元组第四项值级独立基准（4-1f D6 改写 R2-F12 绊线）。

        8 既有源锁定 ("indicator","value")（零漂移）+ 3 新源锁定定制值——
        SSOT 与 16 个 SKILL.md frontmatter 被同步同改时全绿无告警的防线；
        改任一源字段集时须显式修改本基准（变更登记绊线语义延续）。
        """
        legacy_expected = ("indicator", "value")
        new_source_expected = {
            "epo-ops": ("title", "applicant", "filing_date"),
            "sec-edgar": ("company", "form", "filed_at"),
            "comtrade": ("cmd_code", "trade_value", "period"),
        }
        for name, (_, _, _, required_fields) in contracts_41c.ADAPTER_SSOT.items():
            if name in new_source_expected:
                assert required_fields == new_source_expected[name], (
                    f"{name}: 新源 required_fields 应为 {new_source_expected[name]}，实际 {required_fields}"
                )
            else:
                assert required_fields == legacy_expected, (
                    f"{name}: 既有源 required_fields 应零漂移 {legacy_expected}，实际 {required_fields}"
                )


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

    def test_typeless_properties_node_rejected(self) -> None:
        """守卫 1（R1-F4）：含 properties 但未声明 type: object 的节点 → 断言失败。

        防静默误分类：无守卫时该节点落入叶子分支被当叶子比对（子键被吞），
        模板两侧同漏即假一致。消息须含键路径（定位漂移节点）。
        """
        typeless = {
            "type": "object",
            "properties": {
                "container": {"properties": {"x": {"type": "string"}}, "required": ["x"]},
            },
        }
        with pytest.raises(AssertionError, match=r"container.*含 properties 但未声明 type: object"):
            contracts_41d.schema_leaf_keys(typeless)

    def test_empty_properties_node_rejected(self) -> None:
        """守卫 1 分支二（R2-F11①）：properties 为空集（无论 type）→ 断言失败。

        空 properties 的节点无从承载分区内容——与「缺 type」分支分列文案，
        防误导性错误消息（此前两类节点共用同一句「未声明 type: object」）。
        """
        empty_props = {
            "type": "object",
            "properties": {"container": {"type": "object", "properties": {}}},
        }
        with pytest.raises(AssertionError, match=r"container.*的 properties 为空"):
            contracts_41d.schema_leaf_keys(empty_props)

    def test_duplicate_leaf_across_containers_rejected(self) -> None:
        """守卫 2（R1-F4）：跨容器重名叶子 → 断言失败（防 last-wins 覆盖 required 语义）。"""
        duplicated = {
            "type": "object",
            "properties": {
                "c1": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"name": {"type": "string"}},
                },
                "c2": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
            },
        }
        with pytest.raises(AssertionError, match=r"跨容器重名.*c2\.name.*与.*c1\.name"):
            contracts_41d.schema_leaf_keys(duplicated)

    def test_top_level_container_keys_extraction(self) -> None:
        """顶层容器键提取（R1-F3）：仅顶层、与叶子展开判定式共用。

        - swot 形态：双 object 容器均取
        - vrio 形态：二层嵌套容器（resources[].vrio_scores）不取——模板 `###` 只承载顶层
        - 平铺 Schema：无容器键
        """
        swot_like = {
            "type": "object",
            "properties": {
                "internal_factors": {"type": "object", "properties": {"strengths": {"type": "array"}}},
                "external_factors": {"type": "object", "properties": {"opportunities": {"type": "array"}}},
            },
        }
        assert contracts_41d.schema_top_level_container_keys(swot_like) == ("internal_factors", "external_factors")

        vrio_like = {
            "type": "object",
            "properties": {
                "resources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "vrio_scores": {"type": "object", "properties": {"value": {"type": "number"}}},
                        },
                    },
                },
                "note": {"type": "string"},
            },
        }
        assert contracts_41d.schema_top_level_container_keys(vrio_like) == ("resources",)

        flat = {"type": "object", "properties": {"a": {"type": "string"}}}
        assert contracts_41d.schema_top_level_container_keys(flat) == ()


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

    def test_inconsistent_multi_row_required_marks_aggregate_false(self) -> None:
        """边界（R1-F1）：同字段多行必填标注不一致 → all 聚合计非必填。

        docstring 明文的聚合语义（任一行缺「（必填）」即非必填，防末行覆盖漏检）
        此前无测试锁定——本用例补判别力回归保护。
        """
        template = """# 模板

## 基本信息

## 采集表格

### data

| 字段 | 描述 |
| --- | --- |
| strengths（必填） | 优势一 |
| strengths | 优势二（漏标必填）

## 评分锚点

见 references/scoring_anchors.md。

## 数据缺口登记

| 字段 | 缺口描述 | 替代来源 |
| --- | --- |
"""
        fields = contracts_41d.extract_template_fields(template)
        assert fields == {"strengths": False}, "不一致双行须聚合为非必填（后续与 required 链比对即红）"

    def test_missing_collection_section_returns_empty(self) -> None:
        """边界（R1-F1）：缺「## 采集表格」段 → 返回空 dict（后续双向比对必红，非崩溃）。"""
        template = """# 模板

## 基本信息

| 字段 | 说明 |
| --- | --- |
| 分析对象 | 目标企业 |
"""
        assert contracts_41d.extract_template_fields(template) == {}

    def test_gap_register_fields_not_collected(self) -> None:
        """边界（R1-F1）：数据缺口登记区的裸字段名不进比对集（区域截断防污染）。

        缺口区含与叶子键撞名的裸字段（swot 真实模板 opportunities/weaknesses 形态）
        ——若区域截取正则被破坏（如只认 ### 分区），缺口区字段会静默并入比对集
        使断言恒红或掩盖真实漂移。本用例锁定截断边界。
        """
        template = """# 模板

## 基本信息

## 采集表格

### data

| 字段 | 描述 |
| --- | --- |
| strengths（必填） | 优势 |

## 评分锚点

见 references/scoring_anchors.md。

## 数据缺口登记

| 字段 | 缺口描述 | 替代来源 |
| --- | --- | --- |
| opportunities | 行业机会对标数据缺口 | 外部 Agent 采集 |
| weaknesses | 内部劣势证据缺口 | 工作坊补采 |
"""
        fields = contracts_41d.extract_template_fields(template)
        assert fields == {"strengths": True}, "缺口登记区字段不得进入比对集"
        assert "opportunities" not in fields and "weaknesses" not in fields


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


class TestAssertionFailurePaths:
    """断言函数失败路径（R1-F1：判别力回归保护——函数被掏空或语义弱化即红）。

    全部基于真实加载的 swot-tows document/metadata 构造漂移副本
    （dataclasses.replace 构造 frozen dataclass 新实例，零 mock、零副作用），
    match= 钉死目标断言消息——防「因错误的原因变绿」的空洞通过。
    """

    @pytest.fixture
    async def document(self) -> SkillDocument:
        """真实加载 swot-tows 的 L2 SkillDocument（漂移副本的构造基线）。"""
        loader = InMemorySkillLoader()
        return await loader.load_sop("swot-tows")

    async def test_data_sources_drift_detected(self, document: SkillDocument) -> None:
        """[A] 删源漂移：声明源被删 → name 集合断言红。"""
        drifted = replace(document.frontmatter, data_sources=document.frontmatter.data_sources[:1])
        with pytest.raises(AssertionError, match="name 集合与 SSOT 不一致"):
            contracts_41d.assert_data_sources_contract("swot-tows", drifted)

    async def test_data_sources_required_fields_drift_detected(self, document: SkillDocument) -> None:
        """[A] required_fields 漂移（R1-F5 判别力证明）：改值 → 逐字断言红（原仅非空断言不红）。"""
        first_ref = document.frontmatter.data_sources[0]
        drifted_ref = replace(first_ref, required_fields=("indicator",))
        drifted = replace(document.frontmatter, data_sources=(drifted_ref, *document.frontmatter.data_sources[1:]))
        with pytest.raises(AssertionError, match="required_fields 漂移"):
            contracts_41d.assert_data_sources_contract("swot-tows", drifted)

    async def test_io_schema_drift_detected(self, document: SkillDocument) -> None:
        """[A] Schema 漂移：input_schema 与契约文件不等 → 逐字断言红。"""
        drifted_schema = {**document.frontmatter.input_schema, "required": []}
        drifted = replace(document.frontmatter, input_schema=drifted_schema)
        with pytest.raises(AssertionError, match="input_schema 与契约文件不一致"):
            contracts_41d.assert_io_schema_contract("swot-tows", drifted)

    async def test_sop_missing_section_detected(self, document: SkillDocument) -> None:
        """[B] 章节缺失：失败处理章节标题被改名 → 必备章节断言红。"""
        drifted = replace(document, body=document.body.replace("失败处理", "故障处理", 1))
        with pytest.raises(AssertionError, match="SOP 缺少必备章节"):
            contracts_41d.assert_sop_maturity("swot-tows", drifted)

    async def test_cross_consistency_undeclared_marker_detected(self, document: SkillDocument) -> None:
        """[C] 未声明标记：body 追加白名单外源标记 → 双向断言红。"""
        drifted = replace(document, body=document.body + '\n$DATA_SOURCE("world-bank", "外部基准查询")\n')
        with pytest.raises(AssertionError, match="跨循环一致性破坏"):
            contracts_41d.assert_cross_consistency("swot-tows", drifted)

    async def test_template_leaf_key_drift_detected(self, document: SkillDocument) -> None:
        """[D] 叶子键漂移：Schema 删整个容器 → 叶子缺失方向断言红。"""
        schema = document.frontmatter.input_schema
        drifted_props = {k: v for k, v in schema["properties"].items() if k != "external_factors"}
        drifted_meta = replace(document.frontmatter, input_schema={**schema, "properties": drifted_props})
        with pytest.raises(AssertionError, match="模板字段与 Schema 叶子键不一致"):
            contracts_41d.assert_template_schema_alignment("swot-tows", replace(document, frontmatter=drifted_meta))

    async def test_template_section_title_drift_detected(self, document: SkillDocument) -> None:
        """[D] 分区标题漂移（R1-F3 判别力证明）：仅改顶层容器键名（叶子集不变、
        必填标注不变）→ 分区标题双向断言红（此前该漂移方向全绿）。"""
        schema = document.frontmatter.input_schema
        drifted_props = {
            ("internal-factors" if key == "internal_factors" else key): value for key, value in schema["properties"].items()
        }
        drifted_meta = replace(document.frontmatter, input_schema={**schema, "properties": drifted_props})
        with pytest.raises(AssertionError, match="分区标题与 Schema 顶层容器键不一致"):
            contracts_41d.assert_template_schema_alignment("swot-tows", replace(document, frontmatter=drifted_meta))
