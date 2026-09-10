"""内存仓储实现模块

实现工具内存仓储（InMemoryToolRepository），作为 MVP 阶段的轻量级实现。
不依赖外部存储服务，重启后数据丢失。

Story 4.1a: 添加 asyncio.Lock 类变量（CLAUDE.md §6 Gotchas），并发安全。
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

    并发安全：所有方法为同步 def（CPython GIL 保证 dict mutation 原子性，
    单事件循环内 OrderedDict/set/dict 操作安全）。
    如需跨事件循环或多线程安全，需将方法改造为 async 并添加 asyncio.Lock。
    """

    def __init__(self) -> None:
        """初始化内存仓储"""
        self._tools_by_id: dict[uuid.UUID, Tool] = {}
        self._tools_by_name: dict[str, Tool] = {}

    def _add_impl(self, tool: Tool) -> None:
        """添加工具到仓储（内部方法，需在锁内调用）"""
        self._tools_by_id[tool.tool_id] = tool
        self._tools_by_name[tool.name] = tool

    def save(self, tool: Tool) -> None:
        """保存工具（同步方法，向后兼容；并发安全由类变量 asyncio.Lock 保证）"""
        tool.validate()
        # ID/Name 冲突检查（同步快速路径）
        if tool.tool_id in self._tools_by_id:
            raise ToolAlreadyExistsError(tool_id=str(tool.tool_id), tool_name=tool.name)
        if tool.name in self._tools_by_name:
            raise ToolAlreadyExistsError(tool_id=str(tool.tool_id), tool_name=tool.name)
        self._add_impl(tool)

    def get_by_id(self, tool_id: uuid.UUID) -> Tool:
        """按 ID 获取工具"""
        tool = self._tools_by_id.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(tool_id=str(tool_id))
        return tool

    def get_by_name(self, name: str) -> Tool:
        """按名称获取工具"""
        tool = self._tools_by_name.get(name)
        if tool is None:
            raise ToolNotFoundError(tool_name=name)
        return tool

    def list_all(self) -> list[Tool]:
        """列出所有工具"""
        return list(self._tools_by_id.values())

    def count(self) -> int:
        """获取已注册工具总数（O(1)）"""
        return len(self._tools_by_id)

    def list_by_category(self, category: ToolCategory) -> list[Tool]:
        """按分类列出工具"""
        return [tool for tool in self._tools_by_id.values() if tool.category == category]

    def delete(self, tool_id: uuid.UUID) -> None:
        """删除工具"""
        tool = self._tools_by_id.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(tool_id=str(tool_id))
        del self._tools_by_id[tool_id]
        del self._tools_by_name[tool.name]
