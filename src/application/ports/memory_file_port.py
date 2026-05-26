"""应用层记忆文件端口模块

继承 L0StoragePort，添加 MEMORY.md 索引管理语义
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l0_storage import L0StoragePort


@runtime_checkable
class MemoryFilePort(L0StoragePort, Protocol):
    """记忆文件端口 — 继承L0StoragePort，添加记忆管理语义

    继承所有L0方法，额外提供：
    - MEMORY.md索引管理
    - 按类型搜索记忆
    """

    async def update_index(self, entry: dict) -> None:
        """更新MEMORY.md索引

        Args:
            entry: 索引条目，包含 name, type, memory_id, description
        """

    async def remove_from_index(self, memory_id: str) -> None:
        """从索引移除条目

        Args:
            memory_id: 记忆 ID
        """

    async def search_index(self, query: str) -> list[dict]:
        """搜索索引

        Args:
            query: 搜索关键词

        Returns:
            匹配的索引条目列表
        """
