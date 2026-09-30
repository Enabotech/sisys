"""混合数据型 Skills — SDD 架构约束验证测试（Story 4.1d Task 13）

四类结构（范本 test_arch_skill_data_collection.py，不复刻已删除的恒真模式）：
1. 常量区：10 Skills slug 清单（import 契约库 SSOT 唯一来源）+ 7 个 4-1e 非目标
2. 三方一致性：SSOT 表 ↔ 10 个 SKILL.md frontmatter data_sources ↔ 适配器
   get_metadata()（涉及源真实实例化，Key 敏感源占位 Key、china-nbs 注入
   AsyncMock crawler，仅读元数据零网络）
3. 生产链路回归：三个 wiring 文件零 src.infrastructure import + 源码含
   tool_metadata/load_sop 特征串 + ToolExecutionEngine.__init__ 签名锁定
   （零 Python 生产代码改动声明的回归断言）
4. Skills 内容约束：10 个 SKILL.md ≤500 行 + frontmatter 必需字段 + version
   1.0.0 不变 + 16 Skill 最终态全量断言（SSOT 并集内全部物理声明非空且
   name 集合 == SSOT——Subtask 1.4 中间态安全化的最终态闭环）+ 7 个 4-1e
   目标空 tuple + 4-1c 6 Skill 声明不变
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.skills.loader import InMemorySkillLoader
from src.domain.ports.data_source import DataSourcePort
from tests.unit.application.skills.skill_data_collection_contracts import (
    ADAPTER_SSOT,
    DATA_SOURCE_MARKER_PATTERN,
    SKILL_DATA_SOURCES,
    SKILL_MD_MAX_LINES,
    SKILLS_ROOT,
)
from tests.unit.application.skills.skill_framework_contracts import NO_EXTERNAL_SOURCE_SLUGS
from tests.unit.application.skills.skill_mixed_data_contracts import MIXED_SKILL_DATA_SOURCES

# =============================================================================
# 1. 常量区（SSOT：import 契约库唯一来源，禁止复制——R2-F3）
# =============================================================================

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
# SKILLS_ROOT / SKILL_MD_MAX_LINES / DATA_SOURCE_MARKER_PATTERN 一律 import 4-1c
# 契约库单一来源（R1-F9：消除本文件出生时的常量复制，D6/R2-F3 政策收尾）

# 10 个 4-1d 目标（顺序 = 契约库 MIXED_SKILL_DATA_SOURCES key 顺序）
TARGET_SLUGS: tuple[str, ...] = tuple(MIXED_SKILL_DATA_SOURCES.keys())

# 无外部源型 Skill（23 全量 − 4-1c 声明源 − 4-1d 声明源，派生自 4-1e 契约库
# NO_EXTERNAL_SOURCE_SLUGS——D2 收敛，字面清单零复制）：data_sources 恒空不变量
NON_TARGET_SLUGS: tuple[str, ...] = NO_EXTERNAL_SOURCE_SLUGS

# 4-1d 涉及源（7 个；world-bank / imf / uspto / epo-ops / newsapi / tavily / china-nbs——4-1f vrio 增补）
MIXED_INVOLVED_SOURCES: tuple[str, ...] = tuple({name for sources in MIXED_SKILL_DATA_SOURCES.values() for name in sources})

# 生产链路 wiring 文件（零改动回归断言对象）
WIRING_FILES: tuple[Path, ...] = (
    SRC_ROOT / "application" / "use_cases" / "strategic_analysis.py",
    SRC_ROOT / "application" / "use_cases" / "run_tool_chain.py",
    SRC_ROOT / "application" / "services" / "tool_execution_engine.py",
)


def _extract_imports(path: Path) -> set[str]:
    """提取 Python 文件的全部 import 模块名（AST 静态分析）"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _build_involved_adapters() -> dict[str, DataSourcePort]:
    """实例化 4-1d 涉及的 7 个适配器（Key 敏感源占位 Key/凭据；china-nbs 注入
    AsyncMock crawler；仅读取 get_metadata() 元数据，零网络调用）。"""
    from src.infrastructure.config.china_nbs import ChinaNBSConfig
    from src.infrastructure.config.epo_ops import EpoOpsConfig
    from src.infrastructure.config.imf import IMFConfig
    from src.infrastructure.config.newsapi import NewsAPIConfig
    from src.infrastructure.config.tavily import TavilyConfig
    from src.infrastructure.config.uspto import USPTOConfig
    from src.infrastructure.config.worldbank import WorldBankConfig
    from src.infrastructure.external_services.datasources.china_nbs_adapter import ChinaNBSAdapter
    from src.infrastructure.external_services.datasources.epo_ops_adapter import EpoOpsAdapter
    from src.infrastructure.external_services.datasources.imf_adapter import IMFAdapter
    from src.infrastructure.external_services.datasources.newsapi_adapter import NewsAPIAdapter
    from src.infrastructure.external_services.datasources.tavily_adapter import TavilyAdapter
    from src.infrastructure.external_services.datasources.uspto_adapter import USPTOAdapter
    from src.infrastructure.external_services.datasources.worldbank_adapter import WorldBankAdapter

    return {
        "world-bank": WorldBankAdapter(config=WorldBankConfig()),
        "imf": IMFAdapter(config=IMFConfig()),
        "uspto": USPTOAdapter(config=USPTOConfig()),
        "epo-ops": EpoOpsAdapter(
            config=EpoOpsConfig(consumer_key="arch-test-placeholder", consumer_secret="arch-test-placeholder")
        ),
        "newsapi": NewsAPIAdapter(config=NewsAPIConfig(api_key="arch-test-placeholder")),
        "tavily": TavilyAdapter(config=TavilyConfig(api_key="arch-test-placeholder")),
        "china-nbs": ChinaNBSAdapter(crawler_client=AsyncMock(), config=ChinaNBSConfig()),
    }


