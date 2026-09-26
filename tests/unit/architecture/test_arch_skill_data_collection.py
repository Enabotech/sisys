"""Skills 数据采集集成 — SDD 架构约束验证测试

五类结构（范本 test_arch_data_source.py）：
1. 常量区：6 Skills slug 清单 + SSOT 声明表 + 8 适配器映射
2. 三方一致性：SSOT 表 ↔ 6 个 SKILL.md frontmatter data_sources ↔ 适配器 get_metadata()
   （name/url/api_type 逐字一致，防漂移契约）
3. 依赖方向：strategic_analysis.py / run_tool_chain.py 不 import infrastructure；
   ToolExecutionEngine.__init__ 签名锁定（Story 4.4 AC-7.4 BDD 断言保护）；
   跨循环一致性（SOP body $DATA_SOURCE 标记集合 == frontmatter 声明集合）
4. Skills 内容约束：6 个 SKILL.md ≤500 行 + frontmatter 必需字段 + 17 个非目标
   Skill data_sources 空 tuple
5. 合规报告：全部约束通过即架构合规
"""

from __future__ import annotations

import ast
import inspect
import re
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.skills.loader import InMemorySkillLoader

# =============================================================================
# 1. 常量区
# =============================================================================

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
SKILLS_ROOT = SRC_ROOT / "application" / "skills"

TARGET_SLUGS: tuple[str, ...] = (
    "pestel-analysis",
    "porters-five-forces",
    "appeals-analysis",
    "competitor-analysis",
    "scenario-planning",
    "disruptive-innovation",
)

NON_TARGET_SLUGS: tuple[str, ...] = (
    "ansoff-matrix",
    "bsc-scorecard",
    "business-model-canvas",
    "change-management",
    "dependency-graph",
    "gantt-chart",
    "ge-mckinsey-matrix",
    "kpi-tree",
    "org-design-framework",
    "raci-matrix",
    "space-matrix",
    "strategy-map",
    "swot-tows",
    "value-chain-analysis",
    "value-curve-analysis",
    "value-proposition-canvas",
    "vrio-framework",
)

# SSOT：6 个 Skills 数据源白名单声明表（与 Story 数据契约逐字一致）
SKILL_DATA_SOURCES: dict[str, tuple[str, ...]] = {
    "pestel-analysis": ("world-bank", "imf", "eurostat", "ipcc", "newsapi", "china-nbs"),
    "porters-five-forces": ("newsapi", "world-bank", "eurostat"),
    "appeals-analysis": ("tavily", "newsapi", "china-nbs"),
    "competitor-analysis": ("newsapi", "uspto", "tavily", "china-nbs"),
    "scenario-planning": ("tavily", "ipcc", "eurostat"),
    "disruptive-innovation": ("uspto", "tavily"),
}

# SSOT：8 个适配器元数据对齐表（name → (url, api_type, ttl_seconds)）
ADAPTER_SSOT: dict[str, tuple[str, str, int]] = {
    "world-bank": ("https://api.worldbank.org/v2", "rest_json", 604800),
    "imf": ("https://www.imf.org/external/datamapper/api/v1", "sdmx_json", 604800),
    "eurostat": ("https://ec.europa.eu/eurostat/api/dissemination", "sdmx_json", 604800),
    "uspto": ("https://search.patentsview.org", "rest_json", 2592000),
    "ipcc": ("https://www.ipcc.ch/data", "csv_download", 2592000),
    "newsapi": ("https://newsapi.org", "rest_json", 21600),
    "tavily": ("https://api.tavily.com", "rest_json", 86400),
    "china-nbs": ("https://www.stats.gov.cn", "crawler", 86400),
}

WIRING_FILES: tuple[Path, ...] = (
    SRC_ROOT / "application" / "use_cases" / "strategic_analysis.py",
    SRC_ROOT / "application" / "use_cases" / "run_tool_chain.py",
)

DATA_SOURCE_MARKER_PATTERN = re.compile(r"\$DATA_SOURCE\(\s*[\"']([\w-]+)[\"']")
SKILL_MD_MAX_LINES = 500


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


def _build_adapters() -> dict[str, object]:
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
        """8 个适配器 get_metadata() 实测值与 SSOT 对齐表一致（name/url/api_type/ttl）"""
        adapters = _build_adapters()
        assert set(adapters.keys()) == set(ADAPTER_SSOT.keys())
        for name, adapter in adapters.items():
            ref = adapter.get_metadata()  # type: ignore[attr-defined]
            url, api_type, ttl = ADAPTER_SSOT[name]
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
            url, api_type, ttl = ADAPTER_SSOT[ref.name]
            assert ref.url == url, f"{slug}/{ref.name}: frontmatter url 与适配器不一致"
            assert ref.api_type.value == api_type
            assert ref.ttl_seconds == ttl
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

    def test_domain_layer_untouched_by_story(self) -> None:
        """本 Story 零 domain 改动声明校验：工作区 src/domain 无未提交改动"""
        result = subprocess.run(
            ["git", "status", "--porcelain", "src/domain/"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "", f"本 Story 禁止改动 domain 层:\n{result.stdout}"


# =============================================================================
# 4. Skills 内容约束
# =============================================================================


class TestSkillContentConstraints:
    """6 个 SKILL.md 行数/必需字段 + 17 个非目标 Skill 空 tuple 不变量"""

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
        """17 个非目标 Skill 未被误改（data_sources 保持空 tuple）"""
        loader = InMemorySkillLoader()
        document = await loader.load_sop(slug)
        assert document.frontmatter.data_sources == (), f"非目标 Skill {slug} 的 data_sources 被误填"


# =============================================================================
# 5. 合规报告
# =============================================================================


class TestComplianceReport:
    """架构合规汇总（全部约束通过即合规）"""

    def test_all_constraints_checked(self) -> None:
        """合规清单：三方一致性 / 依赖方向 / 签名锁定 / 行数 / 空 tuple 均由本文件覆盖"""
        test_classes = (
            TestThreeWayConsistency,
            TestDependencyDirection,
            TestSkillContentConstraints,
        )
        for cls in test_classes:
            methods = [m for m in dir(cls) if m.startswith("test_")]
            assert methods, f"{cls.__name__} 无测试方法"
