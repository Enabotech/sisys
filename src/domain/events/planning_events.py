"""SISYS 领域层 战略规划事件模块

定义战略规划偏差相关的领域事件

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .base import DomainEvent
from .enums import DeviationLevel, DeviationType


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
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.warning_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "StrategicPlan")
