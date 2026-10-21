"""基础设施层 SingleAgentWorkflow 六阶段图工厂（Story 5-3 — 单 Agent 标准工作流）

六节点 LangGraph StateGraph + 条件边（DC-1 节点适配器模式）：
- 六节点：perceive → plan → execute → verify →（条件边）→ reflect / package_evidence
- verify 后按 verification_passed 分流（pass→package / fail→reflect）
- reflect 后按 `retry_count <= MAX_RETRIES and revised` 分流（可修正且未耗尽
  →plan 重试 / 耗尽或不可修正→package_evidence(failed)——含第四路径
  revised=False 早退）
- 节点适配器：调服务阶段方法 → 显式返回 dict 部分更新合并 state（LangGraph
  节点契约——直接返回 dataclass 实测 InvalidUpdateError；谓词键由适配器写入，
  对照表见 schemas.WorkflowAgentState docstring）
- 阶段逻辑/prompt/LLM 全在应用层服务（AgentWorkflowServicePort——
  infrastructure→application 端口方向合法）；图工厂只做编排

分支键 package 经 path_map 映射到节点 package_evidence（命名禁混用——
executed_phases 末元素钉死 "package" 对齐 444 phase 枚举，R2-F9）。
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from src.application.ports.agent_workflow import AgentWorkflowServicePort
from src.infrastructure.agent_orch.schemas import WorkflowAgentState

#: 重试上限（AC-1 口径锚：reflect 递增后 `<=` 谓词判定——plan 总执行 ≤3
#: 即初始 1 + 重试 2；模块常量形态，R3-F11）
MAX_RETRIES = 2


def build_single_agent_workflow_graph(service: AgentWorkflowServicePort) -> Any:
    """六阶段图工厂（节点适配器——阶段逻辑在应用层服务，适配器负责结果→state 合并）。

    Args:
        service: 六阶段工作流服务端口（图工厂构造注入——引擎按图名分派时传入）

    Returns:
        编译后的 CompiledStateGraph（ainvoke 阻塞执行返回终态 state）
    """

    async def _perceive_node(state: WorkflowAgentState) -> dict[str, Any]:
        result = await service.perceive(dict(state))
        return {
            "perception": result,
            "executed_phases": [*state.get("executed_phases", []), "perceive"],
        }

    async def _plan_node(state: WorkflowAgentState) -> dict[str, Any]:
        result = await service.plan(dict(state))
        return {
            "plan": result,
            "executed_phases": [*state.get("executed_phases", []), "plan"],
        }

    async def _execute_node(state: WorkflowAgentState) -> dict[str, Any]:
        # 服务已聚合历史（读旧 execution 追加合并）——适配器直写全量，勿二次合并（R3-F10）
        result = await service.execute(dict(state))
        return {
            "execution": result,
            "executed_phases": [*state.get("executed_phases", []), "execute"],
        }

    async def _verify_node(state: WorkflowAgentState) -> dict[str, Any]:
        result = await service.verify(dict(state))
        return {
            "verification": result,
            "verification_passed": result.passed,  # 谓词键写入者：verify 适配器
            "confidence": result.confidence,  # 事件真实化数据源
            "executed_phases": [*state.get("executed_phases", []), "verify"],
        }

    async def _reflect_node(state: WorkflowAgentState) -> dict[str, Any]:
        result = await service.reflect(dict(state))
        return {
            "reflection": result,
            "revised": result.revised,  # 谓词键写入者：reflect 适配器
            "retry_count": state.get("retry_count", 0) + 1,  # reflect 执行=消耗一次重试
            "executed_phases": [*state.get("executed_phases", []), "reflect"],
        }

    async def _package_node(state: WorkflowAgentState) -> dict[str, Any]:
        outcome = await service.package_evidence(dict(state))
        # PackageOutcome 拆写两 state 键（evidence + chain——R2-F1）
        return {
            "evidence": outcome.evidence,
            "chain": outcome.chain,
            "executed_phases": [*state.get("executed_phases", []), "package"],
        }

    def _route_after_verify(state: dict[str, Any]) -> str:
        return "package" if state.get("verification_passed") else "reflect"

    def _route_after_reflect(state: dict[str, Any]) -> str:
        # reflect 已递增 retry_count 后判定（`<=` 谓词——plan 总执行 ≤3）
        return "plan" if state.get("retry_count", 0) <= MAX_RETRIES and state.get("revised") else "package"

    graph = StateGraph(WorkflowAgentState)
    graph.add_node("perceive", _perceive_node)
    graph.add_node("plan", _plan_node)
    graph.add_node("execute", _execute_node)
    graph.add_node("verify", _verify_node)
    graph.add_node("reflect", _reflect_node)
    graph.add_node("package_evidence", _package_node)  # 节点名 package_evidence（分支键 package 经 path_map 映射）
    graph.set_entry_point("perceive")
    graph.add_edge("perceive", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "verify")
    graph.add_conditional_edges(
        "verify",
        _route_after_verify,
        {"package": "package_evidence", "reflect": "reflect"},
    )
    graph.add_conditional_edges(
        "reflect",
        _route_after_reflect,
        {"plan": "plan", "package": "package_evidence"},
    )
    graph.add_edge("package_evidence", END)
    return graph.compile()


__all__ = ["MAX_RETRIES", "build_single_agent_workflow_graph"]
