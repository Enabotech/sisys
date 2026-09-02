"""应用层工具注册服务端口模块

定义工具注册服务端口（ToolRegistryServicePort），提供工具注册、查询、分类过滤能力。
遵循六边形架构原则：应用层定义端口，应用层服务实现端口。
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.entities.tool import Tool, ToolCategory


@runtime_checkable
class ToolRegistryServicePort(Protocol):
    """工具注册服务端口

    提供工具注册、查询、分类过滤能力，由应用层服务实现。
    生命周期：SCOPED（每次 bootstrap 创建新实例）
    """

    def register_all(self) -> None:
        """注册所有战略工具（从 StrategicToolCatalog 加载）"""
        ...

    def get_tool(
        self,
        tool_id: uuid.UUID | None = None,
        tool_name: str | None = None,
    ) -> Tool:
        """获取单个工具

        Args:
            tool_id: 工具唯一标识（与 tool_name 二选一）
            tool_name: 工具名称（与 tool_id 二选一）

        Returns:
            工具实体

        Raises:
            ToolNotFoundError: 工具不存在
        """
        ...

    def get_tools_by_category(
        self,
        category: ToolCategory,
    ) -> list[Tool]:
        """按分类获取工具列表

        Args:
            category: 工具分类

        Returns:
            该分类下的工具列表
        """
        ...

    def list_all_tools(self) -> list[Tool]:
        """列出所有已注册工具

        Returns:
            工具列表
        """
        ...

    def tool_count(self) -> int:
        """获取已注册工具总数

        Returns:
            工具总数
        """
        ...
