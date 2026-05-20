"""应用层编排服务模块

OrchestrationService 统一编排入口，根据 task_type 路由到不同引擎

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from src.domain.value_objects.flow_status import FlowStatus

if TYPE_CHECKING:
    from src.domain.ports.workflow_engine import WorkflowEnginePort


@dataclass(frozen=True)
class WorkflowTask:
    """工作流任务值对象"""

    flow_name: str
    parameters: dict[str, Any]
    task_type: Literal["data_pipeline", "agent_reasoning"]


@dataclass(frozen=True)
class WorkflowResult:
    """工作流执行结果值对象"""

    flow_run_id: str
    status: FlowStatus
    submitted_at: datetime


class OrchestrationService:
    """应用层编排服务

    MVP：仅支持 data_pipeline 路由到 WorkflowEnginePort。
    Story 1.18b 补充 agent_reasoning 路由到 LangGraph。

    Args:
        workflow_engine: 工作流引擎端口（通过构造函数注入）
    """

    def __init__(self, workflow_engine: WorkflowEnginePort) -> None:
        self._workflow_engine = workflow_engine

    async def execute(self, task: WorkflowTask) -> WorkflowResult:
        """执行工作流任务

        Args:
            task: 工作流任务

        Returns:
            工作流执行结果

        Raises:
            NotImplementedError: agent_reasoning 由 Story 1.18b 实现
        """
        if task.task_type == "data_pipeline":
            flow_run_id = await self._workflow_engine.submit_flow(task.flow_name, task.parameters)
            status = await self._workflow_engine.get_flow_status(flow_run_id)
            return WorkflowResult(
                flow_run_id=flow_run_id,
                status=status,
                submitted_at=datetime.now(timezone.utc),
            )
        raise NotImplementedError("agent_reasoning 由 Story 1.18b 实现")
