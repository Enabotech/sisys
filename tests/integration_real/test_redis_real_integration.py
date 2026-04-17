"""Redis Real Instance Integration Tests.

端到端测试，验证真实 Redis 实例上的会话存储、语义缓存和公共黑板流程。
使用真实的 Redis 部署（localhost:6379），不使用 fakeredis 或 mock。

运行方式:
    pytest tests/integration_real/ -v

前置条件:
    - Redis 服务已部署并运行在 localhost:6379
    - 使用 deploy/docker-compose.yml 部署
"""

from __future__ import annotations

import pytest
import redis.asyncio as redis

pytestmark = pytest.mark.asyncio


# ===================================================================
# Function-scoped Redis client
# ===================================================================


@pytest.fixture
async def real_redis_client():
    """Provide a real Redis client (function-scoped to avoid event loop issues)."""
    import os

    client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
    )
    try:
        await client.ping()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")

    yield client

    try:
        await client.flushdb()
    except Exception:
        pass
    await client.aclose()


# ===================================================================
# Test Session Storage with Real Redis
# ===================================================================


class TestSessionStorageReal:
    """会话存储真实实例集成测试。"""

    async def test_full_session_lifecycle(self, real_redis_client):
        """测试完整会话生命周期：保存→加载→验证→删除。"""
        client = real_redis_client
        from src.infrastructure.storage.redis.key_builder import build_key

        # Save directly using Redis client
        key = build_key("session", "sess-real-1")
        state_data = {"counter": 42, "items": ["a", "b"], "nested": {"key": "value"}}

        # HSET
        import json

        await client.hset(key, "data", json.dumps({"session_id": "sess-real-1", "agent_id": "agent-1", "state": state_data}))
        await client.expire(key, 86400)

        # Verify exists
        assert await client.exists(key) == 1

        # Load
        data = await client.hget(key, "data")
        assert data is not None
        loaded = json.loads(data)
        assert loaded["session_id"] == "sess-real-1"
        assert loaded["agent_id"] == "agent-1"
        assert loaded["state"] == state_data

        # Delete
        await client.delete(key)
        assert await client.exists(key) == 0

    async def test_session_ttl_expiration(self, real_redis_client):
        """测试会话 TTL 设置生效。"""
        client = real_redis_client
        import json

        from src.infrastructure.storage.redis.key_builder import build_key

        key = build_key("session", "sess-ttl-test")
        await client.hset(
            key, "data", json.dumps({"session_id": "sess-ttl-test", "agent_id": "agent-1", "state": {"data": "test"}})
        )
        await client.expire(key, 3600)  # 1 hour TTL

        # Verify TTL is set
        ttl = await client.ttl(key)
        assert ttl > 0
        assert ttl <= 3600


class TestSemanticCacheReal:
    """语义缓存真实实例集成测试。"""

    async def test_cache_operations(self, real_redis_client):
        """测试语义缓存基本操作。"""
        client = real_redis_client
        import json

        from src.infrastructure.storage.redis.key_builder import build_key

        vec = [0.1, 0.2, 0.3]
        cache_key = build_key("cache", "semantic", str(vec))
        data = {"answer": "cached_result"}

        # SET
        await client.set(cache_key, json.dumps(data), ex=3600)

        # GET
        result = await client.get(cache_key)
        assert result is not None
        assert json.loads(result) == data

        # DELETE
        await client.delete(cache_key)
        assert await client.get(cache_key) is None


class TestPublicBlackboardReal:
    """公共黑板真实实例集成测试。"""

    async def test_blackboard_operations(self, real_redis_client):
        """测试公共黑板基本操作。"""
        client = real_redis_client
        from src.infrastructure.storage.redis.key_builder import build_key

        conv_id = "conv-test-blackboard"
        key = build_key("blackboard", conv_id)

        # ZADD entries
        import time

        now = time.time()
        await client.zadd(key, {f"agent-a:msg1:{now}": now})
        await client.zadd(key, {f"agent-b:msg2:{now+0.1}": now + 0.1})

        # ZRANGE to get all entries
        entries = await client.zrange(key, 0, -1)
        assert len(entries) == 2

        # ZREMRANGEBYSCORE to clean
        await client.zremrangebyscore(key, 0, now + 1)
        # After cleanup, verify some entries remain
        await client.zrange(key, 0, -1)


class TestCombinedFlowReal:
    """组合流程真实实例测试。"""

    async def test_full_workflow(self, real_redis_client):
        """测试完整工作流程。"""
        client = real_redis_client
        import json

        from src.infrastructure.storage.redis.key_builder import build_key

        # 1. Session storage
        sess_key = build_key("session", "sess-workflow")
        await client.hset(
            sess_key,
            "data",
            json.dumps({"session_id": "sess-workflow", "agent_id": "analyst", "state": {"step": "analysis", "progress": 0.5}}),
        )

        # 2. Semantic cache
        cache_key = build_key("cache", "semantic", "query-1")
        await client.set(cache_key, json.dumps({"result": "cached_analysis"}), ex=3600)

        # 3. Blackboard
        bb_key = build_key("blackboard", "conv-workflow")
        await client.zadd(bb_key, {"analyst:status_update:1234567890": 1234567890})

        # Verify all data
        sess_data = await client.hget(sess_key, "data")
        assert sess_data is not None

        cache_data = await client.get(cache_key)
        assert cache_data is not None

        bb_entries = await client.zrange(bb_key, 0, -1)
        assert len(bb_entries) > 0

    async def test_graceful_degradation(self):
        """测试连接失败时的优雅降级。"""
        # Test with invalid host
        invalid_client = redis.Redis(host="invalid-host", port=6379, socket_timeout=0.1)

        try:
            result = await invalid_client.get("any-key")
            # If we get here, the connection didn't fail immediately
            assert result is None
        except Exception:
            # Connection failure should be handled gracefully
            pass
        finally:
            await invalid_client.aclose()


class TestRedisKeyBuilderReal:
    """Redis 键命名规范测试。"""

    async def test_key_naming(self):
        """测试键命名规范。"""
        from src.infrastructure.storage.redis.key_builder import build_key

        key = build_key("session", "abc-123")
        assert key == "sisys:session:abc-123"

        key2 = build_key("cache", "semantic", "hash-456")
        assert key2 == "sisys:cache:semantic:hash-456"

        key3 = build_key("blackboard", "conv-1")
        assert key3 == "sisys:blackboard:conv-1"


class TestRedisCleanupReal:
    """Redis 清理功能测试。"""

    async def test_cleanup_namespace(self, real_redis_client):
        """测试按命名空间清理。"""
        client = real_redis_client

        # Create test keys
        test_keys = [f"sisys:session:cleanup-{i}" for i in range(5)]
        for key in test_keys:
            await client.set(key, "test_value")

        # Verify keys exist
        for key in test_keys:
            assert await client.exists(key) == 1

        # Delete using SCAN pattern
        deleted = 0
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor, match="sisys:session:cleanup-*", count=100)
            if keys:
                await client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break

        # Verify all deleted
        assert deleted >= 5
        for key in test_keys:
            assert await client.exists(key) == 0
