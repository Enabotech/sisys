"""应用层语义缓存中间件模块

语义缓存中间件是 HybridSearchService 的装饰器，遵循装饰器模式。
它不修改 HybridSearchService 的代码，而是通过包装实现缓存逻辑。

核心流程：
1. 生成查询嵌入向量
2. 查询语义缓存（相似度 > 阈值时命中）
3. 命中 → 反序列化缓存结果 → 直接返回
4. 未命中 → 调用 HybridSearchService.search() → 自动写入缓存 → 返回

降级策略：
- 嵌入生成失败 → 直接检索，不缓存（WARNING 日志）
- 缓存不可用 → 透明降级为直接检索（WARNING 日志）
- 缓存数据损坏 → 视为未命中，执行完整检索（WARNING 日志）
"""

from __future__ import annotations

import hashlib
import json
import logging
import struct
import time
from typing import TYPE_CHECKING

from src.application.ports.cache_metrics_port import CacheMetricsPort
from src.application.ports.semantic_cache import SemanticCache
from src.domain.ports.embedding_service import EmbeddingServicePort
from src.domain.ports.l3_vector import SearchResult

if TYPE_CHECKING:
    from src.application.services.hybrid_search_service import HybridSearchService

logger = logging.getLogger(__name__)

# 缓存值 JSON 序列化键
_RESULTS_KEY = "results"
_QUERY_TEXT_KEY = "query_text"
_WEIGHTS_KEY = "weights"


