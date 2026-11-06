"""Story 6-8 - 高管简化视图服务单元测试（四段编排 + derive_health 规则表 + 段级容错）.

Mock 形态（R1 修订钦定）：snapshot_repository/report_repository/audit_repo 三者
AsyncMock(spec=对应 Protocol) + checkpoint_service AsyncMock(spec=CheckpointService)
具体类（仓内无同名 Port——6-7 AsyncMock(spec=StrategicArchiveService) 先例）+ _make_* 工厂。

覆盖面：
    - 循环 A 四段聚合（快照解析/分布计数/留痕三键/UUID 转换/审计投影白名单）；
    - 循环 B derive_health 规则表矩阵（三色×数据形态 ≥9 格全枚举——确定性短路链）；
    - 循环 C 段级容错（四源×抛异常→段 degraded+其余正常+build_degraded）+ state_data
      畸形守卫 + 空 plan 幂等读。

Run with:
    poetry run pytest tests/unit/application/test_executive_view_service.py -v
"""

from __future__ import annotations

import uuid as uuid_module
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest import mock

from src.application.ports.checkpoint import CheckpointSummaryView
from src.application.ports.executive_view import ExecutiveHealth
from src.application.services.checkpoint_service import CheckpointService
from src.application.services.executive_view_service import (
    DEFAULT_AUDIT_WINDOW_DAYS,
    ExecutiveViewService,
    derive_health,
)
from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.entities.strategic_report import ReportType, StrategicReport
from src.domain.ports.audit_repository import AuditRepositoryPort, AuditSearchCriteria, AuditSearchResult
from src.domain.ports.report_repository import ReportRepositoryProtocol
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol

# ===================================================================
# Mock 工厂（_make_* 家族——AsyncMock spec=Protocol/具体类）
# ===================================================================


def _make_latest_state(plan_id: str, *, completed: int, degraded_steps: list[str]) -> dict[str, Any]:
    """构造 latest 快照 state_data 七键（与验收预置工厂同构）."""
    sequence = (
        "performance_gap",
        "market_insight_trend",
        "market_insight_competition",
        "market_insight_strategy",
        "market_insight_org",
        "market_insight_risk",
        "market_insight_execution",
        "market_insight_synthesis",
    )
    done = list(sequence[:completed])
    now = datetime.now(UTC)
    timeline = [
        {
            "step": step,
            "started_at": (now - timedelta(minutes=10)).isoformat(),
            "completed_at": (now - timedelta(minutes=9)).isoformat(),
            "status": "completed",
            "summary_excerpt": f"{step} 摘要",
            "degraded": step in degraded_steps,
        }
        for step in done
    ]
    return {
        "plan_id": plan_id,
        "phase": "market_insight",
        "current_step": done[-1] if done else "performance_gap",
        "completed_steps": completed,
        "total_steps": 8,
        "degraded_steps": list(degraded_steps),
        "timeline": timeline,
    }


def _make_snapshot(state_data: dict[str, Any], *, session_id: str = "blm-planning-plan") -> CheckpointSnapshot:
    """构造真实 CheckpointSnapshot 实体（空 checkpoint_no——484 守卫不触发）."""
    return CheckpointSnapshot(session_id=session_id, state_data=state_data)


def _make_recovery_snapshot(plan_id: str, *, mode: str = "replay", confirmed_by: str = "ceo-x") -> CheckpointSnapshot:
    """构造恢复记录 12 键快照（与 checkpoint_service.py:693-714 构造键面同源）."""
    return CheckpointSnapshot(
        session_id=f"blm-checkpoint-recovery-{plan_id}",
        stage_id="recovery_record",
        state_data={
            "plan_id": plan_id,
            "checkpoint_no": "CP-1",
            "recovery_mode": mode,
            "corrected": False,
            "correction": {},
            "affected_checkpoints": [],
            "pending_sync_checkpoints": [],
            "invalidated_checkpoints": [],
            "confirmed_by": confirmed_by,
            "recovered_at": "2026-11-06T10:00:00+00:00",
            "execution_ms": 12.5,
            "created_via": "cli",
        },
    )


