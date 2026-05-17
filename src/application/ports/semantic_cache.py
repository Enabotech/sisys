"""SemanticCache Protocol — 领域层定义。

定义语义缓存的接口，基础设施层负责实现（如 Redis 实现）。
"""

from __future__ import annotations

from typing import Protocol


class SemanticCache(Protocol):
    """语义缓存协议接口。

    支持基于向量相似度的缓存查询和存储。
    """

    async def get(self, query_embedding: list[float], threshold: float = 0.9) -> dict | None:
        """查询语义缓存。

        Args:
            query_embedding: 查询向量嵌入
            threshold: 相似度阈值

        Returns:
            缓存结果，如果未命中则返回 None
        """

    async def set(self, query_embedding: list[float], result: dict, ttl: int = 86400) -> None:
        """存储到语义缓存。

        Args:
            query_embedding: 查询向量嵌入
            result: 缓存结果数据
            ttl: 过期时间（秒）
        """

    async def invalidate(self, cache_key: str) -> None:
        """使缓存失效。

        Args:
            cache_key: 缓存键
        """
