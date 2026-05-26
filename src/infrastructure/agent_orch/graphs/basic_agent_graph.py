"""基础设施层 BasicAgent 状态图构建模块

从 schemas 导入状态定义，从 nodes 导入节点函数，构建 StateGraph
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.infrastructure.agent_orch.nodes.agent_nodes import analyze_node, synthesize_node
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
    graph.add_node("analyze", analyze_node)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("analyze")
    graph.add_edge("analyze", "synthesize")
    graph.add_edge("synthesize", END)

    return graph