def _make_cp_view(cp_no: str, *, completed: bool, sync_status: str = "in_sync") -> CheckpointSummaryView:
    """构造 CheckpointSummaryView（8 键真实 VO）."""
    return CheckpointSummaryView(
        checkpoint_no=cp_no,
        stage_id="performance_gap",
        completed=completed,
        summary=f"{cp_no} 摘要",
        state_version=1,
        created_via="use_case",
        timestamp="2026-11-06T10:00:00+00:00",
        sync_status=sync_status,
    )


def _make_report(plan_id: str, *, degraded_sections: int = 0) -> StrategicReport:
    """构造真实 StrategicReport 实体（八字段+构造守卫）."""
    return StrategicReport(
        report_id=uuid_module.uuid4(),
        plan_id=plan_id,
        report_type=ReportType.MARKDOWN,
        file_path=f"/tmp/sisys-reports/{plan_id}.md",
        section_count=11,
        degraded_section_count=degraded_sections,
        generation_ms=1234,
        created_at=datetime(2026, 11, 6, 10, 0, 0, tzinfo=UTC),
    )


def _make_audit_item(index: int, *, extra_keys: bool = True) -> dict[str, Any]:
    """构造审计行 dict（15 键全形态——投影白名单断言的脏载荷面）."""
    item: dict[str, Any] = {
        "id": index,
        "log_id": f"log-{index}",
        "timestamp": f"2026-11-06T09:59:5{index:02d}+00:00" if index < 10 else "2026-11-06T09:59:59+00:00",
        "actor": f"actor-{index}",
        "action_type": f"exec-view:probe-{index}",
        "target_resource": f"target-{index}",
    }
    if extra_keys:
        item.update(
            {
                "old_value": None,
                "new_value": None,
                "correction_level": None,
                "checksum": "abc",
                "created_at": "2026-11-06T10:00:00+00:00",
                "archived": False,
                "archived_at": None,
                "correlation_id": None,
                "integrity_verified": True,
            }
        )
    return item


def _make_snapshot_repo(
    *,
    load_return: Any = None,
    load_side_effect: Any = None,
    load_map: dict[str, Any] | None = None,
) -> mock.AsyncMock:
    """快照仓储 Mock（spec=SnapshotRepositoryProtocol；load_map 支持多键分派）."""
    repo = mock.AsyncMock(spec=SnapshotRepositoryProtocol)
    if load_side_effect is not None:
        repo.load.side_effect = load_side_effect
    elif load_map is not None:
        repo.load.side_effect = lambda session_id: load_map.get(session_id)
    else:
        repo.load.return_value = load_return
    return repo


def _make_checkpoint_service(
    *, views: list[CheckpointSummaryView] | None = None, error: Exception | None = None
) -> mock.AsyncMock:
    """Checkpoint 服务 Mock（spec=CheckpointService 具体类——仓内无同名 Port）."""
    service = mock.AsyncMock(spec=CheckpointService)
    if error is not None:
        service.list_checkpoints.side_effect = error
    else:
        service.list_checkpoints.return_value = views or []
    return service


def _make_report_repo(*, report: StrategicReport | None = None, error: Exception | None = None) -> mock.AsyncMock:
    """报告仓储 Mock（spec=ReportRepositoryProtocol）."""
    repo = mock.AsyncMock(spec=ReportRepositoryProtocol)
    if error is not None:
        repo.get_latest_by_plan.side_effect = error
    else:
        repo.get_latest_by_plan.return_value = report
    return repo


def _make_audit_repo(
    *,
    result: AuditSearchResult | None = None,
    error: Exception | None = None,
    captured: dict[str, Any] | None = None,
) -> mock.AsyncMock:
    """审计仓储 Mock（spec=AuditRepositoryPort；captured 捕获 search criteria）."""
    repo = mock.AsyncMock(spec=AuditRepositoryPort)
    if error is not None:
        repo.search.side_effect = error
    else:
        default = AuditSearchResult(items=(), total=0, offset=0, limit=5)
        if captured is not None:

            async def _capture(criteria: AuditSearchCriteria) -> AuditSearchResult:
                captured["criteria"] = criteria
                return result or default

            repo.search.side_effect = _capture
        else:
            repo.search.return_value = result or default
    return repo


