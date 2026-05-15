"""Redis 基础设施层性能基准测试 — Story 1.4 AC 验证。

验证 Story 1.4 定义的性能指标：
- 序列化/反序列化时间 <10ms
- 读取延迟 P95 <5ms
- 写入延迟 P95 <10ms
"""

from __future__ import annotations

import statistics
import time
import uuid
from datetime import datetime

import fakeredis
import fakeredis.aioredis
import pytest

from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache, cosine_similarity
from src.infrastructure.storage.redis.session_storage import RedisSessionStorage
from src.infrastructure.utils.json_ser import json_dumps, json_loads

# ============================================================================
# 性能基准配置
# ============================================================================

BENCHMARK_ITERATIONS = 100
PERF_THRESHOLDS = {
    "serialize_ms": 10,
    "deserialize_ms": 10,
    "read_p95_ms": 5,
    "write_p95_ms": 10,
}


def _percentile(values: list[float], p: float) -> float:
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * p / 100.0)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


def _make_session_data() -> dict:
    return {
        "session_id": str(uuid.uuid4()),
        "agent_id": "ceo-agent-001",
        "state": {
            "conversation": [
                {"role": "user", "content": "分析当前市场趋势", "timestamp": datetime.now().isoformat()} for _ in range(20)
            ],
            "context": {"temperature": 0.7, "max_tokens": 4096, "model": "gpt-4"},
            "metadata": {"created_at": datetime.now().isoformat(), "user_id": str(uuid.uuid4())},
        },
    }


def _make_cache_entry() -> tuple[list[float], dict]:
    embedding = [0.1 * (i % 10) for i in range(1024)]
    result = {
        "answer": "市场趋势显示增长...",
        "sources": [{"doc_id": str(uuid.uuid4()), "chunk_id": str(uuid.uuid4())} for _ in range(5)],
        "confidence": 0.92,
    }
    return embedding, result


def _make_blackboard_entry() -> dict:
    return {
        "conversation_id": str(uuid.uuid4()),
        "agent_id": "analyst-agent-001",
        "content": {"insight": "发现市场机会", "data": {"market_size": 1000000, "growth_rate": 0.15}},
        "confidence": 0.85,
        "citations": [f"doc-{i}" for i in range(3)],
    }


# ============================================================================
# AC-1: 序列化/反序列化性能 <10ms
# ============================================================================


class TestSerializationPerformance:
    """验证序列化/反序列化时间 <10ms。"""

    def test_session_serialize_deserialize_under_10ms(self) -> None:
        data = _make_session_data()
        serialize_times: list[float] = []
        deserialize_times: list[float] = []

        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            serialized = json_dumps(data)
            serialize_times.append((time.perf_counter() - start) * 1000)

            start = time.perf_counter()
            json_loads(serialized)
            deserialize_times.append((time.perf_counter() - start) * 1000)

        assert statistics.mean(serialize_times) < PERF_THRESHOLDS["serialize_ms"]
        assert statistics.mean(deserialize_times) < PERF_THRESHOLDS["deserialize_ms"]
        assert _percentile(serialize_times, 95) < PERF_THRESHOLDS["serialize_ms"]
        assert _percentile(deserialize_times, 95) < PERF_THRESHOLDS["deserialize_ms"]

    def test_cache_serialize_deserialize_under_10ms(self) -> None:
        embedding, result = _make_cache_entry()
        data = {"embedding": embedding, "result": result}
        times: list[float] = []
        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            _ = json_loads(json_dumps(data))
            times.append((time.perf_counter() - start) * 1000)
        assert statistics.mean(times) < PERF_THRESHOLDS["serialize_ms"]

    def test_blackboard_serialize_deserialize_under_10ms(self) -> None:
        data = _make_blackboard_entry()
        times: list[float] = []
        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            _ = json_loads(json_dumps(data))
            times.append((time.perf_counter() - start) * 1000)
        assert statistics.mean(times) < PERF_THRESHOLDS["serialize_ms"]

    def test_json_encoder_handles_special_types(self) -> None:
        from enum import Enum

        class Status(Enum):
            ACTIVE = "active"

        data = {
            "created_at": datetime(2024, 1, 1, 12, 0, 0),
            "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "status": Status.ACTIVE,
            "data": b"hello world",
            "tags": {"tag1", "tag2", "tag3"},
        }
        deserialized = json_loads(json_dumps(data))
        assert deserialized["created_at"] == "2024-01-01T12:00:00"
        assert deserialized["id"] == "12345678-1234-5678-1234-567812345678"
        assert deserialized["status"] == "active"
        assert deserialized["data"] == "hello world"
        assert deserialized["tags"] == ["tag1", "tag2", "tag3"]


# ============================================================================
# AC-2: 读取延迟 P95 <5ms
# ============================================================================


