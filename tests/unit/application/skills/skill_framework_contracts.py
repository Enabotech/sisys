"""Story 4.1e — 7 个纯内部框架 Skills 内容测试共享契约与断言库

本模块是 Task 2-8 七个 `test_<slug>_framework.py` 及架构/集成/验收测试的
共享基础设施：
- 内部框架特有 SSOT 常量（FRAMEWORK_SKILL_SLUGS / 分型常量 / TEMPLATE_FILES /
  失败处理关键词 D3 / 派生 NO_EXTERNAL_SOURCE_SLUGS）
- 六类断言：空声明一等不变量 / IO Schema 契约（import 4-1c 复用）/ SOP 成熟化（分型）/
  跨循环一致性 [C] 空集语义（import 4-1c 复用）/ 模板字段 ↔ Schema 叶子键双向
  对应 [D]（import 4-1d 机械 + 分型第三段）/ references 内容要素字面锚点（本库新增）

跨 Story 共享常量与机械一律从 4-1c/4-1d 契约库 import（R2-F3 单一来源原则），
本库仅自定义内部框架特有常量与断言（第三契约库——承接 4-1d R1-D2 defer 的
NON_TARGET_SLUGS 三副本收敛义务，决策 D2）。

非测试模块（文件名不以 test_ 开头，pytest 不收集）。
"""

from __future__ import annotations

import re

from src.application.ports.skill_loader import SkillDocument
from src.application.skills.skill_manifest import SLUG_TO_TOOL_ID

# 跨 Story 共享常量与断言：import 4-1c 契约库唯一来源（D6 决策，禁止复制）
from tests.unit.application.skills.skill_data_collection_contracts import (
    DATA_SOURCE_MARKER_PATTERN,
    REQUIRED_SOP_SECTIONS,
    SKILL_DATA_SOURCES,
    SKILL_MD_MAX_LINES,
    SKILLS_ROOT,
    assert_cross_consistency,
    assert_io_schema_contract,
    load_io_contract,
)

# 跨 Story 共享机械：import 4-1d 契约库唯一来源（防第三次复制，4-1d 库 docstring 明示）
from tests.unit.application.skills.skill_mixed_data_contracts import (
    GAP_REGISTER_HEADER,
    MIXED_SKILL_DATA_SOURCES,
    REQUIRED_SUFFIX,
    _collection_section,
    build_min_arguments,
    extract_template_fields,
    schema_leaf_keys,
    schema_top_level_container_keys,
)

__all__ = [
    "DATA_SOURCE_MARKER_PATTERN",
    "REQUIRED_SOP_SECTIONS",
    "SKILL_MD_MAX_LINES",
    "SKILLS_ROOT",
    "GAP_REGISTER_HEADER",
    "REQUIRED_SUFFIX",
    "FRAMEWORK_SKILL_SLUGS",
    "SCORING_TYPE_SLUGS",
    "STRUCTURAL_TYPE_SLUGS",
    "SCORING_REFERENCES",
    "STRUCTURAL_REFERENCES",
    "SCORING_TEMPLATE_SECTIONS",
    "STRUCTURAL_TEMPLATE_SECTIONS",
    "TEMPLATE_FILES",
    "SCORING_ANCHOR_REFERENCE",
    "VALIDATION_RULES_REFERENCE",
    "FAILURE_KEYWORDS",
    "NO_EXTERNAL_SOURCE_SLUGS",
    "load_io_contract",
    "build_min_arguments",
    "schema_leaf_keys",
    "extract_template_fields",
    "schema_top_level_container_keys",
    "framework_type",
    "required_references_for",
    "assert_framework_data_sources_empty",
    "assert_io_schema_contract",
    "assert_sop_maturity",
    "assert_cross_consistency",
    "assert_template_schema_alignment",
    "assert_reference_content_anchors",
]

# =============================================================================
# 内部框架特有 SSOT：7 个 Skills 分型声明表（D4 分型决策）
# 与 Story 4.1e「端口与数据契约」数据契约表逐字一致
# =============================================================================

# 评分型 3 个（分值语义：fit 匹配强度 / 块成熟度 / 维度对齐度）
SCORING_TYPE_SLUGS: tuple[str, ...] = (
    "value-proposition-canvas",
    "business-model-canvas",
    "org-design-framework",
)

# 结构型 4 个（确定性规则语义：因果箭头 / DAG / RACI / CPM）
STRUCTURAL_TYPE_SLUGS: tuple[str, ...] = (
    "strategy-map",
    "dependency-graph",
    "raci-matrix",
    "gantt-chart",
)

