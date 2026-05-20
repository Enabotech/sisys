"""领域层 Agent 引擎端口模块

AgentEnginePort Protocol 定义 Agent 编排引擎抽象，支持 LangGraph/AutoGen 等引擎替换

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.domain.value_objects.flow_status import FlowStatus


@runtime_checkable
class AgentEnginePort(Protocol):
    """Agent 引擎端口

    定义 Agent 状态图提交和状态查询的标准接口。
    六边形架构约束：仅使用 Python 标准库类型，不导入 langgraph/langchain。
    """

    async def submit_graph(self, graph_name: str, parameters: dict[str, Any]) -> str:
        """提交 Agent 状态图执行

        Args:
            graph_name: 状态图名称（如 "BasicAgent"）
            parameters: 状态图参数

        Returns:
            graph_run_id: 状态图运行标识符
        """
        ...

    async def get_graph_status(self, graph_run_id: str) -> FlowStatus:
        """查询状态图执行状态

        Args:
            graph_run_id: 状态图运行标识符

        Returns:
            当前状态图执行状态
        """
        ...
