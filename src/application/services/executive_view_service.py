"""高管简化视图服务（Story 6-8）——四段聚合编排 + derive_health 三色推导.

读侧聚合 CQRS 投影（R2 应用层具体端口组合注入四既有基础端口——R1~R4 设计规则落点）：
    - planning 段：snapshot_repository.load(latest 快照) 直读 state_data 七键解析投影；
    - approval 段：checkpoint_service.list_checkpoints 分布计数 + 恢复记录
      （CHECKPOINT_RECOVERY_SESSION_PREFIX 前缀常量单源）12 键直读留痕三键；
    - audit 段：audit_repository.search 全局窗查询 + 投影白名单四键样本；
    - report 段：report_repository.get_latest_by_plan（uuid.UUID 显式转换——OD-13）。

段级独立容错（6-5b 节点→6-7 树形→本 Story 段级降级哲学）：四源各自 try 包裹——单源
异常仅该段 degraded=True（计数/标识降默认值），其余段照常聚合，视图整体不抛（AC-5）；
顶层哨兵 build_degraded = 任一段 degraded（「拿不到数据不得报绿」——health 规则 2 显式
含 build_degraded==False 条件）。

服务无状态（SINGLETON 并发共享——AC-7 并发约束；禁持每次调用的可变实例态）。

端口版本：(v1.0.0)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
from src.application.ports.checkpoint import (
    CHECKPOINT_RECOVERY_SESSION_PREFIX,
    CheckpointSummaryView,
)
from src.application.ports.executive_view import (
    ApprovalSection,
    AuditEventSummary,
    AuditSection,
    ExecutiveHealth,
    ExecutiveView,
    ExecutiveViewPort,
    PlanningSection,
    ReportSection,
)
from src.application.services.checkpoint_service import CheckpointService
from src.domain.entities.strategic_report import StrategicReport
from src.domain.ports.audit_repository import (
    AuditRepositoryPort,
    AuditSearchCriteria,
    AuditSearchResult,
)
from src.domain.ports.report_repository import ReportRepositoryProtocol
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.value_objects.blm_phases import BLM_TOTAL_STEPS

logger = logging.getLogger(__name__)

# 审计摘要时间窗默认天数（服务常量钉死——无参数化 YAGNI：epics/UX 无窗口调节需求来源，OD-10）
DEFAULT_AUDIT_WINDOW_DAYS: int = 7

# 审计样本上限（total 由 AuditSearchResult.total 独立承载——items 只作样本源不作计数源，
# 禁大 limit 拉全量客户端计数——OD-10）
_AUDIT_SAMPLE_LIMIT: int = 5

# sync_status 三态值域（CheckpointSummaryView.sync_status 值域单源对齐）
_SYNC_IN_SYNC = "in_sync"
_SYNC_PENDING = "pending_sync"
_SYNC_INVALIDATED = "invalidated"


def derive_health(
    planning: PlanningSection,
    approval: ApprovalSection,
    report: ReportSection,
    build_degraded: bool,
) -> ExecutiveHealth:
    """RAG 三色健康状态推导（确定性短路规则表——red > green > amber，Task 0.2 冻结原文）.

    Args:
        planning: 规划态势段（red 判据：已完成产出全部降级）.
        approval: 审批中心段（green 判据④：零 checkpoint 或全 in_sync）.
        report: 报告可得性段（green 判据⑤⑥：在位且零降级小节）.
        build_degraded: 顶层降级哨兵（green 判据⑦——「拿不到数据不得报绿」）.

    Returns:
        ExecutiveHealth 三色枚举值（纯函数——四参显式入参禁读全局，禁散落 if 链）.
    """
    # 规则 1（red）：已完成产出全部降级——可信度危险（UX L1250-1252「红色=危险」）
    if planning.available and planning.completed_steps > 0 and planning.degraded_step_count == planning.completed_steps:
        return ExecutiveHealth.RED
    # 规则 2（green）：七合取全满足——全链健康（其一含两原子析取：零 checkpoint 或全 in_sync）
    if (
        planning.available
        and planning.completed_steps == planning.total_steps
        and planning.degraded_step_count == 0
        and (approval.total_checkpoints == 0 or approval.in_sync_count == approval.total_checkpoints)
        and report.available
        and report.degraded_section_count == 0
        and build_degraded is False
    ):
        return ExecutiveHealth.GREEN
    # 规则 3（amber）：其余一切（含未完成/部分降级/sync 异常/无报告/段降级/空 plan 零数据——
    # 空态 amber 是「无可判绿红的中间态」语义注记非错误态）
    return ExecutiveHealth.AMBER


class ExecutiveViewService(ExecutiveViewPort):
    """高管简化视图聚合服务（四段编排——段级容错+空 plan 幂等读）.

    四依赖注入（OD-11）：snapshot_repository/checkpoint_service/report_repository/
    audit_repository 四既有注册名（三 SCOPED + 一 SINGLETON 的 SINGLETON 捕获声明——
    CLI 一次性进程 + 测试双清下无故障面）；checkpoint_service 具体类注入
    （6-7 StrategicArchiveService 具体类注入同款先例——list_checkpoints 是其方法族）.
    """

    def __init__(
        self,
        *,
        snapshot_repository: SnapshotRepositoryProtocol,
        checkpoint_service: CheckpointService,
        report_repository: ReportRepositoryProtocol,
        audit_repository: AuditRepositoryPort,
    ) -> None:
        """四依赖 keyword-only 构造（服务无状态——SINGLETON 并发共享安全）."""
        self._snapshot_repository = snapshot_repository
        self._checkpoint_service = checkpoint_service
        self._report_repository = report_repository
        self._audit_repository = audit_repository

    async def build_executive_view(self, *, plan_id: str) -> ExecutiveView:
        """按 plan_id 构建四段聚合视图（段级独立容错——单源异常不炸整体）.

        Args:
            plan_id: 规划任务标识（UUID 字符串——畸形守卫归用例层 242，服务不守卫）.

        Returns:
            ExecutiveView 八键冻结视图（空 plan 幂等读返回空态视图不抛——AC-5）.
        """
        # 单时间锚派生（R1-F2 修复）：入口取一次 now——generated_at 与审计窗
        # window_end 同锚，AC-4 恒等式 window_start == generated_at − 7d 严格成立
        now = datetime.now(UTC)
        planning = await self._build_planning_section(plan_id)
        approval = await self._build_approval_section(plan_id)
        audit = await self._build_audit_section(now)
        report = await self._build_report_section(plan_id)
        build_degraded = planning.degraded or approval.degraded or audit.degraded or report.degraded
        health = derive_health(planning, approval, report, build_degraded)
        return ExecutiveView(
            plan_id=plan_id,
            generated_at=now.isoformat(),
            health=health,
            build_degraded=build_degraded,
            planning=planning,
            approval=approval,
            audit=audit,
            report=report,
        )

    async def _build_planning_section(self, plan_id: str) -> PlanningSection:
        """规划态势段（latest 快照直读+state_data 七键解析——畸形降级不抛）.

        Args:
            plan_id: 规划任务标识.

        Returns:
            PlanningSection（快照缺席降空态默认值；解析异常/畸形键降 degraded=True）.
        """
        try:
            snapshot = await self._snapshot_repository.load(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}")
            if snapshot is None:
                return PlanningSection(available=False)
            state_data = snapshot.state_data if isinstance(snapshot.state_data, dict) else {}
            completed_steps = int(state_data["completed_steps"])
            total_steps = int(state_data.get("total_steps", BLM_TOTAL_STEPS))
            if total_steps <= 0:
                # 显式早退降级（R1-F1 修复——原 raise KeyError 控制流属内置异常越权）：
                # 与同族缺键/类型错两形态一致留 warning 痕迹，禁静默降级
                logger.warning(
                    "高管视图规划态势段降级: plan_id=%s error=ValueError: total_steps=%s 非正数（除零形态）",
                    plan_id,
                    total_steps,
                )
                return PlanningSection(available=False, degraded=True)
            degraded_steps = state_data.get("degraded_steps") or []
            timeline = state_data.get("timeline") or []
            last_activity = timeline[-1].get("completed_at") if timeline else None
            return PlanningSection(
                available=True,
                completed_steps=completed_steps,
                total_steps=total_steps,
                progress_percent=int(completed_steps / total_steps * 100),
                current_step=state_data.get("current_step"),
                degraded_step_count=len(degraded_steps),
                last_activity_at=last_activity,
            )
        except Exception as error:  # 段级容错：读侧脏数据守卫+单源异常隔离（6-5b 同款降级哲学）
            logger.warning("高管视图规划态势段降级: plan_id=%s error=%s: %s", plan_id, type(error).__name__, error)
            return PlanningSection(available=False, degraded=True)

    async def _build_approval_section(self, plan_id: str) -> ApprovalSection:
        """审批中心段（Checkpoint 分布计数+恢复记录留痕三键直读）.

        Args:
            plan_id: 规划任务标识.

        Returns:
            ApprovalSection（零 checkpoint 降空态；恢复记录缺席留痕三键 None）.
        """
        try:
            views: list[CheckpointSummaryView] = await self._checkpoint_service.list_checkpoints(plan_id=plan_id)
            recovery = await self._snapshot_repository.load(f"{CHECKPOINT_RECOVERY_SESSION_PREFIX}{plan_id}")
            recovery_data = recovery.state_data if recovery is not None and isinstance(recovery.state_data, dict) else None
            return ApprovalSection(
                available=len(views) > 0,
                total_checkpoints=len(views),
                completed_count=sum(1 for view in views if view.completed),
                in_sync_count=sum(1 for view in views if view.sync_status == _SYNC_IN_SYNC),
                pending_sync_count=sum(1 for view in views if view.sync_status == _SYNC_PENDING),
                invalidated_count=sum(1 for view in views if view.sync_status == _SYNC_INVALIDATED),
                last_recovery_mode=recovery_data.get("recovery_mode") if recovery_data else None,
                last_recovery_confirmed_by=recovery_data.get("confirmed_by") if recovery_data else None,
                last_recovered_at=recovery_data.get("recovered_at") if recovery_data else None,
            )
        except Exception as error:  # 段级容错
            logger.warning("高管视图审批中心段降级: plan_id=%s error=%s: %s", plan_id, type(error).__name__, error)
            return ApprovalSection(available=False, degraded=True)

    async def _build_audit_section(self, now: datetime) -> AuditSection:
        """审计摘要段（全局窗查询+投影白名单四键样本——无 available 键，OD-4）.

        Args:
            now: 视图入口时间锚（单锚派生——window_end 与 generated_at 同源，R1-F2）.

        Returns:
            AuditSection（窗口零事件是合法空态非不可得；查询异常降 degraded=True）.
        """
        try:
            window_end = now
            window_start = window_end - timedelta(days=DEFAULT_AUDIT_WINDOW_DAYS)
            criteria = AuditSearchCriteria(
                start_time=window_start,
                end_time=window_end,
                limit=_AUDIT_SAMPLE_LIMIT,
            )
            result: AuditSearchResult = await self._audit_repository.search(criteria)
            # 投影白名单四键（action_type/actor/target_resource/timestamp）——审计行
            # to_dict() 实为 15 键（checksum/correlation_id 等内部载荷）禁入高管视图（安全面）
            recent_events = tuple(
                AuditEventSummary(
                    action_type=str(item.get("action_type", "")),
                    actor=str(item.get("actor", "")),
                    target_resource=str(item.get("target_resource", "")),
                    timestamp=str(item["timestamp"]),
                )
                for item in result.items[:_AUDIT_SAMPLE_LIMIT]
            )
            return AuditSection(
                window_days=DEFAULT_AUDIT_WINDOW_DAYS,
                window_start=window_start.isoformat(),
                window_end=window_end.isoformat(),
                total_events=result.total,
                recent_events=recent_events,
                last_event_at=recent_events[0].timestamp if recent_events else None,
            )
        except Exception as error:  # 段级容错
            logger.warning("高管视图审计摘要段降级: error=%s: %s", type(error).__name__, error)
            return AuditSection(degraded=True)

    async def _build_report_section(self, plan_id: str) -> ReportSection:
        """报告可得性段（get_latest_by_plan——uuid.UUID 显式转换钦定，OD-13）.

        Args:
            plan_id: 规划任务标识（畸形已由用例层 242 拦截故转换安全）.

        Returns:
            ReportSection（无报告降空态；generated_at=created_at.isoformat() 派生映射——
            实体 8 字段无 generated_at 名，R1-F4）.
        """
        try:
            report: StrategicReport | None = await self._report_repository.get_latest_by_plan(uuid.UUID(plan_id))
            if report is None:
                return ReportSection(available=False)
            return ReportSection(
                available=True,
                report_id=str(report.report_id),
                report_type=report.report_type.value,
                file_path=report.file_path,
                section_count=report.section_count,
                degraded_section_count=report.degraded_section_count,
                generated_at=report.created_at.isoformat(),
            )
        except Exception as error:  # 段级容错
            logger.warning("高管视图报告可得性段降级: plan_id=%s error=%s: %s", plan_id, type(error).__name__, error)
            return ReportSection(available=False, degraded=True)
