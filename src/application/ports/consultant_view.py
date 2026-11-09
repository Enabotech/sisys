"""顾问视图端口契约（Story 6-10）——五 VO + 品牌两常量 + PANEL_ARCHIVE_LIMIT + ConsultantViewPort.

读侧 CQRS 投影 DTO（读侧 DTO 归应用层——6-6 CheckpointSummaryView/6-7 五 VO/6-8 七 VO/
6-9 七 VO 先例族第五连；零 domain VO——OD-11 纯三零裁定）。三段聚合：
    - 多项目段（projects）：ArchiveRepositoryPort.find(ArchiveQuery(plan_id=None,
      limit=PANEL_ARCHIVE_LIMIT)) 全量行 distinct plan_id 分组（每 plan 归档计数+
      最新活动时间+循环 get_latest_by_plan 报告概况——plan_id=None 行剔除防御）；
    - 品牌段（brand）：V1 恒系统默认态零 IO 静态段（三段中唯一无数据源段——
      空态/降级全场景值恒不变；品牌配置实现归 Story 6-11「白标报告基础」）；
    - 导出段（export）：项目段循环结果的纯投影派生（零新读——单源纪律 OD-7；
      latest 遮蔽口径：「最新报告为 pdf 的 plan 数」非「历史曾生成计数」）。

ConsultantView 顶层无 plan_id 键（全局视图零输入的 VO 投影——与 6-8 ExecutiveView
8 键/6-9 AnalystView 6 键的分立点，OD-1）；build_consultant_view 零参数签名是
视图族首个全局端口（多项目管理面板本义跨 plan——语义正当性）。

端口版本：(v1.1.0——Story 6-11 品牌段读配置面激活：BrandSection 值语义演进
[键契约 5 键不变]——有模板 configured True+呈现名派生/零模板与降级态默认值；
服务增 brand_template_repository 第三依赖，build_consultant_view 签名零变)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from src.domain.exceptions import EntityValidationError

#: 品牌未配置状态文案（logo_status 与 color_scheme_status 共用——OD-6 品牌面恰两常量；
#: 6-11 v1.1.0 已兑现：消费面演进为读配置——零模板/降级态回落本常量，
#: 有模板时 logo_status ∈ {"已配置","未设置"}、color_scheme_status=预设呈现名）
BRAND_STATUS_UNCONFIGURED: str = "未配置（系统默认）"

#: 品牌字体状态文案（与渲染器冻结字体 _FONT_NAME = "STSong-Light"（reportlab_pdf_renderer.py:60）
#: 事实单源对齐——字面量承载禁 import infra：application 禁依赖 infrastructure
#: （依赖方向矩阵 SERVICE_ALLOWED_PREFIXES 白名单外）；6-11 v1.1.0 已兑现：
#: 有模板时 font_status=FONT_PRESETS 呈现名[同层 import 合法]，本常量是零模板/降级态回落值）
BRAND_FONT_STATUS: str = "STSong-Light（内置）"

#: 面板归档清单查询上限（ArchiveQuery limit 覆写单源——默认 20 截断防御：不覆写则
#: 多项目面板只显示 20 行归档。上限声明：单租户 MVP 量级归档行数 << 1000；超限截断
#: 是 MVP 外量级——归档行超千级触发 SQL 化清单端口立项锚 Epic 7/21）
PANEL_ARCHIVE_LIMIT: int = 1000

#: 最新报告类型值域（ProjectSummary.latest_report_type 守卫单源——ReportType 值域
#: 直传 {None,"markdown","pdf"}；frozenset 单源演进单点：6-11 新增 report_type[如
#: branded_pdf]时服务 str 化直传→守卫抛 242 属预期演进信号——与 BrandSection.configured
#: 演进信号对称[Task 0.1 R4-F6]；守卫 raise 落位：ProjectSummary 构造不得落服务循环级
#: try 内——「新类型未适配」须走顶层红非段降级[演进信号不被劫持]）
LATEST_REPORT_TYPE_DOMAIN: frozenset[str | None] = frozenset({None, "markdown", "pdf"})


@dataclass(frozen=True)
class ProjectSummary:
    """项目行摘要（6 键——跨 plan 清单行级概况投影白名单）.

    投影白名单六键（plan_id str 化钦定——实体 UUID→str，6-8 report_id 同款；
    generation_ms/metadata JSONB 不入 ProjectSummary——展示面零消费[StrategicReport
    八字段投影六键]）；行序口径归服务承载（latest_activity_at 降序+plan_id 字典序
    tie-break+None 时间戳恒排尾——Task 0.2 口径一）。
    """

    plan_id: str
    archive_count: int = 0
    latest_activity_at: str | None = None
    latest_report_type: str | None = None
    latest_report_at: str | None = None
    latest_degraded_section_count: int | None = None

    def __post_init__(self) -> None:
        """构造守卫四形态（外部输入可错字段——plan_id/值域/双计数；违例抛 242）.

        available 恒等式不设守卫（明示裁定 Task 0.1——服务派生投影键，stub 直构
        矛盾 VO 属测试自身缺陷由断言面暴露；守卫面收窄到「外部输入可错的字段」）。
        """
        if not isinstance(self.plan_id, str) or not self.plan_id:
            raise EntityValidationError(
                message="plan_id 必须为非空字符串",
                context={"vo": "ProjectSummary", "field": "plan_id", "plan_id": self.plan_id},
            )
        if self.latest_report_type not in LATEST_REPORT_TYPE_DOMAIN:
            raise EntityValidationError(
                message="latest_report_type 值域外（{None,'markdown','pdf'}——6-11 新类型红属预期演进信号）",
                context={
                    "vo": "ProjectSummary",
                    "field": "latest_report_type",
                    "latest_report_type": str(self.latest_report_type),
                },
            )
        negative_fields = {
            "archive_count": self.archive_count,
            "latest_degraded_section_count": self.latest_degraded_section_count,
        }
        if any(value is not None and value < 0 for value in negative_fields.values()):
            raise EntityValidationError(
                message="项目行计数不得为负",
                context={"vo": "ProjectSummary", **{k: str(v) for k, v in negative_fields.items()}},
            )


@dataclass(frozen=True)
class ProjectsSection:
    """多项目段（4 键——跨 plan 归档清单聚合）.

    段降级两形态分立（OD-12）：find 级异常=段值降默认（plan_count 0+空 tuple——
    「拿不到」）；循环级异常=清单保留+行报告列 None（「部分降级」——行级 None
    与「无报告」同形，段哨兵是唯一区分面）。
    """

    available: bool = False
    degraded: bool = False
    plan_count: int = 0
    projects: tuple[ProjectSummary, ...] = ()

    def __post_init__(self) -> None:
        """构造守卫：plan_count 非负."""
        if self.plan_count < 0:
            raise EntityValidationError(
                message="项目段计数不得为负",
                context={"vo": "ProjectsSection", "plan_count": self.plan_count},
            )


@dataclass(frozen=True)
class BrandSection:
    """品牌段（5 键——6-11 v1.1.0 读配置面已兑现：三形态值语义）.

    键契约 5 键不变、值语义演进（对接锚兑现注记）：有模板→configured True+
    logo_status ∈ {"已配置","未设置"}+配色/字体呈现名（预设常量单源）；零模板
    →五键全默认值（与 6-10 恒值逐字相等——6-10 断言前提演进为「零模板」）；
    查询异常→degraded True+默认值不抛（「degraded 恒 False 零 IO 恒稳」承诺
    勘误为「零模板/降级态下 False——读配置面激活降级语义」）。
    """

    degraded: bool = False
    configured: bool = False
    logo_status: str = BRAND_STATUS_UNCONFIGURED
    color_scheme_status: str = BRAND_STATUS_UNCONFIGURED
    font_status: str = BRAND_FONT_STATUS


@dataclass(frozen=True)
class ExportSection:
    """导出段（7 键——项目段循环结果纯投影派生，零新读——OD-7 单源纪律）.

    plans_with_latest_pdf 是「最新报告为 pdf 的 plan 数」非「历史曾生成计数」
    （latest 遮蔽语义：get_latest_by_plan created_at 降序首行唯一——先生成 PDF 后
    又生成 markdown 的 plan 其 latest=markdown 不入 pdf 计数——「当前交付物形态」
    呈现语义）；available==plans_with_reports>0（「可导出」与「已导出 PDF」分立：
    markdown 亦是可交付物，PDF 缺席不降 available）。
    """

    available: bool = False
    degraded: bool = False
    plans_with_reports: int = 0
    plans_with_latest_pdf: int = 0
    latest_pdf_plan_id: str | None = None
    latest_pdf_object_key: str | None = None
    latest_pdf_generated_at: str | None = None

    def __post_init__(self) -> None:
        """构造守卫：导出双计数非负."""
        negative_fields = {
            "plans_with_reports": self.plans_with_reports,
            "plans_with_latest_pdf": self.plans_with_latest_pdf,
        }
        if any(value < 0 for value in negative_fields.values()):
            raise EntityValidationError(
                message="导出段计数不得为负",
                context={"vo": "ExportSection", **negative_fields},
            )


@dataclass(frozen=True)
class ConsultantView:
    """顾问视图（5 键——三段聚合 + 顶层降级哨兵，顶层无 plan_id 键）.

    build_degraded 是顶层哨兵（任一段 degraded 即 True——projects/export 双段
    联动[OD-12]+brand 恒 False 的 or 链聚合）；generated_at 是视图生成锚（ISO
    字符串——服务入口单时间锚取一次 now，6-8/6-9 单锚派生直系第三连）。
    """

    generated_at: str = ""
    build_degraded: bool = False
    projects: ProjectsSection = field(default_factory=ProjectsSection)
    brand: BrandSection = field(default_factory=BrandSection)
    export: ExportSection = field(default_factory=ExportSection)


@runtime_checkable
class ConsultantViewPort(Protocol):
    """顾问视图端口（读侧聚合 CQRS 投影——R2 应用层具体端口组合注入两既有 R1 端口）.

    零参数签名（全局视图 OD-1——ExecutiveViewPort/AnalystViewPort keyword-only
    plan_id 形态的分立点：多项目管理面板本义跨 plan，视图族首个零 plan_id 输入
    端口）；消费方：GetConsultantViewUseCase（零参透传——零输入零守卫面 OD-3）+
    CLI consultant-view 子命令（经组合根 consultant_view_use_case 注册名 resolve）。
    端口版本：(v1.1.0——Story 6-11 品牌段读配置面：服务增第三依赖+三形态值语义；签名零变)
    """

    async def build_consultant_view(self) -> ConsultantView:
        """构建三段聚合顾问视图（全局多项目面板——零参数）.

        Returns:
            ConsultantView 五键冻结视图（空态幂等读返回空态视图不抛异常——
            AC-5；段级容错下顶层 build_degraded 聚合降级哨兵）。
        """
        ...
