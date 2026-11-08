"""Story 6-10 - 顾问视图服务单元测试（三段编排 + 排序派生矩阵 + 段级容错矩阵）.

Mock 形态（故事 Task 2 循环 A 钦定）：两依赖全 AsyncMock(spec=Protocol)
（ArchiveRepositoryPort/ReportRepositoryProtocol 两端口 Protocol 全在册——组合根
interface 注册面，无需具体类 spec）+ `_make_*` 工厂。

覆盖面：
    - 循环 A 三段聚合（find 全量→None 行剔除+distinct plan 分组+最新活动+行序+
      循环 get_latest_by_plan 报告概况；BrandSection 常量构造行为锚；ExportSection
      纯投影派生+find 调用 limit=1000 覆写锚）；
    - 循环 B 排序与派生矩阵（行序降序/tie-break plan_id 字典序升序/None 时间戳
      恒排尾/None 行剔除/latest 遮蔽/双 plan pdf 判别[口径三]/双 pdf tie-break/
      零 PDF available True/单 pdf 定位三键——Task 0.2 五口径逐格）；
    - 循环 C 段级容错（find 异常双段联动降级+循环单 plan 异常行级 None+双段
      degraded+空态幂等读——OD-12 双段联动新形态+五先例族空态第六连）。

Run with:
    poetry run pytest tests/unit/application/test_consultant_view_service.py -v
"""

from __future__ import annotations

import uuid as uuid_module
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest import mock

from src.domain.ports.archive_repository import ArchiveRepositoryPort
from src.domain.ports.report_repository import ReportRepositoryProtocol

# 浮动时间基准（单测 Mock 全控无背景行——固定锚+微秒偏移判别）
_BASE = datetime(2026, 11, 8, 10, 0, 0, tzinfo=UTC)


def _at(microseconds: int) -> datetime:
    """基准锚+微秒偏移（判别构造——同值禁双调）."""
    return _BASE + timedelta(microseconds=microseconds)


# ===================================================================
# 实体工厂（archived_at/created_at 可编程——未来偏移判别构造 OD-13① 单测面）
# ===================================================================


def _make_archive(
    plan_id: str | None,
    *,
    archived_at: datetime | None,
) -> Any:
    """StrategicArchive 实体工厂（repo.save 直写通道同构构造——archived_at 可编程）."""
    from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive

    return StrategicArchive(
        archive_id=uuid_module.uuid4(),
        plan_id=uuid_module.UUID(plan_id) if plan_id is not None else None,
        plan_type="SP",
        archive_type=ArchiveType.EVIDENCE_PACKAGE,
        assumptions={"tools_used": [], "evidence_refs": []},
        decision_basis={"kind": "evidence_package", "degraded": False},
        execution_deviation={},
        created_at=(archived_at - timedelta(microseconds=1)) if archived_at else None,
        archived_at=archived_at,
    )


def _make_report(
    plan_id: str,
    *,
    report_type: str,
    created_at: datetime,
) -> Any:
    """StrategicReport 实体工厂（report_type/created_at 可编程——ReportType 枚举成员）."""
    from src.domain.entities.strategic_report import ReportType, StrategicReport

    report_id = uuid_module.uuid4()
    return StrategicReport(
        report_id=report_id,
        plan_id=plan_id,
        report_type=ReportType(report_type),
        file_path=(
            f"reports/{plan_id}/{report_id}.pdf"
            if report_type == "pdf"
            else f"reports/{plan_id}_{created_at.strftime('%Y%m%d%H%M%S')}.md"
        ),
        section_count=11,
        degraded_section_count=2,
        generation_ms=1234,
        created_at=created_at,
    )


# ===================================================================
# 端口 Mock 工厂 + 服务组装
# ===================================================================


def _make_archive_repo(
    *,
    rows: tuple[Any, ...] = (),
    error: Exception | None = None,
) -> mock.AsyncMock:
    """归档仓储 Mock（spec=ArchiveRepositoryPort——find 返回序即行级 archived_at 降序契约）."""
    repo = mock.AsyncMock(spec=ArchiveRepositoryPort)
    if error is not None:
        repo.find.side_effect = error
    else:
        repo.find.return_value = list(rows)
    return repo


