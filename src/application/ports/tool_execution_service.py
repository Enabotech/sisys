"""应用层工具执行服务端口模块

定义 ToolExecutionServicePort（应用层端口契约），
与 ToolRegistryServicePort 职责明确分工：
- ToolRegistryServicePort: 注册 + 元数据查询
- ToolExecutionServicePort: 执行编排 + 结果封装

遵循六边形架构：应用层定义端口，应用层服务实现端口。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.domain.entities.tool import Tool
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
)


@runtime_checkable
class ToolExecutionServicePort(Protocol):
    """工具执行服务端口

    提供工具执行编排与结果封装能力，由应用层服务实现。
    生命周期：SCOPED（每次 bootstrap 创建新实例）

    与 ToolRegistryServicePort 职责分工：
    - ToolRegistryServicePort: register_all / get_tool / get_tools_by_category /
      list_all_tools / tool_count（注册 + 元数据查询）
    - ToolExecutionServicePort: execute / get_tool_metadata / list_tools_metadata
      （执行编排 + 结果封装）
    """

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """执行工具

        Args:
            tool_id: 工具唯一标识
            tool_call: 工具调用值对象（含 arguments + tenant_id）
            context: 执行上下文（tenant_id/user_id/session_id/trace_id/timeout_sec）

        Returns:
            工具执行结果（含 status/output/evidence_package）

        Raises:
            ToolNotFoundError: 工具不存在
            ToolExecutionFailedError: 五阶段任一失败（不可重试）
            ToolExecutionRetryExhaustedError: 重试耗尽
            ToolExecutionTimeoutError: 超过 max_total_duration_sec
        """
        ...

    def get_tool_metadata(self, tool_id: uuid.UUID) -> Tool:
        """获取工具元数据（委托 ToolRegistryService.get_tool）

        Args:
            tool_id: 工具唯一标识

        Returns:
            Tool 实体

        Raises:
            ToolNotFoundError: 工具不存在
        """
        ...

    def list_tools_metadata(self, query: ToolListQuery) -> list[Tool]:
        """列出工具元数据（Query Object 模式）

        Args:
            query: 工具列表查询条件

        Returns:
            符合条件的工具列表
        """
        ...


@dataclass(frozen=True)
class ToolListQuery:
    """工具列表查询值对象（Query Object 模式，CLAUDE.md §4）

    Attributes:
        tenant_id: 多租户隔离（可选）
        category: 按分类过滤（可选）
        status: 按状态过滤（可选）
        offset: 分页偏移（默认 0）
        limit: 分页大小（默认 100）
    """

    tenant_id: uuid.UUID | None = None
    category: str | None = None
    status: str | None = None
    offset: int = 0
    limit: int = 100
