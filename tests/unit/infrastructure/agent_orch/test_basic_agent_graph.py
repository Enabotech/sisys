"""BasicAgentGraph 单元测试

验证图定义、节点执行顺序、状态更新

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from src.infrastructure.agent_orch.graphs.basic_agent_graph import (
    BasicAgentState,
    build_basic_agent_graph,
)
from src.infrastructure.agent_orch.nodes.agent_nodes import analysis_node, synthesis_node


class TestBasicAgentState:
    """BasicAgentState TypedDict 验证"""

    def test_state_is_typed_dict(self) -> None:
        """BasicAgentState 应为 TypedDict"""
        from typing import get_type_hints

        hints = get_type_hints(BasicAgentState)
        assert "task_description" in hints
        assert "agent_role" in hints
        assert "analysis_result" in hints
        assert "synthesis_result" in hints

    def test_state_has_four_fields(self) -> None:
        """BasicAgentState 应有 4 个字段"""
        from typing import get_type_hints

        hints = get_type_hints(BasicAgentState)
        assert len(hints) == 4


class TestAnalysisNode:
    """analysis_node 测试"""

    def test_analysis_node_returns_dict(self) -> None:
        """analysis_node 应返回包含 analysis_result 的字典"""
        state: BasicAgentState = {"task_description": "分析市场趋势", "agent_role": "analyst"}
        result = analysis_node(state)
        assert "analysis_result" in result
        assert "分析完成" in result["analysis_result"]

    def test_analysis_node_uses_task_description(self) -> None:
        """analysis_node 应使用 task_description"""
        state: BasicAgentState = {"task_description": "特定任务", "agent_role": "analyst"}
        result = analysis_node(state)
        assert "特定任务" in result["analysis_result"]


class TestSynthesisNode:
    """synthesis_node 测试"""

    def test_synthesis_node_returns_dict(self) -> None:
        """synthesis_node 应返回包含 synthesis_result 的字典"""
        state: BasicAgentState = {
            "task_description": "test",
            "agent_role": "analyst",
            "analysis_result": "分析完成",
        }
        result = synthesis_node(state)
        assert "synthesis_result" in result
        assert "综合完成" in result["synthesis_result"]

    def test_synthesis_node_uses_analysis_result(self) -> None:
        """synthesis_node 应使用 analysis_result"""
        state: BasicAgentState = {
            "task_description": "test",
            "agent_role": "analyst",
            "analysis_result": "自定义分析",
        }
        result = synthesis_node(state)
        assert "自定义分析" in result["synthesis_result"]


class TestBuildBasicAgentGraph:
    """build_basic_agent_graph 测试"""

    def test_build_graph_returns_state_graph(self) -> None:
        """build_basic_agent_graph 应返回 StateGraph"""
        from langgraph.graph import StateGraph

        graph = StateGraph(BasicAgentState)
        result = build_basic_agent_graph(graph)
        assert result is graph

    def test_graph_execution_order(self) -> None:
        """图执行顺序应为 analysis → synthesis → END"""
        compiled = build_basic_agent_graph(
            __import__("langgraph.graph", fromlist=["StateGraph"]).StateGraph(BasicAgentState)
        ).compile()

        result = compiled.invoke(
            {"task_description": "测试", "agent_role": "analyst"},
        )
        assert result.get("analysis_result") is not None
        assert result.get("synthesis_result") is not None
