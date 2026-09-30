"""Skills 数据采集集成 — SDD 架构约束验证测试

五类结构（范本 test_arch_data_source.py）：
1. 常量区：6 Skills slug 清单 + SSOT 声明表 + 8 适配器映射
2. 三方一致性：SSOT 表 ↔ 6 个 SKILL.md frontmatter data_sources ↔ 适配器 get_metadata()
   （name/url/api_type 逐字一致，防漂移契约）
3. 依赖方向：strategic_analysis.py / run_tool_chain.py 不 import infrastructure；
   ToolExecutionEngine.__init__ 签名锁定（Story 4.4 AC-7.4 BDD 断言保护）；
   跨循环一致性（SOP body $DATA_SOURCE 标记集合 == frontmatter 声明集合）
4. Skills 内容约束：6 个 SKILL.md ≤500 行 + frontmatter 必需字段 + 7 个非目标
   Skill data_sources 空 tuple（4-1d Task 1.4 预调整 17 → 7：10 个混合数据型
   Skill 移出非目标清单，其声明守护由 4-1d 契约库与架构测试承载）

注：原 test_domain_layer_untouched_by_story（git status 工作区检查）与
TestComplianceReport.test_all_constraints_checked（恒真自证）已于 4-1c 代码审查
Round 1 删除（R1-P1-2 / R1-P2-1）：前者在 CI 干净 checkout 恒真无判别力
（「零 domain 改动」历史事实由审查取证 + import-linter 依赖方向规则持续守护），
后者仅断言测试类非空不校验任何约束。
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

# =============================================================================
# 1. 常量区
# =============================================================================

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
# SKILLS_ROOT / SKILL_MD_MAX_LINES / DATA_SOURCE_MARKER_PATTERN 一律 import 4-1c
# 契约库单一来源（R2-F13：消除本文件常量复制，对齐 4-1d 架构测试 R1-F9 同款收口）

# 6 个 4-1c 目标（顺序 = 契约库 SKILL_DATA_SOURCES key 顺序，派生防漂移——R2-F13）
TARGET_SLUGS: tuple[str, ...] = tuple(SKILL_DATA_SOURCES.keys())

# 无外部源型 Skill（23 全量 − 4-1c 声明源 − 4-1d 声明源，派生自 4-1e 契约库
# NO_EXTERNAL_SOURCE_SLUGS——D2 收敛，字面清单零复制）：data_sources 恒空不变量
NON_TARGET_SLUGS: tuple[str, ...] = NO_EXTERNAL_SOURCE_SLUGS

# SSOT 常量：import contracts 模块唯一来源（R2-F3 统一——期望数据不按测试层分化，
# 三方一致性断言 = contracts SSOT ↔ 真实 SKILL.md frontmatter ↔ 适配器 get_metadata()）

WIRING_FILES: tuple[Path, ...] = (
    SRC_ROOT / "application" / "use_cases" / "strategic_analysis.py",
    SRC_ROOT / "application" / "use_cases" / "run_tool_chain.py",
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


def _build_adapters() -> dict[str, DataSourcePort]:
    """实例化 8 个适配器（Key 敏感源用测试占位 Key，禁止真实外网调用）"""
    from src.infrastructure.config.china_nbs import ChinaNBSConfig
    from src.infrastructure.config.eurostat import EurostatConfig
    from src.infrastructure.config.imf import IMFConfig
    from src.infrastructure.config.ipcc import IPCCConfig
    from src.infrastructure.config.newsapi import NewsAPIConfig
    from src.infrastructure.config.tavily import TavilyConfig
    from src.infrastructure.config.uspto import USPTOConfig
    from src.infrastructure.config.worldbank import WorldBankConfig
    from src.infrastructure.external_services.datasources.china_nbs_adapter import ChinaNBSAdapter
    from src.infrastructure.external_services.datasources.eurostat_adapter import EurostatAdapter
    from src.infrastructure.external_services.datasources.imf_adapter import IMFAdapter
    from src.infrastructure.external_services.datasources.ipcc_adapter import IPCCAdapter
    from src.infrastructure.external_services.datasources.newsapi_adapter import NewsAPIAdapter
    from src.infrastructure.external_services.datasources.tavily_adapter import TavilyAdapter
    from src.infrastructure.external_services.datasources.uspto_adapter import USPTOAdapter
    from src.infrastructure.external_services.datasources.worldbank_adapter import WorldBankAdapter

    return {
        "world-bank": WorldBankAdapter(config=WorldBankConfig()),
        "imf": IMFAdapter(config=IMFConfig()),
        "eurostat": EurostatAdapter(config=EurostatConfig()),
        "uspto": USPTOAdapter(config=USPTOConfig()),
        "ipcc": IPCCAdapter(config=IPCCConfig()),
        "newsapi": NewsAPIAdapter(config=NewsAPIConfig(api_key="arch-test-placeholder")),
        "tavily": TavilyAdapter(config=TavilyConfig(api_key="arch-test-placeholder")),
        "china-nbs": ChinaNBSAdapter(crawler_client=AsyncMock(), config=ChinaNBSConfig()),
    }


# =============================================================================
# 2. 三方一致性（SSOT ↔ frontmatter ↔ 适配器 get_metadata()）
# =============================================================================


class TestThreeWayConsistency:
    """声明表 SSOT ↔ 6 个 SKILL.md frontmatter ↔ 适配器 get_metadata() 三方一致"""

    def test_adapter_metadata_matches_ssot(self) -> None:
        """11 个适配器 get_metadata() 实测值与 SSOT 对齐表一致（name/url/api_type/ttl）"""
        adapters = _build_adapters()
        assert set(adapters.keys()) == set(ADAPTER_SSOT.keys())
        for name, adapter in adapters.items():
            ref = adapter.get_metadata()
            # 4-1f 定稿：适配器侧解包第 4 项（required_fields）弃用——声明性字段归声明面，
            # 由 frontmatter↔SSOT 双方断言承载（既有 8 适配器 get_metadata 均不填该字段）
            url, api_type, ttl, _ = ADAPTER_SSOT[name]
            assert ref.name == name
            assert ref.url == url, f"{name}: 适配器 url 漂移 {ref.url} != {url}"
            assert ref.api_type.value == api_type, f"{name}: 适配器 api_type 漂移"
            assert ref.ttl_seconds == ttl, f"{name}: 适配器 ttl 漂移"

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    async def test_frontmatter_matches_ssot_and_adapters(self, slug: str) -> None:
        """6 个 SKILL.md frontmatter data_sources 与 SSOT + 适配器元数据三方一致"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        refs = document.frontmatter.data_sources
        assert tuple(ref.name for ref in refs) == SKILL_DATA_SOURCES[slug]
        for ref in refs:
            url, api_type, ttl, required_fields = ADAPTER_SSOT[ref.name]
            assert ref.url == url, f"{slug}/{ref.name}: frontmatter url 与适配器不一致"
            assert ref.api_type.value == api_type
            assert ref.ttl_seconds == ttl
            assert tuple(ref.required_fields) == required_fields, (
                f"{slug}/{ref.name}: frontmatter required_fields 与 SSOT 不一致"
            )
            assert 60 <= ref.ttl_seconds <= 2592000

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    async def test_cross_consistency_markers_vs_whitelist(self, slug: str) -> None:
        """跨循环一致性：SOP body $DATA_SOURCE 标记集合 == frontmatter 声明集合（双向）"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        declared = {ref.name for ref in document.frontmatter.data_sources}
        markers = set(DATA_SOURCE_MARKER_PATTERN.findall(document.body))
        assert markers == declared, f"{slug}: 标记集合 {sorted(markers)} != 声明集合 {sorted(declared)}"


# =============================================================================
# 3. 依赖方向 + 签名锁定
# =============================================================================


class TestDependencyDirection:
    """application 层接线文件依赖方向合规 + Engine 构造签名锁定"""

    @pytest.mark.parametrize("path", WIRING_FILES)
    def test_wiring_files_no_infrastructure_import(self, path: Path) -> None:
        """strategic_analysis.py / run_tool_chain.py 禁止 import infrastructure"""
        for module in _extract_imports(path):
            assert not module.startswith("src.infrastructure"), f"{path.name} 违规 import: {module}"

    @pytest.mark.parametrize("path", WIRING_FILES)
    def test_wiring_files_inject_tool_metadata(self, path: Path) -> None:
        """双入口接线：两个 use case 均注入 extensions["tool_metadata"]（内容约束）"""
        source = path.read_text(encoding="utf-8")
        assert "tool_metadata" in source, f"{path.name} 缺少 tool_metadata 注入"
        assert "load_sop" in source, f"{path.name} 未使用 load_sop 加载 L2 白名单"

    def test_engine_init_signature_locked(self) -> None:
        """ToolExecutionEngine.__init__ 签名锁定（Story 4.4 AC-7.4 BDD 断言保护）"""
        params = list(inspect.signature(ToolExecutionEngine.__init__).parameters)
        assert params == ["self", "llm_client", "sandbox", "retry_policy", "tool_execution_repository"]


# =============================================================================
# 4. Skills 内容约束
# =============================================================================


class TestSkillContentConstraints:
    """6 个 SKILL.md 行数/必需字段 + 7 个非目标 Skill 空 tuple 不变量（4-1d Task 1.4 预调整）"""

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    def test_skill_md_line_count_within_500(self, slug: str) -> None:
        """L2 SKILL.md ≤500 行硬约束（line_count_validator 未实现，由本测试承担）"""
        skill_md = SKILLS_ROOT / slug / "SKILL.md"
        line_count = len(skill_md.read_text(encoding="utf-8").splitlines())
        assert line_count <= SKILL_MD_MAX_LINES, f"{slug}: {line_count} 行超过 {SKILL_MD_MAX_LINES} 行"

    @pytest.mark.parametrize("slug", TARGET_SLUGS)
    async def test_frontmatter_required_fields(self, slug: str) -> None:
        """frontmatter 必需字段完备（slug/name/version + data_sources 非空）"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        meta = document.frontmatter
        assert meta.slug == slug
        assert meta.tool_name
        assert meta.version
        assert meta.data_sources, f"{slug}: data_sources 白名单为空"

    @pytest.mark.parametrize("slug", NON_TARGET_SLUGS)
    async def test_non_target_skills_untouched(self, slug: str) -> None:
        """无外部源型 Skill data_sources 恒空不变量（纯内部框架型分类学守护——D2）。"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        assert document.frontmatter.data_sources == (), f"无外部源型 Skill {slug} 的 data_sources 恒空不变量被破坏"
