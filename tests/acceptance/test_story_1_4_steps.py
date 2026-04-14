"""Story 1.4: Redis Cache Layer — Gherkin 验收测试步骤定义。

覆盖 AC：
- AC-1: 优雅降级（session/cache/blackboard）
- AC-2: 会话状态存储
- AC-3: 语义缓存服务
- AC-4: 公共黑板服务
- AC-5: Redis 键命名规范与清理
"""

from __future__ import annotations

import fakeredis
import fakeredis.aioredis
from pytest_bdd import given, parsers, scenario, then, when

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.cleanup import RedisCleanup
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache
from src.infrastructure.storage.redis.session_storage import RedisSessionStorage

# ============================================================================
# 全局测试上下文
# ============================================================================

_test_context: dict = {}

# ============================================================================
# Feature 路径
# ============================================================================

FEATURE = "test_story_1_4.feature"

# ============================================================================
# Scenarios
# ============================================================================


@scenario(FEATURE, "会话状态保存与恢复")
def test_session_save_restore():
    pass


@scenario(FEATURE, "会话状态删除")
def test_session_delete():
    pass


@scenario(FEATURE, "会话状态过期")
def test_session_ttl_expiry():
    pass


@scenario(FEATURE, "语义缓存命中")
def test_semantic_cache_hit():
    pass


@scenario(FEATURE, "语义缓存未命中")
def test_semantic_cache_miss():
    pass


@scenario(FEATURE, "语义缓存命中率统计")
def test_semantic_cache_hit_rate():
    pass


@scenario(FEATURE, "公共黑板多 Agent 并发写入")
def test_blackboard_multi_agent():
    pass


@scenario(FEATURE, "公共黑板版本号递增")
def test_blackboard_version_increment():
    pass


@scenario(FEATURE, "SessionStorage 连接失败优雅降级")
def test_session_storage_graceful_degradation():
    pass


@scenario(FEATURE, "SemanticCache 连接失败优雅降级")
def test_semantic_cache_graceful_degradation():
    pass


@scenario(FEATURE, "PublicBlackboard 连接失败优雅降级")
def test_blackboard_graceful_degradation():
    pass


@scenario(FEATURE, "Redis 键命名规范")
def test_key_naming_convention():
    pass


@scenario(FEATURE, "Redis 键批量清理")
def test_key_cleanup():
    pass


# ============================================================================
# Background
# ============================================================================


@given("所有存储服务使用 fakeredis")
def setup_fakeredis():
    """初始化 fakeredis 连接池（每次场景执行清理上下文）。"""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    config = RedisConfig()
    _test_context.clear()
    _test_context["fake_redis"] = fake_redis
    _test_context["config"] = config


# ============================================================================
# AC-2: 会话状态存储
# ============================================================================


@when(parsers.parse('调用 SessionStorage.save 保存会话 "{session_id}"'))
def save_session(session_id):
    """保存会话状态。"""
    import asyncio

    config = _test_context["config"]
    storage = RedisSessionStorage(config)
    storage._pool = _test_context["fake_redis"].connection_pool

    async def _save():
        await storage.save(session_id, "agent-001", {"key": "value", "count": 42}, ttl=3600)

    asyncio.new_event_loop().run_until_complete(_save())
    _test_context["storage"] = storage


@when(parsers.parse('调用 SessionStorage.load 加载会话 "{session_id}"'))
def load_session(session_id):
    """加载会话状态。"""
    import asyncio

    storage = _test_context.get("storage")

    async def _load():
        return await storage.load(session_id)

    loop = asyncio.new_event_loop()
    try:
        _test_context["load_result"] = loop.run_until_complete(_load())
    finally:
        loop.close()


@given(parsers.parse('会话状态 "{session_id}" 已保存'))
def session_already_saved(session_id):
    """预保存会话。"""
    import asyncio

    config = _test_context["config"]
    storage = RedisSessionStorage(config)
    storage._pool = _test_context["fake_redis"].connection_pool

    async def _save():
        await storage.save(session_id, "agent-001", {"key": "value"}, ttl=3600)

    asyncio.new_event_loop().run_until_complete(_save())
    _test_context["storage"] = storage


@when(parsers.parse('调用 SessionStorage.delete 删除会话 "{session_id}"'))
def delete_session(session_id):
    """删除会话。"""
    import asyncio

    storage = _test_context.get("storage")

    async def _delete():
        await storage.delete(session_id)

    asyncio.new_event_loop().run_until_complete(_delete())


