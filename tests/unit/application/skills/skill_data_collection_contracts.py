"""Story 4.1c — 6 个外部数据型 Skills 内容测试共享契约与断言库

本模块是 Task 2-7 六个 `test_<slug>_data_collection.py` 的共享基础设施：
- SSOT 声明表（与 Story 「6 个 Skills 数据源白名单声明表」+「适配器对齐表」逐字一致）
- IO Schema 契约加载（`tests/acceptance/contracts/skill_io_schemas.yaml`，Task 0.2 SSOT）
- 四类断言：frontmatter 声明契约 / IO Schema 契约 / SOP 成熟化 / 跨循环一致性 [C]

非测试模块（文件名不以 test_ 开头，pytest 不收集）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from src.application.ports.skill_loader import SkillDocument, ToolMetadata

# =============================================================================
# 路径常量
# =============================================================================

SKILLS_ROOT = Path(__file__).resolve().parents[4] / "src" / "application" / "skills"
CONTRACTS_FILE = Path(__file__).resolve().parents[3] / "acceptance" / "contracts" / "skill_io_schemas.yaml"

# =============================================================================
# SSOT：12 个适配器元数据对齐表（name → (url, api_type, ttl_seconds, required_fields)）
# 与 Story 「适配器 url/api_type/ttl/confidence 对齐表」逐字一致
# （4-1b 8 适配器 get_metadata() 实测值 + 4-1f 三新源）
# 4-1f D6：三元组扩四元组——required_fields 按源定制（8 既有源零漂移保持
# ("indicator","value")；3 新源定制值）。:60 原注释「4.3 字段级化时并入 ADAPTER_SSOT」
# 预案由此落地；原 EXPECTED_REQUIRED_FIELDS 统一常量移除（查表断言取代统一比对——
# 双真相源漂移风险消除，值级绊线改写为 test_required_fields_quadruple_values_locked）。
# =============================================================================

ADAPTER_SSOT: dict[str, tuple[str, str, int, tuple[str, ...]]] = {
    "world-bank": ("https://api.worldbank.org/v2", "rest_json", 604800, ("indicator", "value")),
    "imf": ("https://www.imf.org/external/datamapper/api/v1", "sdmx_json", 604800, ("indicator", "value")),
    "eurostat": ("https://ec.europa.eu/eurostat/api/dissemination", "sdmx_json", 604800, ("indicator", "value")),
    "uspto": ("https://search.patentsview.org", "rest_json", 2592000, ("indicator", "value")),
    "ipcc": ("https://www.ipcc.ch/data", "csv_download", 2592000, ("indicator", "value")),
    "newsapi": ("https://newsapi.org", "rest_json", 21600, ("indicator", "value")),
    "tavily": ("https://api.tavily.com", "rest_json", 86400, ("indicator", "value")),
    "china-nbs": ("https://www.stats.gov.cn", "crawler", 86400, ("indicator", "value")),
    "epo-ops": ("https://ops.epo.org", "rest_json", 604800, ("title", "applicant", "filing_date")),
    "sec-edgar": ("https://efts.sec.gov", "rest_json", 2592000, ("company", "form", "filed_at")),
    "comtrade": ("https://comtradeapi.un.org", "rest_json", 604800, ("cmd_code", "trade_value", "period")),
    "google-patents": (
        "https://bigquery.googleapis.com",
        "rest_json",
        604800,
        ("publication_number", "assignee", "filing_date"),
    ),
}

# SSOT：6 个 Skills 数据源白名单声明表（slug → 声明源 name 有序元组）
SKILL_DATA_SOURCES: dict[str, tuple[str, ...]] = {
    "pestel-analysis": ("world-bank", "imf", "eurostat", "ipcc", "newsapi", "china-nbs"),
    "porters-five-forces": ("newsapi", "world-bank", "eurostat"),
    "appeals-analysis": ("tavily", "newsapi", "china-nbs"),
    "competitor-analysis": ("newsapi", "uspto", "google-patents", "epo-ops", "sec-edgar", "tavily", "china-nbs"),
    "scenario-planning": ("tavily", "ipcc", "eurostat"),
    "disruptive-innovation": ("uspto", "google-patents", "epo-ops", "tavily"),
}

# 声明含 Key 敏感源（newsapi/tavily）的 Skill —— SOP 失败处理章节必须文档化 Key 缺失降级
# （4-1f Task 0 定稿：epo-ops/comtrade 不登记——循 uspto 先例，同为 keyed 源但降级语义由
# Skill §7「未注册行」扩列承载；登记将触发 test_key_sensitive_skills_count 精确集合断言连锁红）
KEY_SENSITIVE_SOURCES = ("newsapi", "tavily")

# SOP body 中 $DATA_SOURCE 标记提取正则（Task 9.3 跨循环一致性同款）
DATA_SOURCE_MARKER_PATTERN = re.compile(r"\$DATA_SOURCE\(\s*[\"']([\w-]+)[\"']")

# SOP 必备章节关键字（AC-3）
REQUIRED_SOP_SECTIONS: tuple[str, ...] = (
    "适用场景",
    "负向触发",
    "输入字段",
    "输出字段",
    "数据采集计划",
    "执行步骤",
    "失败处理",
    "input_examples",
    "References",
)

SKILL_MD_MAX_LINES = 500


# =============================================================================
# 契约加载
# =============================================================================


def load_io_contract(slug: str) -> dict[str, Any]:
    """加载 Task 0.2 契约文件中的 input_schema/output_schema 定义"""
    with CONTRACTS_FILE.open(encoding="utf-8") as f:
        contracts: dict[str, Any] = yaml.safe_load(f)
    skill_contract: dict[str, Any] = contracts["skills"][slug]
    return skill_contract


# =============================================================================
# 断言库
# =============================================================================


def assert_data_sources_contract(slug: str, metadata: ToolMetadata) -> None:
    """frontmatter data_sources 全字段（name/url/api_type/ttl_seconds/required_fields）== SSOT 表"""
    expected_names = SKILL_DATA_SOURCES[slug]
    actual = metadata.data_sources
    assert isinstance(actual, tuple), f"{slug}: data_sources 必须是 tuple"
    assert tuple(ref.name for ref in actual) == expected_names, (
        f"{slug}: data_sources name 集合与 SSOT 不一致: {tuple(ref.name for ref in actual)} != {expected_names}"
    )
    for ref in actual:
        url, api_type, ttl, required_fields = ADAPTER_SSOT[ref.name]
        assert ref.url == url, f"{slug}/{ref.name}: url 漂移 {ref.url} != {url}"
        assert ref.api_type.value == api_type, f"{slug}/{ref.name}: api_type 漂移 {ref.api_type.value} != {api_type}"
        assert ref.ttl_seconds == ttl, f"{slug}/{ref.name}: ttl_seconds 漂移 {ref.ttl_seconds} != {ttl}"
        assert 60 <= ref.ttl_seconds <= 2592000
        assert tuple(ref.required_fields) == required_fields, (
            f"{slug}/{ref.name}: required_fields 漂移 {tuple(ref.required_fields)} != {required_fields}"
        )


def assert_io_schema_contract(slug: str, metadata: ToolMetadata) -> None:
    """frontmatter input_schema/output_schema 与 Task 0.2 契约文件逐字一致且含 required 字段"""
    contract = load_io_contract(slug)
    assert metadata.input_schema == contract["input_schema"], (
        f"{slug}: input_schema 与契约文件不一致: {metadata.input_schema!r}"
    )
    assert metadata.output_schema == contract["output_schema"], (
        f"{slug}: output_schema 与契约文件不一致: {metadata.output_schema!r}"
    )
    assert metadata.input_schema.get("required"), f"{slug}: input_schema 缺少 required 字段"
    assert metadata.output_schema.get("required"), f"{slug}: output_schema 缺少 required 字段"


def assert_sop_maturity(slug: str, document: SkillDocument) -> None:
    """SOP 成熟化断言：必备章节 / input_examples 非 placeholder / ≤500 行 / references+templates 存在"""
    body = document.body
    for section in REQUIRED_SOP_SECTIONS:
        assert section in body, f"{slug}: SOP 缺少必备章节「{section}」"

    # input_examples 非 placeholder
    assert "placeholder" not in body.lower(), f"{slug}: input_examples 仍为 placeholder"

    # 失败处理章节含降级语义（411/412/413）——词边界正则防数字子串伪满足（R1-P2-4）
    failure_section = body.split("失败处理", 1)[-1]
    for keyword in ("411", "412", "413"):
        assert re.search(rf"\b{keyword}\b", failure_section), f"{slug}: 失败处理章节缺少 {keyword} 降级语义"

    # 声明含 Key 敏感源的 Skill 必须文档化 Key 缺失降级话术
    declared = set(SKILL_DATA_SOURCES[slug])
    if declared & set(KEY_SENSITIVE_SOURCES):
        assert "未注册" in failure_section, f"{slug}: 失败处理章节缺少 Key 缺失「未注册」降级话术"
        assert "数据缺口" in failure_section, f"{slug}: 失败处理章节缺少「数据缺口」标注话术"

    # 行数硬约束（L2 ≤500 行；line_count_validator 未实现，由本断言 + Task 9.4 承担）
    skill_md = SKILLS_ROOT / slug / "SKILL.md"
    line_count = len(skill_md.read_text(encoding="utf-8").splitlines())
    assert line_count <= SKILL_MD_MAX_LINES, f"{slug}: SKILL.md {line_count} 行超过 {SKILL_MD_MAX_LINES} 行硬约束"

    # references/templates 配套资源存在性
    skill_dir = SKILLS_ROOT / slug
    references_dir = skill_dir / "references"
    templates_dir = skill_dir / "templates"
    assert references_dir.is_dir() and any(references_dir.iterdir()), f"{slug}: references/ 为空"
    assert templates_dir.is_dir() and any(templates_dir.iterdir()), f"{slug}: templates/ 为空"
    for ref_file in ("triangulation.md", "scoring_anchors.md", "workshop_guide.md"):
        assert (references_dir / ref_file).is_file(), f"{slug}: 缺少 references/{ref_file}"


def assert_cross_consistency(slug: str, document: SkillDocument) -> None:
    """跨循环一致性 [C]：SOP body $DATA_SOURCE 标记 name 集合 == frontmatter.data_sources name 集合（双向）"""
    declared = {ref.name for ref in document.frontmatter.data_sources}
    markers = set(DATA_SOURCE_MARKER_PATTERN.findall(document.body))
    assert markers == declared, (
        f"{slug}: 跨循环一致性破坏 — SOP 标记集合 {sorted(markers)} != frontmatter 声明集合 {sorted(declared)}"
        "（白名单过宽或过窄均不允许）"
    )
