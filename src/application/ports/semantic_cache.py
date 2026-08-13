"""应用层语义缓存端口模块

定义语义缓存的接口，基础设施层通过 Redis 实现此端口
"""

from __future__ import annotations

from typing import Protocol


class SemanticCache(Protocol):
    """语义缓存协议接口

    支持基于向量相似度的缓存查询和存储
    """

    async def get(self, query_embedding: list[float], threshold: float = 0.9) -> dict | None:
        """查询语义缓存

        Args:
            query_embedding: 查询向量嵌入
            threshold: 相似度阈值

        Returns:
            缓存结果，如果未命中则返回 None
        """

    async def set(
        self,
        query_embedding: list[float],
        result: dict,
        ttl: int = 86400,
        doc_ids: list[str] | None = None,
    ) -> None:
        """存储到语义缓存

        Args:
            query_embedding: 查询向量嵌入
            result: 缓存结果数据
            ttl: 过期时间（秒）
            doc_ids: 关联的文档 ID 列表（维护"文档 ID → 缓存键"二级索引）
        """

    async def invalidate(self, cache_key: str) -> None:
        """使缓存失效

        注意: cache_key 应为缓存条目键（`vec:*` 前缀），不要传入二级索引键（`idx:*`）

        Args:
            cache_key: 缓存键
        """

    async def invalidate_pattern(self, pattern: str, count: int = 100) -> None:
        """按模式匹配批量失效缓存

        基于 Redis SCAN 模式匹配，使用 COUNT 参数控制每批扫描数量。

        Args:
            pattern: 模式匹配（如 `vec:*`、`idx:*` 或 `*`）
            count: SCAN 每批数量（默认 100）
        """

    async def invalidate_all(self) -> None:
        """全量清理语义缓存

        删除 `sisys:cache:semantic:*` 前缀下的所有键（含缓存数据 + 二级索引）
        """

    async def invalidate_by_document_id(self, doc_id: str) -> None:
        """按文档 ID 使关联的缓存条目失效

        通过二级索引（Redis Set）查询文档关联的所有缓存键，逐一删除。

        Args:
            doc_id: 文档 ID
        """