# =============================================================================
# 2. 三方一致性（SSOT ↔ 10 个 SKILL.md frontmatter ↔ 适配器 get_metadata()）
# =============================================================================


class TestThreeWayConsistency:
    """声明表 SSOT ↔ 10 个 SKILL.md frontmatter ↔ 涉及源适配器元数据三方一致"""

    def test_involved_adapter_metadata_matches_ssot(self) -> None:
        """涉及源适配器 get_metadata() 实测值与 ADAPTER_SSOT 一致（name/url/api_type/ttl）"""
        adapters = _build_involved_adapters()
        assert set(adapters.keys()) == set(MIXED_INVOLVED_SOURCES)
        for name, adapter in adapters.items():
            ref = adapter.get_metadata()
            # 4-1f 定稿：适配器侧解包第 4 项（required_fields）弃用——声明性字段归声明面，
            # 由 frontmatter↔SSOT 双方断言承载（既有适配器 get_metadata 均不填该字段）
            url, api_type, ttl, _ = ADAPTER_SSOT[name]
            assert ref.name == name
            assert ref.url == url, f"{name}: 适配器 url 漂移 {ref.url} != {url}"
            assert ref.api_type.value == api_type, f"{name}: 适配器 api_type 漂移"
            assert ref.ttl_seconds == ttl, f"{name}: 适配器 ttl 漂移"

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    async def test_frontmatter_matches_ssot_and_adapters(self, slug: str) -> None:
        """10 个 SKILL.md frontmatter data_sources 与 SSOT + 适配器元数据三方一致"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        refs = document.frontmatter.data_sources
        assert tuple(ref.name for ref in refs) == MIXED_SKILL_DATA_SOURCES[slug]
        for ref in refs:
            url, api_type, ttl, required_fields = ADAPTER_SSOT[ref.name]
            assert ref.url == url, f"{slug}/{ref.name}: frontmatter url 与适配器不一致"
            assert ref.api_type.value == api_type
            assert ref.ttl_seconds == ttl
            assert 60 <= ref.ttl_seconds <= 2592000
            assert tuple(ref.required_fields) == required_fields, (
                f"{slug}/{ref.name}: frontmatter required_fields 与 SSOT 不一致"
            )

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    async def test_markers_within_whitelist_cross_consistency(self, slug: str) -> None:
        """SOP body $DATA_SOURCE 标记 name 集合 == frontmatter 声明集合（双向）"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        declared = {ref.name for ref in document.frontmatter.data_sources}
        markers = set(DATA_SOURCE_MARKER_PATTERN.findall(document.body))
        assert markers == declared, f"{slug}: 标记集合 {sorted(markers)} != 声明集合 {sorted(declared)}"


# =============================================================================
# 3. 生产链路回归（零 Python 生产代码改动声明的回归断言）
# =============================================================================


