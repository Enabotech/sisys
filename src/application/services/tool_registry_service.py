"""应用层工具注册服务实现模块

实现工具注册服务（ToolRegistryService），封装 23 种战略工具的注册逻辑与元数据查询。
从 StrategicToolCatalog 加载工具元数据，通过 ToolRepositoryPort 持久化。
"""

from __future__ import annotations

import logging
import uuid

from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG
from src.domain.entities.tool import Tool, ToolCategory
from src.domain.exceptions import EntityValidationError
from src.domain.exceptions.tool_exceptions import ToolAlreadyExistsError
from src.domain.ports.tool_repository import ToolRepositoryPort

logger = logging.getLogger(__name__)


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
        通过 repository.save() 持久化。重复注册时记录 debug 日志并跳过。
        """
        for tool in TOOL_CATALOG:
            try:
                self._repository.save(tool)
            except ToolAlreadyExistsError as exc:
                logger.debug(
                    "工具已注册，跳过: id=%s name=%s",
                    exc.context.get("tool_id"),
                    exc.context.get("tool_name"),
                )

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
            EntityValidationError: 参数缺失（tool_id 与 tool_name 同时为空）
        """
        if tool_id is not None:
            return self._repository.get_by_id(tool_id)
        if tool_name is not None:
            return self._repository.get_by_name(tool_name)
        raise EntityValidationError(
            message="Either tool_id or tool_name must be provided",
            context={"parameter": "tool_id|tool_name"},
        )

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
            工具总数（委托仓储 O(1) 接口）
        """
        return self._repository.count()

    def update_tool_statistics(
        self,
        tool_id: uuid.UUID,
        success: bool = True,
    ) -> Tool:
        """更新工具可靠性评分和执行计数（Beta 分布衰减加权）

        Story 4.1a AC-5: ToolExecuted 事件订阅者异步更新 Tool statistics。

        算法（业界最佳实践 Beta 分布衰减加权）：
        - reliability_score = old * 0.9 + (1.0 if success else 0.0) * 0.1
        - execution_count += 1
        - 钳位到 [0.0, 1.0] 范围

        实现说明：直接 in-place mutation，不调用 _repository.save()。
        原因：InMemoryToolRepository.save() 拒绝更新已存在 ID；
        InMemory 模式下 mutation 即持久化。
        PostgreSQL 真实实现需要单独的 update_statistics 方法（后续 Story 补充）。

        Args:
            tool_id: 工具唯一标识
            success: 本次执行是否成功

        Returns:
            更新后的 Tool 实体

        Raises:
            ToolNotFoundError: 工具不存在
        """
        tool = self.get_tool(tool_id=tool_id)
        old_score = tool.reliability_score
        outcome = 1.0 if success else 0.0
        new_score = old_score * 0.9 + outcome * 0.1
        # In-place mutation（Tool 是非 frozen dataclass）
        tool.reliability_score = max(0.0, min(1.0, new_score))
        tool.execution_count = tool.execution_count + 1
        return tool