class SemanticCacheMiddleware:
    """语义缓存中间件

    装饰 HybridSearchService，实现缓存优先检索策略。
    注入 EmbeddingServicePort 生成查询向量作为缓存键，
    注入 SemanticCache 进行缓存存储/查询，
    注入 HybridSearchService 作为被包装的检索服务。

    Attributes:
        metrics: 缓存指标采集器（CacheMetricsPort 实例）
    """

    def __init__(
        self,
        search_service: HybridSearchService,
        cache: SemanticCache,
        embedding_service: EmbeddingServicePort,
        threshold: float = 0.9,
        ttl: int = 86400,
        avg_tokens_per_search: int = 5000,
        metrics: CacheMetricsPort | None = None,
    ) -> None:
        """初始化语义缓存中间件

        Args:
            search_service: 被包装的检索服务（HybridSearchService 实例）
            cache: 语义缓存存储（SemanticCache 端口实现）
            embedding_service: 嵌入服务（生成查询向量作为缓存键）
            threshold: 缓存命中相似度阈值（默认 0.9）
            ttl: 缓存过期时间（秒，默认 86400 = 24h）
            avg_tokens_per_search: 预估每次检索消耗的 Token 数（默认 5000）
            metrics: 缓存指标采集端口（可选）
        """
        self._search_service = search_service
        self._cache = cache
        self._embedding_service = embedding_service
        self._threshold = threshold
        self._ttl = ttl
        self._avg_tokens_per_search = avg_tokens_per_search
        self._metrics = metrics
        if metrics is not None:
            metrics.set_avg_tokens_per_search(avg_tokens_per_search)

    @property
    def metrics(self) -> CacheMetricsPort | None:
        """获取缓存指标采集器实例"""
        return self._metrics

    @property
    def avg_tokens_per_search(self) -> int:
        """获取预估每次检索的 Token 数"""
        return self._avg_tokens_per_search

    def _build_cache_key(self, query_embedding: list[float], weights: list[float] | None = None) -> str:
        """构建缓存键（含 weights 哈希后缀，用于 set() 时传入 RedisSemanticCache）

        缓存键基于查询嵌入向量的 MD5 哈希。
        包含 weights 参数的哈希后缀，不同 weights 产生不同缓存键。
        此键作为 doc_ids 参数传入 cache.set()，由 RedisSemanticCache 内部用于二级索引。

        Args:
            query_embedding: 查询嵌入向量
            weights: 检索权重参数（可选，用于区分不同权重的缓存）

        Returns:
            缓存键字符串
        """
        vec_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)
        vector_id = hashlib.md5(vec_bytes, usedforsecurity=False).hexdigest()[:16]

        if weights is not None:
            weights_str = json.dumps(weights, sort_keys=True)
            weights_hash = hashlib.md5(weights_str.encode(), usedforsecurity=False).hexdigest()[:8]
            return f"vec:{vector_id}:w{weights_hash}"

        return f"vec:{vector_id}"

    def _serialize_results(self, results: list[SearchResult], query_text: str, weights: list[float] | None) -> dict:
        """序列化检索结果为缓存值格式

        Args:
            results: 检索结果列表
            query_text: 查询文本
            weights: 权重参数

        Returns:
            dict 格式缓存值
        """
        return {
            _RESULTS_KEY: [dict(r) for r in results],
            _QUERY_TEXT_KEY: query_text,
            _WEIGHTS_KEY: weights,
        }

    def _deserialize_results(self, cached: dict) -> list[SearchResult] | None:
        """反序列化缓存值为检索结果列表

        Args:
            cached: 缓存值字典

        Returns:
            SearchResult 列表，反序列化失败返回 None
        """
        try:
            results_data = cached.get(_RESULTS_KEY)
            if results_data is None or not isinstance(results_data, list):
                logger.warning("缓存结果格式异常: 缺少 %s 字段", _RESULTS_KEY)
                return None
            return [SearchResult(id=r["id"], score=r["score"], payload=r["payload"]) for r in results_data]
        except (TypeError, ValueError, KeyError) as e:
            logger.warning("缓存结果反序列化失败: %s", e)
            return None

    def _extract_doc_ids(self, results: list[SearchResult]) -> list[str]:
        """从检索结果中提取文档 ID 列表

        从每个 SearchResult 的 payload 中读取 document_id 字段。

        Args:
            results: 检索结果列表

        Returns:
            文档 ID 列表（去重）
        """
        doc_ids: list[str] = []
        seen: set[str] = set()
        for r in results:
            payload = r.get("payload", {})
            if isinstance(payload, dict):
                doc_id = payload.get("document_id")
                if doc_id and doc_id not in seen:
                    seen.add(doc_id)
                    doc_ids.append(str(doc_id))
        return doc_ids

    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
        weights: list[float] | None = None,
    ) -> list[SearchResult]:
        """执行缓存优先检索

        缓存优先策略：
        1. 生成查询嵌入向量
        2. 通过嵌入向量查询语义缓存（相似度 > threshold 时命中）
        3. 命中 → 反序列化缓存结果 → 直接返回（不执行检索）
        4. 未命中 → 调用 search_service.search() → 序列化结果 → 写入缓存 → 返回

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件
            weights: 单次查询权重覆盖（可选，传递给检索服务）

        Returns:
            检索结果列表

        Raises:
            ValidationError: 查询文本为空或 Collection 名称为空时
            HybridSearchError: 三路检索通道均失败时
        """
        # 步骤 1: 生成查询嵌入向量
        embedding: list[float] | None = None
        try:
            embedding = await self._embedding_service.embed_query(query_text)
        except Exception as e:
            logger.warning("嵌入生成失败，降级为直接检索: %s", e)
            # 嵌入失败：直接检索，不缓存
            fallback_results: list[SearchResult] = await self._search_service.search(
                collection=collection,
                query_text=query_text,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
                weights=weights,
            )
            return fallback_results

        # 步骤 2: 查询语义缓存
        try:
            start_time = time.monotonic()
            cached = await self._cache.get(embedding, threshold=self._threshold)
            latency = time.monotonic() - start_time

            if cached is not None:
                # 缓存命中
                results = self._deserialize_results(cached)
                if results is not None:
                    # 有效缓存命中
                    if self._metrics:
                        self._metrics.record_cache_hit()
                        self._metrics.record_cache_latency(latency)
                    logger.debug("缓存命中: query=%s, latency=%.2fms", query_text[:50], latency * 1000)
                    return results[:limit]
                else:
                    # 缓存数据损坏，视为未命中
                    logger.warning("缓存数据损坏，跳过该条目: query=%s", query_text[:50])
                    if self._metrics:
                        self._metrics.record_cache_miss()
            else:
                # 缓存未命中
                if self._metrics:
                    self._metrics.record_cache_miss()
                logger.debug("缓存未命中: query=%s", query_text[:50])
        except Exception as e:
            # 缓存查询异常：透明降级
            logger.warning("缓存查询失败，降级为直接检索: %s", e)
            if self._metrics:
                self._metrics.record_cache_miss()

        # 步骤 3: 未命中 → 执行完整检索
        result_list: list[SearchResult] = await self._search_service.search(
            collection=collection,
            query_text=query_text,
            limit=limit,
            tenant_id=tenant_id,
            filter_payload=filter_payload,
            weights=weights,
        )

        # 步骤 4: 自动写入缓存
        if embedding is not None:
            try:
                cache_value = self._serialize_results(result_list, query_text, weights)
                doc_ids = self._extract_doc_ids(result_list)
                await self._cache.set(
                    embedding,
                    cache_value,
                    ttl=self._ttl,
                    doc_ids=doc_ids if doc_ids else None,
                )
                logger.debug("缓存写入成功: query=%s, docs=%d", query_text[:50], len(doc_ids))
            except Exception as e:
                logger.warning("缓存写入失败（不影响检索结果）: %s", e)

        return result_list
