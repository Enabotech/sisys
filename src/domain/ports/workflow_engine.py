"""领域层工作流引擎端口模块

WorkflowEnginePort Protocol 定义工作流执行抽象，支持 Prefect/LangGraph 等引擎替换

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.domain.value_objects.flow_status import FlowStatus


@runtime_checkable
class WorkflowEnginePort(Protocol):
    """工作流引擎端口

    定义工作流提交和状态查询的标准接口。
    六边形架构约束：仅使用 Python 标准库类型，不导入 prefect/langgraph。
    """

    async def submit_flow(self, flow_name: str, parameters: dict[str, Any]) -> str:
        """提交工作流执行

        Args:
            flow_name: 工作流名称（如 "DocumentProcessing"）
            parameters: 工作流参数

        Returns:
            flow_run_id: 工作流运行标识符
        """
        ...

    async def get_flow_status(self, flow_run_id: str) -> FlowStatus:
        """查询工作流状态

        Args:
            flow_run_id: 工作流运行标识符

        Returns:
            当前工作流状态
        """
        ...
