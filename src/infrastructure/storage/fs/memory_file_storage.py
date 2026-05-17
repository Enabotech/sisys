"""MemoryFileStorage — MemoryFilePort 实现（Rule 4）

组合注入 FileMemoryAdapter（Rule 3），添加记忆索引管理语义
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
        """写入记忆文件"""
        return await self._adapter.write(memory_id, memory_type, content)

    async def read(self, memory_id: str, memory_type: str) -> str:
        """读取记忆文件"""
        return await self._adapter.read(memory_id, memory_type)

    async def delete(self, memory_id: str, memory_type: str) -> bool:
        """删除记忆文件"""
        return await self._adapter.delete(memory_id, memory_type)

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        """检查记忆文件是否存在"""
        return await self._adapter.exists(memory_id, memory_type)

    async def list_memories(self, memory_type: str) -> list[str]:
        """列出指定类型的记忆"""
        return await self._adapter.list_memories(memory_type)

    # -- MemoryFilePort specific methods --

    async def update_index(self, entry: dict) -> None:
        """更新 MEMORY.md 索引（添加条目）"""
        await asyncio.to_thread(self._adapter.update_index, [entry])

    async def remove_from_index(self, memory_id: str) -> None:
        """从 MEMORY.md 索引移除条目"""
        entries = await asyncio.to_thread(self._adapter.read_index)
        filtered = [e for e in entries if e.get("memory_id") != memory_id]
        await asyncio.to_thread(self._adapter.update_index, filtered)

    async def search_index(self, query: str) -> list[dict]:
        """搜索 MEMORY.md 索引"""
        entries = await asyncio.to_thread(self._adapter.read_index)
        query_lower = query.lower()
        return [
            e for e in entries if query_lower in e.get("name", "").lower() or query_lower in e.get("description", "").lower()
        ]
