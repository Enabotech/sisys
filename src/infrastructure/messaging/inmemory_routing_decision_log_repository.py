"""基础设施层内存路由决策日志仓储模块

基于内存的 RoutingDecisionLogRepository 实现，适用于测试和 MVP 阶段

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging

from src.domain.entities.routing_decision_log import RoutingDecisionLog

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
