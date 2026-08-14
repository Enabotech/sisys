"""SISYS 基础设施层 Redis 语义缓存模块

基于 RediSearch FT.SEARCH 向量索引实现语义缓存查找，
替代 SCAN + Python 余弦相似度方案以提升性能

二级索引命名空间：
- sisys:cache:semantic:vec:{md5} — 缓存数据主键（已有）
- sisys:cache:semantic:idx:doc:{doc_id} — 文档 ID 二级索引（Story 3-9 新增）
  `idx:` 中间段与 `vec:` 精确区分，避免 invalidate_pattern 误删
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import struct

import redis.asyncio as aioredis

from src.domain.exceptions import ValidationError
from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.utils import json_dumps, json_loads

logger = logging.getLogger(__name__)

# RediSearch 索引名前缀（索引名后缀维度，不同维度向量不能共用一个索引）
_INDEX_NAME_PREFIX = "idx:sisys_semantic_cache"

# 二级索引 key 段前缀（与缓存数据键 vec: 精确区分）
_IDX_SEGMENT = "idx"
_DOC_IDX_PREFIX = f"{_IDX_SEGMENT}:doc"


def _build_index_name(embedding_dim: int) -> str:
    """生成 RediSearch 向量索引名（含维度后缀）

    不同维度的向量不能共用一个 RediSearch 索引，因此索引名需包含维度。
    生产环境 bge-m3 为 1024 维，测试环境可用更小维度。

    Args:
        embedding_dim: 向量维度

    Returns:
        索引名，如 `idx:sisys_semantic_cache:1024`
    """
    return f"{_INDEX_NAME_PREFIX}:{embedding_dim}"


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two vectors (pure Python, no numpy).

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Cosine similarity (-1.0 to 1.0), 0.0 for empty/zero vectors.
    """
    if len(vec1) != len(vec2):
        raise ValidationError(message=f"Vector dimensions must match: {len(vec1)} != {len(vec2)}")
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

    sim = dot_product / (norm1 * norm2)
    return max(-1.0, min(1.0, sim))


def _vector_to_bytes(vec: list[float]) -> bytes:
    """Pack float list into FLOAT32 little-endian bytes."""
    return struct.pack(f"<{len(vec)}f", *vec)


