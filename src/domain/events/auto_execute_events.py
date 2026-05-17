"""领域层 自动执行事件模块

定义自动执行机制完成任务后触发的事件

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
class AutoExecuted(DomainEvent):
    """自动执行机制完成任务时触发的事件

    此事件在自动路由决策（Story 1.14b）之后触发，包含执行结果
    下游监听器根据business_event_type发布对应的领域事件
    （DocumentProcessed/ToolExecuted/AgentDecided）

    Attributes:
        session_id: 会话标识符
        task_context: 任务上下文信息
        execution_result: 执行结果字典
        cost_estimate: 成本估算
        latency_ms: 执行延迟（毫秒）
        business_event_type: 业务事件类型，如"DocumentProcessed"等
        route_target: 自动路由选择的目标
        route_score: 路由置信度评分
    """

    session_id: str = ""
    task_context: dict[str, Any] = field(default_factory=dict)
    execution_result: dict[str, Any] = field(default_factory=dict)
    cost_estimate: float = 0.0
    latency_ms: float = 0.0
    business_event_type: str = ""  # "DocumentProcessed" | "ToolExecuted" | "AgentDecided"
    route_target: str = ""  # Target that was selected by auto-route
    route_score: float = 0.0  # Routing confidence score

    def __post_init__(self) -> None:
        """设置event_type、aggregate_id和aggregate_type用于事件追踪"""
        if not self.event_type:
            object.__setattr__(self, "event_type", "AutoExecuted")
        if self.aggregate_id is None and self.event_id:
            object.__setattr__(self, "aggregate_id", self.event_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "AutoExecute")


# 在类定义后注册AutoExecuted（由于event_type的init=False需要手动注册）
DomainEvent._registry["AutoExecuted"] = AutoExecuted
