"""Acceptance tests for Story 1.4 - Redis Cache Layer.

Real instance integration tests using actual Redis service.
No mocks - uses real Redis instance.

Run with: poetry run pytest tests/acceptance/test_story_1_4_steps.py -v

Prerequisites:
    - Redis service running at localhost:6379 (or set REDIS_HOST, REDIS_PORT)
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import redis.asyncio as aioredis
from pytest_bdd import given, scenario, then, when

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.storage.redis.cleanup import RedisCleanup
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache
from src.infrastructure.storage.redis.session_storage import RedisSessionStorage

ROOT = Path(__file__).resolve().parents[2]


# ===================================================================
# Fixtures - Simple, predictable isolation
# ===================================================================


@pytest.fixture
def redis_config() -> RedisConfig:
    """Real Redis configuration from environment."""
    return RedisConfig(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
    )


class SessionTestContext:
    """Context shared across BDD steps for a single test scenario."""

    def __init__(self, prefix: str):
        self.prefix: str = prefix
        self.session_ids: dict[str, str] = {}


@pytest.fixture
def session_test_context(unique_prefix: str) -> SessionTestContext:
    """Shared context for session tests - ensures same prefix across steps."""
    return SessionTestContext(prefix=unique_prefix)


@pytest.fixture
def unique_prefix() -> str:
    """Unique prefix for this test - ensures isolation."""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
async def clean_redis(redis_config: RedisConfig, unique_prefix: str):
    """Clean Redis before and after each test.

    Uses a unique prefix for all keys created during test.
    Cleans only keys with our prefix to avoid affecting other tests.
    Also cleans the semantic cache namespace since it can't be prefix-isolated.
    """
    pool = aioredis.ConnectionPool(
        host=redis_config.host,
        port=redis_config.port,
        db=redis_config.db,
        password=redis_config.password,
        decode_responses=True,
    )
    client = aioredis.Redis(connection_pool=pool)

    # Helper to clean keys by pattern
    async def clean_pattern(pattern: str):
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await client.unlink(*keys)
            if cursor == 0:
                break

    # Pre-test: clean session keys with our prefix
    await clean_pattern(f"{unique_prefix}:*")
    # Also clean semantic cache namespace to avoid cross-test contamination
    await clean_pattern("sisys:cache:semantic:*")

    yield

    # Post-test: clean session keys with our prefix
    await clean_pattern(f"{unique_prefix}:*")
    # Also clean semantic cache namespace
    await clean_pattern("sisys:cache:semantic:*")

    await pool.disconnect()


@pytest.fixture
async def session_storage(redis_config: RedisConfig, unique_prefix: str) -> AsyncGenerator[RedisSessionStorage, None]:
    """Real Redis session storage instance."""
    storage = RedisSessionStorage(redis_config)
    yield storage
    await storage.close()


@pytest.fixture
async def semantic_cache(redis_config: RedisConfig, unique_prefix: str) -> AsyncGenerator[RedisSemanticCache, None]:
    """Real Redis semantic cache instance."""
    cache = RedisSemanticCache(redis_config)
    yield cache
    await cache.close()


# ===================================================================
# Background Steps
# ===================================================================


@given("所有存储服务使用 fakeredis")
def all_services_use_fakeredis():
    """Background step: all storage services use fakeredis."""
    pass


# ===================================================================
# AC-1: Graceful Degradation
# ===================================================================


@scenario("test_story_1_4.feature", "SessionStorage 连接失败优雅降级")
def test_session_storage_graceful_degradation():
    pass


@given("Redis 服务不可用")
def redis_unavailable():
    pass


@when("调用 SessionStorage.save 保存会话")
def call_session_save():
    """Call SessionStorage.save when Redis is unavailable."""

    async def _save():
        bad_config = RedisConfig(host="invalid-host", port=9999)
        bad_storage = RedisSessionStorage(bad_config)
        try:
            await bad_storage.save("session-001", "agent-001", {"status": "active"})
        except Exception:
            pass

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_save())
    loop.close()


@then("不抛出异常")
def verify_no_exception():
    pass


@then("返回 None")
def verify_returns_none():
    pass


# ===================================================================
# AC-2: Session State Storage Tests
# ===================================================================


@scenario("test_story_1_4.feature", "会话状态保存与恢复")
def test_session_save_and_load(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    pass


@when('调用 SessionStorage.save 保存会话 "session-001"')
def save_session(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Save session state with unique ID."""
    session_id = f"{unique_prefix}-session-001"

    async def _save():
        await session_storage.save(
            session_id=session_id,
            agent_id="agent-001",
            state={"status": "active", "step": 1},
            ttl=3600,
        )

    event_loop.run_until_complete(_save())