class RedisSemanticCache:
    """Redis semantic cache using RediSearch vector index.

    Stores embeddings as FLOAT32 binary in Redis Hash, indexed by
    RediSearch for KNN vector similarity search. Single FT.SEARCH
    command replaces the old SCAN + HGET + Python cosine_similarity loop.

    Args:
        redis_client: Redis async client (provided by RedisConnectionManager).
        embedding_dim: Dimension of embedding vectors (default 1024).
        metrics_collector: Optional metrics collector for hit/miss tracking.
    """

    _NAMESPACE = "cache:semantic"
    _ensure_index_lock: asyncio.Lock = asyncio.Lock()

    def __init__(
        self,
        redis_client: aioredis.Redis,
        embedding_dim: int = 1024,
        metrics_collector: EventMetricsCollector | None = None,
    ):
        self._redis = redis_client
        self._embedding_dim = embedding_dim
        self._metrics_collector = metrics_collector
        self._index_ready = False
        self._index_name = _build_index_name(embedding_dim)

    async def _ensure_index(self) -> None:
        """Create RediSearch vector index if not exists (idempotent).

        并发保护：使用类级 asyncio.Lock 保证 FT.CREATE 的幂等创建，
        避免多个协程同时执行 FT.CREATE 引发的竞态（重复创建索引）。
        """
        if self._index_ready:
            return
        async with self._ensure_index_lock:
            # 获取锁后再次检查，避免重复执行 FT.CREATE
            if self._index_ready:
                return
            try:
                await self._redis.execute_command(
                    "FT.CREATE",
                    self._index_name,
                    "ON",
                    "HASH",
                    "PREFIX",
                    "1",
                    build_key(self._NAMESPACE, ""),
                    "SCHEMA",
                    "embedding",
                    "VECTOR",
                    "FLAT",
                    "6",
                    "TYPE",
                    "FLOAT32",
                    "DIM",
                    str(self._embedding_dim),
                    "DISTANCE_METRIC",
                    "COSINE",
                )
                logger.info("Created RediSearch vector index %s (dim=%d)", self._index_name, self._embedding_dim)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    raise
            self._index_ready = True

    def _build_cache_key(self, query_embedding: list[float]) -> str:
        """Generate deterministic cache key from full vector hash."""
        vec_bytes = _vector_to_bytes(query_embedding)
        vector_id = hashlib.md5(vec_bytes, usedforsecurity=False).hexdigest()[:16]
        return f"vec:{vector_id}"

    async def get(self, query_embedding: list[float], threshold: float = 0.9) -> dict | None:
        """Query semantic cache via RediSearch KNN vector search.

        Args:
            query_embedding: Query embedding vector.
            threshold: Minimum cosine similarity (0.0-1.0).

        Returns:
            Cached result dict if hit, None if miss.
        """
        try:
            await self._ensure_index()

            query_bytes = _vector_to_bytes(query_embedding)
            max_distance = 1.0 - threshold

            response = await self._redis.execute_command(
                "FT.SEARCH",
                self._index_name,
                "*=>[KNN 1 @embedding $query_vec]",
                "PARAMS",
                "2",
                "query_vec",
                query_bytes,
                "RETURN",
                "2",
                "__embedding_score",
                "result",
                "DIALECT",
                "2",
            )

            # Response format: [total_count, doc_key, [field_name, field_value], ...]
            if not response or response[0] == 0:
                if self._metrics_collector:
                    self._metrics_collector.record_cache_miss()
                logger.debug("Cache miss")
                return None

            # Parse first result: response[1] = doc key, response[2] = [field, value, ...]
            fields = response[2] if len(response) > 2 and response[2] is not None else []
            distance = None
            result_data = None

            i = 0
            while i < len(fields):
                field_name = fields[i]
                field_value = fields[i + 1] if i + 1 < len(fields) else None

                if field_name == "__embedding_score" and field_value is not None:
                    distance = float(field_value)
                elif field_name == "result":
                    result_data = field_value
                i += 2

            if distance is not None and distance > max_distance:
                if self._metrics_collector:
                    self._metrics_collector.record_cache_miss()
                logger.debug("Cache miss: best distance %.4f > threshold %.4f", distance, max_distance)
                return None

            if result_data is None:
                if self._metrics_collector:
                    self._metrics_collector.record_cache_miss()
                return None

            try:
                parsed = json_loads(result_data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("Corrupt result data: %s", e)
                if self._metrics_collector:
                    self._metrics_collector.record_cache_miss()
                return None

            if not isinstance(parsed, dict):
                logger.warning("Unexpected result type: %s", type(parsed).__name__)
                if self._metrics_collector:
                    self._metrics_collector.record_cache_miss()
                return None

            if self._metrics_collector:
                self._metrics_collector.record_cache_hit()
            similarity = 1.0 - distance if distance is not None else 1.0
            logger.debug("Cache hit with similarity %.4f", similarity)
            return parsed

        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to query semantic cache: %s", e)
            return None

    async def set(
        self,
        query_embedding: list[float],
        result: dict,
        ttl: int = 86400,
        doc_ids: list[str] | None = None,
    ) -> None:
        """Store result in semantic cache with vector embedding.

        Args:
            query_embedding: Embedding vector.
            result: Result data to cache.
            ttl: Time-to-live in seconds.
            doc_ids: 关联的文档 ID 列表（维护"文档 ID → 缓存键"二级索引）。
                使用 Redis pipeline 批量操作，减少网络往返。
        """
        cache_key = self._build_cache_key(query_embedding)
        key = build_key(self._NAMESPACE, cache_key)
        try:
            await self._ensure_index()
            vec_bytes = _vector_to_bytes(query_embedding)

            # 缓存主数据写入 + 二级索引维护：pipeline 打包为一次网络往返
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.hset(key, mapping={"embedding": vec_bytes, "result": json_dumps(result)})
                pipe.expire(key, ttl)
                if doc_ids:
                    unique_doc_ids = list(dict.fromkeys(doc_ids))  # 去重保持顺序
                    for doc_id in unique_doc_ids:
                        doc_idx_key = build_key(self._NAMESPACE, _DOC_IDX_PREFIX, doc_id)
                        pipe.sadd(doc_idx_key, cache_key)
                        pipe.expire(doc_idx_key, ttl)
                await pipe.execute()

            logger.debug(
                "Cached result with key %s and TTL %d (doc_ids=%d)",
                cache_key,
                ttl,
                len(doc_ids) if doc_ids else 0,
            )
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to store semantic cache: %s", e)

    async def invalidate(self, cache_key: str) -> None:
        """Evict a cache entry by key.

        Args:
            cache_key: Internal cache key or full Redis key.
        """
        prefix = build_key(self._NAMESPACE, "")
        if cache_key.startswith(prefix):
            key = cache_key
        else:
            key = build_key(self._NAMESPACE, cache_key)
        try:
            await self._redis.delete(key)
            logger.debug("Invalidated cache key %s", cache_key)
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to invalidate cache key %s: %s", cache_key, e)

    async def invalidate_pattern(self, pattern: str, count: int = 100) -> None:
        """按模式匹配批量失效缓存条目

        基于 Redis SCAN 模式匹配，使用 COUNT 参数控制每批扫描数量。

        Args:
            pattern: 模式匹配（如 `vec:*`、`idx:*` 或 `*`）
            count: SCAN 每批数量（默认 100）
        """
        prefix = build_key(self._NAMESPACE, pattern)
        try:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor=cursor, match=prefix, count=count)
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
            logger.debug("Invalidated keys matching pattern %s", pattern)
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to invalidate pattern %s: %s", pattern, e)

    async def invalidate_all(self) -> None:
        """全量清理语义缓存

        删除 sisys:cache:semantic:* 前缀下的所有键（含缓存数据 + 二级索引）
        """
        await self.invalidate_pattern("*")

    async def invalidate_by_document_id(self, doc_id: str) -> None:
        """按文档 ID 使关联的缓存条目失效

        通过二级索引（Redis Set）查询文档关联的所有缓存键，逐一删除。

        Args:
            doc_id: 文档 ID
        """
        doc_idx_key = build_key(self._NAMESPACE, _DOC_IDX_PREFIX, doc_id)
        try:
            cache_keys = await self._redis.smembers(doc_idx_key)
            if cache_keys:
                # SMEMBERS 返回内部缓存键（vec:{md5}），需转换为完整 Redis 键后删除
                cache_key_strs = [build_key(self._NAMESPACE, str(k)) for k in cache_keys]
                await self._redis.delete(*cache_key_strs)
            await self._redis.delete(doc_idx_key)
            logger.debug(
                "Invalidated %d cache entries for document %s",
                len(cache_keys),
                doc_id,
            )
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to invalidate document %s: %s", doc_id, e)

    async def __aenter__(self) -> RedisSemanticCache:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
