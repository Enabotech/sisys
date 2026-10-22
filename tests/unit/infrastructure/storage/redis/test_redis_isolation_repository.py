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

import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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

    @pytest.mark.parametrize("ttl", [60, 86400, 2592000], ids=["下界60", "默认86400", "上界2592000"])
    async def test_boundary_ttl_accepted(self, repository: RedisIsolationRepository, redis_client: Any, ttl: int) -> None:
        """闭区间端点 60/2592000 合法接受（防边界比较符误改开区间无声退化）。"""
        from src.infrastructure.storage.redis.key_builder import build_key

        state = _make_state()
        await repository.save(state, ttl=ttl)  # 不抛即接受
        remaining = await redis_client.ttl(build_key("isolation", str(state.agent_id)))
        assert ttl - 5 <= remaining <= ttl

    @pytest.mark.parametrize("ttl", [True, 3600.5], ids=["bool是int子类", "float非整数"])
    async def test_bool_and_float_ttl_raise_440(self, repository: RedisIsolationRepository, ttl: Any) -> None:
        """bool/float TTL → 440（bool 不拦则 True→1 秒 TTL 实质缺陷——实现守卫锁定）。"""
        state = _make_state()
        with pytest.raises(AgentConfigError):
            await repository.save(state, ttl=ttl)

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


# ===================================================================
# pipeline 原子性契约（MULTI/EXEC——5-1 先例移植，Story 5-4 R1-F01）
# ===================================================================

_PipelineOps = list[tuple[str, tuple[Any, ...]]]


class _PipelineStub:
    """redis-py Pipeline 替身（入队 + execute 原子应用——5-1 先例同款）。

    redis-py pipeline 命令入队是同步调用、execute 才提交——本替身忠实复刻
    该语义（入队记录 operations，execute 经 apply 回调应用）。
    """

    def __init__(self, apply: Callable[[_PipelineOps], Awaitable[list[Any]]]) -> None:
        self.operations: _PipelineOps = []
        self.execute = AsyncMock(side_effect=lambda: apply(self.operations))

    def hset(self, key: str, field: str, value: str) -> None:
        """入队 HSET（同步调用——对齐 redis-py pipeline 命令排队语义）。"""
        self.operations.append(("hset", (key, field, value)))

    def expire(self, key: str, ttl: int) -> None:
        """入队 EXPIRE（同步调用）。"""
        self.operations.append(("expire", (key, ttl)))

    async def __aenter__(self) -> _PipelineStub:
        """进入 async with（对齐 redis-py Pipeline 异步上下文管理器）。"""
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        """退出 async with（不吞异常）。"""


def _make_repo_with_pipeline_stub() -> tuple[RedisIsolationRepository, dict[str, Any]]:
    """构造带 pipeline 替身的仓储（client.pipeline 记录每次调用——原子性断言面）。

    Returns:
        (仓储实例, {"client": 替身客户端, "pipes": pipeline 替身清单})
    """
    import redis.asyncio as aioredis

    client = AsyncMock(spec=aioredis.Redis)
    pipes: list[_PipelineStub] = []

    async def _apply(operations: _PipelineOps) -> list[Any]:
        return [None] * len(operations)

    def _pipeline(**_kwargs: Any) -> _PipelineStub:
        stub = _PipelineStub(apply=_apply)
        pipes.append(stub)
        return stub

    client.pipeline = MagicMock(side_effect=_pipeline)

    class _AdapterStub:
        """适配器替身（raw_client 实例属性——RedisAdapter.raw_client duck-typing 面）。"""

        def __init__(self) -> None:
            self.raw_client = client

    adapter: Any = _AdapterStub()
    return RedisIsolationRepository(adapter=adapter), {"client": client, "pipes": pipes}


