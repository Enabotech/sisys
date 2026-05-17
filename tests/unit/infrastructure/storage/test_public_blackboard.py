"""RedisPublicBlackboard tests using fakeredis."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard


def _create_blackboard(fake_redis: fakeredis.aioredis.FakeRedis) -> RedisPublicBlackboard:
    """Create PublicBlackboard using fake Redis client."""
    return RedisPublicBlackboard(redis_client=fake_redis)


class TestRedisPublicBlackboard:
    """RedisPublicBlackboard 测试"""

    @pytest.mark.asyncio
    async def test_post_and_get(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        version = await board.post("conv-1", "agent-1", {"data": "value"})
        assert version == 1

        entries = await board.get("conv-1")
        assert len(entries) == 1
        assert entries[0]["content"] == {"data": "value"}
        assert entries[0]["agent_id"] == "agent-1"

    @pytest.mark.asyncio
    async def test_get_empty_conversation(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        entries = await board.get("conv-1")
        assert entries == []

    @pytest.mark.asyncio
    async def test_get_by_agent(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        await board.post("conv-1", "agent-1", {"data": "first"})
        await board.post("conv-1", "agent-1", {"data": "second"})
        await board.post("conv-1", "agent-2", {"data": "other"})

        result = await board.get_by_agent("conv-1", "agent-1")
        assert result is not None
        assert result["content"] == {"data": "second"}
        assert result["version"] == 2

    @pytest.mark.asyncio
    async def test_get_by_agent_not_found(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        await board.post("conv-1", "agent-1", {"data": "value"})

        result = await board.get_by_agent("conv-1", "agent-2")
        assert result is None

    @pytest.mark.asyncio
    async def test_version_increments(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        v1 = await board.post("conv-1", "agent-1", {"data": "first"})
        v2 = await board.post("conv-1", "agent-2", {"data": "second"})
        v3 = await board.post("conv-1", "agent-1", {"data": "third"})

        assert v1 == 1
        assert v2 == 2
        assert v3 == 3

    @pytest.mark.asyncio
    async def test_get_latest(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        await board.post("conv-1", "agent-1", {"data": "first"})
        await board.post("conv-1", "agent-2", {"data": "latest"})

        result = await board.get_latest("conv-1")
        assert result is not None
        assert result["content"] == {"data": "latest"}
        assert result["version"] == 2

    @pytest.mark.asyncio
    async def test_get_latest_empty(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        result = await board.get_latest("conv-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_post_with_confidence_and_citations(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        await board.post(
            "conv-1",
            "agent-1",
            {"data": "value"},
            confidence=0.85,
            citations=["source1", "source2"],
        )

        entries = await board.get("conv-1")
        assert len(entries) == 1
        assert entries[0]["confidence"] == 0.85
        assert entries[0]["citations"] == ["source1", "source2"]

    @pytest.mark.asyncio
    async def test_concurrent_writes(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        results = []
        for i in range(5):
            v = await board.post("conv-1", f"agent-{i}", {"data": f"value-{i}"})
            results.append(v)

        assert len(set(results)) == 5
        assert results == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        board = _create_blackboard(fake_redis)

        async with board:
            pass