def _make_report_repo(
    *,
    reports: dict[str, Any] | None = None,
    error_plans: frozenset[str] = frozenset(),
) -> mock.AsyncMock:
    """报告仓储 Mock（spec=ReportRepositoryProtocol——plan_id→latest 报告映射+定向抛）.

    error_plans：定向抛集合（循环单 plan 异常格——side_effect 函数形态按 plan_id 分派）。
    """
    repo = mock.AsyncMock(spec=ReportRepositoryProtocol)

    def _latest(plan_id: uuid_module.UUID) -> Any:
        if str(plan_id) in error_plans:
            raise RuntimeError(f"report lookup failed for {plan_id}")
        return (reports or {}).get(str(plan_id))

    repo.get_latest_by_plan.side_effect = _latest
    return repo


def _make_service(
    *,
    archive_repo: mock.AsyncMock | None = None,
    report_repo: mock.AsyncMock | None = None,
) -> Any:
    """两依赖注入服务构造（keyword-only——ExecutiveViewService/AnalystViewService 同风格）."""
    from src.application.services.consultant_view_service import ConsultantViewService

    return ConsultantViewService(
        archive_repository=archive_repo or _make_archive_repo(),
        report_repository=report_repo or _make_report_repo(),
    )


# ===================================================================
# 循环 A：三段聚合编排
# ===================================================================


class TestThreeSectionAggregation:
    """三段聚合（find 全量→分组→循环报告概况→brand 常量→export 投影）."""

    async def test_full_data_three_sections(self) -> None:
        """全数据：双 plan 分组计数+报告概况+brand 默认+export 投影（AC-1 编排主链）."""
        plan_a, plan_b = str(uuid_module.uuid4()), str(uuid_module.uuid4())
        pdf_a = _make_report(plan_a, report_type="pdf", created_at=_at(60))
        md_b = _make_report(plan_b, report_type="markdown", created_at=_at(40))
        service = _make_service(
            archive_repo=_make_archive_repo(
                rows=(
                    _make_archive(plan_a, archived_at=_at(300)),
                    _make_archive(plan_a, archived_at=_at(200)),
                    _make_archive(plan_b, archived_at=_at(90)),
                )
            ),
            report_repo=_make_report_repo(reports={plan_a: pdf_a, plan_b: md_b}),
        )
        view = await service.build_consultant_view()
        assert view.projects.plan_count == 2
        assert view.projects.available is True
        rows = {row.plan_id: row for row in view.projects.projects}
        assert rows[plan_a].archive_count == 2
        assert rows[plan_a].latest_activity_at == _at(300).isoformat()
        assert rows[plan_a].latest_report_type == "pdf"
        assert rows[plan_a].latest_report_at == pdf_a.created_at.isoformat()
        assert rows[plan_a].latest_degraded_section_count == 2
        assert rows[plan_b].latest_report_type == "markdown"
        assert view.brand.configured is False
        assert view.export.plans_with_reports == 2
        assert view.export.plans_with_latest_pdf == 1
        assert view.export.latest_pdf_plan_id == plan_a
        assert view.export.latest_pdf_object_key == pdf_a.file_path
        assert view.export.latest_pdf_generated_at == pdf_a.created_at.isoformat()
        assert view.build_degraded is False

    async def test_brand_section_constant_anchor(self) -> None:
        """品牌段行为锚：返回值与品牌两常量恒等（V1 无配置面变异不可构造——行为断言足额 R1）."""
        from src.application.ports.consultant_view import BRAND_FONT_STATUS, BRAND_STATUS_UNCONFIGURED

        service = _make_service()
        view = await service.build_consultant_view()
        assert view.brand.logo_status == BRAND_STATUS_UNCONFIGURED
        assert view.brand.color_scheme_status == BRAND_STATUS_UNCONFIGURED
        assert view.brand.font_status == BRAND_FONT_STATUS
        assert view.brand.degraded is False

    async def test_generated_at_single_time_anchor(self) -> None:
        """单时间锚：generated_at ISO 字符串非空（顶层唯一时间键——6-8/6-9 直系第三连）."""
        service = _make_service()
        view = await service.build_consultant_view()
        assert isinstance(view.generated_at, str) and "T" in view.generated_at

    async def test_find_limit_override_anchor(self) -> None:
        """find 调用参数锚：ArchiveQuery(plan_id=None, limit=1000)——默认 20 截断防御（PANEL_ARCHIVE_LIMIT 单源）."""
        archive_repo = _make_archive_repo(rows=())
        service = _make_service(archive_repo=archive_repo)
        await service.build_consultant_view()
        archive_repo.find.assert_awaited_once()
        query = archive_repo.find.call_args[0][0]
        assert query.plan_id is None, "跨 plan 全量清单（plan_id=None——OD-5）"
        assert query.limit == 1000, "limit 覆写 1000（默认 20 会截断多项目面板——禁用默认值）"

    async def test_report_loop_per_plan_query(self) -> None:
        """报告概况循环口径：逐 plan get_latest_by_plan 点查（N+1 形态——MVP 量级钦定）."""
        plan_a, plan_b = str(uuid_module.uuid4()), str(uuid_module.uuid4())
        report_repo = _make_report_repo()
        service = _make_service(
            archive_repo=_make_archive_repo(
                rows=(_make_archive(plan_a, archived_at=_at(300)), _make_archive(plan_b, archived_at=_at(90)))
            ),
            report_repo=report_repo,
        )
        await service.build_consultant_view()
        assert report_repo.get_latest_by_plan.await_count == 2
        queried = {call.args[0] for call in report_repo.get_latest_by_plan.await_args_list}
        assert queried == {uuid_module.UUID(plan_a), uuid_module.UUID(plan_b)}


