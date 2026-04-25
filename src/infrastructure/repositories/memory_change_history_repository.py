"""InMemoryMemoryChangeHistoryRepository — 记忆变更历史仓储（异步内存实现）。

⚠️ 仅用于测试隔离。生产环境使用 PostgreSQLMemoryChangeHistoryRepository。

架构来源: architecture.md §11.2.5
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from uuid import UUID

from src.domain.entities.memory_change_history import MemoryChangeHistory
from src.domain.repositories.memory_repository import MemoryChangeHistoryRepositoryProtocol


class InMemoryMemoryChangeHistoryRepository(MemoryChangeHistoryRepositoryProtocol):
    """内存记忆变更历史仓储（异步版本）。

    append-only 模式：只允许新增记录，不允许修改或删除历史。
    使用 asyncio.Lock 保护并发访问。
    """

    def __init__(self) -> None:
        self._entities: dict[UUID, MemoryChangeHistory] = {}
        self._lock = asyncio.Lock()

    async def save(self, history: MemoryChangeHistory) -> None:
        """保存历史记录（append-only）。

        Args:
            history: 变更历史记录
        """
        async with self._lock:
            self._entities[history.id] = deepcopy(history)

    async def get_by_memory_id(self, memory_id: UUID) -> list[MemoryChangeHistory]:
        """获取记忆的所有历史记录。

        按 changed_at 升序排序。

        Args:
            memory_id: 记忆 ID

        Returns:
            变更历史列表（按时间排序）
        """
        async with self._lock:
            histories = [h for h in self._entities.values() if h.memory_id == memory_id]
            histories.sort(key=lambda h: h.changed_at)
            return [deepcopy(h) for h in histories]

    async def get_by_id(self, history_id: UUID) -> MemoryChangeHistory | None:
        """通过 ID 获取历史记录。

        Args:
            history_id: 历史记录 ID

        Returns:
            MemoryChangeHistory 如果存在，否则 None
        """
        async with self._lock:
            entity = self._entities.get(history_id)
            if entity is None:
                return None
            return deepcopy(entity)


# 别名：MemoryChangeHistoryRepository
MemoryChangeHistoryRepository = InMemoryMemoryChangeHistoryRepository