class TestPipelineAtomicity:
    """save 的 MULTI/EXEC pipeline 原子提交契约（防崩溃窗口孤儿键）。"""

    async def test_save_uses_single_pipeline_transaction(self) -> None:
        """hset+expire 必须经单次 MULTI/EXEC pipeline 原子提交。

        仓储 docstring 明言原子提交理由：两命令分离时进程在两者之间崩溃
        会留下永不过期的孤儿键——fakeredis 对两种实现行为一致，唯有
        交互序断言能锁定该契约（save 降级为独立 await 命令时本用例红）。
        """
        from src.infrastructure.storage.redis.key_builder import build_key

        repository, stub_state = _make_repo_with_pipeline_stub()
        state = _make_state()
        await repository.save(state, ttl=3600)
        client = stub_state["client"]
        assert len(stub_state["pipes"]) == 1, "save 必须经 pipeline 提交"
        client.pipeline.assert_called_once_with(transaction=True)
        pipe = stub_state["pipes"][0]
        assert [op for op, _ in pipe.operations] == ["hset", "expire"], "hset 与 expire 必须在同一事务管道内"
        key = build_key("isolation", str(state.agent_id))
        assert pipe.operations[0][1][0] == pipe.operations[1][1][0] == key, "hset 与 expire 必须作用于同一键"
        pipe.execute.assert_awaited_once()


# ===================================================================
# 脏数据 fail-loud 契约（读路径防御——Story 5-4 R1-F03）
# ===================================================================


class TestCorruptedPayloadFailLoud:
    """脏数据读取 → StorageError(103) fail-loud（禁静默错值/禁裸异常逃逸）。

    实现侧 get_by_agent_id 的 except Exception 全谱包装脏数据（坏 JSON/
    非法枚举值/缺字段）为 103——本组锁定该契约，防未来 except 收窄为
    redis.RedisError 时脏数据以裸 KeyError/ValueError 逃逸统一异常体系。
    """

    async def test_corrupted_json_raises_storage_error(self, repository: RedisIsolationRepository, redis_client: Any) -> None:
        """latest 字段为非法 JSON → StorageError(103) + cause 携带原异常。"""
        from src.infrastructure.storage.redis.key_builder import build_key

        state = _make_state()
        key = build_key("isolation", str(state.agent_id))
        await redis_client.hset(key, "latest", "{not-valid-json")
        with pytest.raises(StorageError) as exc_info:
            await repository.get_by_agent_id(state.agent_id)
        assert exc_info.value.code == "EXCEPTION_103"
        assert exc_info.value.cause is not None

    async def test_corrupted_enum_value_raises_storage_error(
        self, repository: RedisIsolationRepository, redis_client: Any
    ) -> None:
        """current_level 非法枚举值（外部写入 "L9"）→ StorageError(103)。"""
        from src.infrastructure.storage.redis.key_builder import build_key

        state = _make_state()
        key = build_key("isolation", str(state.agent_id))
        corrupted = json.dumps(
            {
                "agent_id": str(state.agent_id),
                "current_level": "L9",
                "initialized_at": state.initialized_at.isoformat(),
                "updated_at": state.updated_at.isoformat(),
                "last_trigger_reason": "tampered",
            }
        )
        await redis_client.hset(key, "latest", corrupted)
        with pytest.raises(StorageError) as exc_info:
            await repository.get_by_agent_id(state.agent_id)
        assert exc_info.value.code == "EXCEPTION_103"
        assert exc_info.value.cause is not None

    async def test_missing_field_raises_storage_error(self, repository: RedisIsolationRepository, redis_client: Any) -> None:
        """缺 updated_at 字段 → StorageError(103)（禁静默错值降级为 447）。"""
        from src.infrastructure.storage.redis.key_builder import build_key

        state = _make_state()
        key = build_key("isolation", str(state.agent_id))
        corrupted = json.dumps(
            {
                "agent_id": str(state.agent_id),
                "current_level": state.current_level.value,
                "initialized_at": state.initialized_at.isoformat(),
                "last_trigger_reason": "partial",
            }
        )
        await redis_client.hset(key, "latest", corrupted)
        with pytest.raises(StorageError) as exc_info:
            await repository.get_by_agent_id(state.agent_id)
        assert exc_info.value.code == "EXCEPTION_103"
        assert exc_info.value.cause is not None
