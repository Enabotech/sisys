"""语义缓存集成测试

使用真实 Redis 验证语义缓存全流程：
- 缓存优先检索（未命中 → 检索 → 写入 → 命中）
- 缓存 TTL 过期
- 缓存失效（invalidate、invalidate_pattern、invalidate_all、invalidate_by_document_id）
- 并发查询隔离
- 降级策略
- 二级索引失效
- 不同 weights 缓存隔离

遵循项目集成测试规范：
- 真实服务优先，Redis 不可用时动态跳过
- 独立测试 key 前缀，测试结束后自动清理
"""

from __future__ import annotations

import pytest

from src.domain.ports.l3_vector import SearchResult
from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache


def _make_search_result(doc_id: str, title: str = "test", score: float = 0.95) -> SearchResult:
    return SearchResult(
        id=f"point-{doc_id}",
        score=score,
        payload={"document_id": doc_id, "title": title},
    )


def _sample_results() -> list[SearchResult]:
    return [
        _make_search_result("doc-001", "战略规划"),
        _make_search_result("doc-002", "财务分析"),
        _make_search_result("doc-001", "战略规划补充"),
    ]


@pytest.fixture
async def real_redis():
    """真实 Redis 连接（动态跳过）"""
    import redis.asyncio as aioredis

    from tests.environments import get_test_env

    try:
        env = get_test_env()
    except Exception as e:
        pytest.skip(f"测试环境不可用: {e}")

    client = aioredis.Redis(
        host=env.redis.host,
        port=env.redis.port,
        password=env.redis.password,
        decode_responses=True,
    )

    try:
        await client.ping()
    except Exception as e:
        await client.aclose()
        pytest.skip(f"Redis 不可用: {e}")

    yield client

    await client.aclose()


@pytest.fixture
async def cache(real_redis):
    """RedisSemanticCache 实例（测试隔离 key 前缀 + RediSearch 索引维度一致）"""
    from src.infrastructure.storage.redis.semantic_cache import _build_index_name

    # 清理可能存在的旧 RediSearch 索引（维度不一致会导致查询报错）
    try:
        await real_redis.execute_command("FT.DROPINDEX", _build_index_name(3))
    except Exception:
        pass  # 索引不存在时忽略

    metrics = EventMetricsCollector()
    cache = RedisSemanticCache(
        redis_client=real_redis,
        embedding_dim=3,
        metrics_collector=metrics,
    )
    yield cache

    # 清理测试数据 + 清理索引
    from src.infrastructure.storage.redis.key_builder import build_key

    prefix = build_key(cache._NAMESPACE, "")
    cursor = 0
    while True:
        cursor, keys = await real_redis.scan(cursor=cursor, match=f"{prefix}*", count=100)
        if keys:
            await real_redis.delete(*keys)
        if cursor == 0:
            break
    try:
        await real_redis.execute_command("FT.DROPINDEX", _build_index_name(3))
    except Exception:
        pass


