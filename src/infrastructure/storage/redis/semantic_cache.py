"""Redis Semantic Cache — 基础设施层实现。

实现 Story 1.4 定义的 SemanticCache 接口。
使用 Redis Hash 存储嵌入向量和缓存结果，支持纯 Python 余弦相似度计算。
"""

from __future__ import annotations

import json
import logging
import math

import redis

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.key_builder import build_key

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """计算两个向量的余弦相似度（纯 Python 实现，不使用 numpy）。

    Args:
        vec1: 第一个向量
        vec2: 第二个向量

    Returns:
        余弦相似度值（-1.0 到 1.0）
    """
    if len(vec1) != len(vec2):
        raise ValueError(f"Vector dimensions must match: {len(vec1)} != {len(vec2)}")
    if not vec1:
        return 0.0

    dot_product = 0.0
    norm1 = 0.0
    norm2 = 0.0

    for v1, v2 in zip(vec1, vec2):
        dot_product += v1 * v2
        norm1 += v1 * v1
        norm2 += v2 * v2

    norm1 = math.sqrt(norm1)
    norm2 = math.sqrt(norm2)

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    return dot_product / (norm1 * norm2)


class RedisSemanticCache:
    """Redis 语义缓存。

    使用 Redis Hash 存储嵌入向量和缓存结果。
    键格式: sisys:cache:semantic:{cache_key}
    支持基于余弦相似度的语义匹配。

    Args:
        config: Redis 连接配置
        metrics_collector: 可选的指标收集器
    """

    _NAMESPACE = "cache:semantic"

    def __init__(
        self,
        config: RedisConfig,
        metrics_collector: EventMetricsCollector | None = None,
    ):
        """初始化 Redis 语义缓存。

        Args:
            config: Redis 连接配置
            metrics_collector: 可选的指标收集器，用于记录缓存命中/未命中
        """
        self._config = config
        self._metrics_collector = metrics_collector
        self._pool: redis.ConnectionPool | None = None

    def _get_pool(self) -> redis.ConnectionPool:
        """懒加载连接池。"""
        if self._pool is None:
            self._pool = redis.ConnectionPool(
                host=self._config.host,
                port=self._config.port,
                db=self._config.db,
                password=self._config.password,
                max_connections=self._config.max_connections,
                socket_timeout=self._config.socket_timeout,
                decode_responses=True,
            )
        return self._pool

    def _build_cache_key(self, query_embedding: list[float]) -> str:
        """根据查询向量生成缓存键。

        使用向量的哈希值作为键的一部分，确保唯一性。
        """
        # 使用向量的前几个元素生成一个简单的标识符
        vector_id = hash(tuple(round(v, 6) for v in query_embedding[:10]))
        return f"vec:{vector_id}"

    async def get(self, query_embedding: list[float], threshold: float = 0.9) -> dict | None:
        """查询语义缓存。

        遍历所有缓存条目，找到相似度高于阈值的第一个结果。

        Args:
            query_embedding: 查询向量嵌入
            threshold: 相似度阈值

        Returns:
            缓存结果，如果未命中则返回 None
        """
        pool = self._get_pool()
        try:
            with redis.Redis(connection_pool=pool) as client:
                # 使用 SCAN 遍历所有缓存键
                cursor = 0
                pattern = build_key(self._NAMESPACE, "vec:*")

                while True:
                    cursor, keys = client.scan(cursor=cursor, match=pattern, count=100)

                    for key in keys:
                        # 获取缓存条目数据
                        stored_embedding = client.hget(key, "embedding")
                        stored_result = client.hget(key, "result")

                        if stored_embedding is None or stored_result is None:
                            continue

                        stored_vec = json.loads(stored_embedding)
                        similarity = cosine_similarity(query_embedding, stored_vec)

                        if similarity >= threshold:
                            result: dict = json.loads(stored_result)
                            if self._metrics_collector:
                                self._metrics_collector.record_cache_hit()
                            logger.debug("Cache hit with similarity %.4f", similarity)
                            return result

                    if cursor == 0:
                        break

                if self._metrics_collector:
                    self._metrics_collector.record_cache_miss()
                logger.debug("Cache miss")
                return None

        except redis.ConnectionError as e:
            logger.error("Failed to query semantic cache from Redis: %s", e)
            if self._metrics_collector:
                self._metrics_collector.record_cache_miss()
            return None

    async def set(self, query_embedding: list[float], result: dict, ttl: int = 86400) -> None:
        """存储到语义缓存。

        Args:
            query_embedding: 查询向量嵌入
            result: 缓存结果数据
            ttl: 过期时间（秒）
        """
        cache_key = self._build_cache_key(query_embedding)
        key = build_key(self._NAMESPACE, cache_key)
        pool = self._get_pool()
        try:
            with redis.Redis(connection_pool=pool) as client:
                client.hset(key, "embedding", json.dumps(query_embedding))
                client.hset(key, "result", json.dumps(result))
                client.expire(key, ttl)
                logger.debug("Cached result with key %s and TTL %d", cache_key, ttl)
        except redis.ConnectionError as e:
            logger.error("Failed to store semantic cache in Redis: %s", e)

    async def invalidate(self, cache_key: str) -> None:
        """使缓存失效。

        Args:
            cache_key: 缓存键
        """
        key = build_key(self._NAMESPACE, cache_key)
        pool = self._get_pool()
        try:
            with redis.Redis(connection_pool=pool) as client:
                client.delete(key)
                logger.debug("Invalidated cache key %s", cache_key)
        except redis.ConnectionError as e:
            logger.error("Failed to invalidate cache key %s in Redis: %s", cache_key, e)

    def close(self) -> None:
        """关闭连接池。"""
        if self._pool:
            self._pool.disconnect()
            self._pool = None
            logger.debug("Redis connection pool closed")
