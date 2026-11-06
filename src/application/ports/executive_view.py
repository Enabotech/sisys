"""高管简化视图端口契约（Story 6-8）——六 VO + ExecutiveHealth 三值枚举 + ExecutiveViewPort.

读侧 CQRS 投影 DTO（读侧 DTO 归应用层——6-6 CheckpointSummaryView/6-7 五 VO 先例族；
零 domain VO——OD-12 准三零裁定）。四段聚合：
    - 规划态势段（planning）：BLM latest 快照七键解析投影；
    - 审批中心段（approval）：Checkpoint 完成分布 + sync 三态分布 + 恢复留痕三键；
    - 审计摘要段（audit）：全局窗事件总量 + 最近样本投影（无 available 键——窗口零事件
      是合法空态非不可得，与三段 available 语义分立，OD-4）；
    - 报告可得性段（report）：最新报告标识与降级计数（generated_at = 实体
      created_at.isoformat() 派生映射——R1-F4；report_id = str() 化）。

ExecutiveHealth 是全仓首个三值分级枚举（对照先例族全两值：ValidityStatus/staleness/
树节点 status——OD-4 显式注记），值域对齐 UX v2.1「绿色=健康/琥珀=关注/红色=危险」
（amber 不用 yellow——通行 RAG 用语）。

端口版本：(v1.0.0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from src.domain.exceptions import EntityValidationError


class ExecutiveHealth(str, Enum):
    """高管视图 RAG 三色健康状态（红/黄/绿三色判别的值域载体）.

    值域对齐 UX v2.1 L1250-1252「绿色（健康）/琥珀（关注）/红色（危险）」语义；
    amber 不用 yellow（英文词取通行 RAG 用语——OD-4 权威间冲突显式声明）。
    """

    GREEN = "green"
    AMBER = "amber"
    RED = "red"


@dataclass(frozen=True)
class PlanningSection:
    """规划态势段（8 键——BLM latest 快照 state_data 七键解析投影）.

    空态降级值语义：快照缺席（available=False）或 state_data 畸形（degraded=True）时
    计数降 0、标识降 None——键恒在纪律（6-2 R1-6 七键契约同族）。
    progress_percent 为高管视图整数口径（int(completed/total*100) 向下取整），与
    BlmPlanningStatus.progress_percent（round-2 float）口径有意分立（R1-F3 裁定）。
    """

    available: bool = False
    degraded: bool = False
    completed_steps: int = 0
    total_steps: int = 8
    progress_percent: int = 0
    current_step: str | None = None
    degraded_step_count: int = 0
    last_activity_at: str | None = None

    def __post_init__(self) -> None:
        """构造守卫：三计数非负（违例抛 242——实体不变量场景钦定）."""
        if self.completed_steps < 0 or self.total_steps < 0 or self.degraded_step_count < 0:
            raise EntityValidationError(
                message="规划态势段计数不得为负",
                context={
                    "vo": "PlanningSection",
                    "completed_steps": self.completed_steps,
                    "total_steps": self.total_steps,
                    "degraded_step_count": self.degraded_step_count,
                },
            )


@dataclass(frozen=True)
class ApprovalSection:
    """审批中心段（10 键——Checkpoint 分布计数+恢复留痕三键）.

    sync 三态分布派生自 CheckpointSummaryView.sync_status 值域
    （in_sync/pending_sync/invalidated）；三态分布和恒等于总数（完备恒等式——AC-3）。
    恢复留痕三键直读恢复记录 12 键（无恢复记录降 None——键恒在纪律）。
    """

    available: bool = False
    degraded: bool = False
    total_checkpoints: int = 0
    completed_count: int = 0
    in_sync_count: int = 0
    pending_sync_count: int = 0
    invalidated_count: int = 0
    last_recovery_mode: str | None = None
    last_recovery_confirmed_by: str | None = None
    last_recovered_at: str | None = None

    def __post_init__(self) -> None:
        """构造守卫：总计数与三态计数非负."""
        negative_fields = {
            "total_checkpoints": self.total_checkpoints,
            "completed_count": self.completed_count,
            "in_sync_count": self.in_sync_count,
            "pending_sync_count": self.pending_sync_count,
            "invalidated_count": self.invalidated_count,
        }
        if any(value < 0 for value in negative_fields.values()):
            raise EntityValidationError(
                message="审批中心段计数不得为负",
                context={"vo": "ApprovalSection", **negative_fields},
            )


@dataclass(frozen=True)
class AuditEventSummary:
    """审计事件样本（4 键——投影白名单）.

    从审计行 dict 挑键投影（action_type/actor/target_resource/timestamp）；
    审计行 to_dict() 实为 15 键（含 checksum/correlation_id 等内部载荷）禁入
    高管视图——安全面投影白名单（OD-4）。
    """

    action_type: str
    actor: str
    target_resource: str
    timestamp: str


@dataclass(frozen=True)
class AuditSection:
    """审计摘要段（7 键——时间窗 total+最近样本；无 available 键，OD-4）.

    全局窗聚合系统级事件（无 plan 维度——OD-10 语义注记）；total_events 单源
    AuditSearchResult.total；recent_events 恒元组（frozen 纪律）。
    """

    degraded: bool = False
    window_days: int = 7
    window_start: str = ""
    window_end: str = ""
    total_events: int = 0
    recent_events: tuple[AuditEventSummary, ...] = ()
    last_event_at: str | None = None

    def __post_init__(self) -> None:
        """构造守卫：total_events 非负 + recent_events 归一化恒元组."""
        if self.total_events < 0:
            raise EntityValidationError(
                message="审计摘要段事件总量不得为负",
                context={"vo": "AuditSection", "total_events": self.total_events},
            )
        if not isinstance(self.recent_events, tuple):
            object.__setattr__(self, "recent_events", tuple(self.recent_events))


@dataclass(frozen=True)
class ReportSection:
    """报告可得性段（8 键——最新报告标识与降级计数）.

    report_id = str(StrategicReport.report_id)（实体为 uuid.UUID——str 化钦定）；
    generated_at = StrategicReport.created_at.isoformat() 派生映射（实体 8 字段无
    generated_at 名——R1-F4）；无报告时标识降 None、计数降 0。
    """

    available: bool = False
    degraded: bool = False
    report_id: str | None = None
    report_type: str | None = None
    file_path: str | None = None
    section_count: int = 0
    degraded_section_count: int = 0
    generated_at: str | None = None

    def __post_init__(self) -> None:
        """构造守卫：section 双计数非负."""
        if self.section_count < 0 or self.degraded_section_count < 0:
            raise EntityValidationError(
                message="报告可得性段计数不得为负",
                context={
                    "vo": "ReportSection",
                    "section_count": self.section_count,
                    "degraded_section_count": self.degraded_section_count,
                },
            )


@dataclass(frozen=True)
class ExecutiveView:
    """高管简化视图（8 键——四段聚合 + RAG 三色健康状态 + 顶层降级哨兵）.

    build_degraded 是顶层哨兵（任一数据源段级降级即 True——「拿不到数据不得报绿」
    读模型诚实性，6-7 哲学延续；health 规则 2 显式含 build_degraded==False 条件）。
    generated_at 是视图生成锚（ISO 字符串——与审计窗 window 键同型）。
    """

    plan_id: str
    generated_at: str = ""
    health: ExecutiveHealth = ExecutiveHealth.AMBER
    build_degraded: bool = False
    planning: PlanningSection = field(default_factory=PlanningSection)
    approval: ApprovalSection = field(default_factory=ApprovalSection)
    audit: AuditSection = field(default_factory=AuditSection)
    report: ReportSection = field(default_factory=ReportSection)

    def __post_init__(self) -> None:
        """构造守卫：plan_id 非空字符串 + health 枚举成员校验（裸 str 拒绝）."""
        if not isinstance(self.plan_id, str) or not self.plan_id:
            raise EntityValidationError(
                message="plan_id 必须为非空字符串",
                context={"vo": "ExecutiveView", "field": "plan_id", "plan_id": self.plan_id},
            )
        if not isinstance(self.health, ExecutiveHealth):
            raise EntityValidationError(
                message="health 必须为 ExecutiveHealth 枚举成员（裸字符串拒绝）",
                context={"vo": "ExecutiveView", "field": "health", "health": self.health},
            )


@runtime_checkable
class ExecutiveViewPort(Protocol):
    """高管简化视图端口（读侧聚合 CQRS 投影——R2 应用层具体端口组合注入四既有依赖）.

    消费方：GetExecutiveViewUseCase（用例守卫+透传）+ CLI executive-view 子命令
    （经组合根 executive_view_use_case 注册名 resolve）。
    端口版本：(v1.0.0)
    """

    async def build_executive_view(self, *, plan_id: str) -> ExecutiveView:
        """按 plan_id 构建四段聚合视图.

        Args:
            plan_id: 规划任务标识（UUID 字符串——畸形守卫归用例层 242，服务层不守卫）.

        Returns:
            ExecutiveView 八键冻结视图（空 plan 幂等读返回空态视图不抛异常——AC-5）.
        """
        ...
