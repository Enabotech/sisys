"""领域层辩论会话聚合根模块

Story 4.5 — 红蓝辩论机制基础：定义 DebateSession 聚合根（含
DebateSessionState 5 状态机），管理辩论运行时状态与迁移计数。

设计依据：
- Story 4.5 AC-2（ToolExecution 状态机同构）
- architecture.md §7（SYS AGENT 裁决与辩论机制）
- 项目惯例：参考 ToolExecution / SagaStatus 状态机实现

不变量约束:
- debate_id / tenant_id 必须为有效 UUID
- title 必须为非空字符串
- state 必须为 DebateSessionState 枚举值
- started_at 必须 timezone-aware
- 终态不变量：COMPLETED 必有 risk_view 与 completed_at；
  FAILED 必有 failure_reason；非终态 completed_at 必为 None
- state_version ≥ 0（迁移计数，V1 乐观锁 CAS 预留——MVP InMemory 仓储
  幂等覆盖无冲突检测，ToolExecution.save_with_state_version CAS 为 V1 演进先例）
- 状态迁移由 transition_to() 保证，非法迁移抛 EntityStateTransitionError（EXCEPTION_243 复用）
- 实体不发领域事件（项目惯例：事件由应用服务在流程完成后发布）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from src.domain.exceptions import EntityStateTransitionError, EntityValidationError
from src.domain.value_objects.debate import PerspectiveAnalysis, RiskView


class DebateSessionState(str, Enum):
    """辩论会话状态机枚举 — 5 个状态

    Attributes:
        IDLE: 初始态（会话创建）
        GENERATING: 红蓝视角生成中
        SYNTHESIZING: 风险视图合成中
        COMPLETED: 完成（终态）
        FAILED: 失败（终态）
    """

    IDLE = "idle"
    GENERATING = "generating"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


# 状态机迁移矩阵（沿用 SagaStatus dict[state, set[state]] 模式）
VALID_TRANSITIONS: dict[DebateSessionState, set[DebateSessionState]] = {
    DebateSessionState.IDLE: {DebateSessionState.GENERATING},
    DebateSessionState.GENERATING: {
        DebateSessionState.SYNTHESIZING,
        DebateSessionState.FAILED,
    },
    DebateSessionState.SYNTHESIZING: {
        DebateSessionState.COMPLETED,
        DebateSessionState.FAILED,
    },
    DebateSessionState.COMPLETED: set(),  # 终态
    DebateSessionState.FAILED: set(),  # 终态
}

TERMINAL_STATES: frozenset[DebateSessionState] = frozenset(
    {
        DebateSessionState.COMPLETED,
        DebateSessionState.FAILED,
    }
)


@dataclass
class DebateSession:
    """辩论会话聚合根

    状态机语义：
    - 状态迁移矩阵定义在 VALID_TRANSITIONS
    - 非法迁移抛 EntityStateTransitionError（EXCEPTION_243 复用）
    - 终态反向迁移禁止（重试创建新会话）
    - 迁移计数 state_version（V1 乐观锁 CAS 预留）

    Attributes:
        debate_id: 聚合根主键（与 DebateTopic.debate_id 共用）
        tenant_id: 多租户隔离
        title: 议题标题快照
        state: 当前会话状态
        red_analysis: 红方（激进派）视角分析（生成后回填）
        blue_analysis: 蓝方（保守派）视角分析（生成后回填）
        risk_view: 风险全景视图（合成后回填，COMPLETED 必填）
        failure_reason: 失败原因（FAILED 必填）
        started_at: 启动时间（timezone-aware）
        completed_at: 完成时间（COMPLETED 必填，非终态必空）
        state_version: 迁移计数（每次合法迁移 +1）
    """

    debate_id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    state: DebateSessionState = DebateSessionState.IDLE
    red_analysis: PerspectiveAnalysis | None = None
    blue_analysis: PerspectiveAnalysis | None = None
    risk_view: RiskView | None = None
    failure_reason: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    state_version: int = 0

    def __post_init__(self) -> None:
        """构造时强制校验所有不变量（ToolExecution 同构）"""
        self.validate()

    def validate(self) -> bool:
        """验证不变量约束

        Raises:
            EntityValidationError: 任何不变量违反
        """
        if not isinstance(self.debate_id, uuid.UUID):
            raise EntityValidationError(
                message="debate_id must be a valid UUID",
                context={"entity": "DebateSession", "field": "debate_id"},
            )
        if not isinstance(self.tenant_id, uuid.UUID):
            raise EntityValidationError(
                message="tenant_id must be a valid UUID",
                context={"entity": "DebateSession", "field": "tenant_id"},
            )
        if not isinstance(self.title, str) or not self.title.strip():
            raise EntityValidationError(
                message="title 必须为非空字符串",
                context={"entity": "DebateSession", "field": "title"},
            )
        if not isinstance(self.state, DebateSessionState):
            raise EntityValidationError(
                message="state 必须为 DebateSessionState 枚举值",
                context={"entity": "DebateSession", "field": "state"},
            )
        if not isinstance(self.started_at, datetime) or self.started_at.tzinfo is None:
            raise EntityValidationError(
                message="started_at 必须为 timezone-aware datetime",
                context={"entity": "DebateSession", "field": "started_at"},
            )
        if self.state_version < 0:
            raise EntityValidationError(
                message="state_version 必须 ≥ 0",
                context={
                    "entity": "DebateSession",
                    "field": "state_version",
                    "value": self.state_version,
                },
            )
        # 终态不变量：COMPLETED 必有 risk_view 与 completed_at
        if self.state is DebateSessionState.COMPLETED:
            if self.risk_view is None:
                raise EntityValidationError(
                    message="终态 COMPLETED 必须设置 risk_view",
                    context={
                        "entity": "DebateSession",
                        "field": "risk_view",
                        "state": self.state.name,
                    },
                )
            if self.completed_at is None:
                raise EntityValidationError(
                    message="终态 COMPLETED 必须设置 completed_at",
                    context={
                        "entity": "DebateSession",
                        "field": "completed_at",
                        "state": self.state.name,
                    },
                )
        # 终态不变量：FAILED 必有 failure_reason
        if self.state is DebateSessionState.FAILED and (self.failure_reason is None or not self.failure_reason.strip()):
            raise EntityValidationError(
                message="终态 FAILED 必须设置 failure_reason",
                context={
                    "entity": "DebateSession",
                    "field": "failure_reason",
                    "state": self.state.name,
                },
            )
        # 非终态 completed_at 应为 None（避免半成品）
        if self.state not in TERMINAL_STATES and self.completed_at is not None:
            raise EntityValidationError(
                message=f"非终态 {self.state.name} 不应设置 completed_at",
                context={
                    "entity": "DebateSession",
                    "field": "completed_at",
                    "state": self.state.name,
                },
            )
        return True

    def can_transition_to(self, new_state: DebateSessionState) -> bool:
        """检查迁移是否合法

        Args:
            new_state: 目标状态

        Returns:
            True 合法 / False 非法
        """
        allowed = VALID_TRANSITIONS.get(self.state, set())
        return new_state in allowed

    def transition_to(self, new_state: DebateSessionState) -> None:
        """显式状态迁移（带迁移计数递增）

        Args:
            new_state: 目标状态

        Raises:
            EntityStateTransitionError: 非法迁移（复用 EXCEPTION_243）
        """
        if not self.can_transition_to(new_state):
            raise EntityStateTransitionError(
                from_status=self.state.name,
                to_status=new_state.name,
                entity_type="DebateSession",
                entity_id=str(self.debate_id),
            )
        self.state = new_state
        self.state_version += 1


__all__ = [
    "DebateSession",
    "DebateSessionState",
    "TERMINAL_STATES",
    "VALID_TRANSITIONS",
]
