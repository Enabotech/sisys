"""基础设施层记忆文件存储模块

实现 MemoryFilePort 接口，组合 FileMemoryAdapter 并添加 MEMORY.md 索引管理语义
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from src.application.ports.memory_file_port import MemoryFilePort

if TYPE_CHECKING:
    from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter


class MemoryFileStorage(MemoryFilePort):
    """记忆文件存储 — 实现 MemoryFilePort

    组合 FileMemoryAdapter，添加 MEMORY.md 索引管理语义
    """

    def __init__(self, adapter: FileMemoryAdapter):
        """初始化 MemoryFileStorage

        Args:
            adapter: FileMemoryAdapter 实例（Rule 3）
        """
        self._adapter = adapter

    # -- L0StoragePort methods (delegate to adapter) --

    async def write(self, memory_id: str, memory_type: str, content: str) -> bool:
        """写入记忆文件

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            content: 记忆内容

        Returns:
            写入成功返回 True
        """
        return await self._adapter.write(memory_id, memory_type, content)

    async def read(self, memory_id: str, memory_type: str) -> str:
        """读取记忆文件

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            记忆内容

        Raises:
            FileNotFoundError: 文件不存在时抛出
        """
        return await self._adapter.read(memory_id, memory_type)

    async def delete(self, memory_id: str, memory_type: str) -> bool:
        """删除记忆文件

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            删除成功返回 True，文件不存在返回 False
        """
        return await self._adapter.delete(memory_id, memory_type)

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        """检查记忆文件是否存在

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            存在返回 True
        """
        return await self._adapter.exists(memory_id, memory_type)

    async def list_memories(self, memory_type: str) -> list[str]:
        """列出指定类型的所有记忆 ID

        Args:
            memory_type: 记忆类型

        Returns:
            记忆 ID 列表
        """
        return await self._adapter.list_memories(memory_type)

    # -- MemoryFilePort specific methods --

    async def update_index(self, entry: dict) -> None:
        """更新 MEMORY.md 索引，添加指定条目

        Args:
            entry: 索引条目，包含 name, type, memory_id, description
        """
        await asyncio.to_thread(self._adapter.update_index, [entry])

    async def remove_from_index(self, memory_id: str) -> None:
        """从 MEMORY.md 索引移除指定条目

        Args:
            memory_id: 要移除的记忆 ID
        """
        entries = await asyncio.to_thread(self._adapter.read_index)
        filtered = [e for e in entries if e.get("memory_id") != memory_id]
        await asyncio.to_thread(self._adapter.update_index, filtered)

    async def search_index(self, query: str) -> list[dict]:
        """搜索 MEMORY.md 索引，按名称和描述模糊匹配

        Args:
            query: 搜索关键词

        Returns:
            匹配的索引条目列表
        """
        entries = await asyncio.to_thread(self._adapter.read_index)
        query_lower = query.lower()
        return [
            e for e in entries if query_lower in e.get("name", "").lower() or query_lower in e.get("description", "").lower()
        ]
