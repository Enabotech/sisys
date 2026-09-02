"""内存仓储实现模块

实现工具内存仓储（InMemoryToolRepository），作为 MVP 阶段的轻量级实现。
不依赖外部存储服务，重启后数据丢失。
"""

from __future__ import annotations

import uuid

from src.domain.entities.tool import Tool, ToolCategory
from src.domain.exceptions.tool_exceptions import (
    ToolAlreadyExistsError,
    ToolNotFoundError,
)


class InMemoryToolRepository:
    """内存工具仓储

    实现 ToolRepositoryPort 接口，使用内存字典存储工具数据。
    生命周期：SCOPED（每个请求独立实例）
    """

    def __init__(self) -> None:
        """初始化内存仓储"""
        self._tools_by_id: dict[uuid.UUID, Tool] = {}
        self._tools_by_name: dict[str, Tool] = {}

    def save(self, tool: Tool) -> None:
        """保存工具

        仓储层二次守卫：Tool 实体的 __post_init__ 已保证构造期合法，
        此处 validate() 用于防御构造后被外部 mutation 的脏数据
        （Tool 是非 frozen dataclass，需保留运行时校验边界）。

        Args:
            tool: 工具实体

        Raises:
            EntityValidationError: 工具实体违反不变量约束
            ToolAlreadyExistsError: 工具已存在（同 ID 或同名）
        """
        # 不变量校验前置：先验数据合法性，再验重复，避免"非法且重名"被误判为冲突
        tool.validate()
        # 检查 ID 冲突
        if tool.tool_id in self._tools_by_id:
            raise ToolAlreadyExistsError(
                tool_id=str(tool.tool_id),
                tool_name=tool.name,
            )
        # 检查名称冲突
        if tool.name in self._tools_by_name:
            raise ToolAlreadyExistsError(
                tool_id=str(tool.tool_id),
                tool_name=tool.name,
            )
        self._tools_by_id[tool.tool_id] = tool
        self._tools_by_name[tool.name] = tool

    def get_by_id(self, tool_id: uuid.UUID) -> Tool:
        """按 ID 获取工具

        Args:
            tool_id: 工具唯一标识

        Returns:
            工具实体

        Raises:
            ToolNotFoundError: 工具不存在
        """
        tool = self._tools_by_id.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(tool_id=str(tool_id))
        return tool

    def get_by_name(self, name: str) -> Tool:
        """按名称获取工具

        Args:
            name: 工具名称

        Returns:
            工具实体

        Raises:
            ToolNotFoundError: 工具不存在
        """
        tool = self._tools_by_name.get(name)
        if tool is None:
            raise ToolNotFoundError(tool_name=name)
        return tool

    def list_all(self) -> list[Tool]:
        """列出所有工具

        Returns:
            工具列表
        """
        return list(self._tools_by_id.values())

    def count(self) -> int:
        """获取已注册工具总数（O(1)）

        Returns:
            工具总数
        """
        return len(self._tools_by_id)

    def list_by_category(self, category: ToolCategory) -> list[Tool]:
        """按分类列出工具

        Args:
            category: 工具分类

        Returns:
            该分类下的工具列表
        """
        return [tool for tool in self._tools_by_id.values() if tool.category == category]

    def delete(self, tool_id: uuid.UUID) -> None:
        """删除工具

        Args:
            tool_id: 工具唯一标识

        Raises:
            ToolNotFoundError: 工具不存在
        """
        tool = self._tools_by_id.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(tool_id=str(tool_id))
        del self._tools_by_id[tool_id]
        del self._tools_by_name[tool.name]
