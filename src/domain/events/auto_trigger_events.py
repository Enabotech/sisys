"""领域层 自动触发事件模块

定义自动触发机制从领域/心跳事件提取上下文后触发的事件

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class AutoTriggered(DomainEvent):
    """自动触发机制从领域或心跳事件提取上下文时触发的事件

    此事件传递给Story 1.14b（自动路由）进行会话感知的路由决策

    Attributes:
        trigger_type: 触发类型，"domain_event"或"heartbeat"
        session_id: 会话标识符
        agent_id: Agent标识符（可选）
        task_context: 任务上下文信息
        source_event_type: 原始触发事件类型（如"DocumentProcessed"）
        source_event_id: 原始触发事件ID
    """

    event_type: str = field(default="AutoTriggered", init=False)
    trigger_type: str = ""  # "domain_event" | "heartbeat"
    session_id: str = ""
    agent_id: str | None = None
    task_context: dict[str, Any] = field(default_factory=dict)
    source_event_type: str = ""  # 触发的原始事件（如"DocumentProcessed"）
    source_event_id: str | None = None

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type用于事件追踪"""
        if self.aggregate_id is None and self.event_id:
            object.__setattr__(self, "aggregate_id", self.event_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "AutoTrigger")