# ===================================================================
# 循环 B：排序与派生规则矩阵（Task 0.2 五口径逐格）
# ===================================================================


class TestOrderingAndDerivationMatrix:
    """排序与派生矩阵（口径一~四逐格——口径五归循环 C）."""

    async def test_order_latest_activity_desc(self) -> None:
        """行序格①：三 plan 最新活动降序（最新活动优先——顾问作业面语义）."""
        plan_ids = tuple(str(uuid_module.uuid4()) for _ in range(3))
        rows = (
            _make_archive(plan_ids[2], archived_at=_at(70)),
            _make_archive(plan_ids[0], archived_at=_at(300)),
            _make_archive(plan_ids[1], archived_at=_at(90)),
        )
        view = await _make_service(archive_repo=_make_archive_repo(rows=rows)).build_consultant_view()
        assert tuple(row.plan_id for row in view.projects.projects) == plan_ids, (
            "latest_activity_at 降序（find 返回乱序——服务分组后重排）"
        )

    async def test_order_tiebreak_plan_id_asc(self) -> None:
        """行序格②：同时间戳 tie-break plan_id 字典序升序（确定性排序判别）."""
        plan_x, plan_y = sorted((str(uuid_module.uuid4()), str(uuid_module.uuid4())))
        rows = (
            _make_archive(plan_y, archived_at=_at(100)),
            _make_archive(plan_x, archived_at=_at(100)),
        )
        view = await _make_service(archive_repo=_make_archive_repo(rows=rows)).build_consultant_view()
        assert [row.plan_id for row in view.projects.projects] == [plan_x, plan_y]

    async def test_none_timestamp_rows_tail(self) -> None:
        """行序格③：latest_activity_at=None 行恒排尾（StrategicArchive.archived_at 可空——口径一）."""
        plan_none, plan_active = str(uuid_module.uuid4()), str(uuid_module.uuid4())
        rows = (
            _make_archive(plan_none, archived_at=None),
            _make_archive(plan_active, archived_at=_at(50)),
        )
        view = await _make_service(archive_repo=_make_archive_repo(rows=rows)).build_consultant_view()
        rows_out = list(view.projects.projects)
        assert rows_out[-1].plan_id == plan_none, "None 时间戳行恒排尾"
        assert rows_out[-1].latest_activity_at is None

    async def test_none_plan_rows_excluded(self) -> None:
        """口径四：plan_id=None 行剔除（防御性——当前写侧恒带 plan_id）."""
        plan_a = str(uuid_module.uuid4())
        rows = (
            _make_archive(None, archived_at=_at(400)),
            _make_archive(plan_a, archived_at=_at(100)),
        )
        view = await _make_service(archive_repo=_make_archive_repo(rows=rows)).build_consultant_view()
        assert view.projects.plan_count == 1
        assert view.projects.projects[0].plan_id == plan_a
        assert view.projects.projects[0].archive_count == 1, "None 行不计入任何 plan 计数"

    async def test_latest_masking_semantics(self) -> None:
        """口径二：latest 遮蔽——先生成 pdf 后生成 markdown → latest=markdown → pdf 计数不含该 plan."""
        plan_a = str(uuid_module.uuid4())
        md_late = _make_report(plan_a, report_type="markdown", created_at=_at(60))
        service = _make_service(
            archive_repo=_make_archive_repo(rows=(_make_archive(plan_a, archived_at=_at(100)),)),
            report_repo=_make_report_repo(reports={plan_a: md_late}),
        )
        view = await service.build_consultant_view()
        row = view.projects.projects[0]
        assert row.latest_report_type == "markdown", "get_latest_by_plan 结果直判（created_at 降序首行）"
        assert view.export.plans_with_latest_pdf == 0, "历史曾生成 PDF 但 latest 被遮蔽——不计入（当前交付物形态口径）"
        assert view.export.latest_pdf_plan_id is None

    async def test_dual_pdf_latest_selection(self) -> None:
        """口径三：双 plan latest 均 pdf → latest_pdf 三键取 latest_report_at 最大者."""
        plan_a, plan_b = str(uuid_module.uuid4()), str(uuid_module.uuid4())
        pdf_a = _make_report(plan_a, report_type="pdf", created_at=_at(60))
        pdf_b = _make_report(plan_b, report_type="pdf", created_at=_at(80))
        service = _make_service(
            archive_repo=_make_archive_repo(
                rows=(_make_archive(plan_a, archived_at=_at(300)), _make_archive(plan_b, archived_at=_at(90)))
            ),
            report_repo=_make_report_repo(reports={plan_a: pdf_a, plan_b: pdf_b}),
        )
        view = await service.build_consultant_view()
        assert view.export.plans_with_latest_pdf == 2
        assert view.export.latest_pdf_plan_id == plan_b, "latest_report_at 最大者（+80µs > +60µs）"
        assert view.export.latest_pdf_object_key == pdf_b.file_path

    async def test_dual_pdf_tiebreak_plan_id_asc(self) -> None:
        """口径三 tie-break：双 pdf 同 created_at → plan_id 字典序升序取小者（禁「行序首个」）."""
        plan_x, plan_y = sorted((str(uuid_module.uuid4()), str(uuid_module.uuid4())))
        pdf_x = _make_report(plan_x, report_type="pdf", created_at=_at(60))
        pdf_y = _make_report(plan_y, report_type="pdf", created_at=_at(60))
        service = _make_service(
            archive_repo=_make_archive_repo(
                rows=(_make_archive(plan_y, archived_at=_at(90)), _make_archive(plan_x, archived_at=_at(300)))
            ),
            report_repo=_make_report_repo(reports={plan_x: pdf_x, plan_y: pdf_y}),
        )
        view = await service.build_consultant_view()
        assert view.export.latest_pdf_plan_id == plan_x, "tie-break plan_id 升序（与行序[plan_x 在前]无关的独立口径判别）"

    async def test_zero_pdf_available_true(self) -> None:
        """零 PDF 形态：全 latest markdown → available True+latest_pdf 三键 None（可导出与已导出分立）."""
        plan_a = str(uuid_module.uuid4())
        md_a = _make_report(plan_a, report_type="markdown", created_at=_at(50))
        service = _make_service(
            archive_repo=_make_archive_repo(rows=(_make_archive(plan_a, archived_at=_at(100)),)),
            report_repo=_make_report_repo(reports={plan_a: md_a}),
        )
        view = await service.build_consultant_view()
        assert view.export.available is True, "plans_with_reports>0 即 True——markdown 亦是可交付物"
        assert view.export.plans_with_reports == 1
        assert view.export.latest_pdf_plan_id is None
        assert view.export.latest_pdf_object_key is None
        assert view.export.latest_pdf_generated_at is None

    async def test_single_pdf_position_derivation(self) -> None:
        """单 pdf 定位三键直推（object_key==file_path 直传——L4 对象键单源）."""
        plan_a = str(uuid_module.uuid4())
        pdf_a = _make_report(plan_a, report_type="pdf", created_at=_at(60))
        service = _make_service(
            archive_repo=_make_archive_repo(rows=(_make_archive(plan_a, archived_at=_at(100)),)),
            report_repo=_make_report_repo(reports={plan_a: pdf_a}),
        )
        view = await service.build_consultant_view()
        assert view.export.latest_pdf_plan_id == plan_a
        assert view.export.latest_pdf_object_key == pdf_a.file_path
        assert view.export.latest_pdf_generated_at == pdf_a.created_at.isoformat()