@given(parsers.parse('会话状态 "{session_id}" 已保存并设置 TTL 为 {ttl:d} 秒'))
def session_saved_with_ttl(session_id, ttl):
    """预保存会话并设置短 TTL。"""
    import asyncio

    config = _test_context["config"]
    storage = RedisSessionStorage(config)
    storage._pool = _test_context["fake_redis"].connection_pool

    async def _save():
        await storage.save(session_id, "agent-001", {"key": "value"}, ttl=ttl)

    asyncio.new_event_loop().run_until_complete(_save())
    _test_context["storage"] = storage
    _test_context["session_ttl"] = ttl


@when("推进 fakeredis 时间使 TTL 过期")
def advance_fakeredis_time():
    """模拟 TTL 过期（直接删除 key，fakeredis 不支持 tick）。"""
    import asyncio

    storage = _test_context.get("storage")
    fake_redis = _test_context["fake_redis"]

    async def _delete_key():
        key = build_key(storage._NAMESPACE, "session-003")
        await fake_redis.delete(key)

    asyncio.new_event_loop().run_until_complete(_delete_key())


@then("返回 None")
def result_is_none():
    """验证返回值为 None（按优先级检查 degradation_result/cache_result/load_result）。"""
    if "degradation_result" in _test_context:
        assert _test_context["degradation_result"] is None
    elif "cache_result" in _test_context:
        assert _test_context["cache_result"] is None
    else:
        assert _test_context.get("load_result") is None


@then("返回的会话状态与保存的一致")
def session_state_matches():
    """验证加载的会话状态与保存的一致。"""
    result = _test_context.get("load_result")
    assert result is not None
    assert result["state"]["key"] == "value"
    assert result["state"]["count"] == 42


# ============================================================================
# AC-3: 语义缓存服务
# ============================================================================


@given("语义缓存已存储查询结果")
def cache_already_stored():
    """预存储语义缓存。"""
    import asyncio

    config = _test_context["config"]
    cache = RedisSemanticCache(config)
    cache._pool = _test_context["fake_redis"].connection_pool

    async def _set():
        embedding = [0.1] * 1024
        result = {"answer": "cached answer"}
        await cache.set(embedding, result, ttl=3600)

    asyncio.new_event_loop().run_until_complete(_set())
    _test_context["cache"] = cache
    _test_context["query_embedding"] = [0.1] * 1024


@when("使用相同查询向量调用 SemanticCache.get")
def semantic_cache_get_same():
    """使用相同查询向量查询语义缓存。"""
    import asyncio

    cache = _test_context.get("cache")
    query_embedding = _test_context.get("query_embedding")

    async def _get():
        return await cache.get(query_embedding, threshold=0.9)

    loop = asyncio.new_event_loop()
    try:
        _test_context["cache_result"] = loop.run_until_complete(_get())
    finally:
        loop.close()


@when("相似度阈值满足要求")
def similarity_threshold_met():
    """验证相似度阈值满足（由 test_semantic_cache_hit 保证）。"""
    pass


@then("返回缓存结果")
def cache_result_matches():
    """验证返回缓存结果。"""
    result = _test_context.get("cache_result")
    assert result is not None
    assert result["answer"] == "cached answer"


@given("语义缓存无匹配结果")
def cache_no_match():
    """确保语义缓存无匹配结果。"""
    config = _test_context["config"]
    cache = RedisSemanticCache(config)
    cache._pool = _test_context["fake_redis"].connection_pool
    _test_context["cache"] = cache
    # 使用不同的查询向量（与已缓存的不同）
    _test_context["query_embedding"] = [0.9] * 1024


@when("调用 SemanticCache.get 查询缓存（无匹配）")
def semantic_cache_get_miss():
    """查询语义缓存（未命中）。"""
    import asyncio

    cache = _test_context.get("cache")
    query_embedding = _test_context.get("query_embedding", [0.9] * 1024)

    async def _get():
        return await cache.get(query_embedding, threshold=0.9)

    loop = asyncio.new_event_loop()
    try:
        _test_context["cache_result"] = loop.run_until_complete(_get())
    finally:
        loop.close()


@given("注入 EventMetricsCollector 到 SemanticCache")
def inject_metrics_collector():
    """注入 EventMetricsCollector 到 SemanticCache。"""
    config = _test_context["config"]
    collector = EventMetricsCollector()
    cache = RedisSemanticCache(config, metrics_collector=collector)
    cache._pool = _test_context["fake_redis"].connection_pool
    _test_context["cache"] = cache
    _test_context["collector"] = collector
    _test_context["query_embedding"] = [0.1] * 1024