# 全集（数据契约表顺序）
FRAMEWORK_SKILL_SLUGS: tuple[str, ...] = SCORING_TYPE_SLUGS + STRUCTURAL_TYPE_SLUGS

# references 分型三件套（D4：framework_logic.md 为本 Story 首次引入——替位
# 4-1d data_fusion.md 的纯内部型语义「内外融合 → 框架逻辑引导」）
SCORING_REFERENCES: tuple[str, ...] = ("framework_logic.md", "scoring_anchors.md", "workshop_guide.md")
STRUCTURAL_REFERENCES: tuple[str, ...] = ("framework_logic.md", "validation_rules.md", "workshop_guide.md")

# 模板文件名映射（Story Task 0.2 命名表钉死；目录新建 templates/）
TEMPLATE_FILES: dict[str, str] = {
    "value-proposition-canvas": "vpc_canvas_matching.md",
    "business-model-canvas": "bmc_nine_blocks_canvas.md",
    "org-design-framework": "org_star_model_assessment.md",
    "strategy-map": "strategy_map_causal_links.md",
    "dependency-graph": "dependency_task_inventory.md",
    "raci-matrix": "raci_roles_tasks.md",
    "gantt-chart": "gantt_project_plan.md",
}

# 模板四段式结构标题字面值（D5：第三段按分型条件化，四段式骨架统一）
SCORING_TEMPLATE_SECTIONS: tuple[str, ...] = ("基本信息", "采集表格", "评分锚点", "数据缺口登记")
STRUCTURAL_TEMPLATE_SECTIONS: tuple[str, ...] = ("基本信息", "采集表格", "校验规则", "数据缺口登记")

# 模板第三段引用字面串（分型各一）
SCORING_ANCHOR_REFERENCE = "references/scoring_anchors.md"
VALIDATION_RULES_REFERENCE = "references/validation_rules.md"

# 失败处理断言集（D3：纯内部型失败面 = 标记误用 207 + 内部数据不足
# INSUFFICIENT_DATA——SOP 文档级关键词承载，替换 4-1d 的 411/412/413）
FAILURE_KEYWORDS: tuple[str, ...] = ("207", "INSUFFICIENT_DATA")

# 派生式无外部源 slug 收敛（D2：承接 4-1d R1-D2 defer——三处回归网用例改
# import 本常量，字面清单零残留；派生结果 == 7 非空，判别力保留：
# 全集 − 4-1c 声明源 − 4-1d 声明源 == 纯内部型集合）
NO_EXTERNAL_SOURCE_SLUGS: tuple[str, ...] = tuple(
    sorted(set(SLUG_TO_TOOL_ID) - set(SKILL_DATA_SOURCES) - set(MIXED_SKILL_DATA_SOURCES))
)


# =============================================================================
# 分型派生辅助（单一来源——断言函数与测试共用，防两份分型判定漂移）
# =============================================================================


def framework_type(slug: str) -> str:
    """返回 Skill 分型标识（"scoring" / "structural"）。

    Args:
        slug: Skill 标识（kebab-case）。

    Returns:
        分型标识："scoring"（评分型）或 "structural"（结构型）。

    Raises:
        KeyError: slug 不在本 Story 7 个目标集合中。
    """
    if slug in SCORING_TYPE_SLUGS:
        return "scoring"
    if slug in STRUCTURAL_TYPE_SLUGS:
        return "structural"
    raise KeyError(f"{slug} 不在 Story 4.1e 内部框架 Skill 集合中")


def required_references_for(slug: str) -> tuple[str, ...]:
    """按分型返回 references 三件套文件名元组。"""
    return SCORING_REFERENCES if framework_type(slug) == "scoring" else STRUCTURAL_REFERENCES


def required_template_sections_for(slug: str) -> tuple[str, ...]:
    """按分型返回模板四段式结构标题元组（第三段条件化——D5）。"""
    return SCORING_TEMPLATE_SECTIONS if framework_type(slug) == "scoring" else STRUCTURAL_TEMPLATE_SECTIONS


def _third_section_reference_for(slug: str) -> str:
    """按分型返回模板第三段引用字面串。"""
    return SCORING_ANCHOR_REFERENCE if framework_type(slug) == "scoring" else VALIDATION_RULES_REFERENCE


# =============================================================================
# 断言库（内部框架语义；断言函数签名与 4-1c/4-1d 契约库风格一致）
# =============================================================================