def _make_service(
    *,
    snapshot_repo: mock.AsyncMock | None = None,
    checkpoint_service: mock.AsyncMock | None = None,
    report_repo: mock.AsyncMock | None = None,
    audit_repo: mock.AsyncMock | None = None,
) -> ExecutiveViewService:
    """四依赖注入服务构造（keyword-only——6-7 服务五依赖同风格）."""
    return ExecutiveViewService(
        snapshot_repository=snapshot_repo or _make_snapshot_repo(),
        checkpoint_service=checkpoint_service or _make_checkpoint_service(),
        report_repository=report_repo or _make_report_repo(),
        audit_repository=audit_repo or _make_audit_repo(),
    )


def _full_fixture_plan() -> str:
    """全数据形态 plan_id（S1 同构：3/8+1 降级+3 CP 混合+恢复记录+报告）."""
    return "123e4567-e89b-12d3-a456-426614174000"


def _make_full_service_mocks(plan_id: str) -> dict[str, mock.AsyncMock]:
    """全数据形态四 Mock 装配（循环 A 断言基准）."""
    latest = _make_snapshot(_make_latest_state(plan_id, completed=3, degraded_steps=["performance_gap"]))
    recovery = _make_recovery_snapshot(plan_id, mode="replay", confirmed_by="ceo-acceptance-a1")
    snapshot_repo = _make_snapshot_repo(
        load_map={
            f"blm-planning-{plan_id}": latest,
            f"blm-checkpoint-recovery-{plan_id}": recovery,
        }
    )
    checkpoint_service = _make_checkpoint_service(
        views=[
            _make_cp_view("CP-1", completed=True),
            _make_cp_view("CP-2", completed=True),
            _make_cp_view("CP-3", completed=False),
        ]
    )
    report = _make_report(plan_id, degraded_sections=2)
    report_repo = _make_report_repo(report=report)
    audit_items = tuple(_make_audit_item(i) for i in range(1, 6))
    audit_repo = _make_audit_repo(result=AuditSearchResult(items=audit_items, total=42, offset=0, limit=5))
    return {
        "snapshot_repo": snapshot_repo,
        "checkpoint_service": checkpoint_service,
        "report_repo": report_repo,
        "audit_repo": audit_repo,
    }


# ===================================================================
# 循环 A：四段聚合编排（Mock 四端口）
# ===================================================================


