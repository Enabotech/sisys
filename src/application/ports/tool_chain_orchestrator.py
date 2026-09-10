"""应用层工具链编排器端口模块

定义 ToolChainOrchestratorProtocol Protocol（应用层端口契约）。
本协议由 ToolChainOrchestrator 实现，便于通过 composition_root 注入。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.domain.entities.tool_chain import ToolChainDag
from src.domain.entities.tool_chain_run import ToolChainRun
from src.domain.value_objects.tool_execution import ExecutionContext


@runtime_checkable
class ToolChainOrchestratorProtocol(Protocol):
    """工具链编排器端口协议（应用层）

    提供 DAG 拓扑排序 + 并行调度 + 失败策略实施，由 ToolChainOrchestrator 实现。
    生命周期：SCOPED（每次 bootstrap 创建新实例）
    """

    async def execute_chain(
        self,
        dag: ToolChainDag,
        parameters: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolChainRun:
        """执行工具链 DAG

        Args:
            dag: 工具链 DAG 聚合根
            parameters: 调用方参数
            context: 执行上下文

        Returns:
            ToolChainRun 运行时实例（终态）

        Raises:
            ToolChainCycleDetectedError: DAG 含环
            ToolChainDuplicateNodeError: DAG 节点重复
            ToolChainNodeNotFoundError: DAG 边引用不存在的节点
            ToolChainExecutionFailedError: FAIL_FAST 触发
        """
        ...


__all__ = ["ToolChainOrchestratorProtocol"]
