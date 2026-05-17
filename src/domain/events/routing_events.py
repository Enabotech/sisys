"""SISYS 领域层 路由决策事件模块

定义UDMR路由决策相关的领域事件

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from .base import DomainEvent


@dataclass(frozen=True)
class RoutingDecided(DomainEvent):
    """UDMR路由决策时触发的事件

    L1（合规）和L2（四因子评分）字段由Story 11.x填充
    L3（本地/云端静态路由）字段由Story 1.17填充

    Attributes:
        task_id: 任务唯一标识符
        event_type: 事件类型，固定为"RoutingDecided"
        l1_compliance_result: L1合规检查结果
        l2_factor_scores: L2因子评分
        final_routing_score: 最终路由评分
        route_type: 路由类型（local/cloud）
        selected_model: 选中的模型
        estimated_cost: 预估成本
        fallback_reason: 回退原因（timeout/unavailable/health_check_failed）
        health_check_passed: 健康检查是否通过
        health_check_latency_ms: 健康检查延迟（毫秒）
    """

    task_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="RoutingDecided", init=False)
    l1_compliance_result: dict[str, Any] = field(default_factory=dict)
    l2_factor_scores: dict[str, float] = field(default_factory=dict)
    final_routing_score: float = 0.0
    # L3静态路由字段（Story 1.17）
    route_type: Literal["local", "cloud"] = "local"
    selected_model: str = ""
    estimated_cost: float = 0.0
    fallback_reason: Literal["timeout", "unavailable", "health_check_failed"] | None = None
    # 健康检查结果（Story 1.17）
    health_check_passed: bool = True
    health_check_latency_ms: float = 0.0

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.task_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "RoutingTask")
