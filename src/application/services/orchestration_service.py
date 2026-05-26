"""应用层编排服务模块

OrchestrationService 统一编排入口，根据 task_type 路由到不同引擎
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from src.domain.value_objects.flow_status import FlowStatus

if TYPE_CHECKING:
    from src.domain.ports.agent_engine import AgentEnginePort
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

    根据 task_type 路由到不同引擎：
    - data_pipeline → WorkflowEnginePort (Prefect)
    - agent_reasoning → AgentEnginePort (LangGraph)

    Args:
        workflow_engine: 工作流引擎端口（通过构造函数注入）
        agent_engine: Agent 引擎端口（通过构造函数注入）
    """

    def __init__(self, workflow_engine: WorkflowEnginePort, agent_engine: AgentEnginePort) -> None:
        self._workflow_engine = workflow_engine
        self._agent_engine = agent_engine

    async def execute(self, task: WorkflowTask) -> WorkflowResult:
        """执行工作流任务

        Args:
            task: 工作流任务

        Returns:
            工作流执行结果

        Raises:
            ValueError: task 参数无效或未知 task_type
        """
        if not task.flow_name:
            raise ValueError("flow_name 不能为空")
        if not task.parameters and task.task_type == "data_pipeline":
            raise ValueError("data_pipeline 任务必须提供 parameters")

        if task.task_type == "data_pipeline":
            flow_run_id = await self._workflow_engine.submit_flow(task.flow_name, task.parameters)
            status = await self._workflow_engine.get_flow_status(flow_run_id)
            return WorkflowResult(
                flow_run_id=flow_run_id,
                status=status,
                submitted_at=datetime.now(timezone.utc),
            )
        if task.task_type == "agent_reasoning":
            graph_name = task.parameters.get("graph_name")
            if not graph_name:
                raise ValueError("agent_reasoning 任务必须在 parameters 中提供 graph_name")
            graph_run_id = await self._agent_engine.submit_graph(graph_name, task.parameters)
            status = await self._agent_engine.get_graph_status(graph_run_id)
            return WorkflowResult(
                flow_run_id=graph_run_id,
                status=status,
                submitted_at=datetime.now(timezone.utc),
            )
        raise ValueError(f"未知的 task_type: {task.task_type}")