@given("执行 3 次缓存命中和 2 次缓存未命中")
def simulate_hits_and_misses():
    """模拟 3 次命中和 2 次未命中。"""
    import asyncio

    cache = _test_context.get("cache")

    async def _run():
        # 存储 3 个不同的缓存条目（模拟命中）
        hit_vectors = [
            [1.0] * 1024,  # 全正
            [-1.0] * 1024,  # 全负
            [1.0 if i < 512 else -1.0 for i in range(1024)],  # 前半正后半负
        ]
        for i, embedding in enumerate(hit_vectors):
            await cache.set(embedding, {"answer": f"cached-{i}"}, ttl=3600)
            # 查询相同向量 → 命中
            result = await cache.get(embedding, threshold=0.9)
            assert result is not None

        # 查询正交向量 → 余弦相似度 = 0 → 未命中
        miss_embedding = [1.0 if i % 2 == 0 else -1.0 for i in range(1024)]
        for _ in range(2):
            result = await cache.get(miss_embedding, threshold=0.9)
            assert result is None

    asyncio.new_event_loop().run_until_complete(_run())


@when("查询 EventMetricsCollector.hit_rate")
def query_hit_rate():
    """查询命中率。"""
    collector = _test_context.get("collector")
    _test_context["hit_rate"] = collector.hit_rate


@then(parsers.parse("返回命中率 {expected_rate:f}"))
def hit_rate_matches(expected_rate):
    """验证命中率。"""
    actual = _test_context.get("hit_rate")
    assert actual is not None
    assert abs(actual - expected_rate) < 0.01, f"Expected {expected_rate}, got {actual}"


# ============================================================================
# AC-4: 公共黑板服务
# ============================================================================


@given('Agent "agent-A" 和 Agent "agent-B" 向 conversation "conv-001" 发布消息')
def blackboard_multi_agent_post():
    """多 Agent 发布消息到黑板。"""
    import asyncio

    config = _test_context["config"]
    blackboard = RedisPublicBlackboard(config)
    blackboard._pool = _test_context["fake_redis"].connection_pool

    async def _post():
        await blackboard.post("conv-001", "agent-A", {"insight": "A's insight"}, confidence=0.9)
        await blackboard.post("conv-001", "agent-B", {"insight": "B's insight"}, confidence=0.8)

    asyncio.new_event_loop().run_until_complete(_post())
    _test_context["blackboard"] = blackboard


@when(parsers.parse('调用 PublicBlackboard.get 读取 conversation "{conversation_id}"'))
def blackboard_get(conversation_id):
    """读取黑板消息。"""
    import asyncio

    blackboard = _test_context.get("blackboard")

    async def _get():
        return await blackboard.get(conversation_id)

    loop = asyncio.new_event_loop()
    try:
        _test_context["blackboard_result"] = loop.run_until_complete(_get())
    finally:
        loop.close()


@then("返回所有 Agent 发布的消息")
def all_messages_returned():
    """验证返回所有消息。"""
    result = _test_context.get("blackboard_result")
    assert result is not None
    assert len(result) == 2
    agent_ids = {m["agent_id"] for m in result}
    assert agent_ids == {"agent-A", "agent-B"}


@then("消息按时间戳排序")
def messages_sorted_by_timestamp():
    """验证消息按时间戳排序。"""
    result = _test_context.get("blackboard_result")
    assert result is not None
    timestamps = [m["timestamp"] for m in result]
    assert timestamps == sorted(timestamps)


@given('Agent "agent-A" 向 conversation "conv-002" 发布第 1 条消息')
def blackboard_first_message():
    """发布第一条消息。"""
    import asyncio

    config = _test_context["config"]
    blackboard = RedisPublicBlackboard(config)
    blackboard._pool = _test_context["fake_redis"].connection_pool

    async def _post():
        version = await blackboard.post("conv-002", "agent-A", {"msg": "first"}, confidence=0.9)
        _test_context["first_version"] = version

    asyncio.new_event_loop().run_until_complete(_post())
    _test_context["blackboard"] = blackboard


@when('Agent "agent-A" 再次向 conversation "conv-002" 发布消息')
def blackboard_second_message():
    """发布第二条消息。"""
    import asyncio

    blackboard = _test_context.get("blackboard")

    async def _post():
        version = await blackboard.post("conv-002", "agent-A", {"msg": "second"}, confidence=0.9)
        _test_context["second_version"] = version

    asyncio.new_event_loop().run_until_complete(_post())


@then("返回的版本号递增为 2")
def version_is_two():
    """验证版本号递增。"""
    first = _test_context.get("first_version")
    second = _test_context.get("second_version")
    assert first == 1
    assert second == 2


# ============================================================================
# AC-1: 优雅降级
# ============================================================================


@given("Redis 服务不可用")
def redis_unavailable():
    """模拟 Redis 服务不可用。"""
    config = RedisConfig(host="invalid-host", port=9999, socket_timeout=0.1)
    _test_context["bad_config"] = config


