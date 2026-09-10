"""应用层工具链服务实现模块

实现 ToolChainService（应用层服务），委托 ToolChainOrchestrator 执行 + 委托
ToolChainRepository 查询。

设计依据：Story 4.2 AC-6
- 依赖通过端口注入（不导入 infrastructure 具体实现）
- execute_chain 委托 ToolChainOrchestrator
- get_chain_definition / list_chain_definitions 委托 Repository
"""

from __future__ import annotations

import uuid
from typing import Any

from src.application.ports.tool_chain_orchestrator import ToolChainOrchestratorProtocol
from src.domain.entities.tool_chain import ToolChainDag
from src.domain.entities.tool_chain_run import ToolChainRun
from src.domain.exceptions import ToolChainNotFoundError
from src.domain.ports.tool_chain_repository import (
    ToolChainDagQuery,
    ToolChainRepositoryPort,
)
from src.domain.value_objects.tool_execution import ExecutionContext


class ToolChainService:
    """工具链服务（应用层）

    顶层入口：
    - execute_chain → 委托 ToolChainOrchestrator.execute_chain
    - get_chain_definition → 委托 Repository.get_by_id
    - list_chain_definitions → 委托 Repository.list_by_query

    Attributes:
        _repository: 工具链仓储端口
        _orchestrator: 工具链编排器
    """

    def __init__(
        self,
        repository: ToolChainRepositoryPort,
        orchestrator: ToolChainOrchestratorProtocol,
    ) -> None:
        """初始化服务

        Args:
            repository: 工具链仓储端口（领域层注入）
            orchestrator: 工具链编排器协议（应用层）
        """
        self._repository = repository
        self._orchestrator = orchestrator

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
        """
        # 1. 加载工具链定义
        dag = await self.get_chain_definition(chain_id)
        # 2. 委托编排器执行
        return await self._orchestrator.execute_chain(dag, parameters, context)

    async def get_chain_definition(self, chain_id: uuid.UUID) -> ToolChainDag:
        """获取工具链定义（委托 Repository）

        Args:
            chain_id: 工具链定义 ID

        Returns:
            工具链 DAG 聚合根

        Raises:
            ToolChainNotFoundError: chain_id 不存在（EXCEPTION_394，toolchain 子域）
        """
        dag = await self._repository.get_by_id(chain_id)
        if dag is None:
            raise ToolChainNotFoundError(chain_id=str(chain_id))
        return dag

    async def list_chain_definitions(self, query: ToolChainDagQuery) -> list[ToolChainDag]:
        """列出工具链定义（Query Object 模式）

        Args:
            query: 查询条件

        Returns:
            工具链定义列表
        """
        return await self._repository.list_by_query(query)


__all__ = ["ToolChainService"]
