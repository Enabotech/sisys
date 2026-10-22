"""InstantiateAgentUseCase 单元测试（Story 5-1）

覆盖 CEO Agent 实例化用例编排（Mock 端口——单元层允许；InMemoryEventBus
成功路径用真实类）：
- 成功编排顺序断言（角色守卫→加载→构建→save→publish；save 以
  ttl=config.state_ttl 调用；先持久化后发布——无持久化即无事件）
- 角色守卫：非 CEO → AgentRoleNotSupportedError(441) 且 loader 未被调用
  （守卫必须先于加载——若先加载，CFO 会先触发配置缺失 440，441 不可达）
- 配置失败（440）传播
- 持久化失败传播且不发布事件（无幽灵事件）
- 发布失败两分支：raise 路径（Mock side_effect）与 is_success=False 路径
  （真实 EventPublisher 返回 PublishResult 不 raise）——结果均仍返回且
  不回滚业务状态（对齐 run_tool_chain L180-185 先例）
- 实体校验 EntityValidationError(242) 透传不包装
- 返回对象含 agent_id 与实体引用；两次实例化 agent_id 不同

Run with:
    poetry run pytest tests/unit/application/use_cases/test_agent_instantiation.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from src.application.ports.agent_config_loader import AgentConfigLoader
from src.application.ports.isolation_management import IsolationManagementServicePort
from src.application.use_cases.agent_instantiation import (
    SUPPORTED_ROLES,
    AgentInstantiationResult,
    InstantiateAgentUseCase,
)
from src.domain.entities.agent import Agent, AgentRole, AgentStatus
from src.domain.entities.isolation_state import IsolationState
from src.domain.events.agent_events import AgentInstantiated
from src.domain.events.base import DomainEvent
from src.domain.events.enums import IsolationLevel
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.exceptions import (
    AgentConfigError,
    AgentRoleNotSupportedError,
    EntityValidationError,
    StorageError,
)
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.event_publisher import EventPublisher
from src.domain.value_objects.agent_config import AgentConfig
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus


class _TracingEventBus(InMemoryEventBus):
    """记录发布调用序的 InMemoryEventBus 子类（编排顺序断言用）。

    子类化而非实例方法赋值（method-assign 抑制注释红线——以类型安全的
    override 记录调用序，published_events/isinstance 语义完整继承）。
    """

    def __init__(self, calls: list[str]) -> None:
        """初始化追踪总线。

        Args:
            calls: 共享调用序列（与 loader/save 闭包写入同一清单）
        """
        super().__init__()
        self._traced_calls = calls

    async def publish(self, event: DomainEvent) -> PublishResult:
        """发布事件并先记录调用序（对齐 InMemoryEventBus.publish 签名）。"""
        self._traced_calls.append("publish")
        return await super().publish(event)


def _make_config(**overrides) -> AgentConfig:
    """工厂：构造合法 CEO 配置。"""
    defaults: dict = {
        "role": AgentRole.CEO,
        "name": "CEO Agent",
        "description": "首席执行官 Agent",
        "version": "1.0.0",
        "responsibilities": ("战略方向",),
        "domain_knowledge": ("宏观趋势",),
        "preferred_model": None,
        "state_ttl": 43200,
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)


def _make_use_case(
    config: AgentConfig | None = None,
    loader_error: Exception | None = None,
    save_error: Exception | None = None,
    publisher: EventPublisher | None = None,
    isolation_init_error: Exception | None = None,
) -> tuple[
    InstantiateAgentUseCase,
    AsyncMock,
    AsyncMock,
    EventPublisher | InMemoryEventBus,
    AsyncMock,
    list[str],
]:
    """构造用例 + Mock 端口 + 调用序记录（Story 5-4 注入第四依赖 isolation_service）。

    Returns:
        (用例, loader mock, repository mock, 事件发布器, isolation mock, 调用序列)
    """
    calls: list[str] = []
    loader = AsyncMock(spec=AgentConfigLoader)

    async def _load(role: AgentRole) -> AgentConfig:
        calls.append("load")
        if loader_error is not None:
            raise loader_error
        return config if config is not None else _make_config()

    loader.load = AsyncMock(side_effect=_load)

    repository = AsyncMock(spec=AgentRepository)

    async def _save(agent: Agent, ttl: int) -> None:
        calls.append(f"save:{ttl}")
        if save_error is not None:
            raise save_error

    repository.save = AsyncMock(side_effect=_save)

    isolation_service = AsyncMock(spec=IsolationManagementServicePort)

    async def _initialize_agent_isolation(
        agent_id: uuid.UUID, default_level: IsolationLevel, ttl_seconds: int
    ) -> IsolationState:
        calls.append(f"iso.init:{default_level.value}:{ttl_seconds}")
        if isolation_init_error is not None:
            raise isolation_init_error
        return IsolationState.initialize(agent_id, default_level)

    isolation_service.initialize_agent_isolation = AsyncMock(side_effect=_initialize_agent_isolation)

    event_bus = publisher if publisher is not None else _TracingEventBus(calls)

    use_case = InstantiateAgentUseCase(
        config_loader=loader,
        repository=repository,
        event_publisher=event_bus,
        isolation_service=isolation_service,
    )
    return use_case, loader, repository, event_bus, isolation_service, calls


# ===================================================================
# 成功编排（顺序与参数契约）
# ===================================================================


class TestSuccessfulOrchestration:
    """成功路径：守卫→加载→构建→save→publish。"""

    async def test_returns_result_with_agent_id_and_entity(self) -> None:
        use_case, _, _, _, _, _ = _make_use_case()
        result = await use_case.execute(role=AgentRole.CEO)
        assert isinstance(result, AgentInstantiationResult)
        assert isinstance(result.agent_id, uuid.UUID)
        assert result.agent.agent_id == result.agent_id
        assert result.agent.role == AgentRole.CEO
        assert result.agent.status == AgentStatus.IDLE

    async def test_entity_built_from_config(self) -> None:
        config = _make_config()
        use_case, _, _, _, _, _ = _make_use_case(config=config)
        result = await use_case.execute(role=AgentRole.CEO)
        agent = result.agent
        assert agent.name == config.name
        assert agent.description == config.description
        assert agent.domain_knowledge == list(config.domain_knowledge)
        assert agent.responsibilities == list(config.responsibilities)
        assert isinstance(agent.domain_knowledge, list), "tuple 直传将使读写往返类型不对称"

    async def test_save_called_with_config_state_ttl(self) -> None:
        """save 以 ttl=config.state_ttl 显式调用（端口 ttl 必填，无仓储默认值）。"""
        use_case, _, repository, _, _, _ = _make_use_case(config=_make_config(state_ttl=777))
        await use_case.execute(role=AgentRole.CEO)
        repository.save.assert_awaited_once()
        save_args, save_kwargs = repository.save.await_args.args, repository.save.await_args.kwargs
        assert save_kwargs.get("ttl") == 777 or save_args[1] == 777

    async def test_orchestration_order_load_save_publish(self) -> None:
        """编排顺序：load → save → iso.init → publish（Story 5-4 隔离初始化插位——
        save 与 publish 之间；守卫先于 load 由非 CEO 用例钉死）。"""
        use_case, _, _, _, _, calls = _make_use_case(config=_make_config(state_ttl=777))
        await use_case.execute(role=AgentRole.CEO)
        assert calls == ["load", "save:777", "iso.init:L4:777", "publish"], f"编排顺序错误: {calls}"

    async def test_event_published_with_fields(self) -> None:
        use_case, _, _, bus, _, _ = _make_use_case(config=_make_config(version="2.5.0"))
        assert isinstance(bus, InMemoryEventBus)
        result = await use_case.execute(role=AgentRole.CEO)
        events = [e for e in bus.published_events if isinstance(e, AgentInstantiated)]
        assert len(events) == 1
        event = events[0]
        assert event.agent_id == result.agent_id
        assert event.role == "ceo"
        assert event.name == "CEO Agent"
        assert event.config_version == "2.5.0"

    async def test_two_executions_produce_distinct_agent_ids(self) -> None:
        use_case, _, _, _, _, _ = _make_use_case()
        first = await use_case.execute(role=AgentRole.CEO)
        second = await use_case.execute(role=AgentRole.CEO)
        assert first.agent_id != second.agent_id


# ===================================================================
# 角色守卫（先于加载）
# ===================================================================


class TestRoleGuard:
    """非 CEO 角色 → 441 且 loader 未被调用。"""

    @pytest.mark.parametrize(
        "role",
        [AgentRole.CFO, AgentRole.CMO, AgentRole.CTO, AgentRole.COO, AgentRole.CHO, AgentRole.AUD, AgentRole.SYS],
    )
    async def test_unsupported_role_raises_441_without_loading(self, role: AgentRole) -> None:
        use_case, loader, _, _, _, calls = _make_use_case()
        with pytest.raises(AgentRoleNotSupportedError) as exc_info:
            await use_case.execute(role=role)
        assert exc_info.value.code == "EXCEPTION_441"
        assert exc_info.value.context["role"] == role.value
        assert loader.load.await_count == 0, "守卫必须先于加载——loader 不应被调用"
        assert calls == [], "守卫阶段不得有任何下游调用"

    async def test_supported_roles_constant_is_ceo_only(self) -> None:
        """SUPPORTED_ROLES 常量真源（V1 扩展 CFO 时仅改此处）。"""
        assert SUPPORTED_ROLES == frozenset({AgentRole.CEO})

    async def test_context_supported_roles_derived_from_constant(self) -> None:
        use_case, _, _, _, _, _ = _make_use_case()
        with pytest.raises(AgentRoleNotSupportedError) as exc_info:
            await use_case.execute(role=AgentRole.CFO)
        assert exc_info.value.context["supported_roles"] == ["ceo"]


# ===================================================================
# 失败传播
# ===================================================================


class TestFailurePropagation:
    """配置失败传播 / 持久化失败传播不发布 / 实体校验透传。"""

    async def test_config_error_propagates(self) -> None:
        use_case, _, _, bus, _, _ = _make_use_case(loader_error=AgentConfigError(role="ceo", reason="文件缺失"))
        with pytest.raises(AgentConfigError) as exc_info:
            await use_case.execute(role=AgentRole.CEO)
        assert exc_info.value.code == "EXCEPTION_440"

    async def test_save_failure_propagates_without_event(self) -> None:
        """持久化失败 → 异常传播且零事件（无持久化即无事件——无幽灵事件）。"""
        use_case, _, _, bus, _, calls = _make_use_case(save_error=StorageError("redis down"))
        assert isinstance(bus, InMemoryEventBus)
        with pytest.raises(StorageError) as exc_info:
            await use_case.execute(role=AgentRole.CEO)
        assert exc_info.value.code == "EXCEPTION_103"
        assert bus.published_events == [], "持久化失败不得发布事件"
        assert calls == ["load", "save:43200"]

    async def test_entity_validation_error_transparent(self) -> None:
        """实体校验 242 透传不包装（config 产出非法 name 的极端路径）。"""
        broken_config = _make_config()
        object.__setattr__(broken_config, "name", "   ")  # 绕过 VO 校验模拟极端缺陷
        use_case, _, _, _, _, _ = _make_use_case(config=broken_config)
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(role=AgentRole.CEO)
        assert exc_info.value.code == "EXCEPTION_242"


# ===================================================================
# 发布失败不回滚（两分支）
# ===================================================================


class TestPublishFailureDoesNotRollback:
    """发布失败 → 结果仍返回、持久化不回滚（对齐 AgentDecided 先例）。"""

    async def test_publish_raise_path_returns_result(self) -> None:
        """raise 路径（仅 Mock side_effect 可触发——真实 EventPublisher 不 raise）。"""
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock(side_effect=RuntimeError("bus broken"))
        use_case, _, repository, _, _, _ = _make_use_case(publisher=publisher)
        result = await use_case.execute(role=AgentRole.CEO)  # 不抛
        assert isinstance(result, AgentInstantiationResult)
        assert repository.save.await_count == 1, "发布失败不得回滚持久化"

    async def test_publish_is_success_false_path_returns_result(self) -> None:
        """is_success=False 路径（真实失败面：PublishResult 空 results → False）。"""
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock(
            return_value=PublishResult(event_id=str(uuid.uuid4()), results=(ChannelResult("x", False, "err"),))
        )
        use_case, _, repository, _, _, _ = _make_use_case(publisher=publisher)
        result = await use_case.execute(role=AgentRole.CEO)  # 不抛
        assert isinstance(result, AgentInstantiationResult)
        repository.save.assert_awaited_once()


# ===================================================================
# Story 5-4: 隔离初始化注入（第四依赖 + fail-fast 编排骨位）
# ===================================================================


class TestIsolationInitializationWiring:
    """实例化即隔离（save → isolation initialize[fail-fast] → publish）。"""

    async def test_initialize_called_once_with_config_level_and_ttl(self) -> None:
        """save 后 initialize_agent_isolation 恰一次——等级与 TTL 均来自 config
        （default_isolation_level + state_ttl 双消费闭环）。"""
        use_case, _, _, _, isolation, _ = _make_use_case(config=_make_config(state_ttl=777))
        result = await use_case.execute(role=AgentRole.CEO)
        isolation.initialize_agent_isolation.assert_awaited_once()
        init_call = isolation.initialize_agent_isolation.await_args
        assert init_call.args[0] == result.agent_id
        assert init_call.args[1] is IsolationLevel.L4_HARD
        assert init_call.args[2] == 777

    async def test_initialize_failure_fails_fast_no_event(self) -> None:
        """初始化抛异常 → execute 向上抛（fail-fast——DC-3 安全基线优先）且
        AgentInstantiated 未发布（publish 在其后——顺序断言）。"""
        from src.domain.exceptions import IsolationLevelNotSupportedError

        init_error = IsolationLevelNotSupportedError(level="L1", supported_levels=("L4", "L3", "L2"))
        use_case, _, _, bus, _, calls = _make_use_case(isolation_init_error=init_error)
        with pytest.raises(IsolationLevelNotSupportedError):
            await use_case.execute(role=AgentRole.CEO)
        assert "publish" not in calls, "初始化失败不得发布 AgentInstantiated（fail-fast 先于 publish）"
        assert calls == ["load", "save:43200", "iso.init:L4:43200"], calls
        if isinstance(bus, InMemoryEventBus):
            assert not bus.published_events

    async def test_guards_zero_regression_with_fourth_dependency(self) -> None:
        """既有守卫 441/440 零回归（第四依赖不影响守卫序）。"""
        use_case, loader, _, _, isolation, calls = _make_use_case()
        with pytest.raises(AgentRoleNotSupportedError):
            await use_case.execute(role=AgentRole.CFO)
        assert calls == []
        loader.load.assert_not_awaited()
        isolation.initialize_agent_isolation.assert_not_awaited()