class TestReadLatencyPerformance:
    """验证读取延迟 P95 <5ms。"""

    @pytest.mark.asyncio
    async def test_session_read_latency_p95_under_5ms(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = RedisSessionStorage(redis_client=fake_redis)

        session_id = str(uuid.uuid4())
        data = _make_session_data()
        await storage.save(session_id, data["agent_id"], data["state"], ttl=3600)

        latencies: list[float] = []
        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            await storage.load(session_id)
            latencies.append((time.perf_counter() - start) * 1000)

        assert statistics.mean(latencies) < PERF_THRESHOLDS["read_p95_ms"]
        assert _percentile(latencies, 95) < PERF_THRESHOLDS["read_p95_ms"]

    @pytest.mark.asyncio
    async def test_blackboard_read_latency_p95_under_5ms(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        blackboard = RedisPublicBlackboard(redis_client=fake_redis)

        conversation_id = str(uuid.uuid4())
        entry = _make_blackboard_entry()
        await blackboard.post(
            conversation_id=conversation_id,
            agent_id=entry["agent_id"],
            content=entry["content"],
            confidence=entry["confidence"],
            citations=entry["citations"],
        )

        latencies: list[float] = []
        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            await blackboard.get(conversation_id)
            latencies.append((time.perf_counter() - start) * 1000)

        assert statistics.mean(latencies) < PERF_THRESHOLDS["read_p95_ms"]
        assert _percentile(latencies, 95) < PERF_THRESHOLDS["read_p95_ms"]


# ============================================================================
# AC-3: 写入延迟 P95 <10ms
# ============================================================================


class TestWriteLatencyPerformance:
    """验证写入延迟 P95 <10ms。"""

    @pytest.mark.asyncio
    async def test_session_write_latency_p95_under_10ms(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = RedisSessionStorage(redis_client=fake_redis)

        latencies: list[float] = []
        for _ in range(BENCHMARK_ITERATIONS):
            session_id = str(uuid.uuid4())
            data = _make_session_data()
            start = time.perf_counter()
            await storage.save(session_id, data["agent_id"], data["state"], ttl=3600)
            latencies.append((time.perf_counter() - start) * 1000)

        assert statistics.mean(latencies) < PERF_THRESHOLDS["write_p95_ms"]
        assert _percentile(latencies, 95) < PERF_THRESHOLDS["write_p95_ms"]

    @pytest.mark.asyncio
    async def test_blackboard_write_latency_p95_under_10ms(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        blackboard = RedisPublicBlackboard(redis_client=fake_redis)

        latencies: list[float] = []
        conversation_id = str(uuid.uuid4())
        for _ in range(BENCHMARK_ITERATIONS):
            entry = _make_blackboard_entry()
            start = time.perf_counter()
            await blackboard.post(
                conversation_id=conversation_id,
                agent_id=entry["agent_id"],
                content=entry["content"],
                confidence=entry["confidence"],
                citations=entry["citations"],
            )
            latencies.append((time.perf_counter() - start) * 1000)

        assert statistics.mean(latencies) < PERF_THRESHOLDS["write_p95_ms"]
        assert _percentile(latencies, 95) < PERF_THRESHOLDS["write_p95_ms"]

    @pytest.mark.asyncio
    async def test_cache_set_latency_p95_under_10ms(self) -> None:

        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        original_execute = fake_redis.execute_command

        async def _mock_execute(*args, **kwargs):
            if args and args[0] == "FT.CREATE":
                return "OK"
            return await original_execute(*args, **kwargs)

        fake_redis.execute_command = _mock_execute
        cache = RedisSemanticCache(redis_client=fake_redis, embedding_dim=1024)

        latencies: list[float] = []
        for _ in range(BENCHMARK_ITERATIONS):
            embedding, result = _make_cache_entry()
            start = time.perf_counter()
            await cache.set(embedding, result, ttl=86400)
            latencies.append((time.perf_counter() - start) * 1000)

        assert statistics.mean(latencies) < PERF_THRESHOLDS["write_p95_ms"]
        assert _percentile(latencies, 95) < PERF_THRESHOLDS["write_p95_ms"]


# ============================================================================
# AC-4: TTL 验证
# ============================================================================


class TestTTLBehavior:
    """验证 TTL 过期策略。"""

    @pytest.mark.asyncio
    async def test_session_ttl_is_applied(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        storage = RedisSessionStorage(redis_client=fake_redis)

        await storage.save("test-ttl-session", "agent-1", {"key": "value"}, ttl=60)
        ttl = await fake_redis.ttl(build_key(storage._NAMESPACE, "test-ttl-session"))
        assert 0 < ttl <= 60

    @pytest.mark.asyncio
    async def test_cache_ttl_is_applied(self) -> None:

        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        original_execute = fake_redis.execute_command

        async def _mock_execute(*args, **kwargs):
            if args and args[0] == "FT.CREATE":
                return "OK"
            return await original_execute(*args, **kwargs)

        fake_redis.execute_command = _mock_execute
        cache = RedisSemanticCache(redis_client=fake_redis, embedding_dim=1024)

        await cache.set([0.1] * 1024, {"answer": "test"}, ttl=3600)
        keys = await fake_redis.keys("sisys:cache:semantic:vec:*")
        assert len(keys) >= 1
        ttl = await fake_redis.ttl(keys[0])
        assert 0 < int(ttl) <= 3600


# ============================================================================
# AC-5: 余弦相似度性能
# ============================================================================


class TestCosineSimilarityPerformance:
    """验证余弦相似度计算性能。"""

    def test_cosine_similarity_under_1ms_for_1024_dim(self) -> None:
        vec1 = [0.1 * (i % 10) for i in range(1024)]
        vec2 = [0.2 * (i % 5) for i in range(1024)]
        times: list[float] = []
        for _ in range(BENCHMARK_ITERATIONS):
            start = time.perf_counter()
            cosine_similarity(vec1, vec2)
            times.append((time.perf_counter() - start) * 1000)
        assert statistics.mean(times) < 1.0