def assert_framework_data_sources_empty(slug: str, document: SkillDocument) -> None:
    """纯内部型一等不变量：frontmatter data_sources == ()（D1——不写键解析为空 tuple）。

    纯内部框架 Skill 的分析主体是用户输入的内部业务信息（经 ToolCall.arguments
    进入 Think prompt），声明任何外部数据源将破坏三分法自洽（6 外部 + 10 混合 +
    7 纯内部）并违反分类学。
    """
    actual = document.frontmatter.data_sources
    assert actual == (), f"{slug}: 纯内部框架 Skill 不应声明任何外部数据源（实际 {tuple(ref.name for ref in actual)}）"


def assert_sop_maturity(slug: str, document: SkillDocument) -> None:
    """SOP 成熟化断言：必备章节 / input_examples 非 placeholder / ≤500 行 / 失败处理
    双关键词（D3）/ 分型三件套与模板存在性。

    内部框架语义：references 三件套按分型（framework_logic + scoring_anchors 或
    validation_rules + workshop_guide）；失败处理断言集为 207（标记误用守护）+
    INSUFFICIENT_DATA（内部数据不足引导——文档级关键词，非运行时状态）。
    """
    body = document.body
    for section in REQUIRED_SOP_SECTIONS:
        assert section in body, f"{slug}: SOP 缺少必备章节「{section}」"

    # input_examples 非 placeholder
    assert "placeholder" not in body.lower(), f"{slug}: input_examples 仍为 placeholder"

    # 失败处理章节含双关键词——词边界正则防数字子串伪满足（4-1c R1-P2-4 同款）
    failure_section = body.split("失败处理", 1)[-1]
    for keyword in FAILURE_KEYWORDS:
        assert re.search(rf"\b{keyword}\b", failure_section), (
            f"{slug}: 失败处理章节缺少 {keyword} 语义引导（纯内部型失败面 = 标记误用 + 内部数据不足）"
        )

    # 行数硬约束（L2 ≤500 行）
    skill_md = SKILLS_ROOT / slug / "SKILL.md"
    line_count = len(skill_md.read_text(encoding="utf-8").splitlines())
    assert line_count <= SKILL_MD_MAX_LINES, f"{slug}: SKILL.md {line_count} 行超过 {SKILL_MD_MAX_LINES} 行硬约束"

    # references/templates 配套资源存在性（分型三件套）
    skill_dir = SKILLS_ROOT / slug
    references_dir = skill_dir / "references"
    templates_dir = skill_dir / "templates"
    assert references_dir.is_dir() and any(references_dir.iterdir()), f"{slug}: references/ 为空"
    assert templates_dir.is_dir() and any(templates_dir.iterdir()), f"{slug}: templates/ 为空"
    for ref_file in required_references_for(slug):
        assert (references_dir / ref_file).is_file(), f"{slug}: 缺少 references/{ref_file}"
    assert (templates_dir / TEMPLATE_FILES[slug]).is_file(), f"{slug}: 缺少 templates/{TEMPLATE_FILES[slug]}"


def assert_template_schema_alignment(slug: str, document: SkillDocument) -> None:
    """模板字段 ↔ input_schema 叶子键双向对应断言（AC-3 核心，import 4-1d 机械）。

    断言链：
    - 四段式结构完整（第三段按分型：评分锚点 / 校验规则——D5）
    - 第三段引用字面串（分型各一：scoring_anchors.md / validation_rules.md）
    - 数据缺口登记区表头存在
    - 模板采集字段集合 == input_schema 递归展开叶子键集合（双向）
    - required 叶子键标注「（必填）」后缀与 required 链严格一致
    - 采集表格区 `###` 分区标题集合 == input_schema 顶层容器键集合（双向；
      dependency-graph 顶层 array-of-objects 形态由 task_list 分区标题承载）
    """
    template_path = SKILLS_ROOT / slug / "templates" / TEMPLATE_FILES[slug]
    assert template_path.is_file(), f"{slug}: 模板文件不存在 {template_path}"
    template_text = template_path.read_text(encoding="utf-8")

    # 四段式结构（分型第三段）
    for section in required_template_sections_for(slug):
        assert f"## {section}" in template_text, f"{slug}: 模板缺少「{section}」段标题"

    # 第三段引用（分型各一）
    third_reference = _third_section_reference_for(slug)
    assert third_reference in template_text, f"{slug}: 模板第三段缺少 {third_reference} 引用"

    # 数据缺口登记区表头
    gap_section = template_text.split("数据缺口登记", 1)[-1]
    assert GAP_REGISTER_HEADER in gap_section, f"{slug}: 「数据缺口登记」区缺少表头 {GAP_REGISTER_HEADER}"

    # 叶子键双向比对 + required 标注一致性（import 4-1d 机械）
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

    # 分区标题 ↔ 顶层容器键双向断言（Story「内部数据契约」：分区标题字面值 == 顶层键名）
    collection = _collection_section(template_text)
    assert collection is not None, f"{slug}: 模板缺少「采集表格」区（四段式断言已保证存在，此处防御）"
    section_titles = re.findall(r"^###[ \t]+(.+?)[ \t]*$", collection, re.MULTILINE)
    container_keys = schema_top_level_container_keys(document.frontmatter.input_schema)
    extra_titles = sorted(set(section_titles) - set(container_keys))
    missing_keys = sorted(set(container_keys) - set(section_titles))
    assert set(section_titles) == set(container_keys), (
        f"{slug}: 模板分区标题与 Schema 顶层容器键不一致 — 标题多余: {extra_titles} / 容器键缺失: {missing_keys}"
    )


