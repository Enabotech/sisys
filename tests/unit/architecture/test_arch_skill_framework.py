"""内部框架型 Skills — SDD 架构约束验证测试（Story 4.1e Task 10）

四类结构（范本 test_arch_skill_mixed_data.py）：
1. 三方一致性：契约库 SSOT ↔ 7 个 SKILL.md frontmatter ↔ strategic_tool_catalog
   兼容方向（catalog required ⊆ frontmatter required——org-design 四维增强 D10）
2. 23 Skills 最终态闭环：SLUG_TO_TOOL_ID 全集 == 三契约库并集（6+10+7）——
   16 声明外部源 + 7 空声明的分类学终态（本 Story 收官语义）
3. 生产链路 wiring 回归：三个 wiring 文件零 src.infrastructure import + 源码含
   tool_metadata 特征串 + 两 use case 文件 load_sop（engine 豁免）+
   ToolExecutionEngine.__init__ 签名锁定（零引擎改动声明的回归断言）
4. Skills 内容约束 + Schema 合法性强化（D11：23 条目 Draft7 check_schema +
   build_min_arguments 实例经 JsonSchemaValidatorImpl 校验）+ 派生收敛验证（D2）
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from src.application.ports.skill_loader import SkillDocument
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.skills.loader import InMemorySkillLoader
from src.application.skills.skill_manifest import SLUG_TO_TOOL_ID, TOOL_ID_TO_SLUG
from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG
from src.domain.entities.tool import Tool
from src.infrastructure.validation.jsonschema_validator import JsonSchemaValidatorImpl
from tests.unit.application.skills.skill_data_collection_contracts import SKILL_DATA_SOURCES
from tests.unit.application.skills.skill_framework_contracts import (
    FRAMEWORK_SKILL_SLUGS,
    NO_EXTERNAL_SOURCE_SLUGS,
    SKILL_MD_MAX_LINES,
    SKILLS_ROOT,
    build_min_arguments,
    load_io_contract,
)
from tests.unit.application.skills.skill_mixed_data_contracts import MIXED_SKILL_DATA_SOURCES

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"

# 7 个 4-1e 目标（顺序 = 契约库 FRAMEWORK_SKILL_SLUGS key 顺序）
TARGET_SLUGS: tuple[str, ...] = tuple(FRAMEWORK_SKILL_SLUGS)

# wiring 回归文件（4-1d wiring 断言先例整类复用——engine 对 load_sop 豁免）
WIRING_FILES: tuple[Path, ...] = (
    SRC_ROOT / "application" / "use_cases" / "strategic_analysis.py",
    SRC_ROOT / "application" / "use_cases" / "run_tool_chain.py",
    SRC_ROOT / "application" / "services" / "tool_execution_engine.py",
)


@pytest.fixture
async def document(slug: str) -> SkillDocument:
    """真实加载目标 Skill 的 L2 SkillDocument。"""
    loader = InMemorySkillLoader()
    return await loader.load_sop(slug)


def _extract_imports(path: Path) -> list[str]:
    """提取模块级 import 目标（架构依赖方向断言用）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


# =============================================================================
# 1. 三方一致性（契约库 SSOT ↔ frontmatter ↔ catalog 兼容方向）
# =============================================================================


class TestThreeWayConsistency:
    """契约库 ↔ SKILL.md frontmatter ↔ catalog 三方一致（兼容方向：catalog ⊆ frontmatter）。"""

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    async def test_frontmatter_schema_matches_catalog_superset(self, slug: str, document: SkillDocument) -> None:
        """frontmatter schema 是 catalog 的增强超集（既有 required/properties 零删除——R5）。"""
        slug_to_tool = {TOOL_ID_TO_SLUG.get(t.tool_id): t for t in TOOL_CATALOG}
        catalog_tool = slug_to_tool[slug]
        actual_input = document.frontmatter.input_schema
        assert set(catalog_tool.input_schema.get("required", [])) <= set(actual_input.get("required", [])), (
            f"{slug}: catalog 既有 input required 字段被删除"
        )
        assert set(catalog_tool.input_schema.get("properties", {})) <= set(actual_input.get("properties", {})), (
            f"{slug}: catalog 既有 input properties 键被删除"
        )
        assert set(catalog_tool.output_schema.get("properties", {})) <= set(
            document.frontmatter.output_schema.get("properties", {})
        ), f"{slug}: catalog 既有 output properties 键被删除"

    async def test_org_design_galbraith_four_dimensions_added(self) -> None:
        """org-design D10 四维扩展落地：catalog org_structure 含四维子容器（唯一预期增强）。"""
        slug_to_tool = {TOOL_ID_TO_SLUG.get(t.tool_id): t for t in TOOL_CATALOG}
        catalog_tool = slug_to_tool["org-design-framework"]
        org_properties = catalog_tool.input_schema["properties"]["org_structure"]["properties"]
        for dimension in ("strategy", "processes", "rewards", "people"):
            assert dimension in org_properties, f"catalog org_structure 缺少 Galbraith 维度 {dimension}"
            assert org_properties[dimension]["type"] == "object", f"{dimension} 应为子容器"
        # 既有三字段零删除
        for legacy in ("functions", "reporting_lines", "decentralization_level"):
            assert legacy in org_properties, f"catalog org_structure 既有字段 {legacy} 被删除"


