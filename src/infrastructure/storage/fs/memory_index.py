"""基础设施层记忆索引管理模块

实现 IndexManagerPort 接口，提供异步索引操作能力。所有方法使用 to_thread
封装同步 I/O 操作，保留 fcntl.flock 锁语义以保证并发安全

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import asyncio
import fcntl
import re
from pathlib import Path

from src.domain.ports.index_manager import IndexManagerPort
from src.infrastructure.config.memory import MemoryConfig

# 索引行格式正则
INDEX_LINE_PATTERN = re.compile(r"^- \[(\S+)\]\((\S+)\) — (.+)$")


class MemoryIndex(IndexManagerPort):
    """记忆索引管理器

    实现 IndexManagerPort 接口，负责 MEMORY.md 索引的读取、更新、搜索和截断
    所有方法使用 to_thread 封装同步 I/O 操作，保留 fcntl.flock 锁语义
    事件驱动：由 MemoryChangedListener 调用
    """

    MAX_INDEX_LINES = 200  # 索引最大行数

    def __init__(self, config: MemoryConfig):
        """初始化 MemoryIndex

        Args:
            config: MemoryConfig 配置实例
        """
        self.config = config
        self._index_path = Path(config.get_index_path())
        self._lock_path = self._index_path.with_suffix(".lock")

    # ========================================================================
    # IndexManagerPort 实现（异步方法，使用 to_thread）
    # ========================================================================

    async def update_entry(self, entry: dict) -> None:
        """更新索引条目（使用 to_thread 保留锁语义）

        如果 memory_id 已存在则更新，否则追加

        Args:
            entry: 索引条目，包含 name, type, memory_id, description
        """

        def _do_update():
            entry_copy = dict(entry)  # 复制避免修改原字典
            memory_id = entry_copy["memory_id"]
            is_group = entry_copy.pop("is_group", False)

            # 获取现有条目
            entries = self._read_entries_locked()

            # 移除已存在的相同 memory_id 条目
            entries = [e for e in entries if e["memory_id"] != memory_id]

            # 构建路径
            if is_group:
                path = f"group/{entry_copy['type']}/{memory_id}.md"
            else:
                path = f"{entry_copy['type']}/{memory_id}.md"

            # 添加更新后的条目
            entries.append(
                {
                    "name": entry_copy["name"],
                    "type": entry_copy["type"],
                    "memory_id": memory_id,
                    "description": entry_copy.get("description", ""),
                    "path": path,
                }
            )

            # 写入索引
            self._write_entries_locked(entries)

        await asyncio.to_thread(_do_update)

    async def remove_entry(self, memory_id: str) -> None:
        """移除索引条目（使用 to_thread 保留锁语义）

        Args:
            memory_id: 记忆 ID
        """

        def _do_remove():
            entries = self._read_entries_locked()
            entries = [e for e in entries if e["memory_id"] != memory_id]
            self._write_entries_locked(entries)

        await asyncio.to_thread(_do_remove)

    async def read_entries(self) -> list[dict]:
        """读取所有索引条目（使用 to_thread 保留锁语义）

        Returns:
            索引条目列表
        """
        return await asyncio.to_thread(self._read_entries_locked)

    async def search(self, query: str) -> list[dict]:
        """搜索索引条目

        Args:
            query: 搜索关键词（匹配名称）

        Returns:
            匹配的索引条目列表
        """
        entries = await self.read_entries()
        query_lower = query.lower()
        return [e for e in entries if query_lower in e["name"].lower()]

    async def truncate(self) -> None:
        """截断索引到最大行数（使用 to_thread 保留锁语义）

        保留最新 MAX_INDEX_LINES 行（按文件顺序，最后写入的在末尾）
        """

        def _do_truncate():
            if not self._index_path.exists():
                return

            with open(self._index_path, encoding="utf-8") as f:
                lines = f.readlines()

            # 过滤注释和空行
            content_lines = [line for line in lines if line.strip() and not line.startswith("#")]

            if len(content_lines) <= self.MAX_INDEX_LINES:
                return

            # 保留最新 MAX_INDEX_LINES 行
            lines_to_keep = lines[-self.MAX_INDEX_LINES :]

            # 原子写入：先写临时文件再 rename
            temp_path = self._index_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.writelines(lines_to_keep)
            temp_path.rename(self._index_path)

        await asyncio.to_thread(_do_truncate)

    # ========================================================================
    # 内部方法（同步，保留锁语义）
    # ========================================================================

    def _read_entries_locked(self) -> list[dict]:
        """带锁读取索引条目

        Returns:
            索引条目列表
        """
        if not self._index_path.exists():
            return []

        self._ensure_lock_file()
        with open(self._lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
            try:
                with open(self._index_path, encoding="utf-8") as f:
                    return self._parse_index(f.read())
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _write_entries_locked(self, entries: list[dict]) -> None:
        """带锁写入索引条目

        Args:
            entries: 索引条目列表
        """
        self._ensure_lock_file()
        self._index_path.parent.mkdir(parents=True, exist_ok=True)

        # 原子写入：先写临时文件再 rename
        temp_path = self._index_path.with_suffix(".tmp")

        with open(self._lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                content = self._format_entries(entries)
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(content)
                temp_path.rename(self._index_path)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _ensure_lock_file(self) -> None:
        """确保锁文件存在"""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path.touch(exist_ok=True)

    def _parse_index(self, content: str) -> list[dict]:
        """解析索引内容

        Args:
            content: 索引文件内容

        Returns:
            索引条目列表
        """
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = INDEX_LINE_PATTERN.match(line)
            if match:
                name, path, desc = match.groups()
                # 解析 path: {type}/{memory_id}.md 或 group/{type}/{memory_id}.md
                parts = Path(path).parts
                if len(parts) >= 2:
                    if parts[0] == "group":
                        is_group = True
                        mem_type = parts[1]
                    else:
                        is_group = False
                        mem_type = parts[0]
                    mem_id = Path(path).stem
                    entries.append(
                        {
                            "name": name,
                            "type": mem_type,
                            "memory_id": mem_id,
                            "description": desc,
                            "is_group": is_group,
                        }
                    )
        return entries

    def _format_entries(self, entries: list[dict]) -> str:
        """格式化索引条目为文本

        Args:
            entries: 索引条目列表

        Returns:
            格式化后的索引文本
        """
        lines = []
        for entry in entries:
            path = entry.get("path")
            if not path:
                # 从 entry 构建 path
                if entry.get("is_group"):
                    path = f"group/{entry['type']}/{entry['memory_id']}.md"
                else:
                    path = f"{entry['type']}/{entry['memory_id']}.md"
            lines.append(f"- [{entry['name']}]({path}) — {entry.get('description', '')}")
        return "\n".join(lines) + "\n"
