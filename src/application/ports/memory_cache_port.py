"""应用层记忆缓存端口模块

继承 L1CachePort，添加记忆领域特定的语义方法

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l1_cache import L1CachePort


@runtime_checkable
class MemoryCachePort(L1CachePort, Protocol):
    """记忆领域缓存端口

    继承通用 KV 方法，添加记忆特定的语义方法

    记忆键约定：
        私有: memory:user:{user_id}:{name}
        群组: memory:group:{group_id}:{name}
    """

    async def get_memory(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> str | None:
        """读取缓存记忆条目

        Args:
            memory_type: 'private' 或 'group'
            owner_id: 用户 ID 或群组 ID
            name: 记忆名称

        Returns:
            缓存内容，不存在返回 None
        """

    async def set_memory(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
        content: str,
        ttl: int | None = None,
    ) -> bool:
        """写入缓存记忆条目

        Args:
            memory_type: 'private' 或 'group'
            owner_id: 用户 ID 或群组 ID
            name: 记忆名称
            content: 待缓存内容
            ttl: TTL 秒数，None 使用默认值（24h-30h 随机）

        Returns:
            成功返回 True
        """

    async def delete_memory(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> bool:
        """删除指定缓存记忆条目

        Args:
            memory_type: 'private' 或 'group'
            owner_id: 用户 ID 或群组 ID
            name: 记忆名称

        Returns:
            删除成功返回 True
        """

    async def invalidate_owner(
        self,
        memory_type: str,
        owner_id: str,
    ) -> int:
        """使指定所有者的所有缓存条目失效

        Args:
            memory_type: 'private' 或 'group'
            owner_id: 用户 ID 或群组 ID

        Returns:
            失效条目数量
        """
