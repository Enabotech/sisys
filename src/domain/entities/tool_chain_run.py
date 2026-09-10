"""领域层工具链运行时实体模块

定义 ToolChainRun 聚合根 + ToolChainRunState 5 值状态机 + NodeRunStatus 值对象
+ CostAudit 强类型值对象，用于追踪 DAG 工具链运行时状态。

设计依据：
- Story 4.2 AC-4：聚合根 13 字段 + 5 值状态机 + 6 字段 NodeRunStatus + 8 字段 CostAudit
- 项目惯例：参考 ToolExecution 聚合根的状态机迁移模式（VALID_TRANSITIONS dict +
  transition_to() + state_version 乐观锁）
- 与 ToolExecutionState（6 值工具级抽象）独立的状态机（DAG 级抽象）

不可变设计：
- @dataclass(frozen=True) 保证聚合根不可变
- node_runs: dict（节点级状态）+ failed_nodes: tuple（失败节点列表）
- CostAudit 强类型值对象（Orchestrator 内部计算用，最终序列化为 dict）
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from src.domain.entities.tool_chain import FailureStrategy
from src.domain.exceptions import EntityStateTransitionError, EntityValidationError


class ToolChainRunState(str, Enum):
    """工具链运行时状态机枚举 — 5 个状态

    Attributes:
        PENDING: 待执行（创建后初始状态）
        RUNNING: 正在执行（至少一个节点处于 RUNNING）
        COMPLETED: 全部节点成功
        COMPLETED_WITH_ERRORS: 部分节点失败但策略允许继续
        FAILED: DAG 级别失败（FAIL_FAST 触发或全部节点失败）

    注意：本状态机不含 CANCELLED（CLAUDE.md §2 简化原则；本期无业务触发器）
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


# 状态机迁移矩阵（沿用 ToolExecution SagaStatus dict 模式）
VALID_TRANSITIONS: dict[ToolChainRunState, set[ToolChainRunState]] = {
    ToolChainRunState.PENDING: {ToolChainRunState.RUNNING},
    ToolChainRunState.RUNNING: {
        ToolChainRunState.COMPLETED,
        ToolChainRunState.COMPLETED_WITH_ERRORS,
        ToolChainRunState.FAILED,
    },
    ToolChainRunState.COMPLETED: set(),  # 终态
    ToolChainRunState.COMPLETED_WITH_ERRORS: set(),  # 终态
    ToolChainRunState.FAILED: set(),  # 终态
}

TERMINAL_STATES: frozenset[ToolChainRunState] = frozenset(
    {
        ToolChainRunState.COMPLETED,
        ToolChainRunState.COMPLETED_WITH_ERRORS,
        ToolChainRunState.FAILED,
    }
)


@dataclass(frozen=True)
class NodeRunStatus:
    """节点运行状态值对象

    Attributes:
        node_id: 节点标识
        state: 节点状态（PENDING / RUNNING / COMPLETED / FAILED / SKIPPED）
        started_at: 节点启动时间
        completed_at: 节点完成时间
        error: 错误信息
        tool_result: 工具执行结果（ToolResult.output 序列化）
    """

    node_id: str
    state: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    tool_result: dict | None = None


