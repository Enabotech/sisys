"""领域层 战略规划事件模块

定义战略规划偏差相关的领域事件（StrategicDeviationWarning——既有）与
BLM 规划流程事件（PlanningStarted / BlmStageCompleted——Story 6-1 扩展，
保留既有事件类勿整文件覆盖）。

BLM 事件通道钦定（DC-8）：两事件均 reliable 单通道（RabbitMQ + Outbox，
AgentDecided 配置先例——DualChannelEventBus.publish 按事件单模式分派，
一事件不走双通道）；双登记纪律（event_channels.yaml +
ChannelRouter.DEFAULT_MAPPINGS）由 Task 4 落地。

发布点钦定（Task 0.6②）：
- PlanningStarted 由 RunBlmPlanningUseCase 三守卫（443/441/447）通过后、
  submit_graph 前发布（守卫前发布则失败 run 留孤儿事件）。
- BlmStageCompleted 由 BlmPlanningService 各阶段/子步骤方法末尾发布。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.exceptions import EntityValidationError

from .base import DomainEvent
from .enums import DeviationLevel, DeviationType

#: BlmStageCompleted.summary_excerpt 截断上限（fix_attempts violations_excerpt ≤200 先例）
_SUMMARY_EXCERPT_MAX_CHARS: int = 200


@dataclass(frozen=True)
class StrategicDeviationWarning(DomainEvent):
    """战略规划偏离预期轨迹时触发的事件

    Attributes:
        warning_id: 警告唯一标识符
        event_type: 事件类型，固定为"StrategicDeviationWarning"
        deviation_type: 偏差类型
        deviation_level: 偏差级别
        actual_value: 实际值
        planned_value: 计划值
        threshold: 阈值
    """

    warning_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="StrategicDeviationWarning", init=False)
    deviation_type: DeviationType = DeviationType.BUDGET_OVERUN
    deviation_level: DeviationLevel = DeviationLevel.MINOR
    actual_value: float = 0.0
    planned_value: float = 0.0
    threshold: float = 10.0

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.warning_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "StrategicPlan")


@dataclass(frozen=True)
class PlanningStarted(DomainEvent):
    """BLM 规划启动事件（Story 6-1——AC-4①）

    规划任务启动时发布（三守卫通过后、submit_graph 前——防孤儿事件）。
    必填字段必须 kw_only（基类字段全带默认值——agent_events.py 先例注释）。

    Attributes:
        plan_id: 规划任务标识（str——与 BlmPlanningStatus.plan_id 同源）
        agent_id: 执行 Agent 标识（MVP 单 CEO Agent）
        tenant_id: 租户标识
        started_at: 启动时间（timezone-aware UTC）
        event_type: 事件类型，固定为 "PlanningStarted"（init=False 自动注册）
    """

    plan_id: str = field(kw_only=True)
    agent_id: uuid.UUID = field(kw_only=True)
    tenant_id: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_type: str = field(default="PlanningStarted", init=False)

    def __post_init__(self) -> None:
        """自校验：plan_id 非空；设置 aggregate_id（agent_id）与 aggregate_type。"""
        if not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise EntityValidationError(
                message="PlanningStarted.plan_id 必须为非空 str",
                context={"entity_type": "PlanningStarted", "field": "plan_id"},
            )
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "StrategicPlan")


@dataclass(frozen=True)
class BlmStageCompleted(DomainEvent):
    """BLM 阶段/子步骤完成事件（Story 6-1——AC-4②③④）

    各阶段/子步骤完成时发布（BlmPlanningService 各方法末尾）。

    Attributes:
        plan_id: 规划任务标识
        agent_id: 执行 Agent 标识
        stage: 完成阶段标识——8 值全集枚举域守卫
            （performance_gap / market_insight_{trend|market_customer|competition|
            self|opportunity|opportunity_gap} / market_insight_synthesis）
        completed_at: 完成时间（timezone-aware UTC）
        summary_excerpt: 阶段摘要（≤200 截断——violations_excerpt 先例）
        event_type: 事件类型，固定为 "BlmStageCompleted"（init=False 自动注册）
    """

    plan_id: str = field(kw_only=True)
    agent_id: uuid.UUID = field(kw_only=True)
    stage: str = field(kw_only=True)
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    summary_excerpt: str = ""
    event_type: str = field(default="BlmStageCompleted", init=False)

    def __post_init__(self) -> None:
        """自校验：stage 枚举域守卫 + 摘要截断；设置聚合标识。"""
        from src.domain.value_objects.blm_phases import STAGE_VALUE_DOMAIN

        if self.stage not in STAGE_VALUE_DOMAIN:
            raise EntityValidationError(
                message=f"BlmStageCompleted.stage 越域: {self.stage!r}（合法域 8 值——STAGE_VALUE_DOMAIN）",
                context={"entity_type": "BlmStageCompleted", "field": "stage", "value": self.stage},
            )
        if len(self.summary_excerpt) > _SUMMARY_EXCERPT_MAX_CHARS:
            object.__setattr__(self, "summary_excerpt", self.summary_excerpt[:_SUMMARY_EXCERPT_MAX_CHARS])
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "StrategicPlan")
