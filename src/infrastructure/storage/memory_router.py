"""MemoryRouter — 记忆路径路由。

负责生成 Private/Group 记忆的文件路径和索引路径。
与 MemoryIndex 分离：MemoryRouter 仅处理路径生成，索引操作由 MemoryIndex 负责。

路径策略：
- Private: {base_path}/{type}/{uuid}.md
- Group: {base_path}/group/{type}/{uuid}.md
- Private 索引: {base_path}/MEMORY.md
- Group 索引: {base_path}/group/MEMORY.md

架构来源: architecture.md §11.2.3
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.config.memory import MemoryConfig


class MemoryRouter:
    """记忆路径路由器。

    负责生成 Private/Group 记忆的文件路径和索引路径。
    事件驱动：由 MemoryService 或 MemoryChangedListener 调用。
    """

    def __init__(self, config: MemoryConfig):
        """初始化 MemoryRouter。

        Args:
            config: MemoryConfig 配置实例
        """
        self.config = config
        self._base_path = Path(config.memory_l0_path)

    def get_memory_path(self, memory_type: str, memory_id: str, is_group: bool = False) -> str:
        """获取记忆文件路径。

        Args:
            memory_type: 记忆类型（user/feedback/project/reference）
            memory_id: 记忆 ID（UUID）
            is_group: 是否为 Group 记忆

        Returns:
            记忆文件相对路径
        """
        if is_group:
            return f"group/{memory_type}/{memory_id}.md"
        return f"{memory_type}/{memory_id}.md"

    def get_index_path(self, is_group: bool = False) -> str:
        """获取索引文件路径。

        Args:
            is_group: 是否为 Group 记忆索引

        Returns:
            索引文件相对路径
        """
        if is_group:
            return "group/MEMORY.md"
        return "MEMORY.md"

    def resolve_path(self, memory_type: str, memory_id: str, is_group: bool = False) -> Path:
        """解析记忆文件的完整路径。

        Args:
            memory_type: 记忆类型
            memory_id: 记忆 ID
            is_group: 是否为 Group 记忆

        Returns:
            完整的文件系统路径
        """
        relative_path = self.get_memory_path(memory_type, memory_id, is_group)
        return self._base_path / relative_path

    def resolve_index_path(self, is_group: bool = False) -> Path:
        """解析索引文件的完整路径。

        Args:
            is_group: 是否为 Group 记忆索引

        Returns:
            完整的索引文件路径
        """
        relative_path = self.get_index_path(is_group)
        return self._base_path / relative_path
