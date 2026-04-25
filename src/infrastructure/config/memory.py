"""MemoryConfig — 记忆配置模型。

环境变量:
- MEMORY_L0_PATH: L0 文件系统路径（默认 ~/.sisys/memory）
- MEMORY_L1_CACHE_TTL: L1 Redis 缓存 TTL（默认 86400 秒）
- COMPRESSION_MIN_RATIO: 最小压缩率（默认 0.7）
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class MemoryConfig:
    """记忆系统配置。

    使用 from_env() 类方法从环境变量加载配置。
    复用 OtelConfig 模式。
    """

    # L0 文件系统路径
    memory_l0_path: str = ""

    # L1 Redis 缓存 TTL（秒）
    memory_l1_cache_ttl: int = 86400

    # 最小压缩率
    compression_min_ratio: float = 0.7

    @classmethod
    def from_env(cls) -> MemoryConfig:
        """从环境变量加载配置。

        路径优先级（XDG 规范）：
        1. $XDG_CONFIG_HOME/sisys/memory/（若 XDG_CONFIG_HOME 已设置）
        2. $HOME/.config/sisys/memory/（XDG 默认路径）
        3. $HOME/.sisys/memory/（向后兼容旧版本）

        Returns:
            MemoryConfig 实例
        """
        # 确定 base_path
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        home = os.environ.get("HOME", "/root")

        if xdg_config:
            base_path = os.path.join(xdg_config, "sisys", "memory")
        elif os.path.exists(os.path.join(home, ".config", "sisys", "memory")):
            base_path = os.path.join(home, ".config", "sisys", "memory")
        else:
            base_path = os.path.join(home, ".sisys", "memory")

        return cls(
            memory_l0_path=os.environ.get("MEMORY_L0_PATH", base_path),
            memory_l1_cache_ttl=int(os.environ.get("MEMORY_L1_CACHE_TTL", "86400")),
            compression_min_ratio=float(os.environ.get("COMPRESSION_MIN_RATIO", "0.7")),
        )

    def get_base_path(self) -> str:
        """获取基础路径。

        Returns:
            基础路径字符串
        """
        return self.memory_l0_path

    def get_memory_path(self, memory_type: str, memory_id: str) -> str:
        """获取记忆文件路径。

        Args:
            memory_type: 记忆类型（user/feedback/project/reference）
            memory_id: 记忆 ID（UUID）

        Returns:
            记忆文件完整路径
        """
        return f"{self.memory_l0_path}/{memory_type}/{memory_id}.md"

    def get_memory_dir(self, memory_type: str) -> str:
        """获取记忆类型目录。

        Args:
            memory_type: 记忆类型

        Returns:
            记忆类型目录路径
        """
        return f"{self.memory_l0_path}/{memory_type}"

    def get_index_path(self) -> str:
        """获取 MEMORY.md 索引路径。

        Returns:
            MEMORY.md 完整路径
        """
        return f"{self.memory_l0_path}/MEMORY.md"
