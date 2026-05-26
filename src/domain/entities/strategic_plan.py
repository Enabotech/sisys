"""领域层战略规划实体模块

定义战略规划领域实体，遵循 BLM 六阶段模型
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class BLMPhase(str, Enum):
    """BLM（商业领导力模型）阶段枚举"""

    STRATEGIC_INTENT = "strategic_intent"
    MARKET_INSIGHT = "market_insight"
    STRATEGIC_DESIGN = "strategic_design"
    ORGANIZATIONAL_DESIGN = "organizational_design"
    IMPLEMENTATION_PLANNING = "implementation_planning"
    EXECUTION_MONITORING = "execution_monitoring"


class PlanStatus(str, Enum):
    """战略规划状态枚举"""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    ARCHIVED = "archived"


@dataclass
class StrategicPlan:
    """战略规划实体，遵循 BLM 六阶段模型

    不变量约束:
    - plan_id 必须为有效 UUID
    - name 不能为空
    - current_phase 必须为有效 BLMPhase
    - created_at 必须早于或等于 updated_at
    """

    plan_id: uuid.UUID
    name: str
    description: str = ""
    current_phase: BLMPhase = BLMPhase.STRATEGIC_INTENT
    status: PlanStatus = PlanStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_phases: list[BLMPhase] = field(default_factory=list)

    def validate(self) -> bool:
        """验证不变量约束

        Returns:
            所有不变量满足时返回 True

        Raises:
            ValueError: 任何不变量违反时抛出
        """
        if not isinstance(self.plan_id, uuid.UUID):
            raise ValueError("plan_id must be a valid UUID")
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not isinstance(self.current_phase, BLMPhase):
            raise ValueError("current_phase must be a valid BLMPhase")
        # P2-05 Fix: created_at/updated_at have default_factory, never None
        if self.created_at > self.updated_at:
            raise ValueError("created_at must be before or equal to updated_at")
        # P1-01 Fix: Validate completed_phases consistency
        if self.current_phase in self.completed_phases:
            raise ValueError("current_phase must not be in completed_phases")
        return True

    def advance_phase(self, next_phase: BLMPhase) -> None:
        """推进到下一个 BLM 阶段

        Args:
            next_phase: 要推进到的下一个 BLM 阶段

        Raises:
            ValueError: 阶段转换无效或规划已归档/审批通过时抛出
        """
        # P0-03: Status guard — cannot advance archived or approved plans
        if self.status in (PlanStatus.ARCHIVED, PlanStatus.APPROVED):
            raise ValueError(f"Cannot advance phase when plan is {self.status.value}")

        # P0-01 Fix: Guard against advancing past the final phase
        if self.current_phase == BLMPhase.EXECUTION_MONITORING:
            raise ValueError("Plan has reached the final phase (EXECUTION_MONITORING), no further phase advancement possible")

        phase_order = list(BLMPhase)
        current_idx = phase_order.index(self.current_phase)
        next_idx = phase_order.index(next_phase)

        # P0-02: Must advance to immediately next phase (no skipping)
        if next_idx != current_idx + 1:
            raise ValueError("Can only advance to the immediately next phase")

        # P1-01 Fix: Prevent duplicate entries in completed_phases
        if self.current_phase not in self.completed_phases:
            self.completed_phases.append(self.current_phase)
        self.current_phase = next_phase
        self.updated_at = datetime.now(UTC)

    def complete_phase(self) -> None:
        """标记当前阶段为已完成并自动推进

        Raises:
            ValueError: 规划已归档/审批通过或已处于最终阶段时抛出
        """
        # Status guard — cannot complete archived or approved plans
        if self.status in (PlanStatus.ARCHIVED, PlanStatus.APPROVED):
            raise ValueError(f"Cannot complete phase when plan is {self.status.value}")

        # Final phase guard — cannot complete past the final phase
        if self.current_phase == BLMPhase.EXECUTION_MONITORING:
            raise ValueError("Plan has reached the final phase (EXECUTION_MONITORING), no further phase advancement possible")

        # P1-01 Fix: Prevent duplicate entries in completed_phases
        if self.current_phase not in self.completed_phases:
            self.completed_phases.append(self.current_phase)
        phase_order = list(BLMPhase)
        current_idx = phase_order.index(self.current_phase)
        if current_idx < len(phase_order) - 1:
            self.current_phase = phase_order[current_idx + 1]
        self.updated_at = datetime.now(UTC)
