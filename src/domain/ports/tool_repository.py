"""领域层工具仓储端口模块

定义工具仓储端口（ToolRepositoryPort），提供工具的增删查存能力。
遵循六边形架构原则：领域层定义端口，基础设施层实现端口。
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.entities.tool import Tool, ToolCategory


@runtime_checkable
class ToolRepositoryPort(Protocol):
    """工具仓储端口

    提供工具的增删查存能力，由基础设施层实现。
    生命周期：SCOPED（每个请求独立实例）
    """

    def save(self, tool: Tool) -> None:
        """保存工具

        Args:
            tool: 工具实体

        Raises:
            EntityValidationError: 工具实体违反不变量约束
            ToolAlreadyExistsError: 工具已存在（同 ID 或同名）
        """
        ...

    def get_by_id(self, tool_id: uuid.UUID) -> Tool:
        """按 ID 获取工具

        Args:
            tool_id: 工具唯一标识

        Returns:
            工具实体

        Raises:
            ToolNotFoundError: 工具不存在
        """
        ...

    def get_by_name(self, name: str) -> Tool:
        """按名称获取工具

        Args:
            name: 工具名称

        Returns:
            工具实体

        Raises:
            ToolNotFoundError: 工具不存在
        """
        ...

    def list_all(self) -> list[Tool]:
        """列出所有工具

        Returns:
            工具列表
        """
        ...

    def count(self) -> int:
        """获取已注册工具总数

        Returns:
            工具总数（O(1) 操作）
        """
        ...

    def list_by_category(self, category: ToolCategory) -> list[Tool]:
        """按分类列出工具

        Args:
            category: 工具分类

        Returns:
            该分类下的工具列表
        """
        ...

    def delete(self, tool_id: uuid.UUID) -> None:
        """删除工具

        Args:
            tool_id: 工具唯一标识

        Raises:
            ToolNotFoundError: 工具不存在
        """
        ...
