"""IndexManagerPort — 记忆索引管理抽象端口。

负责 MEMORY.md 索引的维护与更新。

设计原则：
- 所有方法使用 to_thread 封装同步 I/O 操作
- 保留 fcntl.flock 锁语义（原子性保证）
- 领域层零外部依赖（仅用 abc + typing）
"""

from __future__ import annotations

from typing import Protocol


class IndexManagerPort(Protocol):
    """记忆索引管理抽象端口。

    负责 MEMORY.md 索引的维护与更新。
    所有索引管理实现必须实现此端口。
    """

    async def update_entry(self, entry: dict) -> None:
        """更新索引条目。

        Args:
            entry: 索引条目，包含 name, type, memory_id, description
        """

    async def remove_entry(self, memory_id: str) -> None:
        """移除索引条目。

        Args:
            memory_id: 记忆 ID
        """

    async def read_entries(self) -> list[dict]:
        """读取所有索引条目。

        Returns:
            索引条目列表
        """

    async def search(self, query: str) -> list[dict]:
        """搜索索引条目。

        Args:
            query: 搜索关键词

        Returns:
            匹配的索引条目列表
        """

    async def truncate(self) -> None:
        """截断索引到最大行数。

        保留最新 MAX_INDEX_LINES 行。
        """
