"""应用层工具注册服务实现模块

实现工具注册服务（ToolRegistryService），封装 23 种战略工具的注册逻辑与元数据查询。
从 StrategicToolCatalog 加载工具元数据，通过 ToolRepositoryPort 持久化。
"""

from __future__ import annotations

import uuid

from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG
from src.domain.entities.tool import Tool, ToolCategory
from src.domain.exceptions import ToolNotFoundError
from src.domain.exceptions.tool_exceptions import ToolAlreadyExistsError
from src.domain.ports.tool_repository import ToolRepositoryPort


class ToolRegistryService:
    """工具注册服务

    实现 ToolRegistryServicePort 接口，封装工具注册与查询逻辑。
    生命周期：SCOPED（每次 bootstrap 创建新实例）
    """

    def __init__(self, repository: ToolRepositoryPort) -> None:
        """初始化工具注册服务

        Args:
            repository: 工具仓储端口
        """
        self._repository = repository

    def register_all(self) -> None:
        """注册所有战略工具（从 StrategicToolCatalog 加载）

        每次调用会从 TOOL_CATALOG 常量加载 23 种工具元数据，
        通过 repository.save() 持久化。
        """
        for tool in TOOL_CATALOG:
            try:
                self._repository.save(tool)
            except ToolAlreadyExistsError:
                # 已存在则跳过（幂等性）
                pass

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
        if tool_id is not None:
            return self._repository.get_by_id(tool_id)
        if tool_name is not None:
            return self._repository.get_by_name(tool_name)
        raise ToolNotFoundError(message="Either tool_id or tool_name must be provided")

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
        return self._repository.list_by_category(category)

    def list_all_tools(self) -> list[Tool]:
        """列出所有已注册工具

        Returns:
            工具列表
        """
        return self._repository.list_all()

    def tool_count(self) -> int:
        """获取已注册工具总数

        Returns:
            工具总数
        """
        return len(self._repository.list_all())