class TestFourSectionAggregation:
    """四段聚合编排断言（AC-1/AC-3/AC-4 编程面）."""

    async def test_planning_section_derived_from_snapshot(self) -> None:
        """planning 段：state_data 七键解析投影（degraded_step_count=len() 派生——R1-F34）."""
        plan_id = _full_fixture_plan()
        state = _make_latest_state(plan_id, completed=3, degraded_steps=["performance_gap"])
        latest = _make_snapshot(state)
        recovery = _make_recovery_snapshot(plan_id, mode="replay", confirmed_by="ceo-acceptance-a1")
        snapshot_repo = _make_snapshot_repo(
            load_map={f"blm-planning-{plan_id}": latest, f"blm-checkpoint-recovery-{plan_id}": recovery}
        )
        service = _make_service(
            snapshot_repo=snapshot_repo,
            checkpoint_service=_make_checkpoint_service(
                views=[
                    _make_cp_view("CP-1", completed=True),
                    _make_cp_view("CP-2", completed=True),
                    _make_cp_view("CP-3", completed=False),
                ]
            ),
            report_repo=_make_report_repo(report=_make_report(plan_id, degraded_sections=2)),
            audit_repo=_make_audit_repo(result=AuditSearchResult(items=(), total=42, offset=0, limit=5)),
        )
        view = await service.build_executive_view(plan_id=plan_id)
        planning = view.planning
        assert planning.available is True
        assert planning.degraded is False
        assert planning.completed_steps == 3
        assert planning.total_steps == 8
        assert planning.progress_percent == 37, "int(3/8*100)=37 向下取整（R1-F3 口径分立）"
        assert planning.degraded_step_count == 1, "派生自 degraded_steps 清单 len() 非直读计数键"
        assert planning.current_step == "market_insight_competition"
        assert planning.last_activity_at == state["timeline"][-1]["completed_at"]

    async def test_report_section_uuid_conversion(self) -> None:
        """report 段：get_latest_by_plan 入参 uuid.UUID 显式转换（OD-13——禁直传 str）."""
        plan_id = _full_fixture_plan()
        mocks = _make_full_service_mocks(plan_id)
        service = _make_service(**mocks)
        view = await service.build_executive_view(plan_id=plan_id)
        import uuid as uuid_module

        mocks["report_repo"].get_latest_by_plan.assert_awaited_once_with(uuid_module.UUID(plan_id))
        report = view.report
        assert report.available is True
        assert report.report_id == str(mocks["report_repo"].get_latest_by_plan.return_value.report_id)
        assert report.report_type == "markdown"
        assert report.section_count == 11
        assert report.degraded_section_count == 2
        assert report.generated_at == mocks["report_repo"].get_latest_by_plan.return_value.created_at.isoformat()

    async def test_approval_distribution_and_recovery_trace(self) -> None:
        """approval 段：分布计数+三态+留痕三键（恢复记录 12 键直读）."""
        plan_id = _full_fixture_plan()
        mocks = _make_full_service_mocks(plan_id)
        service = _make_service(**mocks)
        view = await service.build_executive_view(plan_id=plan_id)
        approval = view.approval
        assert approval.available is True
        assert approval.total_checkpoints == 3
        assert approval.completed_count == 2
        assert approval.in_sync_count == 3
        assert approval.pending_sync_count == 0
        assert approval.invalidated_count == 0
        assert approval.last_recovery_mode == "replay"
        assert approval.last_recovery_confirmed_by == "ceo-acceptance-a1"
        assert approval.last_recovered_at == "2026-11-06T10:00:00+00:00"
        assert (
            approval.in_sync_count + approval.pending_sync_count + approval.invalidated_count == approval.total_checkpoints
        ), "三态分布完备恒等式"

    async def test_audit_window_and_projection_whitelist(self) -> None:
        """audit 段：7 天窗构造+limit=5+投影白名单四键（15 键脏载荷禁入）."""
        import uuid as uuid_module

        plan_id = str(uuid_module.uuid4())
        captured: dict[str, Any] = {}
        items = tuple(_make_audit_item(i) for i in range(1, 6))
        audit_repo = _make_audit_repo(
            result=AuditSearchResult(items=items, total=42, offset=0, limit=5),
            captured=captured,
        )
        service = _make_service(audit_repo=audit_repo)
        before = datetime.now(UTC)
        view = await service.build_executive_view(plan_id=plan_id)
        after = datetime.now(UTC)
        criteria = captured["criteria"]
        assert criteria.limit == 5, "样本 limit 钦定 5（total 独立承载——禁大 limit 客户端计数）"
        assert criteria.start_time is not None and criteria.end_time is not None
        window_days = (criteria.end_time - criteria.start_time).days
        assert window_days == DEFAULT_AUDIT_WINDOW_DAYS == 7
        assert before - timedelta(days=7) - timedelta(seconds=1) <= criteria.start_time
        assert criteria.end_time <= after + timedelta(seconds=1)
        # 单锚派生恒等式（R1-F2）：入口 now 单锚——window 键与 generated_at 严格同源可推导
        assert criteria.start_time == datetime.fromisoformat(view.generated_at) - timedelta(days=DEFAULT_AUDIT_WINDOW_DAYS)
        assert criteria.end_time.isoformat() == view.generated_at
        audit = view.audit
        assert audit.total_events == 42
        assert audit.window_days == 7
        assert len(audit.recent_events) == 5
        for event, source in zip(audit.recent_events, items, strict=True):
            assert event.action_type == source["action_type"]
            assert event.actor == source["actor"]
            assert event.target_resource == source["target_resource"]
            assert event.timestamp == source["timestamp"]
        assert audit.last_event_at == audit.recent_events[0].timestamp

    async def test_empty_plan_idempotent_read(self) -> None:
        """空 plan 幂等读：三段 available False+审计空态+health AMBER+不抛（AC-5）."""
        plan_id = "00000000-0000-0000-0000-000000000000"
        service = _make_service()  # 全 Mock 空返回（load None/[]/None/total 0）
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.plan_id == plan_id
        assert view.build_degraded is False
        assert view.health is ExecutiveHealth.AMBER
        assert view.planning.available is False
        assert view.approval.available is False
        assert view.report.available is False
        assert view.audit.degraded is False
        assert view.audit.total_events == 0
        assert view.audit.recent_events == ()
        assert view.audit.last_event_at is None

    async def test_generated_at_iso_string(self) -> None:
        """顶层 generated_at 为 ISO 字符串（datetime.now(UTC).isoformat() 三时间键同型）."""
        import uuid as uuid_module

        service = _make_service()
        before = datetime.now(UTC)
        view = await service.build_executive_view(plan_id=str(uuid_module.uuid4()))
        after = datetime.now(UTC)
        parsed = datetime.fromisoformat(view.generated_at)
        assert before <= parsed <= after


