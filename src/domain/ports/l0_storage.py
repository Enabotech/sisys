"""L0StoragePort — L0 文件系统存储抽象端口。

负责 ~/.sisys/memory/*.md 文件的异步读写操作。

设计原则：
- I/O 密集型方法：async + aiofiles
- 快速同步操作：async + to_thread（避免阻塞事件循环）
- 领域层零外部依赖（仅用 abc + typing）
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class L0StoragePort(ABC):
    """L0 文件系统存储抽象端口。

    负责 ~/.sisys/memory/*.md 文件的异步读写操作。
    所有 L0 存储实现必须实现此端口。
    """

    @abstractmethod
    async def write(self, memory_id: str, memory_type: str, content: str) -> None:
        """写入记忆文件（I/O 密集型）。

        Args:
            memory_id: 记忆 ID（UUID）
            memory_type: 记忆类型（user/feedback/project/reference）
            content: 记忆内容

        Raises:
            OSError: 如果写入失败
        """
        pass

    @abstractmethod
    async def read(self, memory_id: str, memory_type: str) -> str:
        """读取记忆文件（I/O 密集型）。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            记忆内容

        Raises:
            FileNotFoundError: 如果文件不存在
        """
        pass

    @abstractmethod
    async def delete(self, memory_id: str, memory_type: str) -> None:
        """删除记忆文件（快速同步操作，可用 to_thread 封装）。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
        """
        pass

    @abstractmethod
    async def exists(self, memory_id: str, memory_type: str) -> bool:
        """检查记忆文件是否存在（快速同步操作）。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            True 如果存在，False 否则
        """
        pass

    @abstractmethod
    async def list_memories(self, memory_type: str) -> list[str]:
        """列出指定类型的记忆文件。

        Args:
            memory_type: 记忆类型

        Returns:
            记忆 ID 列表
        """
        pass
