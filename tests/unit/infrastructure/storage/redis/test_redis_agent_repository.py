"""RedisAgentRepository 单元测试（Story 5-1）

覆盖 Agent 聚合 Redis 仓储（Mock 工厂模式——AsyncMock(spec=aioredis.Redis)
raw_client + 闭包 Hash 存储仿真 + _make_agent() 工厂）：
- save/get_by_id/exists/delete 基本行为
- 同 agent_id 二次 save 的 upsert 语义（读回第二实体、TTL 重置为第二次值）
- _agent_to_hash/_hash_to_agent 序列化往返（UUID/AgentRole/AgentStatus/datetime
  显式重建——json_loads 不还原类型，调用方重建责任）
- save(agent, ttl) TTL 必填（缺参 TypeError 契约）
- ttl 越界（<60 或 >2592000）抛 AgentConfigError(440)（仓储防御性二次校验）
- Redis 连接异常（raw_client 抛 ConnectionError）→ save 包装 StorageError
  向上传播不静默（对齐 RedisSnapshotStore.save 先例）

Subtask 3.5 fakeredis 快速回归见 TestFakeredisSemantics（真实 hset/expire/ttl 语义）。

Run with:
    poetry run pytest tests/unit/infrastructure/storage/redis/test_redis_agent_repository.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.domain.entities.agent import Agent, AgentRole, AgentStatus
from src.domain.exceptions import AgentConfigError, StorageError
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository


def _make_agent(**overrides) -> Agent:
    """工厂：构造合法 Agent 实体（可覆盖任意字段）。"""
    defaults: dict = {
        "agent_id": uuid.uuid4(),
        "role": AgentRole.CEO,
        "name": "CEO Agent",
        "description": "首席执行官 Agent",
        "domain_knowledge": ["宏观趋势", "竞争格局"],
        "responsibilities": ["战略方向", "最终决策"],
    }
    defaults.update(overrides)
    return Agent(**defaults)


def _make_repo_with_store() -> tuple[RedisAgentRepository, dict[str, Any]]:
    """构造带 Hash 存储语义的仓储 + raw_client 替身（AsyncMock spec + 闭包存储）。

    Returns:
        (仓储实例, 状态字典 {"client": 替身, "store": 键→field→值, "ttls": 键→TTL})
    """
    import redis.asyncio as aioredis

    store: dict[str, dict[str, str]] = {}
    ttls: dict[str, int] = {}
    client = AsyncMock(spec=aioredis.Redis)

    async def _hset(key: str, field: str, value: str) -> int:
        store.setdefault(key, {})[field] = value
        return 1

    async def _hget(key: str, field: str) -> str | None:
        return store.get(key, {}).get(field)

    async def _expire(key: str, ttl: int) -> int:
        ttls[key] = ttl
        return 1

    async def _delete(*keys: str) -> int:
        count = sum(1 for key in keys if key in store)
        for key in keys:
            store.pop(key, None)
            ttls.pop(key, None)
        return count

    async def _exists(*keys: str) -> int:
        return sum(1 for key in keys if key in store)

    async def _ttl(key: str) -> int:
        return ttls.get(key, -2)

    client.hset = AsyncMock(side_effect=_hset)
    client.hget = AsyncMock(side_effect=_hget)
    client.expire = AsyncMock(side_effect=_expire)
    client.delete = AsyncMock(side_effect=_delete)
    client.exists = AsyncMock(side_effect=_exists)
    client.ttl = AsyncMock(side_effect=_ttl)

    repo = RedisAgentRepository(adapter=RedisAdapter(redis_client=client))
    return repo, {"client": client, "store": store, "ttls": ttls}


# ===================================================================
# save / get_by_id / exists / delete 基本行为
# ===================================================================


class TestBasicOperations:
    """仓储四方法基本行为。"""

    async def test_save_persists_hash_with_latest_field(self) -> None:
        repo, state = _make_repo_with_store()
        agent = _make_agent()
        await repo.save(agent, ttl=86400)
        key = build_key("agent", str(agent.agent_id))
        assert key in state["store"], "键未写入"
        assert "latest" in state["store"][key], "必须单 field latest 承载 JSON blob"

    async def test_save_sets_ttl(self) -> None:
        repo, state = _make_repo_with_store()
        agent = _make_agent()
        await repo.save(agent, ttl=3600)
        key = build_key("agent", str(agent.agent_id))
        assert state["ttls"][key] == 3600

    async def test_save_ttl_is_required_positional(self) -> None:
        """save(agent, ttl) TTL 必填——无默认值（避免与 VO 默认值双真源，DC-8）。"""
        repo, _ = _make_repo_with_store()
        agent = _make_agent()
        with pytest.raises(TypeError):
            await repo.save(agent)  # type: ignore[call-arg]

    async def test_get_by_id_returns_agent(self) -> None:
        repo, _ = _make_repo_with_store()
        agent = _make_agent()
        await repo.save(agent, ttl=86400)
        restored = await repo.get_by_id(agent.agent_id)
        assert restored is not None
        assert restored.agent_id == agent.agent_id

    async def test_get_by_id_missing_returns_none(self) -> None:
        repo, _ = _make_repo_with_store()
        assert await repo.get_by_id(uuid.uuid4()) is None

    async def test_exists_true_after_save_false_after_delete(self) -> None:
        repo, _ = _make_repo_with_store()
        agent = _make_agent()
        assert await repo.exists(agent.agent_id) is False
        await repo.save(agent, ttl=86400)
        assert await repo.exists(agent.agent_id) is True
        await repo.delete(agent.agent_id)
        assert await repo.exists(agent.agent_id) is False

    async def test_delete_missing_key_no_error(self) -> None:
        repo, _ = _make_repo_with_store()
        await repo.delete(uuid.uuid4())  # 幂等删除，不抛


# ===================================================================
# upsert 语义（同 agent_id 二次 save）
# ===================================================================


class TestUpsertSemantics:
    """save 的 insert-or-update 语义契约。"""

    async def test_second_save_overwrites_entity(self) -> None:
        repo, _ = _make_repo_with_store()
        agent_id = uuid.uuid4()
        first = _make_agent(agent_id=agent_id, name="第一版")
        await repo.save(first, ttl=86400)
        second = _make_agent(agent_id=agent_id, name="第二版", status=AgentStatus.WAITING)
        await repo.save(second, ttl=7200)

        restored = await repo.get_by_id(agent_id)
        assert restored is not None
        assert restored.name == "第二版", "读回必须是第二实体（upsert 覆盖）"
        assert restored.status == AgentStatus.WAITING

    async def test_second_save_resets_ttl(self) -> None:
        repo, state = _make_repo_with_store()
        agent_id = uuid.uuid4()
        await repo.save(_make_agent(agent_id=agent_id), ttl=86400)
        await repo.save(_make_agent(agent_id=agent_id), ttl=7200)
        key = build_key("agent", str(agent_id))
        assert state["ttls"][key] == 7200, "TTL 必须重置为第二次值"


# ===================================================================
# 序列化往返（UUID/Enum/datetime 显式重建）
# ===================================================================


class TestSerializationRoundtrip:
    """实体↔Hash 转换全字段往返（非恒真断言——类型重建逐一校验）。"""

    async def test_roundtrip_all_fields(self) -> None:
        repo, _ = _make_repo_with_store()
        created = datetime(2026, 10, 14, 8, 30, 0, tzinfo=UTC)
        updated = datetime(2026, 10, 14, 9, 0, 0, tzinfo=UTC)
        agent = _make_agent(
            status=AgentStatus.RUNNING,
            failure_reason="",
            created_at=created,
            updated_at=updated,
        )
        await repo.save(agent, ttl=86400)
        restored = await repo.get_by_id(agent.agent_id)

        assert restored is not None
        assert restored.agent_id == agent.agent_id
        assert isinstance(restored.agent_id, uuid.UUID)
        assert restored.role == agent.role
        assert restored.name == agent.name
        assert restored.description == agent.description
        assert restored.status == agent.status
        assert restored.failure_reason == agent.failure_reason
        assert restored.domain_knowledge == agent.domain_knowledge
        assert restored.responsibilities == agent.responsibilities
        assert restored.created_at == created
        assert restored.updated_at == updated

    async def test_roundtrip_rebuilds_types_explicitly(self) -> None:
        """json_loads 不还原类型——Enum/datetime 必须 isinstance 重建断言。"""
        repo, _ = _make_repo_with_store()
        agent = _make_agent()
        await repo.save(agent, ttl=86400)
        restored = await repo.get_by_id(agent.agent_id)

        assert restored is not None
        assert isinstance(restored.role, AgentRole), "role 必须重建为 AgentRole 枚举"
        assert isinstance(restored.status, AgentStatus), "status 必须重建为 AgentStatus 枚举"
        assert isinstance(restored.created_at, datetime), "created_at 必须重建为 datetime"
        assert isinstance(restored.domain_knowledge, list), "domain_knowledge 必须重建为 list[str]"
        assert isinstance(restored.responsibilities, list), "responsibilities 必须重建为 list[str]"

    def test_agent_to_hash_converts_to_primitives(self) -> None:
        """静态转换方法：UUID→str、Enum→value、datetime→ISO 字符串。"""
        agent = _make_agent()
        hash_data = RedisAgentRepository._agent_to_hash(agent)
        for value in hash_data.values():
            assert isinstance(value, str), f"hash field 值必须是 str 原始类型: {value!r}"
        assert hash_data["agent_id"] == str(agent.agent_id)
        assert hash_data["role"] == "ceo"
        assert hash_data["status"] == "idle"


# ===================================================================
# TTL 防御性校验（范围 60~2592000）
# ===================================================================


class TestTtlValidation:
    """仓储层防御性二次校验（VO 是主校验，本层防直调绕过）。"""

    @pytest.mark.parametrize("ttl", [59, 30, 2592001, 9999999])
    async def test_out_of_range_ttl_raises_440(self, ttl: int) -> None:
        repo, _ = _make_repo_with_store()
        with pytest.raises(AgentConfigError) as exc_info:
            await repo.save(_make_agent(), ttl=ttl)
        assert exc_info.value.code == "EXCEPTION_440"

    @pytest.mark.parametrize("ttl", [60, 86400, 2592000])
    async def test_boundary_ttl_accepted(self, ttl: int) -> None:
        repo, _ = _make_repo_with_store()
        agent = _make_agent()
        await repo.save(agent, ttl=ttl)  # 端点值合法，不抛


# ===================================================================
# 连接异常包装（不静默）
# ===================================================================


class TestConnectionErrorPropagation:
    """Redis 不可达 → 包装 StorageError 向上传播（禁静默吞异常）。"""

    async def test_save_connection_error_wrapped_as_storage_error(self) -> None:
        import redis.asyncio as aioredis

        client = AsyncMock(spec=aioredis.Redis)
        client.hset = AsyncMock(side_effect=aioredis.ConnectionError("connection refused"))
        repo = RedisAgentRepository(adapter=RedisAdapter(redis_client=client))

        with pytest.raises(StorageError) as exc_info:
            await repo.save(_make_agent(), ttl=86400)
        assert isinstance(exc_info.value.cause, aioredis.ConnectionError)

    async def test_get_by_id_connection_error_wrapped(self) -> None:
        import redis.asyncio as aioredis

        client = AsyncMock(spec=aioredis.Redis)
        client.hget = AsyncMock(side_effect=aioredis.ConnectionError("connection refused"))
        repo = RedisAgentRepository(adapter=RedisAdapter(redis_client=client))

        with pytest.raises(StorageError):
            await repo.get_by_id(uuid.uuid4())


# ===================================================================
# fakeredis 快速回归（真实 hset/expire/ttl 语义）
# ===================================================================


class TestFakeredisSemantics:
    """fakeredis 实测 hset+expire+ttl 语义（TTL 断言先例 test_redis_cache.py）。"""

    async def test_save_then_key_exists_with_positive_ttl(self) -> None:
        fakeredis = pytest.importorskip("fakeredis.aioredis")
        client = fakeredis.FakeRedis(decode_responses=True)
        try:
            repo = RedisAgentRepository(adapter=RedisAdapter(redis_client=client))
            agent = _make_agent()
            await repo.save(agent, ttl=86400)
            key = build_key("agent", str(agent.agent_id))
            assert await client.exists(key) == 1
            assert await client.ttl(key) == 86400

            restored = await repo.get_by_id(agent.agent_id)
            assert restored is not None
            assert restored.role == AgentRole.CEO
        finally:
            await client.aclose()
