"""SISYS 领域层 心跳事件模块

定义心跳定时器相关的领域事件

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from .base import DomainEvent


@dataclass(frozen=True)
class HeartbeatTriggered(DomainEvent):
    """周期性心跳定时器触发时触发的事件

    Attributes:
        heartbeat_id: 心跳唯一标识符
        event_type: 事件类型，固定为"HeartbeatTriggered"
        wake_reason: 唤醒原因
        todo_items: 待办事项列表
        cost_budget: 成本预算
    """

    heartbeat_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="HeartbeatTriggered", init=False)
    wake_reason: str = ""
    todo_items: Sequence[str] = field(default_factory=tuple)
    cost_budget: float = 0.0

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.heartbeat_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Heartbeat")
