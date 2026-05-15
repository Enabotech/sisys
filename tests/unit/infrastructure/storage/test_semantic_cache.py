"""RedisSemanticCache tests — mock-based for RediSearch FT.SEARCH."""

from __future__ import annotations

import struct
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.semantic_cache import (
    RedisSemanticCache,
    _vector_to_bytes,
    cosine_similarity,
)
from src.infrastructure.utils import json_dumps


def _make_cache(
    metrics_collector: EventMetricsCollector | None = None,
    embedding_dim: int = 3,
) -> tuple[RedisSemanticCache, AsyncMock]:
    """Create SemanticCache with mocked Redis client."""
    mock_redis = AsyncMock()
    cache = RedisSemanticCache(
        redis_client=mock_redis,
        embedding_dim=embedding_dim,
        metrics_collector=metrics_collector,
    )
    return cache, mock_redis


def _ft_search_response(result_json: str | None, distance: float | None) -> list:
    """Build a mock FT.SEARCH response."""
    if result_json is None:
        return [0]
    return [
        1,
        "sisys:cache:semantic:vec:test",
        ["__embedding_score", str(distance), "result", result_json],
    ]


class TestCosineSimilarity:
    """Cosine similarity calculation tests."""

    def test_identical_vectors(self) -> None:
        vec = [1.0, 0.0, 0.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_partial_similarity(self) -> None:
        sim = cosine_similarity([1.0, 0.0], [1.0, 1.0])
        assert sim == pytest.approx(0.7071067811865475, rel=1e-5)

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="dimensions must match"):
            cosine_similarity([1.0, 2.0], [1.0])

    def test_empty_vectors(self) -> None:
        assert cosine_similarity([], []) == 0.0

    def test_zero_vector(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_clamped_result(self) -> None:
        result = cosine_similarity([1e-200], [1e-200])
        assert -1.0 <= result <= 1.0


class TestVectorToBytes:
    """FLOAT32 binary conversion tests."""

    def test_round_trip(self) -> None:
        original = [0.1, 0.2, 0.3]
        packed = _vector_to_bytes(original)
        unpacked = list(struct.unpack(f"<{len(original)}f", packed))
        for orig, unpk in zip(original, unpacked):
            assert orig == pytest.approx(unpk, rel=1e-6)

    def test_output_length(self) -> None:
        vec = [1.0, 2.0, 3.0, 4.0]
        packed = _vector_to_bytes(vec)
        assert len(packed) == 4 * 4  # 4 floats * 4 bytes each


class TestRedisSemanticCache:
    """RedisSemanticCache tests with mocked FT.SEARCH."""

    @pytest.mark.asyncio
    async def test_set_creates_index_and_stores(self) -> None:
        cache, mock_redis = _make_cache()
        mock_redis.execute_command = AsyncMock(return_value="OK")
        mock_redis.hset = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)

        embedding = [0.1, 0.2, 0.3]
        result = {"answer": "test"}
        await cache.set(embedding, result)

        # Should have called FT.CREATE (ensure_index)
        mock_redis.execute_command.assert_called_once()
        call_args = mock_redis.execute_command.call_args[0]
        assert call_args[0] == "FT.CREATE"

        # Should have stored via HSET
        mock_redis.hset.assert_called_once()
        hset_args = mock_redis.hset.call_args
        assert "embedding" in hset_args[1]["mapping"]
        assert "result" in hset_args[1]["mapping"]

    @pytest.mark.asyncio
    async def test_get_hit(self) -> None:
        cache, mock_redis = _make_cache()
        result_data = {"answer": "test"}
        mock_redis.execute_command = AsyncMock(
            return_value=_ft_search_response(json_dumps(result_data), 0.05)
        )

        found = await cache.get([0.1, 0.2, 0.3], threshold=0.9)
        assert found is not None
        assert found["answer"] == "test"

    @pytest.mark.asyncio
    async def test_get_miss_empty(self) -> None:
        cache, mock_redis = _make_cache()
        mock_redis.execute_command = AsyncMock(return_value=[0])

        found = await cache.get([0.1, 0.2, 0.3], threshold=0.9)
        assert found is None

    @pytest.mark.asyncio
    async def test_get_miss_below_threshold(self) -> None:
        cache, mock_redis = _make_cache()
        mock_redis.execute_command = AsyncMock(
            return_value=_ft_search_response(json_dumps({"answer": "test"}), 0.5)
        )

        # threshold=0.9 means max_distance=0.1, distance=0.5 is too far
        found = await cache.get([0.1, 0.2, 0.3], threshold=0.9)
        assert found is None

    @pytest.mark.asyncio
    async def test_invalidate(self) -> None:
        cache, mock_redis = _make_cache()
        mock_redis.execute_command = AsyncMock(return_value="OK")
        mock_redis.delete = AsyncMock(return_value=1)

        await cache.set([0.1, 0.2, 0.3], {"answer": "test"})
        cache_key = cache._build_cache_key([0.1, 0.2, 0.3])
        await cache.invalidate(cache_key)

        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_recording(self) -> None:
        metrics = EventMetricsCollector()

        # Miss
        cache, mock_redis = _make_cache(metrics_collector=metrics)
        mock_redis.execute_command = AsyncMock(return_value=[0])
        await cache.get([0.1], threshold=0.9)
        assert metrics.metrics.cache_misses_total == 1

        # Hit
        mock_redis.execute_command = AsyncMock(
            return_value=_ft_search_response(json_dumps({"result": "value"}), 0.01)
        )
        await cache.get([0.1], threshold=0.9)
        assert metrics.metrics.cache_hits_total == 1

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        cache, _mock_redis = _make_cache()
        async with cache:
            pass

    @pytest.mark.asyncio
    async def test_deterministic_cache_key(self) -> None:
        cache, _mock_redis = _make_cache()
        key1 = cache._build_cache_key([0.1, 0.2, 0.3])
        key2 = cache._build_cache_key([0.1, 0.2, 0.3])
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_index_already_exists_is_ok(self) -> None:
        cache, mock_redis = _make_cache()
        mock_redis.execute_command = AsyncMock(
            side_effect=Exception("Index already exists")
        )
        mock_redis.hset = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)

        await cache.set([0.1, 0.2, 0.3], {"answer": "test"})
        mock_redis.hset.assert_called_once()
