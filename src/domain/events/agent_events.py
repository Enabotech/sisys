"""SISYS 领域层 Agent事件模块。

定义 Agent 决策相关的领域事件。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class AgentDecided(DomainEvent):
    """Agent做出决策时触发的事件。

    Attributes:
        agent_id: Agent唯一标识符。
        event_type: 事件类型，固定为"AgentDecided"。
        decision_result: 决策结果字典。
        confidence: 决策置信度，范围0.0-1.0。
    """

    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="AgentDecided", init=False)
    decision_result: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def __post_init__(self) -> None:
        """初始化后设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Agent")