# ===================================================================
# 循环 C：段级容错与空态幂等读（OD-12 双段联动）
# ===================================================================


class TestSectionFaultTolerance:
    """段级容错矩阵（find 级+循环级两捕获位分立+空态幂等读）."""

    async def test_find_error_dual_degradation(self) -> None:
        """find 异常格：projects+export 双段联动降级+brand 照常+顶层 degraded+不抛（OD-12）."""
        service = _make_service(archive_repo=_make_archive_repo(error=RuntimeError("archive find down")))
        view = await service.build_consultant_view()
        assert view.projects.degraded is True
        assert view.projects.plan_count == 0
        assert view.projects.projects == ()
        assert view.projects.available is False
        assert view.export.degraded is True, "双段联动（派生源受损——复合段新形态）"
        assert view.export.available is False
        assert view.export.plans_with_reports == 0
        assert view.export.latest_pdf_plan_id is None
        assert view.brand.degraded is False, "brand 零 IO 恒稳照常"
        assert view.brand.configured is False
        assert view.build_degraded is True

    async def test_loop_single_plan_error_row_level_none(self) -> None:
        """循环单 plan 异常格：该行报告列三键 None+双段 degraded+其余 plan 行照常（保守诚实）."""
        plan_a, plan_b = str(uuid_module.uuid4()), str(uuid_module.uuid4())
        md_b = _make_report(plan_b, report_type="markdown", created_at=_at(40))
        service = _make_service(
            archive_repo=_make_archive_repo(
                rows=(_make_archive(plan_a, archived_at=_at(300)), _make_archive(plan_b, archived_at=_at(90)))
            ),
            report_repo=_make_report_repo(reports={plan_b: md_b}, error_plans=frozenset({plan_a})),
        )
        view = await service.build_consultant_view()
        rows = {row.plan_id: row for row in view.projects.projects}
        assert rows[plan_a].latest_report_type is None, "行级 None 与「无报告」同形——段哨兵是唯一区分面"
        assert rows[plan_a].latest_report_at is None
        assert rows[plan_a].latest_degraded_section_count is None
        assert rows[plan_a].archive_count == 1, "清单保留（部分降级——行聚合照常）"
        assert rows[plan_b].latest_report_type == "markdown", "其余 plan 行照常聚合"
        assert view.projects.degraded is True
        assert view.export.degraded is True, "双段联动（循环级同样联动——OD-12）"
        assert view.export.plans_with_reports == 1, "仅 plan_b 入计（plan_a 报告列 None）"
        assert view.build_degraded is True

    async def test_empty_state_idempotent_read(self) -> None:
        """空态格：find 返回空列表 → 三段空态默认+brand 完整+build_degraded False+不抛（绝对空态归单测承载）."""
        service = _make_service(archive_repo=_make_archive_repo(rows=()))
        view = await service.build_consultant_view()
        assert view.projects.available is False
        assert view.projects.degraded is False
        assert view.projects.plan_count == 0
        assert view.projects.projects == ()
        assert view.export.available is False
        assert view.export.degraded is False
        assert view.export.plans_with_reports == 0
        assert view.export.plans_with_latest_pdf == 0
        assert view.export.latest_pdf_plan_id is None
        assert view.export.latest_pdf_object_key is None
        assert view.export.latest_pdf_generated_at is None
        assert view.brand.configured is False, "brand 完整默认态五键（恒在段）"
        assert view.brand.font_status == "STSong-Light（内置）"
        assert view.build_degraded is False, "「没有数据」非「拿不到数据」"


class TestServiceStatelessness:
    """服务无状态（SINGLETON 并发共享——AC-7 约束）."""

    async def test_no_mutable_instance_state(self) -> None:
        """调用前后实例属性集恒等（禁持每次调用的可变实例态）."""
        plan_a = str(uuid_module.uuid4())
        service = _make_service(archive_repo=_make_archive_repo(rows=(_make_archive(plan_a, archived_at=_at(100)),)))
        before = set(vars(service).keys())
        await service.build_consultant_view()
        await service.build_consultant_view()
        assert set(vars(service).keys()) == before
