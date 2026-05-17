"""领域层 自动路由事件模块

定义自动路由机制做出路由决策后触发的事件

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
class AutoRouted(DomainEvent):
    """自动路由机制做出路由决策时触发的事件

    此事件传递给Story 1.14c（自动执行）以执行任务

    Attributes:
        route_type: 路由类型，如"hash"、"semantic"或"mixed"
        session_id: 会话标识符
        task_context: 任务上下文信息
        route_target: 目标Agent或工具ID
        route_score: 路由置信度评分
        trigger_event_type: 原始触发事件类型（如"AutoTriggered"）
        trigger_event_id: 原始触发事件ID
    """

    route_type: str = ""  # "hash" | "semantic" | "mixed" - 路由类型
    session_id: str = ""
    task_context: dict[str, Any] = field(default_factory=dict)
    route_target: str = ""  # 目标Agent或工具ID
    route_score: float = 0.0  # 路由置信度评分
    trigger_event_type: str = ""  # 原始触发事件类型（如"AutoTriggered"）
    trigger_event_id: str | None = None

    def __post_init__(self) -> None:
        """设置event_type、aggregate_id和aggregate_type用于事件追踪"""
        if not self.event_type:
            object.__setattr__(self, "event_type", "AutoRouted")
        if self.aggregate_id is None and self.event_id:
            object.__setattr__(self, "aggregate_id", self.event_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "AutoRoute")


# 在类定义后注册AutoRouted（由于event_type的init=False需要手动注册）
DomainEvent._registry["AutoRouted"] = AutoRouted
