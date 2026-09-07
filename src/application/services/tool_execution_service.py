"""应用层工具执行服务实现模块

实现 ToolExecutionService（应用层服务），封装工具执行编排与结果封装逻辑。
委托元数据查询给 ToolRegistryService（职责分离）。

设计原则：
- 与 ToolRegistryService 明确分工（不重叠职责）
- 通过端口注入依赖，不导入 infrastructure 具体实现
- execute() 使用 ExecutionContext（frozen dataclass）非 context: dict
"""

from __future__ import annotations

import logging
import uuid

from src.application.ports.tool_execution_service import (
    ToolListQuery,
)
from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.domain.entities.tool import Tool
from src.domain.exceptions.tool_exceptions import ToolNotFoundError
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


class ToolExecutionService:
    """工具执行服务

    实现 ToolExecutionServicePort 接口，封装工具执行编排与结果封装。
    生命周期：SCOPED（每次 bootstrap 创建新实例）

    与 ToolRegistryService 职责分工：
    - ToolRegistryService：注册 + 元数据查询（register_all / get_tool / list_all_tools）
    - ToolExecutionService：执行编排 + 结果封装（execute / get_tool_metadata / list_tools_metadata）
    """

    def __init__(
        self,
        registry: ToolRegistryServicePort,
        engine: ToolExecutionEngine,
    ) -> None:
        """初始化工具执行服务

        Args:
            registry: 工具注册服务端口（委托元数据查询）
            engine: 工具执行引擎（执行五阶段工作流）
        """
        self._registry = registry
        self._engine = engine

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """执行工具（委托 ToolExecutionEngine 五阶段工作流）

        Args:
            tool_id: 工具唯一标识
            tool_call: 工具调用值对象
            context: 执行上下文

        Returns:
            ToolResult 执行结果
        """
        # 先校验 tool 是否存在（委托元数据查询给 Registry）
        try:
            tool = self._registry.get_tool(tool_id=tool_id)
        except ToolNotFoundError:
            logger.warning(
                "工具不存在，无法执行: tool_id=%s tenant_id=%s",
                tool_id,
                context.tenant_id,
            )
            raise

        logger.info(
            "开始执行工具: tool_name=%s tool_id=%s tenant_id=%s",
            tool.name,
            tool_id,
            context.tenant_id,
        )

        # 委托给 ToolExecutionEngine 五阶段工作流
        result: ToolResult = await self._engine.execute(
            tool_id=tool_id,
            tool=tool,
            tool_call=tool_call,
            context=context,
        )
        return result

    def get_tool_metadata(self, tool_id: uuid.UUID) -> Tool:
        """获取工具元数据（委托 ToolRegistryService.get_tool）

        Args:
            tool_id: 工具唯一标识

        Returns:
            Tool 实体

        Raises:
            ToolNotFoundError: 工具不存在
        """
        return self._registry.get_tool(tool_id=tool_id)

    def list_tools_metadata(self, query: ToolListQuery) -> list[Tool]:
        """列出工具元数据（Query Object 模式）

        Args:
            query: 工具列表查询条件

        Returns:
            符合条件的工具列表
        """
        tools = self._registry.list_all_tools()
        if query.category is not None:
            tools = [t for t in tools if t.category.value == query.category]
        if query.status is not None:
            tools = [t for t in tools if t.status.value == query.status]
        return tools[query.offset : query.offset + query.limit]