class TestProductionWiringRegression:
    """wiring 文件依赖方向 + 接线特征串 + Engine 签名锁定（本 Story 零改动回归）"""

    @pytest.mark.parametrize("path", WIRING_FILES)
    def test_wiring_files_no_infrastructure_import(self, path: Path) -> None:
        """use case / engine 文件不 import infrastructure（六边形依赖方向）"""
        assert path.is_file(), f"wiring 文件不存在: {path}"
        for module in _extract_imports(path):
            assert not module.startswith("src.infrastructure"), f"{path.name}: 违规 import {module}"

    @pytest.mark.parametrize("path", WIRING_FILES)
    def test_wiring_files_carry_existing_feature_strings(self, path: Path) -> None:
        """源码含既有接线特征串（4-1c 交付未被本 Story 破坏）。"""
        source = path.read_text(encoding="utf-8")
        assert "tool_metadata" in source, f"{path.name}: 缺少 tool_metadata 接线特征串"
        if path.name != "tool_execution_engine.py":
            assert "load_sop" in source, f"{path.name}: 缺少 load_sop 接线特征串"

    def test_engine_init_signature_locked(self) -> None:
        """ToolExecutionEngine.__init__ 签名锁定（Story 4.4 AC-7.4 BDD 断言保护）"""
        params = list(inspect.signature(ToolExecutionEngine.__init__).parameters)
        assert params == ["self", "llm_client", "sandbox", "retry_policy", "tool_execution_repository"]


# =============================================================================
# 4. Skills 内容约束（最终态闭环）
# =============================================================================


class TestSkillContentConstraints:
    """10 个 SKILL.md 内容约束 + 16 Skill 最终态全量断言 + 4-1e 守护"""

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    def test_skill_md_line_count_within_500(self, slug: str) -> None:
        """L2 SKILL.md ≤500 行硬约束"""
        skill_md = SKILLS_ROOT / slug / "SKILL.md"
        line_count = len(skill_md.read_text(encoding="utf-8").splitlines())
        assert line_count <= SKILL_MD_MAX_LINES, f"{slug}: {line_count} 行超过 {SKILL_MD_MAX_LINES} 行"

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    async def test_frontmatter_required_fields(self, slug: str) -> None:
        """frontmatter 必需字段完备（slug/name/version）+ data_sources 非空 + version 保持 1.0.0"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        meta = document.frontmatter
        assert meta.slug == slug
        assert meta.tool_name
        assert meta.data_sources, f"{slug}: data_sources 白名单为空"
        assert meta.version == "1.0.0", f"{slug}: version 应保持 1.0.0（成熟化不升版，4-1c 先例）"

    async def test_final_state_16_skills_all_declared_matching_ssot(self) -> None:
        """16 Skill 最终态全量断言：SSOT 并集（4-1c ∪ 4-1d）内全部 Skill 物理声明
        非空且 name 有序集合 == 各自 SSOT（Subtask 1.4 中间态安全化的最终态闭环）。"""
        ssot_union = dict(SKILL_DATA_SOURCES) | dict(MIXED_SKILL_DATA_SOURCES)
        assert len(ssot_union) == 16, f"SSOT 并集应为 16，实际 {len(ssot_union)}"
        loader = InMemorySkillLoader()
        for slug, expected in ssot_union.items():
            document = await loader.load_sop(slug)
            refs = document.frontmatter.data_sources
            assert refs, f"{slug}: 最终态 data_sources 不得为空（SSOT 已登记）"
            assert tuple(ref.name for ref in refs) == expected, (
                f"{slug}: 声明 {tuple(ref.name for ref in refs)} != SSOT {expected}"
            )

    @pytest.mark.parametrize("slug", NON_TARGET_SLUGS)
    async def test_non_target_skills_untouched(self, slug: str) -> None:
        """无外部源型 Skill data_sources 恒空不变量（纯内部框架型分类学守护——D2）。"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        assert document.frontmatter.data_sources == (), f"无外部源型 Skill {slug} 的 data_sources 恒空不变量被破坏"

    async def test_41c_six_skills_declarations_unchanged(self) -> None:
        """4-1c 既有 6 Skill 声明零回归（name 有序集合 == 4-1c SSOT）"""
        loader = InMemorySkillLoader()
        for slug, expected in SKILL_DATA_SOURCES.items():
            document = await loader.load_sop(slug)
            assert tuple(ref.name for ref in document.frontmatter.data_sources) == expected, f"{slug}: 4-1c 声明被修改"

    def test_ssot_single_source_imported_not_copied(self) -> None:
        """SSOT 单一来源：MIXED_SKILL_DATA_SOURCES 从契约库 import（本文件零复制）。"""
        source = Path(__file__).read_text(encoding="utf-8")
        # 启发式：不得出现「"slug": ("src1", "src2"),」形态的条目字面复制
        literal_pairs = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith('"') and ': ("' in line and line.strip().endswith("),")
        ]
        assert not literal_pairs, f"检测到 SSOT 条目字面复制（R2-F3 单一来源违规）: {literal_pairs[:2]}"
