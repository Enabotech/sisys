"""基础设施层文件系统记忆适配器模块

实现 L0StoragePort 接口，提供异步文件操作能力。write/read 使用 aiofiles（I/O 密集型），
delete/exists/list_memories 使用 asyncio.to_thread()（快速同步操作）
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import cast

import aiofiles

from src.domain.exceptions import NotFoundError
from src.domain.ports.l0_storage import L0StoragePort
from src.infrastructure.config.memory import MemoryConfig

# MEMORY.md 索引行格式
INDEX_PATTERN = re.compile(r"^- \[(\S+)\]\((\S+)\) — (.+)$")


class FileMemoryAdapter(L0StoragePort):
    """L0 文件系统适配器

    实现 L0StoragePort 接口，负责 ~/.sisys/memory/*.md 文件的异步读写操作
    保留原有同步方法用于向后兼容
    """

    def __init__(self, config: MemoryConfig):
        """初始化 FileMemoryAdapter

        Args:
            config: MemoryConfig 配置实例
        """
        self.config = config
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        """确保基础路径存在"""
        base_path = Path(self.config.memory_l0_path)
        base_path.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # L0StoragePort 实现（异步方法）
    # ========================================================================

    async def write(self, memory_id: str, memory_type: str, content: str) -> bool:
        """写入记忆文件（I/O 密集型，使用 aiofiles）

        Args:
            memory_id: 记忆 ID（UUID）
            memory_type: 记忆类型（user/feedback/project/reference）
            content: 记忆内容

        Returns:
            True 如果写入成功，False 否则

        Raises:
            OSError: 如果写入失败
        """
        dir_path = Path(self.config.memory_l0_path) / memory_type
        dir_path.mkdir(parents=True, exist_ok=True)

        file_path = dir_path / f"{memory_id}.md"
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)
        return True

    async def read(self, memory_id: str, memory_type: str) -> str:
        """读取记忆文件（I/O 密集型，使用 aiofiles）

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            记忆内容

        Raises:
            FileNotFoundError: 如果文件不存在
        """
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        if not file_path.exists():
            raise NotFoundError(f"Memory file not found: {file_path}")
        async with aiofiles.open(file_path, encoding="utf-8") as f:
            content: str = await f.read()
            return cast(str, content)

    async def delete(self, memory_id: str, memory_type: str) -> bool:
        """删除记忆文件（快速同步操作，使用 to_thread）

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            True 如果删除成功，False 如果文件不存在
        """

        def _do_delete():
            file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
            if file_path.exists():
                file_path.unlink()
                return True
            return False

        return await asyncio.to_thread(_do_delete)

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        """检查记忆文件是否存在（快速同步操作，使用 to_thread）

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            True 如果存在，False 否则
        """

        def _do_check():
            return (Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md").exists()

        return await asyncio.to_thread(_do_check)

    async def list_memories(self, memory_type: str) -> list[str]:
        """列出指定类型的记忆文件（快速同步操作，使用 to_thread）

        Args:
            memory_type: 记忆类型

        Returns:
            记忆 ID 列表
        """

        def _do_list():
            dir_path = Path(self.config.memory_l0_path) / memory_type
            if not dir_path.exists():
                return []
            return [p.stem for p in dir_path.glob("*.md")]

        return await asyncio.to_thread(_do_list)

    # ========================================================================
    # 向后兼容的同步方法（已废弃，不推荐使用）
    # ========================================================================

    def write_sync(self, memory_id: str, memory_type: str, content: str) -> None:
        """同步写入记忆文件

        .. deprecated::
            请使用 async write() 方法替代。此方法仅为向后兼容保留

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            content: 记忆内容
        """
        dir_path = Path(self.config.memory_l0_path) / memory_type
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{memory_id}.md"
        file_path.write_text(content, encoding="utf-8")

    def read_sync(self, memory_id: str, memory_type: str) -> str:
        """同步读取记忆文件

        .. deprecated::
            请使用 async read() 方法替代。此方法仅为向后兼容保留

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            记忆内容

        Raises:
            FileNotFoundError: 文件不存在时抛出
        """
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        if not file_path.exists():
            raise NotFoundError(f"Memory file not found: {file_path}")
        return file_path.read_text(encoding="utf-8")

    def update_index(self, entries: list[dict]) -> None:
        """更新 MEMORY.md 索引（同步方法，向后兼容）

        格式: - [{name}]({type}/{memory_id}.md) — {description}

        Args:
            entries: 索引条目列表，每条包含 name, type, memory_id, description
        """
        index_path = Path(self.config.memory_l0_path) / "MEMORY.md"
        lines = []

        for entry in entries:
            name = entry["name"]
            mem_type = entry["type"]
            mem_id = entry["memory_id"]
            desc = entry.get("description", "")
            lines.append(f"- [{name}]({mem_type}/{mem_id}.md) — {desc}")

        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def read_index(self) -> list[dict]:
        """读取 MEMORY.md 索引（同步方法，向后兼容）

        Returns:
            索引条目列表，每条包含 name, type, memory_id, description
        """
        index_path = Path(self.config.memory_l0_path) / "MEMORY.md"
        if not index_path.exists():
            return []

        entries = []
        for line in index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = INDEX_PATTERN.match(line)
            if match:
                name, path, desc = match.groups()
                # 解析 path: {type}/{memory_id}.md
                parts = Path(path).parts
                if len(parts) >= 2:
                    mem_type = parts[0]
                    mem_id = Path(path).stem
                    entries.append(
                        {
                            "name": name,
                            "type": mem_type,
                            "memory_id": mem_id,
                            "description": desc,
                        }
                    )
        return entries

    async def get_memory_ids_by_type(self, memory_type: str) -> list[str]:
        """获取指定类型的所有记忆 ID（异步版本）

        Args:
            memory_type: 记忆类型

        Returns:
            记忆 ID 列表
        """
        return await self.list_memories(memory_type)

    def get_path(self, memory_id: str, memory_type: str) -> str:
        """获取记忆文件完整路径

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            完整路径字符串
        """
        return str(Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md")
