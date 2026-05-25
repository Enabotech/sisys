"""基础设施层内存路由决策日志仓储模块

基于内存的 RoutingDecisionLogRepository 实现，适用于测试和 MVP 阶段

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging
from datetime import datetime

from src.domain.entities.routing_decision_log import RoutingDecisionLog
from src.domain.ports.routing_decision_log_repository import CostSummary

logger = logging.getLogger(__name__)


class InMemoryRoutingDecisionLogRepository:
    """内存路由决策日志仓储实现"""

    def __init__(self) -> None:
        self._logs: dict[str, RoutingDecisionLog] = {}

    async def save(self, log: RoutingDecisionLog) -> None:
        """保存路由决策日志到内存"""
        self._logs[str(log.log_id)] = log
        logger.debug("Saved routing decision log: log_id=%s", log.log_id)

    async def find_by_task_id(self, task_id: str) -> RoutingDecisionLog | None:
        """根据任务 ID 查找路由决策日志"""
        for log in self._logs.values():
            if log.task_id == task_id:
                return log
        return None

    async def query_cost_summary(
        self,
        start_time: datetime,
        end_time: datetime,
        route_type: str | None = None,
    ) -> CostSummary:
        """按时间范围聚合查询成本摘要"""
        total_cost = 0.0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        record_count = 0

        for log in self._logs.values():
            if log.timestamp < start_time or log.timestamp > end_time:
                continue
            if route_type is not None and log.route_type != route_type:
                continue
            total_cost += log.cost_actual
            total_prompt_tokens += log.prompt_tokens
            total_completion_tokens += log.completion_tokens
            record_count += 1

        return CostSummary(
            total_cost=total_cost,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            record_count=record_count,
        )