@dataclass(frozen=True)
class CostAudit:
    """成本审计强类型值对象（Orchestrator 内部计算用）

    最终序列化为 dict 写入 ToolChainRun.cost_audit 与 ToolChainExecuted.cost_audit。
    沿用 4.1a `ToolExecuted.cost_audit: dict[str, Any]` 惯例，避免破坏既有契约。

    Attributes:
        llm_prompt_tokens: LLM prompt token 总和
        llm_completion_tokens: LLM completion token 总和
        llm_total_tokens: LLM token 总和
        sandbox_duration_sec: 沙箱执行总时长（秒）
        api_calls: 外部 API 调用次数
        parallel_speedup_ratio: Amdahl 加速比（serial / parallel）
        critical_path_sec: 关键路径长度（最长路径上各节点耗时求和）
        wall_clock_sec: 实际 wall-clock 时长
    """

    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    llm_total_tokens: int = 0
    sandbox_duration_sec: float = 0.0
    api_calls: int = 0
    parallel_speedup_ratio: float | None = None
    critical_path_sec: float | None = None
    wall_clock_sec: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（事件载荷 + 持久化用）"""
        return asdict(self)


@dataclass(frozen=True)
class ToolChainRun:
    """工具链运行时聚合根

    状态机语义：
    - 状态迁移矩阵定义在 VALID_TRANSITIONS
    - 非法迁移抛 EntityStateTransitionError（EXCEPTION_243）
    - 终态反向迁移禁止
    - 乐观锁 state_version 防止并发覆盖

    Attributes:
        chain_run_id: 聚合根主键
        chain_id: 关联 ToolChainDag ID
        tenant_id: 多租户隔离
        state: 当前运行时状态
        started_at: 启动时间（timezone-aware）
        completed_at: 完成时间（终态时必填）
        node_runs: 节点运行状态字典（node_id → NodeRunStatus）
        failed_nodes: 失败的节点 node_id 列表
        total_duration_sec: 实际 wall-clock 耗时
        critical_path_sec: 关键路径长度
        parallel_speedup_ratio: Amdahl 加速比
        failure_strategy: 运行时使用的策略快照
        cost_audit: 成本审计字典（沿用 4.1a 惯例）
        state_version: 乐观锁版本号
    """

    chain_run_id: uuid.UUID
    chain_id: uuid.UUID
    tenant_id: uuid.UUID
    state: ToolChainRunState
    started_at: datetime
    completed_at: datetime | None = None
    node_runs: dict[str, NodeRunStatus] = field(default_factory=dict)
    failed_nodes: tuple[str, ...] = ()
    total_duration_sec: float | None = None
    critical_path_sec: float | None = None
    parallel_speedup_ratio: float | None = None
    failure_strategy: FailureStrategy = FailureStrategy.SKIP_DOWNSTREAM
    cost_audit: dict[str, Any] = field(default_factory=dict)
    state_version: int = 0

    def __post_init__(self) -> None:
        """构造时强制校验所有不变量"""
        self.validate()

    def validate(self) -> bool:
        """验证不变量约束

        Raises:
            EntityValidationError: 任何不变量违反
        """
        if not isinstance(self.chain_run_id, uuid.UUID):
            raise EntityValidationError(
                message="chain_run_id must be a valid UUID",
                context={"entity": "ToolChainRun", "field": "chain_run_id"},
            )
        if not isinstance(self.chain_id, uuid.UUID):
            raise EntityValidationError(
                message="chain_id must be a valid UUID",
                context={"entity": "ToolChainRun", "field": "chain_id"},
            )
        if not isinstance(self.tenant_id, uuid.UUID):
            raise EntityValidationError(
                message="tenant_id must be a valid UUID",
                context={"entity": "ToolChainRun", "field": "tenant_id"},
            )
        if not isinstance(self.state, ToolChainRunState):
            raise EntityValidationError(
                message="state 必须为 ToolChainRunState 枚举值",
                context={"entity": "ToolChainRun", "field": "state"},
            )
        if not isinstance(self.started_at, datetime) or self.started_at.tzinfo is None:
            raise EntityValidationError(
                message="started_at 必须为 timezone-aware datetime",
                context={"entity": "ToolChainRun", "field": "started_at"},
            )
        if self.state_version < 0:
            raise EntityValidationError(
                message="state_version 必须 ≥ 0",
                context={
                    "entity": "ToolChainRun",
                    "field": "state_version",
                    "value": self.state_version,
                },
            )
        if not isinstance(self.failure_strategy, FailureStrategy):
            raise EntityValidationError(
                message="failure_strategy 必须为 FailureStrategy 枚举值",
                context={
                    "entity": "ToolChainRun",
                    "field": "failure_strategy",
                    "value": self.failure_strategy,
                },
            )
        # 终态必有 completed_at
        if self.state in TERMINAL_STATES and self.completed_at is None:
            raise EntityValidationError(
                message=f"终态 {self.state.name} 必须设置 completed_at",
                context={
                    "entity": "ToolChainRun",
                    "field": "completed_at",
                    "state": self.state.name,
                },
            )
        # 非终态 completed_at 应为 None（避免半成品）
        if self.state not in TERMINAL_STATES and self.completed_at is not None:
            raise EntityValidationError(
                message=f"非终态 {self.state.name} 不应设置 completed_at",
                context={
                    "entity": "ToolChainRun",
                    "field": "completed_at",
                    "state": self.state.name,
                },
            )
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise EntityValidationError(
                message="completed_at 不能早于 started_at",
                context={
                    "entity": "ToolChainRun",
                    "started_at": self.started_at.isoformat(),
                    "completed_at": self.completed_at.isoformat(),
                },
            )
        if not isinstance(self.node_runs, dict):
            raise EntityValidationError(
                message="node_runs 必须为 dict[str, NodeRunStatus]",
                context={"entity": "ToolChainRun", "field": "node_runs"},
            )
        if not isinstance(self.failed_nodes, tuple):
            raise EntityValidationError(
                message="failed_nodes 必须为 tuple[str, ...]",
                context={"entity": "ToolChainRun", "field": "failed_nodes"},
            )
        return True

    def can_transition_to(self, new_state: ToolChainRunState) -> bool:
        """检查迁移是否合法

        Args:
            new_state: 目标状态

        Returns:
            True 合法 / False 非法
        """
        allowed = VALID_TRANSITIONS.get(self.state, set())
        return new_state in allowed

    def transition_to(self, new_state: ToolChainRunState) -> None:
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
                entity_type="ToolChainRun",
                entity_id=str(self.chain_run_id),
            )
        object.__setattr__(self, "state", new_state)
        object.__setattr__(self, "state_version", self.state_version + 1)


__all__ = [
    "ToolChainRun",
    "ToolChainRunState",
    "VALID_TRANSITIONS",
    "TERMINAL_STATES",
    "NodeRunStatus",
    "CostAudit",
]