# ===================================================================
# 循环 B：derive_health 规则表矩阵（三色×数据形态 ≥9 格全枚举）
# ===================================================================


def _sections(
    *,
    planning_available: bool = True,
    completed: int = 8,
    total: int = 8,
    degraded_steps: int = 0,
    approval_total: int = 0,
    approval_in_sync: int = 0,
    report_available: bool = True,
    report_degraded_sections: int = 0,
) -> tuple[Any, Any, Any]:
    """derive_health 四参的段构造 helper（PlanningSection/ApprovalSection/ReportSection）."""
    from src.application.ports.executive_view import ApprovalSection, PlanningSection, ReportSection

    planning = PlanningSection(
        available=planning_available,
        completed_steps=completed,
        total_steps=total,
        degraded_step_count=degraded_steps,
    )
    approval = ApprovalSection(
        available=approval_total > 0,
        total_checkpoints=approval_total,
        in_sync_count=approval_in_sync,
    )
    report = ReportSection(
        available=report_available,
        degraded_section_count=report_degraded_sections,
    )
    return planning, approval, report


class TestDeriveHealthMatrix:
    """derive_health 规则表矩阵（red > green > amber 短路链——Task 0.2 冻结规则逐字）."""

    def test_red_all_completed_degraded(self) -> None:
        """规则 1（red）：degraded_step_count == completed_steps > 0."""
        planning, approval, report = _sections(completed=3, total=8, degraded_steps=3)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.RED

    def test_red_zero_completed_not_red(self) -> None:
        """规则 1 边界：completed==0 非 red（空态归 amber）."""
        planning, approval, report = _sections(completed=0, total=8, degraded_steps=0)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.AMBER

    def test_red_requires_planning_available(self) -> None:
        """规则 1 边界：available=False 时 3/3 全降级计数形态仍非 red（合取项判别格——R1-F4）.

        纯函数直构形态（真实服务 available=False 时计数恒归零不可达——本格为规则 1 的
        planning.available 合取项提供突变判别：删除该合取项则本格误判 RED 即红）.
        """
        planning, approval, report = _sections(planning_available=False, completed=3, total=8, degraded_steps=3)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.AMBER

    def test_red_overrides_green_conditions(self) -> None:
        """规则 1 优先于 green：其余 green 条件全满足仍 red（短路链 red > green）."""
        planning, approval, report = _sections(completed=8, total=8, degraded_steps=8)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.RED

    def test_green_all_conditions(self) -> None:
        """规则 2（green）：七合取全满足（8/8+零 checkpoint 支路+报告零降级）."""
        planning, approval, report = _sections()
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.GREEN

    def test_green_all_in_sync_branch(self) -> None:
        """规则 2 支路④：≥1 checkpoint 全 in_sync 亦 green."""
        planning, approval, report = _sections(approval_total=3, approval_in_sync=3)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.GREEN

    def test_green_broken_incomplete(self) -> None:
        """规则 2 破坏②：completed != total → amber."""
        planning, approval, report = _sections(completed=3, total=8, degraded_steps=0)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.AMBER

    def test_green_broken_partial_degraded(self) -> None:
        """规则 2 破坏③：部分降级（degraded>0 且 < completed）→ amber."""
        planning, approval, report = _sections(completed=3, total=8, degraded_steps=1)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.AMBER

    def test_green_broken_sync_anomaly(self) -> None:
        """规则 2 破坏④：checkpoint 有非 in_sync → amber."""
        planning, approval, report = _sections(approval_total=3, approval_in_sync=2)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.AMBER

    def test_green_broken_no_report(self) -> None:
        """规则 2 破坏⑤：无报告 → amber."""
        planning, approval, report = _sections(report_available=False)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.AMBER

    def test_green_broken_report_degraded(self) -> None:
        """规则 2 破坏⑥：报告降级计数 >0 → amber."""
        planning, approval, report = _sections(report_degraded_sections=2)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.AMBER

    def test_green_broken_build_degraded(self) -> None:
        """规则 2 破坏⑦：build_degraded → 恒非 green（拿不到数据不得报绿）."""
        planning, approval, report = _sections()
        assert derive_health(planning, approval, report, build_degraded=True) is ExecutiveHealth.AMBER

    def test_amber_planning_unavailable(self) -> None:
        """规则 3 兜底：planning 不可得（available False）→ amber（空 plan 中间态）."""
        planning, approval, report = _sections(planning_available=False)
        assert derive_health(planning, approval, report, build_degraded=False) is ExecutiveHealth.AMBER


