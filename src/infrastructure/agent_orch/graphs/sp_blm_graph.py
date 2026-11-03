"""基础设施层 SpBlmGraph——BLM 前两阶段图工厂（Story 6-1）

BLM（Business Leadership Model）前两阶段 LangGraph 状态图：阶段 1 业绩
差距分析 → 市场洞察六子步骤（or.md 钦定序）→ 综合洞察。

图形态钦定（R3-1）：8 节点 + 7 条直连边 + END——降级在 BlmPlanningService
方法内全量捕获（AC-6①），节点永不因业务失败抛错，顺序段无条件分支点，
纯顺序段全部直连（SingleAgentWorkflow 先例：条件边仅用于真分支点）。

落位钦定（OD-4/architecture L3244）：本文件即 FR-SP-05 钦定落位
sp_blm_graph.py——Epic 10 Story 10-1 在本文件扩展阶段 3-6 节点
（战略意图/创新焦点/业务设计/执行设计），避免双文件分裂。

compile() 不加 checkpointer（R1-DF5 语义分立裁定：BLM 阶段产物快照是
应用层数据面，图执行态 checkpointer 归 6.3 执行中断恢复面）。
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from src.application.ports.blm_planning import BlmPlanningServicePort
from src.domain.value_objects.blm_phases import MarketInsightStep
from src.infrastructure.agent_orch.schemas import SpBlmState


def build_sp_blm_graph(service: BlmPlanningServicePort) -> Any:
    """构造 BLM 前两阶段图（已编译——引擎 _build_graph 分派调用）。

    Args:
        service: BLM 规划服务端口（图节点的阶段方法执行方）。

    Returns:
        已编译 CompiledGraph（无 checkpointer——对齐 SingleAgentWorkflow 先例）。
    """

    async def _performance_gap_node(state: SpBlmState) -> dict[str, Any]:
        """阶段 1 节点：业绩差距分析（适配器——服务方法 → dict 部分更新）。"""
        context = state["context"]
        result = await service.run_performance_gap_analysis(context)
        plan_id = state["plan_id"]
        return {
            "gap_artifacts": result,
            "degraded_steps": service.project_degraded_steps(plan_id),
            "timeline": service.project_timeline(plan_id),
            "chain_records": service.project_chain_records(plan_id),
        }

    def _make_insight_node(step: MarketInsightStep) -> Any:
        """构造子步骤节点闭包（六步同构——prior_outputs 从 state 组装）。"""

        async def _insight_node(state: SpBlmState) -> dict[str, Any]:
            context = state["context"]
            prior_outputs = {
                "performance_gap": state.get("gap_artifacts"),
                "insight_steps": tuple(state.get("insight_step_results", ())),
            }
            result = await service.run_insight_step(step, context, prior_outputs)
            # 服务已聚合 degraded/timeline——适配器直写全量勿二次合并（5-3 execute 先例）
            return {
                "insight_step_results": [*state.get("insight_step_results", []), result],
                "degraded_steps": service.project_degraded_steps(state["plan_id"]),
                "timeline": service.project_timeline(state["plan_id"]),
                "chain_records": service.project_chain_records(state["plan_id"]),
            }

        return _insight_node

    async def _synthesize_node(state: SpBlmState) -> dict[str, Any]:
        """综合节点：六子步骤产物聚合（含阶段 1 产物——degraded_inputs 跨阶段提取）。"""
        context = state["context"]
        step_outputs = {
            "insight_steps": tuple(state.get("insight_step_results", ())),
            "performance_gap": state.get("gap_artifacts"),
        }
        synthesis = await service.synthesize_insights(step_outputs, context)
        return {
            "synthesis": synthesis,
            "degraded_steps": service.project_degraded_steps(state["plan_id"]),
            "timeline": service.project_timeline(state["plan_id"]),
            "chain_records": service.project_chain_records(state["plan_id"]),
        }

    graph = StateGraph(SpBlmState)
    graph.add_node("performance_gap", _performance_gap_node)
    graph.add_node("insight_trend", _make_insight_node(MarketInsightStep.TREND))
    graph.add_node("insight_market_customer", _make_insight_node(MarketInsightStep.MARKET_CUSTOMER))
    graph.add_node("insight_competition", _make_insight_node(MarketInsightStep.COMPETITION))
    graph.add_node("insight_self", _make_insight_node(MarketInsightStep.SELF))
    graph.add_node("insight_opportunity", _make_insight_node(MarketInsightStep.OPPORTUNITY))
    graph.add_node("insight_opportunity_gap", _make_insight_node(MarketInsightStep.OPPORTUNITY_GAP))
    graph.add_node("synthesize", _synthesize_node)

    graph.set_entry_point("performance_gap")
    graph.add_edge("performance_gap", "insight_trend")
    graph.add_edge("insight_trend", "insight_market_customer")
    graph.add_edge("insight_market_customer", "insight_competition")
    graph.add_edge("insight_competition", "insight_self")
    graph.add_edge("insight_self", "insight_opportunity")
    graph.add_edge("insight_opportunity", "insight_opportunity_gap")
    graph.add_edge("insight_opportunity_gap", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


__all__ = ["build_sp_blm_graph"]
