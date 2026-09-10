"""应用层工具链服务端口模块

定义 ToolChainServicePort Protocol（应用层端口契约），
提供工具链编排的顶层入口（execute_chain / get_chain_definition / list_chain_definitions）。

设计依据：Story 4.2 AC-6
- 应用层服务端口，组合 ToolExecutionServicePort + EventBusPort + ToolChainRepositoryPort
- 与 ToolChainOrchestratorProtocol 职责分工：Orchestrator 负责调度，Service 负责入口编排
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from src.domain.entities.tool_chain import ToolChainDag
from src.domain.entities.tool_chain_run import ToolChainRun
from src.domain.ports.tool_chain_repository import ToolChainDagQuery
from src.domain.value_objects.tool_execution import ExecutionContext


@runtime_checkable
class ToolChainServicePort(Protocol):
    """工具链服务端口协议（应用层）

    提供工具链编排的顶层入口，由应用层服务实现。
    生命周期：SCOPED（每次 bootstrap 创建新实例）
    """

    async def execute_chain(
        self,
        chain_id: uuid.UUID,
        parameters: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolChainRun:
        """执行工具链（顶层入口）

        Args:
            chain_id: 工具链定义 ID
            parameters: 工具链执行参数
            context: 执行上下文

        Returns:
            ToolChainRun: 运行时实例

        Raises:
            ToolNotFoundError: chain_id 不存在
            ToolChainCycleDetectedError: DAG 包含循环依赖
            ToolChainDuplicateNodeError: DAG 节点重复
            ToolChainNodeNotFoundError: DAG 边引用不存在的节点
            ToolChainExecutionFailedError: FAIL_FAST 触发
        """
        ...

    async def get_chain_definition(self, chain_id: uuid.UUID) -> ToolChainDag:
        """获取工具链定义（委托 Repository）

        Args:
            chain_id: 工具链定义 ID

        Returns:
            工具链 DAG 聚合根

        Raises:
            ToolNotFoundError: chain_id 不存在
        """
        ...

    async def list_chain_definitions(self, query: ToolChainDagQuery) -> list[ToolChainDag]:
        """列出工具链定义（Query Object 模式）

        Args:
            query: 查询条件

        Returns:
            工具链定义列表
        """
        ...


__all__ = ["ToolChainServicePort"]