# ===================================================================
# 循环 C：段级容错与畸形守卫（四源×异常矩阵）
# ===================================================================


class TestSectionFaultTolerance:
    """段级独立容错（单源异常仅该段 degraded，其余段照常，视图不抛——AC-5）."""

    async def test_snapshot_load_error_degrades_planning_only(self) -> None:
        """snapshot 源异常 → planning.degraded+其余正常+build_degraded.

        latest 键抛异常（恢复记录键不受波及——同一仓储两读路径分立）.
        """
        plan_id = _full_fixture_plan()
        mocks = _make_full_service_mocks(plan_id)
        recovery = _make_recovery_snapshot(plan_id)

        def _load_by_key(session_id: str) -> Any:
            if session_id.startswith("blm-planning-"):
                raise RuntimeError("redis down")
            return recovery

        snapshot_repo = _make_snapshot_repo()
        snapshot_repo.load.side_effect = _load_by_key
        mocks["snapshot_repo"] = snapshot_repo
        service = _make_service(**mocks)
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.planning.degraded is True
        assert view.planning.available is False
        assert view.approval.degraded is False
        assert view.audit.degraded is False
        assert view.report.degraded is False
        assert view.build_degraded is True
        assert view.health is not ExecutiveHealth.GREEN

    async def test_checkpoint_error_degrades_approval_only(self) -> None:
        """checkpoint 源异常 → approval.degraded（其余正常）."""
        plan_id = _full_fixture_plan()
        mocks = _make_full_service_mocks(plan_id)
        mocks["checkpoint_service"] = _make_checkpoint_service(error=RuntimeError("probe failed"))
        service = _make_service(**mocks)
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.approval.degraded is True
        assert view.approval.available is False
        assert view.planning.degraded is False
        assert view.report.degraded is False
        assert view.build_degraded is True

    async def test_audit_error_degrades_audit_only(self) -> None:
        """audit 源异常 → audit.degraded（其余正常）."""
        plan_id = _full_fixture_plan()
        mocks = _make_full_service_mocks(plan_id)
        mocks["audit_repo"] = _make_audit_repo(error=RuntimeError("pg down"))
        service = _make_service(**mocks)
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.audit.degraded is True
        assert view.audit.total_events == 0
        assert view.planning.degraded is False
        assert view.report.degraded is False
        assert view.build_degraded is True

    async def test_report_error_degrades_report_only(self) -> None:
        """report 源异常 → report.degraded（其余正常）."""
        plan_id = _full_fixture_plan()
        mocks = _make_full_service_mocks(plan_id)
        mocks["report_repo"] = _make_report_repo(error=RuntimeError("pg down"))
        service = _make_service(**mocks)
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.report.degraded is True
        assert view.report.available is False
        assert view.planning.degraded is False
        assert view.audit.degraded is False
        assert view.build_degraded is True

    async def test_all_sources_error_view_not_raised(self) -> None:
        """四源全异常 → 四段全 degraded+视图正常返回（不抛）+health 非 green."""
        plan_id = _full_fixture_plan()
        service = _make_service(
            snapshot_repo=_make_snapshot_repo(load_side_effect=RuntimeError("e1")),
            checkpoint_service=_make_checkpoint_service(error=RuntimeError("e2")),
            report_repo=_make_report_repo(error=RuntimeError("e3")),
            audit_repo=_make_audit_repo(error=RuntimeError("e4")),
        )
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.build_degraded is True
        assert view.health is ExecutiveHealth.AMBER

    async def test_malformed_state_data_missing_key(self) -> None:
        """state_data 畸形（缺 completed_steps 键）→ planning 降级不抛（读侧脏数据守卫）."""
        plan_id = _full_fixture_plan()
        malformed = _make_snapshot({"plan_id": plan_id, "phase": "market_insight"})
        service = _make_service(snapshot_repo=_make_snapshot_repo(load_return=malformed))
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.planning.degraded is True
        assert view.planning.available is False
        assert view.planning.completed_steps == 0

    async def test_malformed_state_data_bad_type(self) -> None:
        """state_data 畸形（completed_steps 非 int 形态）→ planning 降级不抛（AC-5 三腿全断——R2-F1）."""
        plan_id = _full_fixture_plan()
        state = _make_latest_state(plan_id, completed=3, degraded_steps=[])
        malformed = _make_snapshot({**state, "completed_steps": "not-a-number"})
        service = _make_service(snapshot_repo=_make_snapshot_repo(load_return=malformed))
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.planning.degraded is True
        assert view.planning.available is False
        assert view.planning.completed_steps == 0

    async def test_malformed_state_data_zero_total(self) -> None:
        """state_data 畸形（total_steps=0 除零形态）→ planning 降级不抛（AC-5 三腿全断——R2-F1）."""
        plan_id = _full_fixture_plan()
        state = _make_latest_state(plan_id, completed=0, degraded_steps=[])
        state["total_steps"] = 0
        service = _make_service(snapshot_repo=_make_snapshot_repo(load_return=_make_snapshot(state)))
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.planning.degraded is True
        assert view.planning.available is False
        assert view.planning.completed_steps == 0

    async def test_numeric_string_state_data_leniently_accepted(self) -> None:
        """字符串数字形态经 int() 宽容采用（AC-5 第三形态——R3-F1 行为锁定）.

        「宽容-严格」分界钦定（R3 注记：缺键且有单源常量→默认 / 值现且可强转→采用 /
        值现且不可用→降级）：int("8")==8 静默成功不降级——本格钉死该宽容采用是**预期
        行为**（与 current_step 错型穿透 R1 注记同族），防未来被误「修复」为严格形态。
        """
        plan_id = _full_fixture_plan()
        state = _make_latest_state(plan_id, completed=3, degraded_steps=[])
        state["completed_steps"] = "3"
        state["total_steps"] = "8"
        service = _make_service(snapshot_repo=_make_snapshot_repo(load_return=_make_snapshot(state)))
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.planning.degraded is False
        assert view.planning.available is True
        assert view.planning.completed_steps == 3
        assert view.planning.total_steps == 8
        assert view.planning.progress_percent == 37

    async def test_recovery_record_corrupted_degrades_trace_keys(self) -> None:
        """恢复记录损坏（state_data 畸形）→ 留痕三键降 None 不抛（AsyncMock 面单测承载——R1-F2）."""
        plan_id = _full_fixture_plan()
        corrupted = CheckpointSnapshot(
            session_id=f"blm-checkpoint-recovery-{plan_id}",
            stage_id="recovery_record",
            state_data={"plan_id": plan_id},  # 缺 recovery_mode/confirmed_by/recovered_at
        )
        snapshot_repo = _make_snapshot_repo(
            load_map={
                f"blm-planning-{plan_id}": _make_snapshot(_make_latest_state(plan_id, completed=3, degraded_steps=[])),
                f"blm-checkpoint-recovery-{plan_id}": corrupted,
            }
        )
        service = _make_service(snapshot_repo=snapshot_repo)
        view = await service.build_executive_view(plan_id=plan_id)
        assert view.approval.last_recovery_mode is None
        assert view.approval.last_recovery_confirmed_by is None
        assert view.approval.last_recovered_at is None
        # 损坏记录（缺键 dict）经 isinstance 守卫走 .get() 空态——非「拿不到数据」不降段
        # （R1-F5：钉死「isinstance 守卫不得改为降级」——与无恢复记录形成可判别对照）
        assert view.approval.degraded is False

    async def test_service_stateless_shared_instance(self) -> None:
        """服务无状态约束：同一实例两次调用结果互不污染（AC-7 并发约束的单测面）."""
        plan_id = _full_fixture_plan()
        service = _make_service(**_make_full_service_mocks(plan_id))
        first = await service.build_executive_view(plan_id=plan_id)
        second = await service.build_executive_view(plan_id=plan_id)
        assert first.plan_id == second.plan_id
        assert first.health == second.health
        assert first.planning.completed_steps == second.planning.completed_steps
