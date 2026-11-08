"""顾问视图服务（Story 6-10）——三段聚合编排 + 排序派生 + 双段联动容错.

读侧聚合 CQRS 投影（R2 应用层具体端口组合注入两既有 R1 端口）：
    - 多项目段（projects）：ArchiveRepositoryPort.find(ArchiveQuery(plan_id=None,
      limit=PANEL_ARCHIVE_LIMIT)) 全量行 → plan_id=None 行剔除（防御）→ distinct
      plan 分组（每 plan 归档计数+最新活动时间）→ 循环 ReportRepositoryProtocol
      .get_latest_by_plan 报告概况（N+1 点查——MVP plan 数个位数量级 <50ms 实测
      预期）→ 两趟稳定排序（Task 0.2 口径一）；
    - 品牌段（brand）：零 IO 静态段（纯常量构造——_build_brand 无任何仓储调用）；
    - 导出段（export）：项目段循环结果的纯投影派生（零新读——服务仅两读源
      archives+reports，第三段不发起 IO；单源纪律 OD-7）。

段级容错（OD-12 双段联动——段级容错族的复合段新形态）：archive find 异常 →
projects+export 双段联动降级（export 派生源受损——结构性依赖非耦合缺陷）；
循环内单 plan get_latest_by_plan 异常 → 该行报告列三键 None+双段 degraded=True
（保守诚实：「拿不到」与「没有」经段哨兵区分——行级 None 同形，段哨兵是唯一
区分面；降级值两形态分立：find 级=段值降默认[plan_count 0+空 tuple]；循环级=
清单保留+报告列 None——「部分降级」语义）；brand 段零降级面（零 IO 恒稳——
degraded 键恒 False 是结构性承诺）；视图整体不抛（AC-5 空态幂等读五先例族第六连）。

排序钦定（Task 0.2 口径一——可执行两趟稳定排序）：latest_activity_at 降序
（最新活动优先）+ 同时间戳 tie-break plan_id 字典序升序 + None 时间戳恒排尾
（None 归一 "" 在 reverse 后居尾）；两趟实现（plan_id 升序先排+latest_activity_at
归一降序后排）——str 不支持一元负号禁 key=(-ts, plan_id) 伪码；禁 reverse=True
整键复合反转（会连带把 tie-break 反转为降序）；禁依赖 find 返回序（find 序是
行级 archived_at 降序非 plan 聚合序，两序分立）。

性能口径注记（OD-8——docstring 承载）：N+1 点查链（plan 数百级成热点）与
find 1000 行截断双风险——「DISTINCT+JOIN LATERAL 单查询化 / SQL 化清单端口」
立项锚 Epic 7/21。

服务无状态（SINGLETON 并发共享——AC-7 约束；禁持每次调用的可变实例态）。

端口版本：(v1.0.0)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from src.application.ports.consultant_view import (
    BRAND_FONT_STATUS,
    BRAND_STATUS_UNCONFIGURED,
    PANEL_ARCHIVE_LIMIT,
    BrandSection,
    ConsultantView,
    ConsultantViewPort,
    ExportSection,
    ProjectsSection,
    ProjectSummary,
)
from src.domain.entities.strategic_archive import StrategicArchive
from src.domain.ports.archive_repository import ArchiveQuery, ArchiveRepositoryPort
from src.domain.ports.report_repository import ReportRepositoryProtocol

__all__ = ["ConsultantViewService"]

logger = logging.getLogger(__name__)


class ConsultantViewService(ConsultantViewPort):
    """顾问视图聚合服务（三段编排——双段联动容错+空态幂等读）.

    两依赖注入（OD-10）：archive_repository（SCOPED v1.1.0）+ report_repository
    （SCOPED v1.0.0）两既有注册名——两 SCOPED 无混态的最简形态（6-8 三 SCOPED+
    一 SINGLETON/6-9 两 SINGLETON+一 SCOPED 后；SINGLETON 服务捕获两 SCOPED 声明：
    CLI 一次性进程+测试双清下无故障面——三连注记先例；未来 7-2 长驻 REST 面改
    SCOPED 触发器注记）。
    """

    def __init__(
        self,
        *,
        archive_repository: ArchiveRepositoryPort,
        report_repository: ReportRepositoryProtocol,
    ) -> None:
        """两依赖 keyword-only 构造（服务无状态——SINGLETON 并发共享安全）."""
        self._archive_repository = archive_repository
        self._report_repository = report_repository

    async def build_consultant_view(self) -> ConsultantView:
        """构建三段聚合顾问视图（零参数——全局多项目面板；段级容错不抛）.

        Returns:
            ConsultantView 五键冻结视图（空态幂等读返回空态视图不抛——AC-5；
            generated_at 服务入口单时间锚取一次 now——顶层唯一时间键）.
        """
        # 单时间锚派生（6-8/6-9 单锚直系第三连）：入口取一次 now
        now = datetime.now(UTC)
        projects_section, summaries, file_paths, projects_degraded = await self._build_projects_section()
        brand_section = self._build_brand_section()
        export_section = self._build_export_section(summaries, file_paths, projects_degraded)
        build_degraded = projects_degraded or export_section.degraded or brand_section.degraded
        return ConsultantView(
            generated_at=now.isoformat(),
            build_degraded=build_degraded,
            projects=projects_section,
            brand=brand_section,
            export=export_section,
        )

    async def _build_projects_section(
        self,
    ) -> tuple[ProjectsSection, list[ProjectSummary], dict[str, str], bool]:
        """多项目段构建（find 全量→None 剔除→分组→循环报告概况→两趟排序）.

        Returns:
            (ProjectsSection, 行清单, plan_id→最新报告 file_path 映射, 段降级标记)
            ——file_path 映射是循环结果的组成部分（export 段定位键派生面，ProjectSummary
            投影白名单不含 file_path；零新读纪律下的纯投影输入）.

        Raises:
            无（find 级异常段降级返回默认值；循环级异常行级 None+降级标记）.
        """
        try:
            rows = await self._archive_repository.find(ArchiveQuery(plan_id=None, limit=PANEL_ARCHIVE_LIMIT))
        except Exception as error:  # 段级容错（find 级）：双段联动降级起点——段值降默认
            logger.warning("顾问视图多项目段降级: error=%s: %s", type(error).__name__, error)
            return ProjectsSection(degraded=True), [], {}, True

        # 口径四：plan_id=None 行剔除（防御性——当前写侧思维链归档恒带 plan_id，
        # None 仅可达于手工修数/未来写入方，读侧守卫廉价且诚实）
        grouped: dict[str, list[StrategicArchive]] = {}
        for row in rows:
            if row.plan_id is None:
                continue
            grouped.setdefault(str(row.plan_id), []).append(row)

        degraded = False
        summaries: list[ProjectSummary] = []
        file_paths: dict[str, str] = {}
        for plan_id, plan_rows in grouped.items():
            latest_activity = max(
                (row.archived_at for row in plan_rows if row.archived_at is not None),
                default=None,
            )
            report = None
            try:
                report = await self._report_repository.get_latest_by_plan(uuid.UUID(plan_id))
            except Exception as error:  # 段级容错（循环级）：行级 None+双段联动标记
                # OD-12：行级 None 与「无报告」同形——段哨兵是唯一区分面（保守诚实）
                logger.warning("顾问视图项目行报告概况降级: plan_id=%s error=%s: %s", plan_id, type(error).__name__, error)
                degraded = True
            # ProjectSummary 构造在行级 try 外（Task 0.1 R4-F6 守卫 raise 落位钦定：
            # 值域守卫[6-11 新类型]须走顶层红非段降级——演进信号不被劫持）
            summaries.append(
                ProjectSummary(
                    plan_id=plan_id,
                    archive_count=len(plan_rows),
                    latest_activity_at=latest_activity.isoformat() if latest_activity is not None else None,
                    latest_report_type=report.report_type.value if report is not None else None,
                    latest_report_at=report.created_at.isoformat() if report is not None else None,
                    latest_degraded_section_count=report.degraded_section_count if report is not None else None,
                )
            )
            if report is not None:
                file_paths[plan_id] = report.file_path

        # 口径一：两趟稳定排序（第二键 plan_id 升序先排+第一键归一降序后排——
        # None 归一 "" 在 reverse 后恒居尾；稳定排序保 tie-break）
        summaries.sort(key=lambda summary: summary.plan_id)
        summaries.sort(key=lambda summary: summary.latest_activity_at or "", reverse=True)
        section = ProjectsSection(
            available=len(summaries) > 0,
            degraded=degraded,
            plan_count=len(summaries),
            projects=tuple(summaries),
        )
        return section, summaries, file_paths, degraded

    def _build_brand_section(self) -> BrandSection:
        """品牌段构建（V1 恒系统默认态零 IO 静态段——纯常量构造）.

        值级断言语义=「V1 交付时点品牌面未配置事实」：6-11 实施后 configured 可
        True、status 可为已配置值（预期演进信号非 flake）；届时本段演进读配置面
        ——端口版本 v1.1.0 触发器注记（OD-6）。
        """
        return BrandSection(
            degraded=False,
            configured=False,
            logo_status=BRAND_STATUS_UNCONFIGURED,
            color_scheme_status=BRAND_STATUS_UNCONFIGURED,
            font_status=BRAND_FONT_STATUS,
        )

    def _build_export_section(
        self,
        summaries: list[ProjectSummary],
        file_paths: dict[str, str],
        projects_degraded: bool,
    ) -> ExportSection:
        """导出段构建（项目段循环结果纯投影派生——零新读，OD-7 单源纪律）.

        口径二（latest 遮蔽）：plans_with_latest_pdf 计「最新为 pdf 的 plan 数」
        非「历史曾生成计数」（get_latest_by_plan created_at 降序首行唯一——先生成
        PDF 后又生成 markdown 的 plan 不入 pdf 计数）；口径三（latest_pdf 三键选择）：
        latest_report_at 最大者+tie-break plan_id 字典序升序（禁「行序首个 pdf」
        备选——两口径在 tie-break 方向分叉；两趟稳定排序同款实现）。

        Args:
            summaries: 项目段行清单（投影输入面）.
            file_paths: plan_id→最新报告 file_path 映射（定位键派生面——循环结果）.
            projects_degraded: 项目段降级标记（双段联动入参——OD-12）.

        Returns:
            ExportSection 七键段（available==plans_with_reports>0——「可导出」与
            「已导出 PDF」分立：markdown 亦是可交付物，PDF 缺席不降 available）.
        """
        plans_with_reports = sum(1 for summary in summaries if summary.latest_report_type is not None)
        pdf_rows = [summary for summary in summaries if summary.latest_report_type == "pdf"]
        # 口径三两趟：plan_id 升序先排（tie-break）+ latest_report_at 归一降序后排
        pdf_rows.sort(key=lambda summary: summary.plan_id)
        pdf_rows.sort(key=lambda summary: summary.latest_report_at or "", reverse=True)
        latest_pdf = pdf_rows[0] if pdf_rows else None
        return ExportSection(
            available=plans_with_reports > 0,
            degraded=projects_degraded,  # 双段联动（派生源受损——OD-12）
            plans_with_reports=plans_with_reports,
            plans_with_latest_pdf=len(pdf_rows),
            latest_pdf_plan_id=latest_pdf.plan_id if latest_pdf is not None else None,
            latest_pdf_object_key=file_paths.get(latest_pdf.plan_id) if latest_pdf is not None else None,
            latest_pdf_generated_at=latest_pdf.latest_report_at if latest_pdf is not None else None,
        )
