"""Saga 状态枚举 - 领域层定义

SagaStatus 定义 Saga 实例的生命周期状态和合法转换规则
"""

from __future__ import annotations

from enum import Enum


class SagaStatus(str, Enum):
    """Saga 实例状态枚举。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        """是否为终态。"""
        return self in (SagaStatus.COMPLETED, SagaStatus.COMPENSATED, SagaStatus.FAILED)

    def can_transition_to(self, target: SagaStatus) -> bool:
        """检查是否可转换到目标状态。"""
        valid_transitions: dict[SagaStatus, set[SagaStatus]] = {
            SagaStatus.PENDING: {SagaStatus.RUNNING},
            SagaStatus.RUNNING: {SagaStatus.COMPLETED, SagaStatus.COMPENSATING, SagaStatus.FAILED},
            SagaStatus.COMPENSATING: {SagaStatus.COMPENSATED, SagaStatus.FAILED},
        }
        return target in valid_transitions.get(self, set())
