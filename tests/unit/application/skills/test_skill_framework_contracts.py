"""Story 4.1e — 第三契约库（内部框架型）自检测试

验证 skill_framework_contracts.py 的常量 SSOT / identity 单一来源 / 分型契约 /
断言函数签名与失败路径判别力（每断言函数 ≥1 坏数据 pytest.raises 负例——
4-1d R1-F1 先例强制）。

自包含设计：失败路径负例经 monkeypatch SKILLS_ROOT + tmp_path 迷你 Skill 目录
构造，不依赖 7 个目标 Skill 的成熟化状态（Task 2-8 交付前即可全绿）。
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import tests.unit.application.skills.skill_framework_contracts as contracts
from src.application.ports.skill_loader import SkillDocument, ToolMetadata

# ===================================================================
# 独立硬编码基准（变异演示判别力来源——与契约库常量分离维护）
# ===================================================================

STORY_SSOT: tuple[str, ...] = (
    "value-proposition-canvas",
    "business-model-canvas",
    "org-design-framework",
    "strategy-map",
    "dependency-graph",
    "raci-matrix",
    "gantt-chart",
)

STORY_TEMPLATE_FILES: dict[str, str] = {
    "value-proposition-canvas": "vpc_canvas_matching.md",
    "business-model-canvas": "bmc_nine_blocks_canvas.md",
    "org-design-framework": "org_star_model_assessment.md",
    "strategy-map": "strategy_map_causal_links.md",
    "dependency-graph": "dependency_task_inventory.md",
    "raci-matrix": "raci_roles_tasks.md",
    "gantt-chart": "gantt_project_plan.md",
}


# ===================================================================
# 迷你 Skill 目录构造器（失败路径负例共用——tmp_path 自包含）
# ===================================================================


def _make_document(slug: str, body: str, input_schema: dict[str, Any] | None = None) -> SkillDocument:
    """构造测试用 SkillDocument（frontmatter 含指定 input_schema）。"""
    metadata = ToolMetadata(
        tool_name=slug,
        slug=slug,
        category="execution_management",
        input_schema=input_schema or {},
        output_schema={},
    )
    return SkillDocument(tool_name=slug, slug=slug, content="", token_count=0, frontmatter=metadata, body=body)


def _write_mini_skill(
    tmp_path: Path,
    slug: str,
    *,
    skill_md_lines: list[str] | None = None,
    template_text: str = "",
    reference_files: dict[str, str] | None = None,
) -> None:
    """在 tmp_path 下构造迷你 Skill 目录（SKILL.md + references/ + templates/）。"""
    skill_dir = tmp_path / slug
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "templates").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("\n".join(skill_md_lines or ["---", "---", "# x"]), encoding="utf-8")
    template_name = contracts.TEMPLATE_FILES.get(slug, "t.md")
    (skill_dir / "templates" / template_name).write_text(template_text, encoding="utf-8")
    for name, text in (reference_files or {}).items():
        (skill_dir / "references" / name).write_text(text, encoding="utf-8")


class TestFrameworkSkillSlugs:
    """SSOT 声明表：7 slug 有序元组 + 分型划分 + manifest 注册 + 派生收敛。"""

    def test_entries_match_story_ssot_verbatim(self) -> None:
        """契约库 slug 清单与 Story 数据契约表逐字一致（有序）。"""
        assert contracts.FRAMEWORK_SKILL_SLUGS == STORY_SSOT

    def test_exactly_seven_skills(self) -> None:
        assert len(contracts.FRAMEWORK_SKILL_SLUGS) == 7

    def test_type_partition_complete_and_disjoint(self) -> None:
        """分型划分完整：评分型 3 + 结构型 4，互斥且并集 == 全集。"""
        scoring = set(contracts.SCORING_TYPE_SLUGS)
        structural = set(contracts.STRUCTURAL_TYPE_SLUGS)
        assert len(scoring) == 3
        assert len(structural) == 4
        assert not (scoring & structural), "分型互斥被破坏"
        assert scoring | structural == set(contracts.FRAMEWORK_SKILL_SLUGS)

    def test_all_registered_in_manifest(self) -> None:
        from src.application.skills.skill_manifest import SLUG_TO_TOOL_ID

        assert set(contracts.FRAMEWORK_SKILL_SLUGS) <= set(SLUG_TO_TOOL_ID)

    def test_derived_no_external_source_slugs(self) -> None:
        """派生收敛（D2）：全集 − 4-1c − 4-1d == 本 Story 7 slug（非空，判别力保留）。"""
        derived = contracts.NO_EXTERNAL_SOURCE_SLUGS
        assert len(derived) == 7, f"派生结果应恰为 7（实际 {len(derived)}）"
        assert set(derived) == set(STORY_SSOT), f"派生集合与本 Story 目标不一致: {derived}"


class TestSharedConstantsSingleSource:
    """跨 Story 共享常量 identity 断言（is 检查——import 而非复制，4-1d R2-F2 先例）。"""

    def test_shared_constants_are_imported_not_copied(self) -> None:
        import tests.unit.application.skills.skill_data_collection_contracts as contracts_41c
        import tests.unit.application.skills.skill_mixed_data_contracts as contracts_41d

        assert contracts.REQUIRED_SOP_SECTIONS is contracts_41c.REQUIRED_SOP_SECTIONS
        assert contracts.SKILL_MD_MAX_LINES is contracts_41c.SKILL_MD_MAX_LINES
        assert contracts.SKILLS_ROOT is contracts_41c.SKILLS_ROOT
        assert contracts.load_io_contract is contracts_41c.load_io_contract
        assert contracts.schema_leaf_keys is contracts_41d.schema_leaf_keys
        assert contracts.extract_template_fields is contracts_41d.extract_template_fields
        assert contracts.build_min_arguments is contracts_41d.build_min_arguments
        assert contracts.DATA_SOURCE_MARKER_PATTERN is contracts_41c.DATA_SOURCE_MARKER_PATTERN

    def test_line_limit_value_locked(self) -> None:
        assert contracts.SKILL_MD_MAX_LINES == 500

    def test_shared_machinery_from_41d_not_copied(self) -> None:
        """模板机械（分区截取/顶层容器键提取）从 4-1d 库 import（防第三次复制）。"""
        import tests.unit.application.skills.skill_mixed_data_contracts as contracts_41d

        assert contracts.schema_top_level_container_keys is contracts_41d.schema_top_level_container_keys


class TestTemplateContract:
    """分型契约常量：模板命名表 / 三件套 / 第三段字面值 / 失败处理关键词。"""

    def test_template_files_match_story_table(self) -> None:
        assert contracts.TEMPLATE_FILES == STORY_TEMPLATE_FILES

    def test_template_files_all_markdown_and_unique(self) -> None:
        names = list(contracts.TEMPLATE_FILES.values())
        assert all(name.endswith(".md") for name in names)
        assert len(set(names)) == len(names) == 7

    def test_scoring_references_trio(self) -> None:
        """评分型三件套：framework_logic / scoring_anchors / workshop_guide（D4）。"""
        assert contracts.SCORING_REFERENCES == ("framework_logic.md", "scoring_anchors.md", "workshop_guide.md")

    def test_structural_references_trio(self) -> None:
        """结构型三件套：framework_logic / validation_rules / workshop_guide（D4）。"""
        assert contracts.STRUCTURAL_REFERENCES == ("framework_logic.md", "validation_rules.md", "workshop_guide.md")

    def test_template_sections_by_type(self) -> None:
        """模板四段式第三段按分型条件化（D5）：评分锚点 / 校验规则。"""
        assert contracts.SCORING_TEMPLATE_SECTIONS == ("基本信息", "采集表格", "评分锚点", "数据缺口登记")
        assert contracts.STRUCTURAL_TEMPLATE_SECTIONS == ("基本信息", "采集表格", "校验规则", "数据缺口登记")

    def test_third_section_reference_literals(self) -> None:
        assert contracts.SCORING_ANCHOR_REFERENCE == "references/scoring_anchors.md"
        assert contracts.VALIDATION_RULES_REFERENCE == "references/validation_rules.md"

    def test_failure_keywords_semantics(self) -> None:
        """失败处理断言集（D3）：207 + INSUFFICIENT_DATA，替换 411/412/413。"""
        assert contracts.FAILURE_KEYWORDS == ("207", "INSUFFICIENT_DATA")
        # 判别力负例：外部采集语义关键词不得混入纯内部型断言集
        for stale in ("411", "412", "413"):
            assert stale not in contracts.FAILURE_KEYWORDS

    def test_framework_type_dispatch(self) -> None:
        assert contracts.framework_type("value-proposition-canvas") == "scoring"
        assert contracts.framework_type("gantt-chart") == "structural"
        with pytest.raises(KeyError):
            contracts.framework_type("swot-tows")


class TestAssertionFunctions:
    """六断言函数存在性 + 签名形态（4-1d TestAssertionFunctions 先例）。"""

    def test_assertion_functions_exist(self) -> None:
        for name in (
            "assert_framework_data_sources_empty",
            "assert_io_schema_contract",
            "assert_sop_maturity",
            "assert_cross_consistency",
            "assert_template_schema_alignment",
            "assert_reference_content_anchors",
        ):
            assert callable(getattr(contracts, name)), f"缺少断言函数 {name}"

    def test_assertion_signatures(self) -> None:
        """断言签名落两种形态之一：(slug, metadata) 或 (slug, document)。"""
        for name in (
            "assert_framework_data_sources_empty",
            "assert_io_schema_contract",
            "assert_sop_maturity",
            "assert_cross_consistency",
            "assert_template_schema_alignment",
            "assert_reference_content_anchors",
        ):
            params = tuple(inspect.signature(getattr(contracts, name)).parameters)
            assert params in (("slug", "metadata"), ("slug", "document")), f"{name} 签名形态异常: {params}"


class TestAssertionFailurePaths:
    """失败路径负例（判别力实证——每断言函数 ≥1 坏数据 pytest.raises，4-1d R1-F1 先例）。"""

    def test_framework_data_sources_empty_rejects_declaration(self) -> None:
        """data_sources 非空 → 红（纯内部型一等不变量）。"""
        from src.domain.value_objects.data_source import DataSourceApiType, DataSourceRef

        ref = DataSourceRef(
            name="world-bank", url="https://api.worldbank.org/v2", ttl_seconds=604800, api_type=DataSourceApiType.REST_JSON
        )
        document = _make_document("value-proposition-canvas", body="x")
        document = replace(document, frontmatter=replace(document.frontmatter, data_sources=(ref,)))
        with pytest.raises(AssertionError, match="不应声明任何外部数据源"):
            contracts.assert_framework_data_sources_empty("value-proposition-canvas", document)

    def test_io_schema_contract_detects_drift(self) -> None:
        """schema 漂移 → 红（复用 4-1c 断言的判别力，用既有 yaml 条目 swot-tows 验证）。"""
        contract = contracts.load_io_contract("swot-tows")
        drifted = {**contract["input_schema"], "required": []}
        metadata = ToolMetadata(
            tool_name="SWOT-TOWS",
            slug="swot-tows",
            category="strategic_selection",
            input_schema=drifted,
            output_schema=contract["output_schema"],
        )
        with pytest.raises(AssertionError, match="input_schema 与契约文件不一致"):
            contracts.assert_io_schema_contract("swot-tows", metadata)

    def test_sop_maturity_rejects_missing_section(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SOP 缺必备章节 → 红。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(tmp_path, "gantt-chart", skill_md_lines=["# x"])
        body = "适用场景 负向触发 输入字段 输出字段 执行步骤 失败处理 207 INSUFFICIENT_DATA input_examples References"
        document = _make_document("gantt-chart", body=body)
        with pytest.raises(AssertionError, match="缺少必备章节"):
            contracts.assert_sop_maturity("gantt-chart", document)

    def test_sop_maturity_rejects_placeholder(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(tmp_path, "gantt-chart", skill_md_lines=["# x"])
        body = (
            "适用场景 负向触发 输入字段 输出字段 数据采集计划 执行步骤 失败处理"
            " 207 INSUFFICIENT_DATA input_examples References placeholder"
        )
        document = _make_document("gantt-chart", body=body)
        with pytest.raises(AssertionError, match="placeholder"):
            contracts.assert_sop_maturity("gantt-chart", document)

    def test_sop_maturity_rejects_missing_failure_keywords(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """失败处理缺 D3 关键词（207 / INSUFFICIENT_DATA）→ 红（词边界）。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(tmp_path, "gantt-chart", skill_md_lines=["# x"])
        body = "适用场景 负向触发 输入字段 输出字段 数据采集计划 执行步骤 失败处理 input_examples References"
        document = _make_document("gantt-chart", body=body)
        with pytest.raises(AssertionError, match="失败处理章节缺少 207"):
            contracts.assert_sop_maturity("gantt-chart", document)

    def test_sop_maturity_rejects_411_style_keywords_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """判别力负例：仅含 411/412/413（外部采集语义）不含 207 → 红。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(tmp_path, "gantt-chart", skill_md_lines=["# x"])
        body = "适用场景 负向触发 输入字段 输出字段 数据采集计划 执行步骤 失败处理 411 412 413 input_examples References"
        document = _make_document("gantt-chart", body=body)
        with pytest.raises(AssertionError, match="失败处理章节缺少 207"):
            contracts.assert_sop_maturity("gantt-chart", document)

    def test_sop_maturity_rejects_line_overflow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SKILL.md 超 500 行 → 红。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(tmp_path, "gantt-chart", skill_md_lines=["x"] * 501)
        body = (
            "适用场景 负向触发 输入字段 输出字段 数据采集计划 执行步骤 失败处理 207 INSUFFICIENT_DATA input_examples References"
        )
        document = _make_document("gantt-chart", body=body)
        with pytest.raises(AssertionError, match="超过.*行硬约束"):
            contracts.assert_sop_maturity("gantt-chart", document)

    def test_sop_maturity_rejects_wrong_references_trio(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """结构型 Skill 用评分型三件套（scoring_anchors）→ 红（分型判别力）。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(
            tmp_path,
            "gantt-chart",
            skill_md_lines=["# x"],
            reference_files={"scoring_anchors.md": "x", "workshop_guide.md": "x"},
        )
        body = (
            "适用场景 负向触发 输入字段 输出字段 数据采集计划 执行步骤 失败处理 207 INSUFFICIENT_DATA input_examples References"
        )
        document = _make_document("gantt-chart", body=body)
        with pytest.raises(AssertionError, match="缺少 references/framework_logic.md"):
            contracts.assert_sop_maturity("gantt-chart", document)

    def test_sop_maturity_rejects_missing_template(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(
            tmp_path,
            "gantt-chart",
            skill_md_lines=["# x"],
            template_text="占位（非空目录即可）",
            reference_files={
                "framework_logic.md": "x",
                "validation_rules.md": "x",
                "workshop_guide.md": "x",
            },
        )
        (tmp_path / "gantt-chart" / "templates" / "notes.md").write_text("目录非空占位", encoding="utf-8")
        (tmp_path / "gantt-chart" / "templates" / contracts.TEMPLATE_FILES["gantt-chart"]).unlink()
        body = (
            "适用场景 负向触发 输入字段 输出字段 数据采集计划 执行步骤 失败处理 207 INSUFFICIENT_DATA input_examples References"
        )
        document = _make_document("gantt-chart", body=body)
        with pytest.raises(AssertionError, match="缺少 templates/"):
            contracts.assert_sop_maturity("gantt-chart", document)

    def test_cross_consistency_rejects_stray_marker(self) -> None:
        """空集语义判别力：body 含 $DATA_SOURCE 标记 + data_sources=() → 红。"""
        document = _make_document("raci-matrix", body='data = $DATA_SOURCE("world-bank", "查询")')
        with pytest.raises(AssertionError, match="跨循环一致性破坏"):
            contracts.assert_cross_consistency("raci-matrix", document)

    def test_template_alignment_rejects_extra_field(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """模板字段多余 → 红（双向断言）。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        schema = {
            "type": "object",
            "required": ["project_plan"],
            "properties": {
                "project_plan": {
                    "type": "object",
                    "required": ["tasks"],
                    "description": "项目计划",
                    "properties": {"tasks": {"type": "array", "description": "任务清单", "items": {"type": "string"}}},
                }
            },
        }
        template = (
            "## 基本信息\n| 字段 | 说明 |\n\n## 采集表格\n\n### project_plan\n\n"
            "| 字段 | 说明 |\n| --- | --- |\n| tasks（必填） | 任务 A |\n| extra（必填） | 多余字段 |\n\n"
            "## 校验规则\n见 references/validation_rules.md。\n\n"
            "## 数据缺口登记\n\n| 字段 | 缺口描述 | 替代来源 |\n"
        )
        _write_mini_skill(tmp_path, "gantt-chart", template_text=template)
        document = _make_document("gantt-chart", body="x", input_schema=schema)
        with pytest.raises(AssertionError, match="模板多余"):
            contracts.assert_template_schema_alignment("gantt-chart", document)

    def test_template_alignment_rejects_missing_leaf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """叶子缺失 → 红（双向断言）。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        schema = {
            "type": "object",
            "required": ["project_plan"],
            "properties": {
                "project_plan": {
                    "type": "object",
                    "required": ["tasks", "dependencies"],
                    "description": "项目计划",
                    "properties": {
                        "tasks": {"type": "array", "description": "任务清单", "items": {"type": "string"}},
                        "dependencies": {"type": "array", "description": "依赖", "items": {"type": "string"}},
                    },
                }
            },
        }
        template = (
            "## 基本信息\n| 字段 | 说明 |\n\n## 采集表格\n\n### project_plan\n\n"
            "| 字段 | 说明 |\n| --- | --- |\n| tasks（必填） | 任务 A |\n\n"
            "## 校验规则\n见 references/validation_rules.md。\n\n"
            "## 数据缺口登记\n\n| 字段 | 缺口描述 | 替代来源 |\n"
        )
        _write_mini_skill(tmp_path, "gantt-chart", template_text=template)
        document = _make_document("gantt-chart", body="x", input_schema=schema)
        with pytest.raises(AssertionError, match="叶子缺失.*dependencies"):
            contracts.assert_template_schema_alignment("gantt-chart", document)

    def test_template_alignment_rejects_wrong_third_section_for_type(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """分型判别力：结构型模板第三段误写「评分锚点」→ 红。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        schema = {
            "type": "object",
            "required": ["project_plan"],
            "properties": {
                "project_plan": {
                    "type": "object",
                    "required": ["tasks"],
                    "description": "项目计划",
                    "properties": {"tasks": {"type": "array", "description": "任务清单", "items": {"type": "string"}}},
                }
            },
        }
        template = (
            "## 基本信息\n| 字段 | 说明 |\n\n## 采集表格\n\n### project_plan\n\n"
            "| 字段 | 说明 |\n| --- | --- |\n| tasks（必填） | 任务 A |\n\n"
            "## 评分锚点\n见 references/scoring_anchors.md。\n\n"
            "## 数据缺口登记\n\n| 字段 | 缺口描述 | 替代来源 |\n"
        )
        _write_mini_skill(tmp_path, "gantt-chart", template_text=template)
        document = _make_document("gantt-chart", body="x", input_schema=schema)
        with pytest.raises(AssertionError, match="校验规则"):
            contracts.assert_template_schema_alignment("gantt-chart", document)


class TestReferenceContentAnchorsNegative:
    """references 内容要素字面锚点判别力（R6：两分型各一负例）。"""

    def _scoring_document(self) -> SkillDocument:
        schema = {
            "type": "object",
            "required": ["value_map"],
            "properties": {
                "value_map": {
                    "type": "object",
                    "required": ["products", "pains"],
                    "description": "价值图",
                    "properties": {
                        "products": {"type": "array", "description": "产品清单", "items": {"type": "string"}},
                        "pains": {"type": "array", "description": "痛点清单", "items": {"type": "string"}},
                    },
                }
            },
        }
        return _make_document("value-proposition-canvas", body="x", input_schema=schema)

    def _structural_references(self) -> dict[str, str]:
        return {
            "framework_logic.md": "## 步骤\n步骤 1 确认任务与依赖（tasks/dependencies）。\n",
            "validation_rules.md": "## 规则\n规则 1 DAG 无环校验（正则解析任务名）。\n",
            "workshop_guide.md": "引导者与业务专家分工，30 min 环节含产出物，会后按模板构造 arguments。\n",
        }

    def test_framework_logic_without_numbered_steps_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(
            tmp_path,
            "value-proposition-canvas",
            reference_files={
                "framework_logic.md": "先分析 pains 再分析 gains（无编号步骤）。",
                "scoring_anchors.md": "分档含义表。正例：x。反例：y。",
                "workshop_guide.md": "引导者/业务专家，30 min，产出物，arguments。",
            },
        )
        with pytest.raises(AssertionError, match="framework_logic.md 缺少编号步骤序列"):
            contracts.assert_reference_content_anchors("value-proposition-canvas", self._scoring_document())

    def test_framework_logic_without_english_keys_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(
            tmp_path,
            "value-proposition-canvas",
            reference_files={
                "framework_logic.md": "步骤 1 分析价值图与客户画像（全中文表述，无英文字段名）。",
                "scoring_anchors.md": "分档含义表。正例：x。反例：y。",
                "workshop_guide.md": "引导者/业务专家，30 min，产出物，arguments。",
            },
        )
        with pytest.raises(AssertionError, match="framework_logic.md 未提及模板字段英文名"):
            contracts.assert_reference_content_anchors("value-proposition-canvas", self._scoring_document())

    def test_scoring_anchors_without_separate_examples_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """「正反例」合并词不含「正例」子串 → 红（R3-3 锚点定义）。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(
            tmp_path,
            "value-proposition-canvas",
            reference_files={
                "framework_logic.md": "步骤 1 匹配 pains 与 pain_relievers（products 对应 jobs）。",
                "scoring_anchors.md": "分档含义表。正反例锚点如下。",
                "workshop_guide.md": "引导者/业务专家，30 min，产出物，arguments。",
            },
        )
        with pytest.raises(AssertionError, match="scoring_anchors.md 缺少「正例」"):
            contracts.assert_reference_content_anchors("value-proposition-canvas", self._scoring_document())

    def test_scoring_anchors_without_grade_table_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        _write_mini_skill(
            tmp_path,
            "value-proposition-canvas",
            reference_files={
                "framework_logic.md": "步骤 1 匹配 pains 与 pain_relievers（products 对应 jobs）。",
                "scoring_anchors.md": "刻度声明。正例：x。反例：y。（无档位表）",
                "workshop_guide.md": "引导者/业务专家，30 min，产出物，arguments。",
            },
        )
        with pytest.raises(AssertionError, match="scoring_anchors.md 缺少「分档含义」"):
            contracts.assert_reference_content_anchors("value-proposition-canvas", self._scoring_document())

    def test_structural_validation_rules_without_keyword_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """结构型判别力：validation_rules 缺关键字（RACI/DAG/CPM/箭头/正则）→ 红。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        references = self._structural_references()
        references["validation_rules.md"] = "规则 1 任务名不得为空。规则 2 依赖引用必须存在。（无关键字）"
        _write_mini_skill(
            tmp_path,
            "gantt-chart",
            reference_files={
                **references,
                "framework_logic.md": "步骤 1 拆分任务（tasks）与依赖（dependencies）。",
            },
        )
        schema = {
            "type": "object",
            "required": ["project_plan"],
            "properties": {
                "project_plan": {
                    "type": "object",
                    "required": ["tasks", "dependencies"],
                    "description": "项目计划",
                    "properties": {
                        "tasks": {"type": "array", "description": "任务清单", "items": {"type": "string"}},
                        "dependencies": {"type": "array", "description": "依赖边", "items": {"type": "string"}},
                    },
                }
            },
        }
        document = _make_document("gantt-chart", body="x", input_schema=schema)
        with pytest.raises(AssertionError, match="validation_rules.md 缺少关键字"):
            contracts.assert_reference_content_anchors("gantt-chart", document)

    def test_structural_workshop_guide_without_arguments_loop_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """workshop_guide 缺会后「模板→arguments 构造」闭环句 → 红。"""
        monkeypatch.setattr(contracts, "SKILLS_ROOT", tmp_path)
        references = self._structural_references()
        references["workshop_guide.md"] = "引导者与业务专家分工，30 min 环节含产出物。（缺会后闭环）"
        _write_mini_skill(tmp_path, "gantt-chart", reference_files=references)
        schema = {
            "type": "object",
            "required": ["project_plan"],
            "properties": {
                "project_plan": {
                    "type": "object",
                    "required": ["tasks", "dependencies"],
                    "description": "项目计划",
                    "properties": {
                        "tasks": {"type": "array", "description": "任务清单", "items": {"type": "string"}},
                        "dependencies": {"type": "array", "description": "依赖边", "items": {"type": "string"}},
                    },
                }
            },
        }
        document = _make_document("gantt-chart", body="x", input_schema=schema)
        with pytest.raises(AssertionError, match="workshop_guide.md 缺少会后"):
            contracts.assert_reference_content_anchors("gantt-chart", document)
