"""StrategicReport 实体与报告文档 VO 单元测试（Story 6-5a Task 1 循环 A）。

覆盖面：
- 实体不变量：report_type 枚举成员校验（裸 str 拒绝——ArchiveType validate 同款形态）/
  file_path 非空 / 计数不变量（degraded_section_count ≤ section_count），违例 242
- VO 校验：ReportSection.level 值域 1-3（R2-6 收窄——不开 H4）/ ReportBlock.kind
  白名单四值 / 表格列数一致（rows 每行 len == len(headers)），违例 242

Run with:
    poetry run pytest tests/unit/domain/test_strategic_report.py -v
"""

import uuid
from datetime import datetime, timezone

import pytest

from src.domain.entities.strategic_report import ReportType, StrategicReport
from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.markdown_report import (
    MarkdownReportDocument,
    ReportBlock,
    ReportSection,
)


class TestReportTypeEnum:
    """ReportType 枚举值域（6-5b PDF 预留值——本 Story 仅产 MARKDOWN）。"""

    def test_markdown_value(self) -> None:
        """MARKDOWN 成员值为 "markdown"（L2 report_type 列与事件 report_type 键源）。"""
        assert ReportType.MARKDOWN.value == "markdown"

    def test_pdf_value_reserved(self) -> None:
        """PDF 成员值为 "pdf"（6-5b 预留——本 Story 零产出）。"""
        assert ReportType.PDF.value == "pdf"

    def test_member_count(self) -> None:
        """枚举恰两成员（增减即契约变更——6-5b 前不扩）。"""
        assert len(list(ReportType)) == 2


class TestStrategicReportValidConstruction:
    """StrategicReport 合法构造面。"""

    def test_defaults_construction(self) -> None:
        """缺省构造：report_id 自动 uuid4 / report_type=MARKDOWN / created_at UTC now。"""
        report = StrategicReport(
            plan_id=str(uuid.uuid4()),
            file_path="reports/plan-1_20261103120000.md",
            section_count=11,
            degraded_section_count=0,
            generation_ms=150,
        )
        assert isinstance(report.report_id, uuid.UUID)
        assert report.report_type is ReportType.MARKDOWN
        assert report.section_count == 11
        assert report.degraded_section_count == 0
        assert report.generation_ms == 150
        assert isinstance(report.created_at, datetime)
        assert report.created_at.tzinfo is not None

    def test_full_construction(self) -> None:
        """全字段构造（frozen——字段可读不可变）。"""
        report_id = uuid.uuid4()
        created_at = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
        report = StrategicReport(
            report_id=report_id,
            plan_id="plan-full",
            report_type=ReportType.MARKDOWN,
            file_path="reports/plan-full_20261103120000.md",
            section_count=11,
            degraded_section_count=2,
            generation_ms=300,
            created_at=created_at,
        )
        assert report.report_id == report_id
        assert report.report_type is ReportType.MARKDOWN
        assert report.created_at == created_at

    def test_frozen_immutability(self) -> None:
        """frozen dataclass——字段赋值抛 FrozenInstanceError（setattr 动态形态——静态面合法）。"""
        from dataclasses import FrozenInstanceError

        report = StrategicReport(plan_id="p", file_path="reports/p_1.md", section_count=0, degraded_section_count=0)
        with pytest.raises(FrozenInstanceError):
            setattr(report, "plan_id", "other")


