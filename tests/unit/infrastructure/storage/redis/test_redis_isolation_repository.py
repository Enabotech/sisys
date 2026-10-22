"""Story 5.4: RedisIsolationRepository 单元测试（fakeredis）

覆盖 AC-2（持久化/TTL/键空间）:
- save → get_by_agent_id 往返字段逐项相等（UUID/IsolationLevel/datetime 显式重建
  断言——透传 str 必红，5-1 变异先例）
- 键形态断言 sisys:isolation:{agent_id}（禁侵入 agent namespace）
- save 后 redis.ttl 落在 [ttl-5, ttl] 容差区间（禁真实等待过期）
- TTL 越界（<60 / >2592000）→ AgentConfigError(440)
- upsert: 二次 save 覆盖且 TTL 重置
- get 不存在返回 None / delete 幂等 / exists
- 连接异常 → StorageError(103) 包装（cause 属性经构造参数传递——from exc 仅设
  __cause__ 不够，5-1 Task 3 实测教训）
- Hash 单 field latest 形态（raw_client hget）

Run with:
    poetry run pytest tests/unit/infrastructure/storage/redis/test_redis_isolation_repository.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import fakeredis.aioredis
import pytest

from src.domain.entities.isolation_state import IsolationState
from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import AgentConfigError, StorageError
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository


def _make_state(level: IsolationLevel = IsolationLevel.L4_HARD) -> IsolationState:
    """合法 IsolationState 工厂（固定时刻——往返断言确定性）。"""
    now = datetime(2026, 10, 22, 8, 0, 0, tzinfo=UTC)
    return IsolationState.initialize(uuid.uuid4(), level, now=now)


def _make_switched_state() -> IsolationState:
    """已切换状态（L3——往返字段丰富性）。"""
    now = datetime(2026, 10, 22, 8, 0, 0, tzinfo=UTC)
    state = IsolationState.initialize(uuid.uuid4(), IsolationLevel.L4_HARD, now=now)
    state.switch_to(IsolationLevel.L3_SOFT, "任务需要软隔离", now=datetime(2026, 10, 22, 9, 0, 0, tzinfo=UTC))
    return state


@pytest.fixture
async def redis_client() -> Any:
    """fakeredis 场景级客户端（asyncio_mode=auto 裸 async fixture）。

    client 注解 Any: FakeRedis 的类型存根未声明 aclose（运行时已实现——
    fakeredis 2.x），Any 注解按运行时契约直调。
    """
    client: Any = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def repository(redis_client: Any) -> RedisIsolationRepository:
    """被测仓储（fakeredis 客户端注入 RedisAdapter）。"""
    return RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))


class TestSaveGetRoundtrip:
    """save → get_by_agent_id 往返（显式重建纪律）。"""

    async def test_roundtrip_fields_equal(self, repository: RedisIsolationRepository) -> None:
        """往返字段逐项相等（含类型重建断言）。"""
        state = _make_switched_state()
        await repository.save(state, ttl=86400)
        rebuilt = await repository.get_by_agent_id(state.agent_id)
        assert rebuilt is not None
        assert isinstance(rebuilt.agent_id, uuid.UUID), "agent_id 未显式重建 UUID"
        assert isinstance(rebuilt.current_level, IsolationLevel), "current_level 未显式重建枚举"
        assert isinstance(rebuilt.updated_at, datetime), "updated_at 未显式重建 datetime"
        assert rebuilt.agent_id == state.agent_id
        assert rebuilt.current_level is IsolationLevel.L3_SOFT
        assert rebuilt.initialized_at == state.initialized_at
        assert rebuilt.updated_at == state.updated_at
        assert rebuilt.last_trigger_reason == "任务需要软隔离"

    async def test_get_missing_returns_none(self, repository: RedisIsolationRepository) -> None:
        """键不存在返回 None。"""
        assert await repository.get_by_agent_id(uuid.uuid4()) is None

    async def test_key_namespace_isolation(self, repository: RedisIsolationRepository, redis_client: Any) -> None:
        """键形态 sisys:isolation:{agent_id}（禁侵入 agent namespace）。"""
        from src.infrastructure.storage.redis.key_builder import build_key

        state = _make_state()
        await repository.save(state, ttl=86400)
        expected_key = build_key("isolation", str(state.agent_id))
        assert await redis_client.exists(expected_key) == 1
        agent_key = build_key("agent", str(state.agent_id))
        assert await redis_client.exists(agent_key) == 0, "隔离键不得写入 agent namespace"

    async def test_hash_single_field_latest(self, repository: RedisIsolationRepository, redis_client: Any) -> None:
        """Hash 单 field latest 形态（RedisAgentRepository 同款）。"""
        from src.infrastructure.storage.redis.key_builder import build_key

        state = _make_state()
        await repository.save(state, ttl=86400)
        key = build_key("isolation", str(state.agent_id))
        fields = await redis_client.hkeys(key)
        assert fields == ["latest"], f"Hash 应恰单 field latest（实际 {fields}）"


class TestTtlValidation:
    """TTL 防御校验（闭区间 60~2592000）。"""

    async def test_save_then_ttl_within_tolerance(self, repository: RedisIsolationRepository, redis_client: Any) -> None:
        """save 后 redis.ttl 落在 [ttl-5, ttl] 容差区间。"""
        from src.infrastructure.storage.redis.key_builder import build_key

        state = _make_state()
        await repository.save(state, ttl=86400)
        remaining = await redis_client.ttl(build_key("isolation", str(state.agent_id)))
        assert 86400 - 5 <= remaining <= 86400, f"TTL 漂移: {remaining}"

    @pytest.mark.parametrize("ttl", [59, 2592001], ids=["下界外59", "上界外2592001"])
    async def test_out_of_range_ttl_raises_440(self, repository: RedisIsolationRepository, ttl: int) -> None:
        """TTL 越界 → AgentConfigError(440)——reason 语义含 state_ttl。"""
        state = _make_state()
        with pytest.raises(AgentConfigError) as exc_info:
            await repository.save(state, ttl=ttl)
        assert exc_info.value.code == "EXCEPTION_440"
        assert "state_ttl" in exc_info.value.context.get("reason", "")

    async def test_non_int_ttl_raises_440(self, repository: RedisIsolationRepository) -> None:
        """非整数 TTL → 440。"""
        state = _make_state()
        bad_ttl: Any = "86400"
        with pytest.raises(AgentConfigError):
            await repository.save(state, ttl=bad_ttl)

    async def test_upsert_overwrites_and_resets_ttl(self, repository: RedisIsolationRepository, redis_client: Any) -> None:
        """二次 save 覆盖（upsert 语义）且 TTL 重置。"""
        from src.infrastructure.storage.redis.key_builder import build_key

        state = _make_state()
        await repository.save(state, ttl=3600)
        state.switch_to(IsolationLevel.L2_COLLAB, "协作分析需要")
        await repository.save(state, ttl=86400)
        rebuilt = await repository.get_by_agent_id(state.agent_id)
        assert rebuilt is not None
        assert rebuilt.current_level is IsolationLevel.L2_COLLAB
        remaining = await redis_client.ttl(build_key("isolation", str(state.agent_id)))
        assert 86400 - 5 <= remaining <= 86400


class TestDeleteAndExists:
    """delete 幂等与 exists。"""

    async def test_delete_idempotent(self, repository: RedisIsolationRepository) -> None:
        """删除不存在键无异常（幂等）。"""
        await repository.delete(uuid.uuid4())  # 不抛即通过

    async def test_exists_lifecycle(self, repository: RedisIsolationRepository) -> None:
        """exists: 保存前 False → 保存后 True → 删除后 False。"""
        state = _make_state()
        assert await repository.exists(state.agent_id) is False
        await repository.save(state, ttl=86400)
        assert await repository.exists(state.agent_id) is True
        await repository.delete(state.agent_id)
        assert await repository.exists(state.agent_id) is False


class TestStorageErrorWrapping:
    """连接异常包装（StorageError.cause 经构造参数传递——禁静默）。"""

    class _BrokenRawClient:
        """恒抛连接异常的 raw_client 替身（duck-typing 契约面）。

        pipeline 为同步方法直接抛（真实客户端 pipeline() 同步返回 async
        context manager——`async with` 表达式求值阶段即抛）；其余 async 方法
        在 await 时抛。
        """

        @staticmethod
        def pipeline(transaction: bool = True) -> Any:
            raise ConnectionError("redis down")

        @staticmethod
        async def hget(key: str, field: str) -> Any:
            raise ConnectionError("redis down")

        @staticmethod
        async def delete(key: str) -> Any:
            raise ConnectionError("redis down")

        @staticmethod
        async def exists(key: str) -> Any:
            raise ConnectionError("redis down")

    class _BrokenAdapter:
        """适配器替身（raw_client 实例属性——RedisAdapter.raw_client 的 duck-typing 面）。"""

        def __init__(self) -> None:
            self.raw_client = TestStorageErrorWrapping._BrokenRawClient()

    def _broken_repository(self) -> RedisIsolationRepository:
        broken_adapter: Any = self._BrokenAdapter()
        return RedisIsolationRepository(adapter=broken_adapter)

    async def test_save_error_wrapped_with_cause(self) -> None:
        """save 连接异常 → StorageError 包装 + cause 属性携带原异常。"""
        state = _make_state()
        with pytest.raises(StorageError) as exc_info:
            await self._broken_repository().save(state, ttl=86400)
        assert exc_info.value.code == "EXCEPTION_103"
        assert exc_info.value.cause is not None
        assert isinstance(exc_info.value.cause, ConnectionError), "cause 须经构造参数传递（from exc 仅设 __cause__）"

    async def test_get_error_wrapped(self) -> None:
        """get 连接异常 → StorageError（确定性读取不静默降级）。"""
        with pytest.raises(StorageError):
            await self._broken_repository().get_by_agent_id(uuid.uuid4())

    async def test_delete_error_wrapped(self) -> None:
        """delete 连接异常 → StorageError。"""
        with pytest.raises(StorageError):
            await self._broken_repository().delete(uuid.uuid4())

    async def test_exists_error_wrapped(self) -> None:
        """exists 连接异常 → StorageError。"""
        with pytest.raises(StorageError):
            await self._broken_repository().exists(uuid.uuid4())
