"""应用层工具执行服务实现模块

实现 ToolExecutionService（应用层服务），封装工具执行编排与结果封装逻辑。
委托元数据查询给 ToolRegistryService（职责分离）。

设计原则：
- 与 ToolRegistryService 明确分工（不重叠职责）
- 通过端口注入依赖，不导入 infrastructure 具体实现
- execute() 使用 ExecutionContext（frozen dataclass）非 context: dict
"""

from __future__ import annotations

import dataclasses
import logging
import uuid

from src.application.ports.tool_execution_service import (
    ToolListQuery,
)
from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.application.ports.tool_version_service import ToolVersionServicePort
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
        tool_version_service: ToolVersionServicePort | None = None,
    ) -> None:
        """初始化工具执行服务

        Args:
            registry: 工具注册服务端口（委托元数据查询）
            engine: 工具执行引擎（执行五阶段工作流）
            tool_version_service: 工具版本服务端口（Story 4-6 可选注入——
                注入后启用版本路由与派生副本；未注入保持 4.1a 原行为）
        """
        self._registry = registry
        self._engine = engine
        self._version_service = tool_version_service

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """执行工具（委托 ToolExecutionEngine 五阶段工作流）

        版本路由（Story 4-6，可选注入生效）：resolve_version 命中灰度时以
        dataclasses.replace 派生执行用 Tool 副本（version/schema 替换）——
        引擎与装饰器链零改动，ToolExecution 聚合快照 tool.version 自动生效。

        Args:
            tool_id: 工具唯一标识
            tool_call: 工具调用值对象（.version 显式指定则跳过流量路由）
            context: 执行上下文（trace_id 作为 route_key）

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

        execution_tool = await self._resolve_execution_tool(tool, tool_call, context)

        logger.info(
            "开始执行工具: tool_name=%s tool_id=%s tenant_id=%s version=%s",
            tool.name,
            tool_id,
            context.tenant_id,
            execution_tool.version,
        )

        # 委托给 ToolExecutionEngine 五阶段工作流
        result: ToolResult = await self._engine.execute(
            tool_id=tool_id,
            tool=execution_tool,
            tool_call=tool_call,
            context=context,
        )
        return result

    async def _resolve_execution_tool(
        self,
        tool: Tool,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> Tool:
        """版本路由与派生副本（Story 4-6 最小侵入设计）。

        - 未注入 version service → 原样返回 registry Tool（4.1a 行为）
        - ToolCall.version 显式 → 精确版本（跳过流量路由）
        - 否则按 route_key（context.trace_id）规范散列路由
        - 命中非当前版本 → dataclasses.replace 派生副本（仅执行视图，
          引擎/装饰器零改动）

        Args:
            tool: registry 原始 Tool
            tool_call: 调用值对象（.version 显式版本）
            context: 执行上下文

        Returns:
            执行用 Tool（原始或派生副本）
        """
        if self._version_service is None:
            return tool
        version_tv = await self._version_service.resolve_version(
            tool.tool_id,
            requested_version=tool_call.version,
            route_key=context.trace_id,
        )
        if (
            version_tv.version == tool.version
            and version_tv.input_schema == tool.input_schema
            and version_tv.output_schema == tool.output_schema
        ):
            return tool
        return dataclasses.replace(
            tool,
            version=version_tv.version,
            input_schema=dict(version_tv.input_schema),
            output_schema=dict(version_tv.output_schema),
        )

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
