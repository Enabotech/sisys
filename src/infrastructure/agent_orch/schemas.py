"""基础设施层 Agent 编排 Schema 模块

定义 LangGraph 状态图的状态 TypedDict，供 Engine 和 Graph 共享

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import TypedDict


class BasicAgentState(TypedDict, total=False):
    """BasicAgent 状态图状态定义

    MVP 阶段最小状态，验证编排架构而非业务逻辑

    Attributes:
        task_description: 任务描述
        agent_role: Agent 角色
        analysis_result: 分析结果
        synthesis_result: 综合结果
    """

    task_description: str
    agent_role: str
    analysis_result: str
    synthesis_result: str