class TestStrategicReportInvariants:
    """实体不变量守卫（违例抛 EntityValidationError 242——构造期 fail-loud）。"""

    def test_report_type_rejects_bare_str(self) -> None:
        """裸 str 拒绝（ArchiveType validate 同款——仅枚举成员合法——cast 注入非法形态）。"""
        from typing import cast

        with pytest.raises(EntityValidationError) as exc_info:
            StrategicReport(
                plan_id="p",
                report_type=cast("ReportType", "markdown"),
                file_path="reports/p_1.md",
                section_count=0,
                degraded_section_count=0,
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert "report_type" in str(exc_info.value.context)

    def test_file_path_empty_rejected(self) -> None:
        """file_path 非空守卫（L0 逻辑路径单源派生锚）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            StrategicReport(plan_id="p", file_path="", section_count=0, degraded_section_count=0)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_file_path_whitespace_only_rejected(self) -> None:
        """file_path 纯空白拒（CR1-F6——strip 非空，防空白路径静默落库）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            StrategicReport(plan_id="p", file_path="   ", section_count=0, degraded_section_count=0)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_plan_id_empty_rejected(self) -> None:
        """plan_id 非空守卫（CR1-F6——字段表「非空 UUID 字符串」契约落地，防脏实体毒化 L2 查询面）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            StrategicReport(plan_id="", file_path="reports/p_1.md", section_count=0, degraded_section_count=0)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "plan_id"

    def test_negative_section_count_rejected(self) -> None:
        """section_count 负值拒（CR1-F6——字段表 ≥0 约束；负值对 -5 ≤ -5 会绕过大小不变量）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            StrategicReport(plan_id="p", file_path="reports/p_1.md", section_count=-5, degraded_section_count=-5)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_negative_generation_ms_rejected(self) -> None:
        """generation_ms 负值拒（CR1-F6——耗时字段 ≥0 约束）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            StrategicReport(
                plan_id="p", file_path="reports/p_1.md", section_count=1, degraded_section_count=0, generation_ms=-100
            )
        assert exc_info.value.code == "EXCEPTION_242"

    def test_degraded_exceeds_section_rejected(self) -> None:
        """计数不变量：degraded_section_count > section_count 抛 242（缺三步场景锁死）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            StrategicReport(
                plan_id="p",
                file_path="reports/p_1.md",
                section_count=11,
                degraded_section_count=12,
            )
        assert exc_info.value.code == "EXCEPTION_242"

    def test_degraded_equal_section_allowed(self) -> None:
        """边界：degraded == section 合法（极端形态 11 == 11——R2-2 算术上限）。"""
        report = StrategicReport(
            plan_id="p",
            file_path="reports/p_1.md",
            section_count=11,
            degraded_section_count=11,
        )
        assert report.degraded_section_count == 11


class TestReportSectionVo:
    """ReportSection VO（level 值域 1-3——R2-6 收窄，level=4 无渲染语法放行即缺陷）。"""

    def test_valid_levels(self) -> None:
        """level 1/2/3 三档全部合法（H1/H2/H3）。"""
        for level in (1, 2, 3):
            section = ReportSection(title=f"章-{level}", level=level)
            assert section.level == level
            assert section.blocks == ()

    def test_level_zero_rejected(self) -> None:
        """level=0 越下界抛 242。"""
        with pytest.raises(EntityValidationError) as exc_info:
            ReportSection(title="章", level=0)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_level_four_rejected(self) -> None:
        """level=4 越上界抛 242（与「严格 1-3 不开 H4」冻结三方对齐）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            ReportSection(title="章", level=4)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_blocks_tuple(self) -> None:
        """blocks 接受 ReportBlock 元组（章节内容载体）。"""
        block = ReportBlock(kind="paragraph", text="段落文本")
        section = ReportSection(title="小节", level=3, blocks=(block,))
        assert section.blocks == (block,)


class TestReportBlockVo:
    """ReportBlock VO（联合形态单类 + kind 判别——四块型冻结）。"""

    def test_paragraph_block(self) -> None:
        """paragraph 块：text 载荷。"""
        block = ReportBlock(kind="paragraph", text="结论文本")
        assert block.kind == "paragraph"
        assert block.text == "结论文本"

    def test_bullet_list_block(self) -> None:
        """bullet_list 块：items 元组载荷。"""
        block = ReportBlock(kind="bullet_list", items=("要点一", "要点二"))
        assert block.items == ("要点一", "要点二")

    def test_table_block(self) -> None:
        """table 块：headers + rows 元组载荷。"""
        block = ReportBlock(
            kind="table",
            headers=("维度", "评估"),
            rows=(("政治", "稳定"), ("经济", "增长")),
        )
        assert len(block.rows) == 2

    def test_callout_block(self) -> None:
        """callout 块：降级/缺失标注载荷（`> ` 前缀渲染）。"""
        block = ReportBlock(kind="callout", text="⚠️ [数据缺失] 看趋势：该步骤归档记录不可用")
        assert block.kind == "callout"

    def test_kind_whitelist_rejected(self) -> None:
        """kind 白名单外抛 242（四块型冻结——heading/code 等均非法）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            ReportBlock(kind="heading", text="标题")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_table_column_mismatch_rejected(self) -> None:
        """表格列数不一致抛 242（rows 每行 len == len(headers)——GFM 列对齐守卫）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            ReportBlock(kind="table", headers=("维度", "评估"), rows=(("政治", "评估要点", "多余列"),))
        assert exc_info.value.code == "EXCEPTION_242"

    def test_table_row_not_tuple_rejected(self) -> None:
        """数据行非 tuple 形态抛 242（str 行 len 巧合撞列数不可静默通过——cast 注入非法形态）。"""
        from typing import cast

        with pytest.raises(EntityValidationError) as exc_info:
            ReportBlock(
                kind="table",
                headers=("维度", "评估"),
                rows=cast("tuple[tuple[str, ...], ...]", ("政治评估",)),
            )
        assert exc_info.value.code == "EXCEPTION_242"

    def test_table_empty_headers_with_rows_rejected(self) -> None:
        """空表头带数据行抛 242（列数 0 != 行列数——防畸形表）。"""
        with pytest.raises(EntityValidationError):
            ReportBlock(kind="table", headers=(), rows=(("政治", "评估"),))


class TestMarkdownReportDocumentVo:
    """MarkdownReportDocument VO（文档根——应用层聚合产物→渲染器入参）。"""

    def test_defaults_construction(self) -> None:
        """缺省构造：meta_rows/sections 空 + toc_enabled=True。"""
        document = MarkdownReportDocument(plan_id="plan-1", title="战略规划报告（BLM 前两阶段）")
        assert document.plan_id == "plan-1"
        assert document.meta_rows == ()
        assert document.sections == ()
        assert document.toc_enabled is True

    def test_full_construction(self) -> None:
        """全字段构造（元信息两列表 + 章节元组 + toc 开关）。"""
        section = ReportSection(title="1 业绩差距分析", level=2)
        document = MarkdownReportDocument(
            plan_id="plan-1",
            title="战略规划报告（BLM 前两阶段）",
            meta_rows=(("报告类型", "markdown"), ("计划标识", "plan-1")),
            sections=(section,),
            toc_enabled=False,
        )
        assert document.meta_rows[0] == ("报告类型", "markdown")
        assert document.sections == (section,)
        assert document.toc_enabled is False
