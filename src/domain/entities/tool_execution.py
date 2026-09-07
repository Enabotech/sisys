"""领域层工具执行聚合根模块

定义 ToolExecution 聚合根（含 ToolExecutionState 6 状态机），
与 Tool 生命周期字段解耦，专门管理工具运行时状态。

设计依据：
- Story 4.1a AC-1 Part B
- architecture.md §17 工具执行引擎设计
- 项目惯例：参考 Agent / Checkpoint / StrategicPlan 状态机实现

不变量约束:
- execution_id / tenant_id / tool_id 必须为有效 UUID
- tool_version 必须为非空字符串
- state 必须为 ToolExecutionState 枚举值
- started_at 必须 timezone-aware
- 终态（COMPLETED / FAILED）必须设置 completed_at
- 非终态 completed_at 必须为 None
- retry_count ≥ 0
- state_version ≥ 0（乐观锁）
- 状态迁移由 transition_to() 方法保证，非法迁移抛 EntityStateTransitionError
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.domain.exceptions import EntityStateTransitionError, EntityValidationError


class ToolExecutionState(str, Enum):
    """工具执行状态机枚举 — 6 个状态"""

    IDLE = "IDLE"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# 状态机迁移矩阵（沿用 SagaStatus dict[state, set[state]] 模式）
VALID_TRANSITIONS: dict[ToolExecutionState, set[ToolExecutionState]] = {
    ToolExecutionState.IDLE: {ToolExecutionState.PLANNING},
    ToolExecutionState.PLANNING: {
        ToolExecutionState.EXECUTING,
        ToolExecutionState.FAILED,
    },
    ToolExecutionState.EXECUTING: {
        ToolExecutionState.VALIDATING,
        ToolExecutionState.FAILED,
    },
    ToolExecutionState.VALIDATING: {
        ToolExecutionState.COMPLETED,
        ToolExecutionState.FAILED,
    },
    ToolExecutionState.COMPLETED: set(),  # 终态
    ToolExecutionState.FAILED: set(),  # 终态
}

TERMINAL_STATES: frozenset[ToolExecutionState] = frozenset(
    {
        ToolExecutionState.COMPLETED,
        ToolExecutionState.FAILED,
    }
)


@dataclass
class ToolExecution:
    """工具执行聚合根

    状态机语义：
    - 状态迁移矩阵定义在 VALID_TRANSITIONS
    - 非法迁移抛 EntityStateTransitionError（EXCEPTION_243）
    - 终态（COMPLETED/FAILED）反向迁移禁止（重试创建新 attempt）
    - 乐观锁 state_version 防止并发覆盖

    Attributes:
        execution_id: 聚合根主键
        tenant_id: 多租户隔离
        tool_id: 关联 Tool 聚合根 ID（ID-only 引用）
        tool_version: 工具版本快照
        state: 当前执行状态
        started_at: 启动时间（timezone-aware）
        completed_at: 完成时间（终态时必填）
        retry_count: 本次执行内尝试次数
        failure_reason: 失败原因
        plan: Think 阶段产物
        code: Code 阶段产物
        result: Execute 阶段产物
        observation: Observe 阶段产物
        validation: Validate 阶段产物
        evidence_package: 完整证据包
        state_version: 乐观锁版本号
    """

    execution_id: uuid.UUID
    tenant_id: uuid.UUID
    tool_id: uuid.UUID
    tool_version: str
    state: ToolExecutionState
    started_at: datetime
    completed_at: datetime | None = None
    retry_count: int = 0
    failure_reason: str | None = None
    plan: str | None = None
    code: str | None = None
    result: str | None = None
    observation: str | None = None
    validation: str | None = None
    evidence_package: dict | None = None
    state_version: int = 0

    def __post_init__(self) -> None:
        """构造时强制校验所有不变量"""
        self.validate()

    def validate(self) -> bool:
        """验证不变量约束

        Raises:
            EntityValidationError: 任何不变量违反
        """
        if not isinstance(self.execution_id, uuid.UUID):
            raise EntityValidationError(
                message="execution_id must be a valid UUID",
                context={"entity": "ToolExecution", "field": "execution_id"},
            )
        if not isinstance(self.tenant_id, uuid.UUID):
            raise EntityValidationError(
                message="tenant_id must be a valid UUID",
                context={"entity": "ToolExecution", "field": "tenant_id"},
            )
        if not isinstance(self.tool_id, uuid.UUID):
            raise EntityValidationError(
                message="tool_id must be a valid UUID",
                context={"entity": "ToolExecution", "field": "tool_id"},
            )
        if not isinstance(self.tool_version, str) or not self.tool_version:
            raise EntityValidationError(
                message="tool_version 必须为非空字符串",
                context={"entity": "ToolExecution", "field": "tool_version"},
            )
        if not isinstance(self.state, ToolExecutionState):
            raise EntityValidationError(
                message="state 必须为 ToolExecutionState 枚举值",
                context={"entity": "ToolExecution", "field": "state"},
            )
        if not isinstance(self.started_at, datetime) or self.started_at.tzinfo is None:
            raise EntityValidationError(
                message="started_at 必须为 timezone-aware datetime",
                context={"entity": "ToolExecution", "field": "started_at"},
            )
        if self.retry_count < 0:
            raise EntityValidationError(
                message="retry_count 必须 ≥ 0",
                context={
                    "entity": "ToolExecution",
                    "field": "retry_count",
                    "value": self.retry_count,
                },
            )
        if self.state_version < 0:
            raise EntityValidationError(
                message="state_version 必须 ≥ 0",
                context={
                    "entity": "ToolExecution",
                    "field": "state_version",
                    "value": self.state_version,
                },
            )
        # 终态必有 completed_at
        if self.state in TERMINAL_STATES and self.completed_at is None:
            raise EntityValidationError(
                message=f"终态 {self.state.name} 必须设置 completed_at",
                context={
                    "entity": "ToolExecution",
                    "field": "completed_at",
                    "state": self.state.name,
                },
            )
        # 非终态 completed_at 应为 None（避免半成品）
        if self.state not in TERMINAL_STATES and self.completed_at is not None:
            raise EntityValidationError(
                message=f"非终态 {self.state.name} 不应设置 completed_at",
                context={
                    "entity": "ToolExecution",
                    "field": "completed_at",
                    "state": self.state.name,
                },
            )
        return True

    def can_transition_to(self, new_state: ToolExecutionState) -> bool:
        """检查迁移是否合法

        Args:
            new_state: 目标状态

        Returns:
            True 合法 / False 非法
        """
        allowed = VALID_TRANSITIONS.get(self.state, set())
        return new_state in allowed

    def transition_to(self, new_state: ToolExecutionState) -> None:
        """显式状态迁移（带乐观锁递增）

        Args:
            new_state: 目标状态

        Raises:
            EntityStateTransitionError: 非法迁移（复用 EXCEPTION_243）
        """
        if not self.can_transition_to(new_state):
            raise EntityStateTransitionError(
                from_status=self.state.name,
                to_status=new_state.name,
                entity_type="ToolExecution",
                entity_id=str(self.execution_id),
            )
        self.state = new_state
        self.state_version += 1


__all__ = [
    "ToolExecution",
    "ToolExecutionState",
    "VALID_TRANSITIONS",
    "TERMINAL_STATES",
]
