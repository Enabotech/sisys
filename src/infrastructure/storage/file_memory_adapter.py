"""FileMemoryAdapter — L0 文件系统适配器。

路径优先级（XDG 规范）：
1. $XDG_CONFIG_HOME/sisys/memory/（若 XDG_CONFIG_HOME 已设置）
2. $HOME/.config/sisys/memory/（XDG 默认路径）
3. $HOME/.sisys/memory/（向后兼容旧版本）

目录结构: {base_path}/{type}/{memory_id}.md
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.config.memory import MemoryConfig

# MEMORY.md 索引行格式
INDEX_PATTERN = re.compile(r"^- \[(\S+)\]\((\S+)\) — (.+)$")


class FileMemoryAdapter:
    """L0 文件系统适配器。

    负责 ~/.sisys/memory/*.md 文件的读写操作。
    """

    def __init__(self, config: MemoryConfig):
        """初始化 FileMemoryAdapter。

        Args:
            config: MemoryConfig 配置实例
        """
        self.config = config
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        """确保基础路径存在。"""
        base_path = Path(self.config.memory_l0_path)
        base_path.mkdir(parents=True, exist_ok=True)

    def write(self, memory_id: str, memory_type: str, content: str) -> None:
        """写入记忆文件。

        Args:
            memory_id: 记忆 ID（UUID）
            memory_type: 记忆类型（user/feedback/project/reference）
            content: 记忆内容

        Raises:
            OSError: 如果写入失败
        """
        dir_path = Path(self.config.memory_l0_path) / memory_type
        dir_path.mkdir(parents=True, exist_ok=True)

        file_path = dir_path / f"{memory_id}.md"
        file_path.write_text(content, encoding="utf-8")

    def read(self, memory_id: str, memory_type: str) -> str:
        """读取记忆文件。

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
            raise FileNotFoundError(f"Memory file not found: {file_path}")
        return file_path.read_text(encoding="utf-8")

    def delete(self, memory_id: str, memory_type: str) -> None:
        """删除记忆文件。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Raises:
            FileNotFoundError: 如果文件不存在
        """
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        if file_path.exists():
            file_path.unlink()

    def list_memories(self, memory_type: str) -> list[str]:
        """列出指定类型的记忆文件。

        Args:
            memory_type: 记忆类型

        Returns:
            记忆 ID 列表
        """
        dir_path = Path(self.config.memory_l0_path) / memory_type
        if not dir_path.exists():
            return []

        memory_ids = []
        for file_path in dir_path.glob("*.md"):
            memory_ids.append(file_path.stem)
        return memory_ids

    def exists(self, memory_id: str, memory_type: str) -> bool:
        """检查记忆文件是否存在。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            True 如果存在，False 否则
        """
        file_path = Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md"
        return file_path.exists()

    def update_index(self, entries: list[dict]) -> None:
        """更新 MEMORY.md 索引。

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
        """读取 MEMORY.md 索引。

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

    def get_memory_ids_by_type(self, memory_type: str) -> list[str]:
        """获取指定类型的所有记忆 ID。

        Args:
            memory_type: 记忆类型

        Returns:
            记忆 ID 列表
        """
        return self.list_memories(memory_type)

    def get_path(self, memory_id: str, memory_type: str) -> str:
        """获取记忆文件完整路径。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            完整路径字符串
        """
        return str(Path(self.config.memory_l0_path) / memory_type / f"{memory_id}.md")
