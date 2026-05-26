"""基础设施层缓存条目数据模型模块

定义语义缓存的存储实体结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CacheEntry:
    """缓存条目数据模型

    Attributes:
        cache_key: 缓存键
        query_embedding: 查询向量嵌入
        result: 缓存结果数据
        similarity_threshold: 相似度阈值
        created_at: 创建时间
        ttl: 过期时间（秒）
    """

    cache_key: str
    query_embedding: list[float]
    result: dict
    similarity_threshold: float = 0.9
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ttl: int = 86400

    def to_dict(self) -> dict:
        """序列化为字典

        Returns:
            包含缓存条目字段的字典
        """
        return {
            "cache_key": self.cache_key,
            "query_embedding": self.query_embedding,
            "result": self.result,
            "similarity_threshold": self.similarity_threshold,
            "created_at": self.created_at.isoformat(),
            "ttl": self.ttl,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CacheEntry:
        """从字典反序列化

        Args:
            data: 包含缓存条目字段的字典

        Returns:
            CacheEntry 实例
        """
        return cls(
            cache_key=data["cache_key"],
            query_embedding=data["query_embedding"],
            result=data["result"],
            similarity_threshold=data.get("similarity_threshold", 0.9),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if isinstance(data.get("created_at"), str)
                else data.get("created_at", datetime.now(UTC))
            ),
            ttl=data.get("ttl", 86400),
        )