def assert_reference_content_anchors(slug: str, document: SkillDocument) -> None:
    """references 内容要素字面锚点断言（AC-2 验证标准——存在性断言的补强）。

    最低要素契约（防止「文件存在但要素残缺」的假一致）：
    - framework_logic.md：编号步骤序列（「步骤 1」或「第 1 步」起序，任一形态）
      + 提及模板分区/字段英文名（叶子键 ≥2 个）
    - scoring_anchors.md（评分型）：「分档含义」+「正例」与「反例」两个独立字样
      （不接受「正反例」合并词——其不含「正例」子串）
    - validation_rules.md（结构型）：逐条编号规则（「规则 1」或「1.」起序）+
      关键字至少其一（大小写不敏感）：RACI / DAG / CPM / 箭头 / 正则
    - workshop_guide.md：参与者角色分工（引导者/业务专家）+ 流程环节含时长与
      产出物 + 会后「模板→arguments 构造」闭环句
    """
    references_dir = SKILLS_ROOT / slug / "references"
    leaves = schema_leaf_keys(document.frontmatter.input_schema)

    framework_logic = (references_dir / "framework_logic.md").read_text(encoding="utf-8")
    assert "步骤 1" in framework_logic or "第 1 步" in framework_logic, (
        f"{slug}: framework_logic.md 缺少编号步骤序列（「步骤 1」或「第 1 步」起序）"
    )
    mentioned = [key for key in leaves if key in framework_logic]
    assert len(mentioned) >= 2, (
        f"{slug}: framework_logic.md 未提及模板字段英文名（至少 2 个叶子键，实际提及 {len(mentioned)} 个）"
    )

    if framework_type(slug) == "scoring":
        anchors = (references_dir / "scoring_anchors.md").read_text(encoding="utf-8")
        assert "分档含义" in anchors, f"{slug}: scoring_anchors.md 缺少「分档含义」"
        assert "正例" in anchors, f"{slug}: scoring_anchors.md 缺少「正例」（不接受「正反例」合并词）"
        assert "反例" in anchors, f"{slug}: scoring_anchors.md 缺少「反例」（不接受「正反例」合并词）"
    else:
        rules = (references_dir / "validation_rules.md").read_text(encoding="utf-8")
        assert "规则 1" in rules or "1." in rules, f"{slug}: validation_rules.md 缺少逐条编号规则（「规则 1」或「1.」起序）"
        keywords = ("RACI", "DAG", "CPM", "箭头", "正则")
        assert any(keyword.lower() in rules.lower() for keyword in keywords), (
            f"{slug}: validation_rules.md 缺少关键字（RACI/DAG/CPM/箭头/正则 至少其一，大小写不敏感）"
        )

    guide = (references_dir / "workshop_guide.md").read_text(encoding="utf-8")
    assert "引导者" in guide and "业务专家" in guide, f"{slug}: workshop_guide.md 缺少参与者角色分工（引导者/业务专家）"
    assert "产出" in guide and ("min" in guide.lower() or "分钟" in guide), (
        f"{slug}: workshop_guide.md 缺少流程环节时长与产出物"
    )
    assert "arguments" in guide, f"{slug}: workshop_guide.md 缺少会后「模板→arguments 构造」闭环句"