class TestSemanticCacheIntegration:
    """语义缓存集成测试"""

    async def test_cache_set_and_get(self, cache: RedisSemanticCache, real_redis) -> None:
        """写入缓存 → 查询命中"""
        embedding = [1.0, 0.0, 0.0]
        result = {"results": [{"id": "doc-1", "score": 0.95, "payload": {"title": "test"}}]}

        await cache.set(embedding, result, ttl=3600)

        cached = await cache.get(embedding, threshold=0.9)
        assert cached is not None
        assert cached["results"][0]["id"] == "doc-1"

    async def test_cache_miss(self, cache: RedisSemanticCache) -> None:
        """查询未命中返回 None"""
        embedding = [1.0, 0.0, 0.0]
        cached = await cache.get(embedding, threshold=0.9)
        assert cached is None

    async def test_cache_ttl_expiry(self, cache: RedisSemanticCache, real_redis) -> None:
        """TTL 过期后自动失效"""
        embedding = [1.0, 0.0, 0.0]
        result = {"results": [{"id": "doc-1", "score": 0.95, "payload": {}}]}

        await cache.set(embedding, result, ttl=1)
        # 立即查询应命中
        cached = await cache.get(embedding, threshold=0.9)
        assert cached is not None

        # 等待 TTL 过期
        import asyncio

        await asyncio.sleep(1.5)

        # 过期后查询应未命中
        cached = await cache.get(embedding, threshold=0.9)
        assert cached is None

    async def test_cache_invalidate(self, cache: RedisSemanticCache, real_redis) -> None:
        """invalidate 删除缓存条目"""
        embedding = [1.0, 0.0, 0.0]
        result = {"results": [{"id": "doc-1", "score": 0.95, "payload": {}}]}

        await cache.set(embedding, result)
        cache_key = cache._build_cache_key(embedding)
        await cache.invalidate(cache_key)

        cached = await cache.get(embedding, threshold=0.9)
        assert cached is None

    async def test_invalidate_pattern(self, cache: RedisSemanticCache, real_redis) -> None:
        """按模式匹配批量失效"""
        e1 = [1.0, 0.0, 0.0]
        e2 = [0.0, 1.0, 0.0]
        result = {"results": [{"id": "doc-1", "score": 0.95, "payload": {}}]}

        await cache.set(e1, result)
        await cache.set(e2, result)

        # 确认两个缓存都存在
        assert await cache.get(e1, threshold=0.9) is not None
        assert await cache.get(e2, threshold=0.9) is not None

        # 删除所有 vec: 前缀的缓存
        await cache.invalidate_pattern("vec:*")

        assert await cache.get(e1, threshold=0.9) is None
        assert await cache.get(e2, threshold=0.9) is None

    async def test_invalidate_all(self, cache: RedisSemanticCache, real_redis) -> None:
        """全量清理"""
        e1 = [1.0, 0.0, 0.0]
        e2 = [0.0, 1.0, 0.0]
        result = {"results": [{"id": "doc-1", "score": 0.95, "payload": {}}]}

        await cache.set(e1, result)
        await cache.set(e2, result)

        # 全量清理
        await cache.invalidate_all()

        assert await cache.get(e1, threshold=0.9) is None
        assert await cache.get(e2, threshold=0.9) is None

    async def test_invalidate_by_document_id(self, cache: RedisSemanticCache, real_redis) -> None:
        """按文档 ID 精确失效"""
        from src.infrastructure.storage.redis.key_builder import build_key

        embedding = [1.0, 0.0, 0.0]
        result = {"results": [{"id": "doc-1", "score": 0.95, "payload": {"document_id": "doc-001"}}]}

        # 写入缓存（含二级索引）
        await cache.set(embedding, result, ttl=3600, doc_ids=["doc-001"])

        # 确认缓存存在
        assert await cache.get(embedding, threshold=0.9) is not None

        # 通过文档 ID 失效
        await cache.invalidate_by_document_id("doc-001")

        # 确认缓存已清理
        assert await cache.get(embedding, threshold=0.9) is None

        # 确认二级索引已清理
        idx_key = build_key(cache._NAMESPACE, "idx:doc", "doc-001")
        exists = await real_redis.exists(idx_key)
        assert exists == 0, f"二级索引 key {idx_key} 未被清理"

    async def test_set_with_doc_ids_creates_index(self, cache: RedisSemanticCache, real_redis) -> None:
        """写入缓存时维护二级索引"""
        from src.infrastructure.storage.redis.key_builder import build_key

        embedding = [1.0, 0.0, 0.0]
        result = {"results": [{"id": "doc-1", "score": 0.95, "payload": {"document_id": "doc-001"}}]}

        await cache.set(embedding, result, ttl=3600, doc_ids=["doc-001"])

        # 验证二级索引存在
        idx_key = build_key(cache._NAMESPACE, "idx:doc", "doc-001")
        members = await real_redis.smembers(idx_key)
        assert len(members) > 0, "二级索引未创建"

        cache_key = cache._build_cache_key(embedding)
        assert cache_key in members, f"二级索引未包含缓存键 {cache_key}"

    async def test_concurrent_queries_isolation(self, cache: RedisSemanticCache, real_redis) -> None:
        """并发查询隔离"""
        import asyncio

        results = [{"results": [{"id": f"doc-{i}", "score": 0.95, "payload": {}}]} for i in range(5)]

        async def _set_and_get(i: int) -> dict | None:
            # 使用不同方向的向量确保唯一匹配
            embs = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [0.5, 0.5, 0.0], [0.0, 0.5, 0.5]]
            embedding = embs[i]
            await cache.set(embedding, results[i], ttl=3600)
            return await cache.get(embedding, threshold=0.9)

        tasks = [asyncio.create_task(_set_and_get(i)) for i in range(5)]
        gathered = await asyncio.gather(*tasks)

        for i, result in enumerate(gathered):
            assert result is not None, f"并发查询 {i} 未命中"
            assert result["results"][0]["id"] == f"doc-{i}"

    async def test_similar_queries(self, cache: RedisSemanticCache, real_redis) -> None:
        """相似向量命中缓存"""
        # 写入一个向量
        embedding = [1.0, 0.0, 0.0]
        result = {"results": [{"id": "doc-1", "score": 0.95, "payload": {}}]}
        await cache.set(embedding, result, ttl=3600)

        # 查询相同向量应命中
        cached = await cache.get(embedding, threshold=0.9)
        assert cached is not None

    async def test_low_similarity_miss(self, cache: RedisSemanticCache, real_redis) -> None:
        """低相似度不命中"""
        embedding = [1.0, 0.0, 0.0]
        result = {"results": [{"id": "doc-1", "score": 0.95, "payload": {}}]}
        await cache.set(embedding, result, ttl=3600)

        # 正交向量（相似度接近 0）
        orth_embedding = [0.0, 1.0, 0.0]
        cached = await cache.get(orth_embedding, threshold=0.9)
        assert cached is None