# =============================================================================
# 2. 23 Skills 最终态闭环（分类学终态：16 声明 + 7 空声明 == 23）
# =============================================================================


class TestFinalStateClosure:
    """23 Skills 最终态闭环：SLUG_TO_TOOL_ID 全集 == 三契约库并集（6+10+7）。"""

    def test_manifest_union_three_contracts(self) -> None:
        """manifest 全集 == 4-1c ∪ 4-1d ∪ 4-1e 三库并集（无遗漏无多余）。"""
        union = set(SKILL_DATA_SOURCES) | set(MIXED_SKILL_DATA_SOURCES) | set(FRAMEWORK_SKILL_SLUGS)
        assert len(union) == 23, f"三库并集应为 23，实际 {len(union)}"
        assert set(SLUG_TO_TOOL_ID) == union, (
            f"manifest 与三库并集不一致: 多余 {set(SLUG_TO_TOOL_ID) - union} / 缺失 {union - set(SLUG_TO_TOOL_ID)}"
        )

    def test_taxonomy_sixteen_declared_seven_empty(self) -> None:
        """分类学终态：16 声明外部源 + 7 空声明（6 外部 + 10 混合 + 7 纯内部）。"""
        assert len(SKILL_DATA_SOURCES) == 6
        assert len(MIXED_SKILL_DATA_SOURCES) == 10
        assert len(FRAMEWORK_SKILL_SLUGS) == 7
        assert len(NO_EXTERNAL_SOURCE_SLUGS) == 7, "派生无外部源集合应恰为 7"

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    async def test_framework_skills_data_sources_empty_final_state(self, slug: str) -> None:
        """7 个纯内部框架 Skill data_sources 空 tuple 终态（一等不变量——D1）。"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        assert document.frontmatter.data_sources == (), f"纯内部框架 Skill {slug} 的 data_sources 恒空不变量被破坏"


# =============================================================================
# 3. 生产链路 wiring 回归（零引擎改动声明的回归断言——4-1d 先例整类复用）
# =============================================================================


class TestWiringRegression:
    """wiring 文件依赖方向 + 接线特征串 + Engine 签名锁定（本 Story 零改动回归）。"""

    @pytest.mark.parametrize("path", WIRING_FILES)
    def test_wiring_files_no_infrastructure_import(self, path: Path) -> None:
        """use case / engine 文件不 import infrastructure（六边形依赖方向）。"""
        assert path.is_file(), f"wiring 文件不存在: {path}"
        for module in _extract_imports(path):
            assert not module.startswith("src.infrastructure"), f"{path.name}: 违规 import {module}"

    @pytest.mark.parametrize("path", WIRING_FILES)
    def test_wiring_files_carry_existing_feature_strings(self, path: Path) -> None:
        """源码含既有接线特征串（4-1c 交付未被本 Story 破坏——engine 对 load_sop 豁免）。"""
        source = path.read_text(encoding="utf-8")
        assert "tool_metadata" in source, f"{path.name}: 缺少 tool_metadata 接线特征串"
        if path.name != "tool_execution_engine.py":
            assert "load_sop" in source, f"{path.name}: 缺少 load_sop 接线特征串"

    def test_engine_init_signature_locked(self) -> None:
        """ToolExecutionEngine.__init__ 签名锁定（Story 4.4 AC-7.4 BDD 断言保护）。"""
        params = list(inspect.signature(ToolExecutionEngine.__init__).parameters)
        assert params == ["self", "llm_client", "sandbox", "retry_policy", "tool_execution_repository"]


# =============================================================================
# 4. Skills 内容约束 + Schema 合法性强化（D11）+ 派生收敛验证（D2）
# =============================================================================


class TestSkillContentConstraints:
    """7 个 SKILL.md 内容约束终态（≤500 行 + 必需字段 + version 1.0.0）。"""

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    async def test_skill_md_line_count_within_500(self, slug: str) -> None:
        skill_md = SKILLS_ROOT / slug / "SKILL.md"
        line_count = len(skill_md.read_text(encoding="utf-8").splitlines())
        assert line_count <= SKILL_MD_MAX_LINES, f"{slug}: SKILL.md {line_count} 行超限"

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    async def test_frontmatter_required_fields_and_version(self, slug: str, document: SkillDocument) -> None:
        meta = document.frontmatter
        assert meta.slug == slug
        assert meta.tool_name
        assert meta.version == "1.0.0", f"{slug}: version 应保持 1.0.0（成熟化不升版，4-1d 先例）"


class TestSchemaLegalityHardening:
    """Schema 合法性强化（D11：23 条目 Draft7 check_schema + 实例校验——4-3 基建测试级衔接）。

    断言面 = frontmatter/yaml 条目侧，与 4.1 注册验收（catalog 侧 23 工具 46 schema
    check_schema）互补不重复。
    """

    def test_all_23_yaml_entries_pass_draft7_check_schema(self) -> None:
        """yaml SSOT 23 条目 input/output schema 全部通过 Draft7 结构校验。"""
        from jsonschema import Draft7Validator

        all_slugs = set(SKILL_DATA_SOURCES) | set(MIXED_SKILL_DATA_SOURCES) | set(FRAMEWORK_SKILL_SLUGS)
        for slug in sorted(all_slugs):
            contract = load_io_contract(slug)
            Draft7Validator.check_schema(contract["input_schema"])
            Draft7Validator.check_schema(contract["output_schema"])

    def test_framework_min_arguments_pass_jsonschema_validator(self) -> None:
        """7 条目 build_min_arguments 实例经 JsonSchemaValidatorImpl.validate_arguments 通过。

        以 yaml input_schema 构造 Tool 实体走 4-3 基建校验链（测试级衔接，
        不改生产链路）。
        """
        validator = JsonSchemaValidatorImpl()
        for slug in FRAMEWORK_SKILL_SLUGS:
            contract = load_io_contract(slug)
            tool = Tool(
                tool_id=SLUG_TO_TOOL_ID[slug],
                name=slug,
                slug=slug,
                input_schema=contract["input_schema"],
                output_schema=contract["output_schema"],
            )
            result = validator.validate_arguments(tool, build_min_arguments(slug))
            assert result.is_valid, f"{slug}: 最小实例未通过 schema 校验: {result.violations}"

    def test_framework_output_schema_without_data_sources_provenance(self) -> None:
        """D6 惯例偏离登记：7 条目 output_schema 均不含 data_sources 溯源键。"""
        for slug in FRAMEWORK_SKILL_SLUGS:
            contract = load_io_contract(slug)
            assert "data_sources" not in contract["output_schema"].get("properties", {}), (
                f"{slug}: 纯内部型 output_schema 不应含 data_sources 溯源键（D6）"
            )
            assert "data_sources" not in contract["output_schema"].get("required", []), (
                f"{slug}: 纯内部型 output_schema required 不应含 data_sources（D6）"
            )


class TestDerivedConvergence:
    """派生收敛验证（D2：NON_TARGET_SLUGS 三副本 import 契约库，字面清单零残留）。"""

    def test_no_literal_slug_list_residual_in_regression_files(self) -> None:
        """三处回归网用例的字面清单零残留（grep 语义——import 派生已收敛）。"""
        regression_files = [
            REPO_ROOT / "tests" / "unit" / "application" / "skills" / "test_pestel_analysis_data_collection.py",
            REPO_ROOT / "tests" / "unit" / "architecture" / "test_arch_skill_data_collection.py",
            REPO_ROOT / "tests" / "unit" / "architecture" / "test_arch_skill_mixed_data.py",
        ]
        for file_path in regression_files:
            source = file_path.read_text(encoding="utf-8")
            # 字面清单形态检测：slug 作为带引号的元组项出现（import 派生后应为零）
            literal_hits = [line.strip() for line in source.splitlines() if '"business-model-canvas",' in line]
            assert not literal_hits, f"{file_path.name}: NON_TARGET_SLUGS 字面清单残留: {literal_hits}"
            assert "NO_EXTERNAL_SOURCE_SLUGS" in source, f"{file_path.name}: 应 import NO_EXTERNAL_SOURCE_SLUGS 派生（D2 收敛）"

    def test_derived_set_equals_framework_slugs(self) -> None:
        """派生集合 == 本 Story 7 slug（判别力保留——非空且精确）。"""
        assert set(NO_EXTERNAL_SOURCE_SLUGS) == set(FRAMEWORK_SKILL_SLUGS)
