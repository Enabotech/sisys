"""SISYS 领域层 隔离级别事件模块。

定义Agent隔离级别切换相关的领域事件。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .base import DomainEvent
from .enums import IsolationLevel


@dataclass(frozen=True)
class IsolationLevelSwitched(DomainEvent):
    """Agent隔离级别切换时触发的事件。

    Attributes:
        agent_id: Agent唯一标识符。
        event_type: 事件类型，固定为"IsolationLevelSwitched"。
        previous_level: 切换前的隔离级别。
        target_level: 目标隔离级别。
        trigger_reason: 触发原因。
        approval_chain: 审批链列表。
        switch_timestamp: 切换时间戳。
    """

    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="IsolationLevelSwitched", init=False)
    previous_level: IsolationLevel = IsolationLevel.L4_HARD
    target_level: IsolationLevel = IsolationLevel.L4_HARD
    trigger_reason: str = ""
    approval_chain: list[str] = field(default_factory=list)
    switch_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Agent")
