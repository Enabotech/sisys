"""Story 5.4: IsolationManagementService 单元测试

覆盖 AC-3/AC-4（服务层）:
- initialize: 构建→save(state, ttl) 参数断言 / 非法等级由实体工厂 446 拦截透传
- get 守卫序: agent None → 443 且 isolation_repository 未被调（calls 顺序断言）/
  隔离态透传 / 隔离态缺失 → 447（context agent_id）/ 仓储异常透传
- switch 守卫序: 443 先于 447（calls 顺序）/ 447 / no-op 零副作用（save/publish
  零调用计数）/ 合法切换 save 恰一次且 TTL 真源 == config.state_ttl
  （config_loader.load 恰一次）/ 事件六字段 / publish 双分支容错
  （raise + is_success=False 各配独立命名用例）

单测 Mock 端口合规（AsyncMock(spec=Protocol) + side_effect 闭包——
test_agent_instantiation.py _make_use_case 先例）。

Run with:
    poetry run pytest tests/unit/application/services/test_isolation_management_service.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.agent_config_loader import AgentConfigLoader
from src.application.ports.isolation_management import (
    IsolationManagementServicePort,
    IsolationSwitchResult,
)
from src.application.services.isolation_management_service import IsolationManagementService
from src.domain.entities.agent import Agent, AgentRole
from src.domain.entities.isolation_state import IsolationState
from src.domain.events.enums import IsolationLevel
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.exceptions import (
    AgentNotFoundError,
    IsolationLevelNotSupportedError,
    IsolationStateNotInitializedError,
    StorageError,
)
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.isolation_repository import IsolationRepository

AGENT_ID = uuid.uuid4()
NOW = datetime(2026, 10, 22, 8, 0, 0, tzinfo=UTC)


def _make_agent() -> Agent:
    """真实 Agent 实体（443 守卫通过态）。"""
    agent = Agent(
        agent_id=AGENT_ID,
        role=AgentRole.CEO,
        name="CEO Agent",
        description="首席执行官",
        domain_knowledge=["宏观趋势"],
        responsibilities=["战略方向"],
    )
    agent.validate()
    return agent


def _make_state(level: IsolationLevel = IsolationLevel.L4_HARD) -> IsolationState:
    """真实 IsolationState（仓储返回态）。"""
    return IsolationState.initialize(AGENT_ID, level, now=NOW)


def _make_config(state_ttl: int = 777) -> Any:
    """真实 AgentConfig（state_ttl 可调——TTL 真源断言锚）。"""
    from src.domain.value_objects.agent_config import AgentConfig

    return AgentConfig(
        role=AgentRole.CEO,
        name="CEO Agent",
        description="首席执行官",
        version="1.0.0",
        responsibilities=("战略方向",),
        domain_knowledge=("宏观趋势",),
        preferred_model=None,
        state_ttl=state_ttl,
    )


def _success_publish_result() -> PublishResult:
    return PublishResult(
        event_id=str(uuid.uuid4()),
        results=(ChannelResult(channel_name="inmemory", success=True),),
    )


def _make_service(
    state: IsolationState | Exception | None = None,
    agent: Agent | None = None,
    publish_error: Exception | None = None,
    publish_result: PublishResult | None = None,
    state_ttl: int = 777,
) -> tuple[IsolationManagementService, dict[str, Any]]:
    """四替身组装工厂（AsyncMock spec 端口 + side_effect 闭包记录 calls 序列）。

    Args:
        state: 隔离仓储返回态（None=缺失；Exception 实例=抛出——异常透传面）
        agent: Agent 仓储返回实体（None=443 面）
        publish_error: publish 抛出异常（DC-10 raise 分支面）
        publish_result: publish 返回结果（默认成功；is_success=False 面由此注入）
        state_ttl: config 桩 TTL（TTL 真源断言锚）

    Returns:
        (service, mocks)——mocks 含 isolation_repo/agent_repo/publisher/config_loader/calls
    """
    calls: list[str] = []

    isolation_repo = AsyncMock(spec=IsolationRepository)

    async def _get_by_agent_id(agent_id: uuid.UUID) -> Any:
        calls.append("iso.get")
        if isinstance(state, Exception):
            raise state
        return state

    async def _save(s: IsolationState, ttl: int) -> None:
        calls.append("iso.save")

    isolation_repo.get_by_agent_id = AsyncMock(side_effect=_get_by_agent_id)
    isolation_repo.save = AsyncMock(side_effect=_save)

    agent_repo = AsyncMock(spec=AgentRepository)

    async def _get_by_id(agent_id: uuid.UUID) -> Any:
        calls.append("agent.get")
        return agent

    agent_repo.get_by_id = AsyncMock(side_effect=_get_by_id)

    publisher = AsyncMock(spec=EventPublisher)

    async def _publish(event: Any) -> Any:
        calls.append("publish")
        if publish_error is not None:
            raise publish_error
        return publish_result if publish_result is not None else _success_publish_result()

    publisher.publish = AsyncMock(side_effect=_publish)

    config_loader = AsyncMock(spec=AgentConfigLoader)

    async def _load(role: AgentRole) -> Any:
        calls.append("config.load")
        return _make_config(state_ttl)

    config_loader.load = AsyncMock(side_effect=_load)

    service = IsolationManagementService(
        isolation_repository=isolation_repo,
        agent_repository=agent_repo,
        event_publisher=publisher,
        agent_config_loader=config_loader,
    )
    return service, {
        "isolation_repo": isolation_repo,
        "agent_repo": agent_repo,
        "publisher": publisher,
        "config_loader": config_loader,
        "calls": calls,
    }


class TestInitializeAgentIsolation:
    """initialize_agent_isolation（upsert——前置条件由调用方保证）。"""

    async def test_initialize_saves_state_with_ttl(self) -> None:
        """构建状态 → repo.save(state, ttl) 恰一次（参数含等级与 TTL 双消费）。"""
        service, mocks = _make_service()
        state = await service.initialize_agent_isolation(AGENT_ID, IsolationLevel.L4_HARD, 777)
        assert isinstance(state, IsolationState)
        assert state.current_level is IsolationLevel.L4_HARD
        assert state.last_trigger_reason == "initial_default"
        mocks["isolation_repo"].save.assert_awaited_once()
        saved_call = mocks["isolation_repo"].save.await_args
        assert saved_call.args[0].current_level is IsolationLevel.L4_HARD
        assert saved_call.kwargs["ttl"] == 777

    async def test_initialize_invalid_level_446_passthrough(self) -> None:
        """非法等级（L1 越白名单）由实体工厂 446 拦截——服务不重复校验向上透传。"""
        service, mocks = _make_service()
        with pytest.raises(IsolationLevelNotSupportedError) as exc_info:
            await service.initialize_agent_isolation(AGENT_ID, IsolationLevel.L1_FUSED, 777)
        assert exc_info.value.code == "EXCEPTION_446"
        mocks["isolation_repo"].save.assert_not_awaited()

    async def test_initialize_upsert_semantics(self) -> None:
        """重复初始化覆盖（upsert——重复初始化覆盖回默认等级是安全方向设计意图，
        R1-F33 注记的运行时锚）。"""
        service, mocks = _make_service()
        first = await service.initialize_agent_isolation(AGENT_ID, IsolationLevel.L4_HARD, 777)
        second = await service.initialize_agent_isolation(AGENT_ID, IsolationLevel.L3_SOFT, 888)
        assert second.current_level is IsolationLevel.L3_SOFT
        assert second.last_trigger_reason == "initial_default"
        assert first.initialized_at == first.updated_at  # 单 now 双用不变量
        # upsert 语义锚: 两次初始化各触发一次仓储写（mock 仓储下的覆盖语义由 save 计数锁定）
        assert mocks["isolation_repo"].save.await_count == 2, "重复初始化应各写一次（第二次覆盖第一次）"


class TestGetIsolationState:
    """get_isolation_state（守卫序: 443 → 447——隔离检查入口）。"""

    async def test_agent_not_found_443_isolation_repo_not_called(self) -> None:
        """agent 缺失 → 443 且 isolation_repository 未被调（calls 顺序断言）。"""
        service, mocks = _make_service(agent=None)
        with pytest.raises(AgentNotFoundError) as exc_info:
            await service.get_isolation_state(AGENT_ID)
        assert exc_info.value.code == "EXCEPTION_443"
        assert exc_info.value.context["agent_id"] == str(AGENT_ID)
        assert mocks["calls"] == ["agent.get"], "443 守卫必须先于隔离态读（iso.* 不得被调）"

    async def test_state_passthrough(self) -> None:
        """隔离态存在 → 透传返回（字段一致）。"""
        state = _make_state(IsolationLevel.L3_SOFT)
        service, mocks = _make_service(agent=_make_agent(), state=state)
        result = await service.get_isolation_state(AGENT_ID)
        assert result is state
        assert mocks["calls"] == ["agent.get", "iso.get"]

    async def test_state_missing_447_with_agent_id(self) -> None:
        """隔离态缺失 → 447（context 携带 agent_id——三种成因统一诊断锚）。"""
        service, _ = _make_service(agent=_make_agent(), state=None)
        with pytest.raises(IsolationStateNotInitializedError) as exc_info:
            await service.get_isolation_state(AGENT_ID)
        assert exc_info.value.code == "EXCEPTION_447"
        assert exc_info.value.context["agent_id"] == str(AGENT_ID)

    async def test_repo_exception_passthrough(self) -> None:
        """仓储异常透传（StorageError 不吞——确定性读取不静默降级）。"""
        service, _ = _make_service(agent=_make_agent(), state=StorageError("redis down"))
        with pytest.raises(StorageError):
            await service.get_isolation_state(AGENT_ID)


class TestSwitchIsolationLevel:
    """switch_isolation_level（守卫序: 443 → 447 → 446 实体内聚 + no-op + 事件）。"""

    async def test_agent_not_found_443_guard_first(self) -> None:
        """443 守卫先行（isolation repo 未被调）。"""
        service, mocks = _make_service(agent=None)
        with pytest.raises(AgentNotFoundError):
            await service.switch_isolation_level(AGENT_ID, IsolationLevel.L3_SOFT, "原因")
        assert mocks["calls"] == ["agent.get"], "443 必须先于隔离态读"

    async def test_state_missing_447(self) -> None:
        """隔离态缺失 → 447。"""
        service, _ = _make_service(agent=_make_agent(), state=None)
        with pytest.raises(IsolationStateNotInitializedError):
            await service.switch_isolation_level(AGENT_ID, IsolationLevel.L3_SOFT, "原因")

    async def test_invalid_level_446_from_entity(self) -> None:
        """L1（合法枚举越白名单）→ 实体 switch_to 446（服务不重复校验）。"""
        state = _make_state(IsolationLevel.L4_HARD)
        service, mocks = _make_service(agent=_make_agent(), state=state)
        with pytest.raises(IsolationLevelNotSupportedError) as exc_info:
            await service.switch_isolation_level(AGENT_ID, IsolationLevel.L1_FUSED, "尝试融合")
        assert exc_info.value.code == "EXCEPTION_446"
        mocks["isolation_repo"].save.assert_not_awaited()
        mocks["publisher"].publish.assert_not_awaited()

    async def test_noop_zero_side_effects(self) -> None:
        """同等级 no-op: switched=False + event=None + save/publish/config 零调用。"""
        state = _make_state(IsolationLevel.L4_HARD)
        service, mocks = _make_service(agent=_make_agent(), state=state)
        result = await service.switch_isolation_level(AGENT_ID, IsolationLevel.L4_HARD, "同等级重试")
        assert isinstance(result, IsolationSwitchResult)
        assert result.switched is False
        assert result.event is None
        assert result.state.current_level is IsolationLevel.L4_HARD
        mocks["isolation_repo"].save.assert_not_awaited()
        mocks["publisher"].publish.assert_not_awaited()
        mocks["config_loader"].load.assert_not_awaited()

    async def test_switch_config_load_failure_propagates_440(self) -> None:
        """config_loader.load 抛 440 → 向上透传且 save/publish 零调用（TTL 真源在 load）。"""
        from src.domain.exceptions import AgentConfigError

        state = _make_state(IsolationLevel.L4_HARD)
        service, mocks = _make_service(agent=_make_agent(), state=state)
        mocks["config_loader"].load = AsyncMock(side_effect=AgentConfigError(reason="yaml 配置解析失败"))
        with pytest.raises(AgentConfigError) as exc_info:
            await service.switch_isolation_level(AGENT_ID, IsolationLevel.L3_SOFT, "配置失败面")
        assert exc_info.value.code == "EXCEPTION_440"
        # load 先于 save（编排骨位 L145→L146）——配置失败时零仓储写零事件
        mocks["isolation_repo"].save.assert_not_awaited()
        mocks["publisher"].publish.assert_not_awaited()

    async def test_valid_switch_saves_with_config_ttl_and_publishes(self) -> None:
        """合法切换: save 恰一次且 ttl == config.state_ttl（config_loader.load 恰一次）
        + publish 恰一次 + 事件六字段。"""
        state = _make_state(IsolationLevel.L4_HARD)
        service, mocks = _make_service(agent=_make_agent(), state=state, state_ttl=999)
        result = await service.switch_isolation_level(AGENT_ID, IsolationLevel.L3_SOFT, "任务需要软隔离")
        assert result.switched is True
        assert result.state.current_level is IsolationLevel.L3_SOFT
        # TTL 真源断言（R1-F01: config.state_ttl——config_loader.load(agent.role) 恰一次）
        mocks["config_loader"].load.assert_awaited_once()
        loaded_role = mocks["config_loader"].load.await_args.args[0]
        assert loaded_role is AgentRole.CEO
        mocks["isolation_repo"].save.assert_awaited_once()
        saved_call = mocks["isolation_repo"].save.await_args
        assert saved_call.kwargs["ttl"] == 999, "TTL 必须取自 config.state_ttl（真源单点）"
        assert saved_call.args[0].current_level is IsolationLevel.L3_SOFT
        # 事件六字段
        mocks["publisher"].publish.assert_awaited_once()
        event = mocks["publisher"].publish.await_args.args[0]
        assert type(event).__name__ == "IsolationLevelSwitched"
        assert event.agent_id == AGENT_ID
        assert event.previous_level is IsolationLevel.L4_HARD
        assert event.target_level is IsolationLevel.L3_SOFT
        assert event.trigger_reason == "任务需要软隔离"
        assert event.aggregate_id == AGENT_ID
        assert event.aggregate_type == "Agent"
        # 单钟纪律锚: 事件时刻即状态变更时刻（服务不得独立取钟——对齐实体单 now 双用叙事）
        assert event.switch_timestamp is result.state.updated_at
        assert result.event is event

    async def test_publish_raise_logs_and_returns_result(self, caplog: pytest.LogCaptureFixture) -> None:
        """publish 抛异常 → 记日志不回滚（状态已切换是事实——DC-10）。"""
        state = _make_state(IsolationLevel.L4_HARD)
        service, mocks = _make_service(agent=_make_agent(), state=state, publish_error=RuntimeError("bus broken"))
        with caplog.at_level("WARNING"):
            result = await service.switch_isolation_level(AGENT_ID, IsolationLevel.L3_SOFT, "发布失败面")
        assert result.switched is True, "发布失败不得回滚切换结果"
        mocks["isolation_repo"].save.assert_awaited_once()
        assert any("发布失败" in record.message for record in caplog.records), "必须记 warning 日志"

    async def test_publish_is_success_false_logs_and_returns_result(self, caplog: pytest.LogCaptureFixture) -> None:
        """publish 返回 is_success=False → 结果正常返回 + save 保持 + warning。

        R2-F05 独立命名用例——真实总线失败不抛异常而返回失败结果，
        单 except 分支在真实链路不可达（双分支容错对齐 InstantiateAgentUseCase 先例）。
        """
        failed_result = PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="rabbitmq", success=False, error="rejected"),),
        )
        state = _make_state(IsolationLevel.L4_HARD)
        service, mocks = _make_service(agent=_make_agent(), state=state, publish_result=failed_result)
        with caplog.at_level("WARNING"):
            result = await service.switch_isolation_level(AGENT_ID, IsolationLevel.L3_SOFT, "失败结果面")
        assert result.switched is True
        mocks["isolation_repo"].save.assert_awaited_once(), "失败结果不得回滚持久化"
        assert any("发布失败" in record.message for record in caplog.records)

    async def test_approval_chain_forwarded_to_event(self) -> None:
        """approval_chain 显式转发到事件字段（默认空——MVP 用户直切）。"""
        state = _make_state(IsolationLevel.L4_HARD)
        service, mocks = _make_service(agent=_make_agent(), state=state)
        result = await service.switch_isolation_level(AGENT_ID, IsolationLevel.L2_COLLAB, "协作", approval_chain=("sys_agent",))
        assert result.switched is True
        event = mocks["publisher"].publish.await_args.args[0]
        assert event.approval_chain == ["sys_agent"]


class TestServiceContract:
    """服务端口契约面（Protocol 合规）。"""

    def test_service_implements_port(self) -> None:
        """IsolationManagementService 实现 IsolationManagementServicePort。"""
        service, _ = _make_service()
        assert isinstance(service, IsolationManagementServicePort)

    def test_result_dataclass_shape(self) -> None:
        """IsolationSwitchResult 三字段形态。"""
        result = IsolationSwitchResult(switched=False, state=_make_state(), event=None)
        assert result.switched is False
        assert result.event is None
