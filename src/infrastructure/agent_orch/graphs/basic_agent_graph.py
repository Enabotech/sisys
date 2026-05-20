"""基础设施层 BasicAgent 状态图构建模块

从 schemas 导入状态定义，从 nodes 导入节点函数，构建 StateGraph

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.infrastructure.agent_orch.nodes.agent_nodes import analysis_node, synthesis_node
from src.infrastructure.agent_orch.schemas import BasicAgentState

__all__ = ["BasicAgentState", "build_basic_agent_graph"]


def build_basic_agent_graph(graph: StateGraph) -> StateGraph:
    """构建 BasicAgent 状态图

    MVP 阶段最小图：analysis → synthesis → END

    Args:
        graph: 空的 StateGraph 实例

    Returns:
        配置好节点的 StateGraph
    """
    graph.add_node("analysis", analysis_node)
    graph.add_node("synthesis", synthesis_node)

    graph.set_entry_point("analysis")
    graph.add_edge("analysis", "synthesis")
    graph.add_edge("synthesis", END)

    return graph
