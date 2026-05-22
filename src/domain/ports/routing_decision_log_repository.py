"""领域层路由决策日志仓储端口模块

定义路由决策日志的持久化接口，供基础设施层实现

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities.routing_decision_log import RoutingDecisionLog


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
