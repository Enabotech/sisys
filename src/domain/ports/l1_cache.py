"""L1CachePort — L1 缓存存储抽象端口。

对应 architecture.md §11.2.9 L1 缓存策略：
- 写入时失效：MemoryChanged 事件触发缓存失效
- 读取时加速：高频访问可先查 L1，L1 未命中则查 L0
- 不作为真相源：决策时以 L0 为准

设计原则：
- 领域层零外部依赖（仅用 abc + typing）
- 异步优先（async def）
"""

from __future__ import annotations

from typing import Protocol


class L1CachePort(Protocol):
    """L1 缓存存储接口。

    对应 architecture.md §11.2.9 L1 缓存策略：
    - 写入时失效：MemoryChanged 事件触发缓存失效
    - 读取时加速：高频访问可先查 L1，L1 未命中则查 L0
    - 不作为真相源：决策时以 L0 为准

    注意：L1 层包含两种缓存：
    - 记忆缓存（RedisMemoryCache）→ 本接口
    - 语义缓存（RedisSemanticCache）→ 独立接口，见 semantic_cache.py
    """

    async def get(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> str | None:
        """从缓存读取。

        Args:
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            缓存内容，不存在返回 None
        """

    async def set(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
        content: str,
        ttl: int | None = None,
    ) -> bool:
        """写入缓存。

        Args:
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称
            content: 内容
            ttl: TTL 秒数，None 使用默认（24h-30h 随机）

        Returns:
            是否成功
        """

    async def delete(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> bool:
        """删除缓存。

        Returns:
            是否成功
        """

    async def invalidate_pattern(
        self,
        memory_type: str,
        owner_id: str,
    ) -> int:
        """按模式失效缓存。

        Args:
            memory_type: 记忆类型
            owner_id: 所有者 ID

        Returns:
            失效的 key 数量
        """
