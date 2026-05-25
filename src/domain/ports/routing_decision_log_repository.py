"""领域层路由决策日志仓储端口模块

定义路由决策日志的持久化接口，供基础设施层实现

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from src.domain.entities.routing_decision_log import RoutingDecisionLog


@dataclass(frozen=True)
class CostSummary:
    """成本聚合摘要

    Attributes:
        total_cost: 总成本（元）
        total_prompt_tokens: 总 prompt Token 数
        total_completion_tokens: 总 completion Token 数
        record_count: 记录数
    """

    total_cost: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    record_count: int = 0


@runtime_checkable
class RoutingDecisionLogRepository(Protocol):
    """路由决策日志仓储端口

    定义路由决策日志的持久化操作接口
    """

    async def save(self, log: RoutingDecisionLog) -> None:
        """保存路由决策日志

        Args:
            log: 路由决策日志实体
        """
        ...

    async def find_by_task_id(self, task_id: str) -> RoutingDecisionLog | None:
        """根据任务 ID 查找路由决策日志

        Args:
            task_id: 任务标识符

        Returns:
            匹配的路由决策日志，未找到返回 None
        """
        ...

    async def query_cost_summary(
        self,
        start_time: datetime,
        end_time: datetime,
        route_type: str | None = None,
    ) -> CostSummary:
        """按时间范围聚合查询成本摘要

        Args:
            start_time: 起始时间（含）
            end_time: 结束时间（含）
            route_type: 可选路由类型过滤

        Returns:
            成本聚合摘要
        """
        ...
