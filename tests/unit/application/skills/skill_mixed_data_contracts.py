"""Story 4.1d — 10 个混合数据型 Skills 内容测试共享契约与断言库

本模块是 Task 2-11 十个 `test_<slug>_mixed_data.py` 及架构/集成/验收测试的
共享基础设施：
- 混合数据特有 SSOT 常量（MIXED_SKILL_DATA_SOURCES / 模板微格式契约常量）
- 模板字段提取器与 Schema 叶子键展开（AC-3 模板对应断言核心）
- 五类断言：frontmatter 声明契约 / IO Schema 契约 / SOP 成熟化 /
  跨循环一致性 [C] / 模板字段 ↔ Schema 叶子键双向对应 [D]

跨 Story 共享常量一律从 4-1c 契约库 import（R2-F3 单一来源原则，决策 D6），
本库仅自定义混合数据特有常量与断言（防 4-1e 第三次复制）。

非测试模块（文件名不以 test_ 开头，pytest 不收集）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.application.ports.skill_loader import SkillDocument, ToolMetadata

# 跨 Story 共享常量：import 4-1c 契约库唯一来源（D6 决策，禁止复制）
from tests.unit.application.skills.skill_data_collection_contracts import (
    ADAPTER_SSOT,
    DATA_SOURCE_MARKER_PATTERN,
    KEY_SENSITIVE_SOURCES,
    REQUIRED_SOP_SECTIONS,
    SKILL_MD_MAX_LINES,
    SKILLS_ROOT,
    load_io_contract,
)

__all__ = [
    "ADAPTER_SSOT",
    "DATA_SOURCE_MARKER_PATTERN",
    "KEY_SENSITIVE_SOURCES",
    "REQUIRED_SOP_SECTIONS",
    "SKILLS_ROOT",
    "SKILL_MD_MAX_LINES",
    "MIXED_SKILL_DATA_SOURCES",
    "TEMPLATE_REQUIRED_SECTIONS",
    "REQUIRED_REFERENCES",
    "TEMPLATE_FILES",
    "SCORING_ANCHOR_REFERENCE",
    "GAP_REGISTER_HEADER",
    "REQUIRED_SUFFIX",
    "load_io_contract",
    "load_io_contract_keys",
    "schema_leaf_keys",
    "extract_template_fields",
    "build_min_arguments",
    "assert_data_sources_contract",
    "assert_io_schema_contract",
    "assert_sop_maturity",
    "assert_cross_consistency",
    "assert_template_schema_alignment",
]

# =============================================================================
# 混合数据特有 SSOT：10 个 Skills 数据源白名单声明表
# 与 Story 4.1d「端口与数据契约」声明表逐字一致（slug → 声明源 name 有序元组）
# 统一 2 源策略（决策 D2）：内部数据是分析主体，外部源仅提供行业基准参照
# =============================================================================

MIXED_SKILL_DATA_SOURCES: dict[str, tuple[str, ...]] = {
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

# =============================================================================
# 模板微格式契约常量（Task 0.2/1.2 钉死，多 Agent 并行防发散——R9 风险收敛）
# =============================================================================

# 模板四段式结构标题字面值（工作坊可直接使用）
TEMPLATE_REQUIRED_SECTIONS: tuple[str, ...] = (
    "基本信息",
    "采集表格",
    "评分锚点",
    "数据缺口登记",
)

# references 三件套（data_fusion.md 替代 4-1c triangulation.md——决策 D3：
# 混合数据型交叉验证主轴是「外部基准 ↔ 内部数据」而非「外部多源」）
REQUIRED_REFERENCES: tuple[str, ...] = ("data_fusion.md", "scoring_anchors.md", "workshop_guide.md")

# 模板文件名映射（Story「模板文件命名」表固化；目录新建 templates/）
TEMPLATE_FILES: dict[str, str] = {
    "swot-tows": "swot_factors_collection.md",
    "ansoff-matrix": "ansoff_product_market_matrix.md",
    "value-curve-analysis": "value_curve_factors_grid.md",
    "ge-mckinsey-matrix": "ge_business_unit_scoresheet.md",
    "space-matrix": "space_dimension_scoring.md",
    "value-chain-analysis": "value_chain_activities_inventory.md",
    "vrio-framework": "vrio_resources_checklist.md",
    "bsc-scorecard": "bsc_kpi_scorecard.md",
    "kpi-tree": "kpi_tree_decomposition.md",
    "change-management": "change_stakeholder_assessment.md",
}

# 评分锚点引用字面串（模板「评分锚点」区必须引用）
SCORING_ANCHOR_REFERENCE = "references/scoring_anchors.md"

# 数据缺口登记区表头字面串（内部数据不可得时的降级记录区）
GAP_REGISTER_HEADER = "| 字段 | 缺口描述 | 替代来源 |"

# required 标注统一语法后缀（提取器剥离后缀取纯字段名比对）
REQUIRED_SUFFIX = "（必填）"


# =============================================================================
# 契约加载辅助
# =============================================================================


def load_io_contract_keys() -> tuple[str, ...]:
    """加载 IO 契约 yaml 全部 slug 键集合（4-1c ∪ 4-1d 条目互锁断言用）。"""
    import yaml

    contracts_file = Path(__file__).resolve().parents[3] / "acceptance" / "contracts" / "skill_io_schemas.yaml"
    with contracts_file.open(encoding="utf-8") as f:
        contracts: dict[str, Any] = yaml.safe_load(f)
    return tuple(contracts["skills"].keys())


# =============================================================================
# Schema 叶子键展开（嵌套 Schema 展开约定，Round 1 D1-B 勘正补定）
# =============================================================================


def schema_leaf_keys(schema: dict[str, Any]) -> dict[str, bool]:
    """递归展开 input_schema 的叶子键集合（叶子键 → 是否必填）。

    展开约定（「内部数据契约」节）：
    - 叶子键 = 末端 properties 键（type object 且有 properties 的子键递归展开，
      该容器键不进比对集，以模板「采集表格」分区标题承载）
    - array 键展开为其 items.properties（items 为对象时）
    - 平铺 Schema（无嵌套 properties）退化为顶层键即叶子键
    - 必填判定 = 叶子出现在其直接容器的 required 列表中（JSON Schema 语义：
      父级容器自身的 required 使容器必填，不使容器内全部子字段必填）
    """
    leaves: dict[str, bool] = {}

    def _walk(node: dict[str, Any]) -> None:
        required = node.get("required") if isinstance(node.get("required"), list) else None
        for key, sub in node.get("properties", {}).items():
            is_required = required is not None and key in required
            if sub.get("type") == "object" and sub.get("properties"):
                # 嵌套对象：容器键不进比对集（分区标题承载），递归展开
                _walk(sub)
            elif sub.get("type") == "array" and isinstance(sub.get("items"), dict) and sub["items"].get("properties"):
                # array of object：展开 items.properties（容器键不进比对集）
                _walk(sub["items"])
            else:
                leaves[key] = is_required

    _walk(schema)
    return leaves


# =============================================================================
# 模板字段提取器（Markdown 表格字段列 + 「（必填）」后缀剥离）
# =============================================================================


def extract_template_fields(template_text: str) -> dict[str, bool]:
    """从模板「采集表格」区提取字段集合（字段名 → 是否标注必填）。

    微格式契约（Task 0.2 钉死）：
    - 仅「采集表格」区（`## 采集表格` 到下一个二级标题之间）的表格行参与提取；
      「基本信息」区表格字段不进比对集
    - 三级标题（`### xxx`）= 嵌套顶层键分区标题，不进比对集
    - 表格数据行首列 = 字段名，带「（必填）」后缀表示 required（剥离后缀取纯字段名）
    - 表头行与分隔行（`| --- |` 形态）跳过
    - 同字段多行（逐条因素一行的形态）时必填标注须全行一致：all 聚合——
      任一行缺「（必填）」后缀即该字段计为非必填（与 required 链比对即红，
      防单行标注破坏被末行覆盖而漏检）
    """
    field_marks: dict[str, list[bool]] = {}

    # 截取「采集表格」区（到下一个二级标题为止）
    match = re.search(r"^##\s*采集表格\s*$", template_text, re.MULTILINE)
    if match is None:
        return {}
    after = template_text[match.end() :]
    next_section = re.search(r"^##\s", after, re.MULTILINE)
    section = after[: next_section.start()] if next_section else after

    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        # 跳过表头分隔行（全部为 --- 形态）与空字段列
        if not first or set(first) <= {"-", " ", ":"}:
            continue
        # 跳过表头行（首列为通用表头字面值「字段」）
        if first == "字段":
            continue
        is_required = first.endswith(REQUIRED_SUFFIX)
        field_name = first[: -len(REQUIRED_SUFFIX)] if is_required else first
        field_marks.setdefault(field_name, []).append(is_required)
    return {name: all(flags) for name, flags in field_marks.items()}


# =============================================================================
# 最小合法实例构造（集成/验收测试共用的内部数据参数工厂，单一来源）
# =============================================================================


def _fill_min_instance(schema: dict[str, Any]) -> Any:
    """按 JSON Schema required 链递归构造最小合法实例（required 字段逐层填充）。"""
    schema_type = schema.get("type")
    if schema_type == "object":
        required = schema.get("required", [])
        return {key: _fill_min_instance(sub) for key, sub in schema.get("properties", {}).items() if key in required}
    if schema_type == "array":
        items = schema.get("items", {})
        if isinstance(items, dict) and items.get("properties"):
            return [_fill_min_instance(items)]
        return ["示例"]
    if schema_type == "number":
        return 1.0
    if schema_type == "integer":
        return 1
    return "示例"


def build_min_arguments(slug: str) -> dict[str, Any]:
    """从 IO 契约 yaml 程序化构造 input_schema 最小合法实例（SSOT 防漂移）。

    per-slug 代表性 arguments 的唯一来源是 tests/acceptance/contracts/
    skill_io_schemas.yaml 的 required 链（Task 0.2 固化），禁止手写漂移。
    集成测试（内外融合 repr 断言）与验收测试（arguments 注入）统一 import。
    """
    contract = load_io_contract(slug)
    instance = _fill_min_instance(contract["input_schema"])
    assert isinstance(instance, dict), f"{slug} input_schema 顶层必须为 object"
    return instance


# =============================================================================
# 断言库（混合数据语义；断言函数签名与 4-1c 契约库风格一致）
# =============================================================================


def assert_data_sources_contract(slug: str, metadata: ToolMetadata) -> None:
    """frontmatter data_sources 全字段（name/url/api_type/ttl_seconds/required_fields）== SSOT 表

    混合数据语义：声明源查 MIXED_SKILL_DATA_SOURCES（本 Story SSOT），
    逐源 url/api_type/ttl 与 ADAPTER_SSOT（import 4-1c 库）逐字对齐。
    """
    expected_names = MIXED_SKILL_DATA_SOURCES[slug]
    actual = metadata.data_sources
    assert isinstance(actual, tuple), f"{slug}: data_sources 必须是 tuple"
    assert tuple(ref.name for ref in actual) == expected_names, (
        f"{slug}: data_sources name 集合与 SSOT 不一致: {tuple(ref.name for ref in actual)} != {expected_names}"
    )
    for ref in actual:
        url, api_type, ttl = ADAPTER_SSOT[ref.name]
        assert ref.url == url, f"{slug}/{ref.name}: url 漂移 {ref.url} != {url}"
        assert ref.api_type.value == api_type, f"{slug}/{ref.name}: api_type 漂移 {ref.api_type.value} != {api_type}"
        assert ref.ttl_seconds == ttl, f"{slug}/{ref.name}: ttl_seconds 漂移 {ref.ttl_seconds} != {ttl}"
        assert 60 <= ref.ttl_seconds <= 2592000
        assert ref.required_fields, f"{slug}/{ref.name}: required_fields 不能为空（AC-1 全字段断言）"


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
    """SOP 成熟化断言：必备章节 / input_examples 非 placeholder / ≤500 行 / references+templates 存在

    混合数据语义：references 三件套为 data_fusion.md / scoring_anchors.md /
    workshop_guide.md（D3 决策，替代 4-1c triangulation.md）。
    """
    body = document.body
    for section in REQUIRED_SOP_SECTIONS:
        assert section in body, f"{slug}: SOP 缺少必备章节「{section}」"

    # input_examples 非 placeholder
    assert "placeholder" not in body.lower(), f"{slug}: input_examples 仍为 placeholder"

    # 失败处理章节含降级语义（411/412/413）——词边界正则防数字子串伪满足（4-1c R1-P2-4）
    failure_section = body.split("失败处理", 1)[-1]
    for keyword in ("411", "412", "413"):
        assert re.search(rf"\b{keyword}\b", failure_section), f"{slug}: 失败处理章节缺少 {keyword} 降级语义"

    # 声明含 Key 敏感源的 Skill 必须文档化 Key 缺失降级话术（7 断言 3 跳过天然适配）
    declared = set(MIXED_SKILL_DATA_SOURCES[slug])
    if declared & set(KEY_SENSITIVE_SOURCES):
        assert "未注册" in failure_section, f"{slug}: 失败处理章节缺少 Key 缺失「未注册」降级话术"
        assert "数据缺口" in failure_section, f"{slug}: 失败处理章节缺少「数据缺口」标注话术"

    # 行数硬约束（L2 ≤500 行；line_count_validator 未实现，由本断言 + 架构测试承担）
    skill_md = SKILLS_ROOT / slug / "SKILL.md"
    line_count = len(skill_md.read_text(encoding="utf-8").splitlines())
    assert line_count <= SKILL_MD_MAX_LINES, f"{slug}: SKILL.md {line_count} 行超过 {SKILL_MD_MAX_LINES} 行硬约束"

    # references/templates 配套资源存在性（三件套为混合数据语义）
    skill_dir = SKILLS_ROOT / slug
    references_dir = skill_dir / "references"
    templates_dir = skill_dir / "templates"
    assert references_dir.is_dir() and any(references_dir.iterdir()), f"{slug}: references/ 为空"
    assert templates_dir.is_dir() and any(templates_dir.iterdir()), f"{slug}: templates/ 为空"
    for ref_file in REQUIRED_REFERENCES:
        assert (references_dir / ref_file).is_file(), f"{slug}: 缺少 references/{ref_file}"
    assert (templates_dir / TEMPLATE_FILES[slug]).is_file(), f"{slug}: 缺少 templates/{TEMPLATE_FILES[slug]}"


def assert_cross_consistency(slug: str, document: SkillDocument) -> None:
    """跨循环一致性 [C]：SOP body $DATA_SOURCE 标记 name 集合 == frontmatter.data_sources name 集合（双向）"""
    declared = {ref.name for ref in document.frontmatter.data_sources}
    markers = set(DATA_SOURCE_MARKER_PATTERN.findall(document.body))
    assert markers == declared, (
        f"{slug}: 跨循环一致性破坏 — SOP 标记集合 {sorted(markers)} != frontmatter 声明集合 {sorted(declared)}"
        "（白名单过宽或过窄均不允许）"
    )


def assert_template_schema_alignment(slug: str, document: SkillDocument) -> None:
    """模板字段 ↔ input_schema 叶子键双向对应断言（AC-3 核心，本 Story 特有）。

    断言链：
    - 四段式结构完整（TEMPLATE_REQUIRED_SECTIONS 逐段标题存在）
    - 评分锚点引用（模板文本含 references/scoring_anchors.md 字面串）
    - 数据缺口登记区表头存在
    - 模板采集字段集合 == input_schema 递归展开叶子键集合（双向：多余=失败，缺失=失败）
    - required 叶子键标注「（必填）」后缀（有/无后缀与 required 链严格一致）
    """
    template_path = SKILLS_ROOT / slug / "templates" / TEMPLATE_FILES[slug]
    assert template_path.is_file(), f"{slug}: 模板文件不存在 {template_path}"
    template_text = template_path.read_text(encoding="utf-8")

    # 四段式结构
    for section in TEMPLATE_REQUIRED_SECTIONS:
        assert f"## {section}" in template_text, f"{slug}: 模板缺少「{section}」段标题"

    # 评分锚点引用
    assert SCORING_ANCHOR_REFERENCE in template_text, f"{slug}: 模板「评分锚点」区缺少 {SCORING_ANCHOR_REFERENCE} 引用"

    # 数据缺口登记区表头
    gap_section = template_text.split("数据缺口登记", 1)[-1]
    assert GAP_REGISTER_HEADER in gap_section, f"{slug}: 「数据缺口登记」区缺少表头 {GAP_REGISTER_HEADER}"

    # 叶子键双向比对 + required 标注一致性
    leaves = schema_leaf_keys(document.frontmatter.input_schema)
    fields = extract_template_fields(template_text)
    assert set(fields) == set(leaves), (
        f"{slug}: 模板字段与 Schema 叶子键不一致 — "
        f"模板多余: {sorted(set(fields) - set(leaves))} / 叶子缺失: {sorted(set(leaves) - set(fields))}"
    )
    mismatched = {name for name in leaves if fields[name] != leaves[name]}
    assert not mismatched, (
        f"{slug}: 必填标注与 required 链不一致的字段: {sorted(mismatched)}"
        f"（required 叶子须带「{REQUIRED_SUFFIX}」后缀，非 required 不得带）"
    )