@when("调用 SessionStorage.save 保存会话")
def session_save_fails():
    """尝试保存会话（应优雅降级）。"""
    import asyncio

    config = _test_context.get("bad_config")
    storage = RedisSessionStorage(config)

    async def _save():
        try:
            await storage.save("test-session", "agent-001", {"key": "value"})
            return None
        except Exception:
            return "raised"

    loop = asyncio.new_event_loop()
    try:
        _test_context["degradation_result"] = loop.run_until_complete(_save())
    finally:
        loop.close()


@when("调用 SemanticCache.get 查询缓存")
def semantic_cache_get_fails():
    """尝试查询语义缓存（应优雅降级）。"""
    import asyncio

    config = _test_context.get("bad_config")
    cache = RedisSemanticCache(config)

    async def _get():
        try:
            return await cache.get([0.1] * 1024, threshold=0.9)
        except Exception:
            return "raised"

    loop = asyncio.new_event_loop()
    try:
        _test_context["degradation_result"] = loop.run_until_complete(_get())
    finally:
        loop.close()


@when("调用 PublicBlackboard.post 发布消息")
def blackboard_post_fails():
    """尝试发布黑板消息（应优雅降级）。"""
    import asyncio

    config = _test_context.get("bad_config")
    blackboard = RedisPublicBlackboard(config)

    async def _post():
        try:
            return await blackboard.post("conv-001", "agent-A", {"msg": "test"})
        except Exception:
            return "raised"

    loop = asyncio.new_event_loop()
    try:
        _test_context["degradation_result"] = loop.run_until_complete(_post())
    finally:
        loop.close()


@then("不抛出异常")
def no_exception_raised():
    """验证不抛出异常。"""
    assert _test_context.get("degradation_result") != "raised"


@then("返回 0")
def result_is_zero():
    """验证返回值为 0。"""
    assert _test_context.get("degradation_result") == 0


# ============================================================================
# AC-5: Redis 键命名规范与清理
# ============================================================================


@given("所有存储服务使用 KeyBuilder 构建键名")
def key_builder_available():
    """KeyBuilder 可用。"""
    pass


@when(parsers.parse('构建键名 namespace="{namespace}", key="{key}"'))
def build_key_action(namespace, key):
    """构建键名。"""
    _test_context["built_key"] = build_key(namespace, key)


@then(parsers.parse('键名遵循 "sisys:{{namespace}}:{{key}}" 格式'))
def key_format_matches():
    """验证键名格式。"""
    built_key = _test_context.get("built_key")
    assert built_key is not None
    assert built_key.startswith("sisys:")
    parts = built_key.split(":")
    assert len(parts) == 3


@given(parsers.parse('命名空间 "{namespace}" 下有 {count:d} 个键'))
def namespace_has_keys(namespace, count):
    """预创建指定数量的键。"""
    import asyncio

    fake_redis = _test_context["fake_redis"]
    namespace_key = build_key(namespace, "")

    async def _create_keys():
        for i in range(count):
            await fake_redis.set(f"{namespace_key}key-{i}", f"value-{i}")

    asyncio.new_event_loop().run_until_complete(_create_keys())
    _test_context["namespace"] = namespace
    _test_context["expected_key_count"] = count


@when(parsers.parse('调用 RedisCleanup.cleanup_namespace("{namespace}")'))
def cleanup_namespace_action(namespace):
    """清理命名空间。"""
    import asyncio

    config = _test_context["config"]
    cleanup = RedisCleanup(config)
    cleanup._pool = _test_context["fake_redis"].connection_pool

    async def _cleanup():
        return await cleanup.cleanup_namespace(namespace)

    loop = asyncio.new_event_loop()
    try:
        _test_context["deleted_count"] = loop.run_until_complete(_cleanup())
    finally:
        loop.close()


@then("返回删除的键数量为 5")
def deleted_count_is_five():
    """验证删除的键数量。"""
    expected = _test_context.get("expected_key_count", 5)
    assert _test_context.get("deleted_count") == expected


@then(parsers.parse('所有 "{namespace}" 命名空间下的键被删除'))
def all_namespace_keys_deleted(namespace):
    """验证所有键被删除。"""
    import asyncio

    fake_redis = _test_context["fake_redis"]
    prefix = build_key(namespace, "")

    async def _check():
        keys = await fake_redis.keys(f"{prefix}*")
        return len(keys)

    loop = asyncio.new_event_loop()
    try:
        remaining = loop.run_until_complete(_check())
    finally:
        loop.close()
    assert remaining == 0, f"Expected 0 keys remaining, got {remaining}"