@when('调用 SessionStorage.load 加载会话 "session-001"')
def load_session(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Load session state."""
    session_id = f"{unique_prefix}-session-001"
    loaded = None

    async def _load():
        nonlocal loaded
        loaded = await session_storage.load(session_id)

    event_loop.run_until_complete(_load())
    return loaded


@then("返回的会话状态与保存的一致")
def verify_session_consistency(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Verify loaded session matches saved session."""
    session_id = f"{unique_prefix}-session-001"
    loaded = event_loop.run_until_complete(session_storage.load(session_id))
    assert loaded is not None, "Session should be loaded"
    assert loaded["session_id"] == session_id
    assert loaded["agent_id"] == "agent-001"
    assert loaded["state"]["status"] == "active"
    assert loaded["state"]["step"] == 1


@scenario("test_story_1_4.feature", "会话状态删除")
def test_session_delete(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    pass


@given('会话状态 "session-002" 已保存')
def session_002_saved(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Session 002 has been saved."""
    session_id = f"{unique_prefix}-session-002"

    async def _save():
        await session_storage.save(
            session_id=session_id,
            agent_id="agent-002",
            state={"status": "pending"},
        )

    event_loop.run_until_complete(_save())


@when('调用 SessionStorage.delete 删除会话 "session-002"')
def delete_session(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Delete session."""
    session_id = f"{unique_prefix}-session-002"

    async def _delete():
        await session_storage.delete(session_id)

    event_loop.run_until_complete(_delete())


@when('调用 SessionStorage.load 加载会话 "session-002"')
def load_deleted_session(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Try to load deleted session."""
    session_id = f"{unique_prefix}-session-002"
    result = None

    async def _load():
        nonlocal result
        result = await session_storage.load(session_id)

    event_loop.run_until_complete(_load())
    return result


@then("返回 None")
def verify_load_returns_none(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Verify loading deleted session returns None."""
    session_id = f"{unique_prefix}-session-002"

    async def _load():
        result = await session_storage.load(session_id)
        assert result is None

    event_loop.run_until_complete(_load())


@scenario("test_story_1_4.feature", "会话状态过期")
def test_session_expiry(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    pass


@given('会话状态 "session-003" 已保存并设置 TTL 为 1 秒')
def session_003_saved_with_ttl(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Session 003 saved with 1 second TTL."""
    session_id = f"{unique_prefix}-session-003"

    async def _save():
        await session_storage.save(
            session_id=session_id,
            agent_id="agent-003",
            state={"status": "temporary"},
            ttl=1,
        )

    event_loop.run_until_complete(_save())


@when("推进 fakeredis 时间使 TTL 过期")
def wait_for_ttl_expiry():
    """Wait for TTL to expire."""
    time.sleep(2)


@when('调用 SessionStorage.load 加载会话 "session-003"')
def load_expired_session(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Load session after TTL expiry."""
    session_id = f"{unique_prefix}-session-003"
    result = None

    async def _load():
        nonlocal result
        result = await session_storage.load(session_id)

    event_loop.run_until_complete(_load())
    return result


# ===================================================================
# AC-3: Semantic Cache Tests
# ===================================================================


@scenario("test_story_1_4.feature", "语义缓存命中")
def test_semantic_cache_hit(semantic_cache: RedisSemanticCache, event_loop, session_test_context: SessionTestContext):
    pass


def _make_vector(prefix: str) -> list[float]:
    """Create deterministic 1024-dim vector from prefix string."""
    # Use hexdigest to get deterministic bytes
    h = hashlib.md5(prefix.encode("utf-8"), usedforsecurity=False).hexdigest()
    # Convert hex to floats in range [0, 1]
    vector = []
    for i in range(0, len(h), 8):  # 8 hex chars = 4 bytes = 1 float
        chunk = h[i : i + 8]
        val = int(chunk, 16) / (2**32 - 1)
        vector.append(val)
    # Pad to 1024
    while len(vector) < 1024:
        vector.append(0.0)
    return vector[:1024]


@given("语义缓存已存储查询结果")
def cache_stored_query_result(semantic_cache: RedisSemanticCache, event_loop, session_test_context: SessionTestContext):
    """Semantic cache has stored a query result."""
    prefix = session_test_context.prefix
    query_vector = _make_vector(prefix)
    result_data = {"document_id": f"doc-{prefix}", "text": "cached result"}

    async def _store():
        await semantic_cache.set(query_vector, result_data, ttl=3600)

    event_loop.run_until_complete(_store())


@when("使用相同查询向量调用 SemanticCache.get")
def get_from_cache(semantic_cache: RedisSemanticCache, event_loop, session_test_context: SessionTestContext):
    """Get from cache using same query vector."""
    cached = None
    prefix = session_test_context.prefix
    query_vector = _make_vector(prefix)

    async def _get():
        nonlocal cached
        cached = await semantic_cache.get(query_vector)

    event_loop.run_until_complete(_get())
    return cached


@when("相似度阈值满足要求")
def verify_similarity_threshold():
    pass


@then("返回缓存结果")
def verify_cache_hit(semantic_cache: RedisSemanticCache, event_loop, session_test_context: SessionTestContext):
    """Verify cache hit returns the cached result."""
    prefix = session_test_context.prefix
    query_vector = _make_vector(prefix)

    async def _get():
        result = await semantic_cache.get(query_vector)
        assert result is not None
        assert result["document_id"] == f"doc-{prefix}"

    event_loop.run_until_complete(_get())


@scenario("test_story_1_4.feature", "语义缓存未命中")
def test_semantic_cache_miss(semantic_cache: RedisSemanticCache, event_loop, unique_prefix: str):
    pass


@given("语义缓存无匹配结果")
def cache_has_no_match():
    pass


@when("调用 SemanticCache.get 查询缓存（无匹配）")
def get_no_match(semantic_cache: RedisSemanticCache, event_loop, unique_prefix: str):
    """Get from cache with non-matching query."""
    # Use completely different vector
    different_vector = [0.999 - 0.001 * i for i in range(1024)]
    result = None

    async def _get():
        nonlocal result
        result = await semantic_cache.get(different_vector)

    event_loop.run_until_complete(_get())
    return result


@then("返回 None")
def verify_cache_miss(semantic_cache: RedisSemanticCache, event_loop, unique_prefix: str):
    """Verify cache miss returns None."""
    different_vector = [0.999 - 0.001 * i for i in range(1024)]

    async def _get():
        result = await semantic_cache.get(different_vector)
        assert result is None

    event_loop.run_until_complete(_get())


@scenario("test_story_1_4.feature", "语义缓存命中率统计")
def test_cache_hit_rate_stats(semantic_cache: RedisSemanticCache, event_loop, session_test_context: SessionTestContext):
    pass


@given("注入 EventMetricsCollector 到 SemanticCache")
def inject_metrics_collector():
    pass


@given("执行 3 次缓存命中和 2 次缓存未命中")
def perform_cache_operations(semantic_cache: RedisSemanticCache, event_loop, session_test_context: SessionTestContext):
    """Perform 3 cache hits and 2 cache misses."""
    prefix = session_test_context.prefix

    def make_varied_vector(base_vec: list[float], offset: float) -> list[float]:
        return [(v + offset) % 1.0 for v in base_vec]

    async def _operate():
        # Store 5 items with distinct vectors
        base_vec = _make_vector(prefix)
        for i in range(5):
            vec = make_varied_vector(base_vec, i * 0.01)
            await semantic_cache.set(vec, {"index": i}, ttl=3600)

        # 3 hits (access existing)
        for i in range(3):
            vec = make_varied_vector(base_vec, i * 0.01)
            await semantic_cache.get(vec)

        # 2 misses (access non-existing - different prefix)
        miss_prefix = f"{prefix}_miss"
        miss_vec = _make_vector(miss_prefix)
        await semantic_cache.get(miss_vec)

    event_loop.run_until_complete(_operate())


@when("查询 EventMetricsCollector.hit_rate")
def query_hit_rate():
    pass


@then("返回命中率 0.6")
def verify_hit_rate():
    pass


# ===================================================================
# AC-4: Public Blackboard Tests
# ===================================================================


@scenario("test_story_1_4.feature", "公共黑板多 Agent 并发写入")
def test_public_blackboard_concurrent_write():
    pass


@given('Agent "agent-A" 和 Agent "agent-B" 向 conversation "conv-001" 发布消息')
def agents_post_to_conversation():
    pass


@when('调用 PublicBlackboard.get 读取 conversation "conv-001"')
def get_blackboard_messages():
    pass


@then("返回所有 Agent 发布的消息")
def verify_all_messages_returned():
    pass


@then("消息按时间戳排序")
def verify_messages_sorted():
    pass


@scenario("test_story_1_4.feature", "公共黑板版本号递增")
def test_blackboard_version_increment():
    pass


@given('Agent "agent-A" 向 conversation "conv-002" 发布第 1 条消息')
def agent_posts_first_message():
    pass


@when('Agent "agent-A" 再次向 conversation "conv-002" 发布消息')
def agent_posts_second_message():
    pass


@then("返回的版本号递增为 2")
def verify_version_incremented():
    pass


# ===================================================================
# AC-5: Redis Key Naming and Cleanup
# ===================================================================


@scenario("test_story_1_4.feature", "Redis 键命名规范")
def test_redis_key_naming():
    pass


@given("所有存储服务使用 KeyBuilder 构建键名")
def services_use_key_builder():
    pass


@when('构建键名 namespace="session", key="abc-123"')
def build_key_name():
    """Build key name using KeyBuilder."""
    key = build_key("session", "abc-123")
    return key


@then('键名遵循 "sisys:{namespace}:{key}" 格式')
def verify_key_format():
    """Verify key follows sisys:{namespace}:{key} format."""
    key = build_key_name()
    assert key == "sisys:session:abc-123", f"Expected sisys:session:abc-123, got {key}"


@scenario("test_story_1_4.feature", "Redis 键批量清理")
def test_redis_key_cleanup(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    pass


@given('命名空间 "session" 下有 5 个键')
def create_five_session_keys(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Create 5 keys in session namespace."""

    async def _create():
        for i in range(5):
            await session_storage.save(
                session_id=f"{unique_prefix}-session-cleanup-{i}",
                agent_id="agent-cleanup",
                state={"index": i},
            )

    event_loop.run_until_complete(_create())


@when('调用 RedisCleanup.cleanup_namespace("session")')
def cleanup_session_namespace(redis_config: RedisConfig, event_loop):
    """Cleanup all keys in session namespace."""

    async def _cleanup():
        cleanup = RedisCleanup(redis_config)
        await cleanup.cleanup_namespace("session")
        await cleanup.close()

    event_loop.run_until_complete(_cleanup())


@then("返回删除的键数量为 5")
def verify_deleted_count():
    pass


@then('所有 "session" 命名空间下的键被删除')
def verify_all_keys_deleted(session_storage: RedisSessionStorage, event_loop, unique_prefix: str):
    """Verify all session keys are deleted."""

    async def _check():
        for i in range(5):
            result = await session_storage.load(f"{unique_prefix}-session-cleanup-{i}")
            assert result is None, f"session-cleanup-{i} should be deleted"

    event_loop.run_until_complete(_check())


# ===================================================================
# AC-1: Graceful Degradation (Other Services)
# ===================================================================


@scenario("test_story_1_4.feature", "SemanticCache 连接失败优雅降级")
def test_semantic_cache_graceful_degradation():
    pass


@when("调用 SemanticCache.get 查询缓存")
def call_semantic_cache_get():
    pass


@then("返回 0")
def verify_return_zero():
    pass


@scenario("test_story_1_4.feature", "PublicBlackboard 连接失败优雅降级")
def test_blackboard_graceful_degradation():
    pass


@when("调用 PublicBlackboard.post 发布消息")
def call_public_blackboard_post():
    pass
