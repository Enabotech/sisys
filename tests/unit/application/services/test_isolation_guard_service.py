"""Story 5.5: IsolationGuardService 守卫服务单元测试（三方法守卫序/矩阵消费/白名单真源）

覆盖 AC-2（ensure_agent_executable 放行返回策略）+ AC-3（三面运行时守卫）:
- ensure_agent_executable: 状态入口恰一次（443→447 守卫序透传）+ 策略联查返回
- ensure_agent_access: 矩阵消费（decide_isolation_access 唯一判定源）/ 448 五字段
  context / 449 共享面写 / 放行静默 / actor 状态获取经 isolation_management
  恰一次（禁直查仓储——calls 断言）
- ensure_tool_access: 白名单经 AgentConfig.allowed_tools 真源（config_loader.load(role)
  恰一次）/ L3 共享池短路（config_loader 零调用）/ 443·447 透传 /
  isolation_management 先于 agent_repository 顺序断言

单测 Mock 端口合规: AsyncMock(spec=Protocol) 三替身（隔离管理/Agent 仓储/配置加载）。

Run with:
    poetry run pytest tests/unit/application/services/test_isolation_guard_service.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from src.application.ports.isolation_guard import IsolationGuardPort
from src.application.services.isolation_guard_service import IsolationGuardService
from src.domain.entities.agent import Agent, AgentRole
from src.domain.entities.isolation_state import IsolationState
from src.domain.events.enums import IsolationLevel
from src.domain.value_objects.agent_config import AgentConfig
from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource
from src.domain.value_objects.isolation_policy import DataIsolationMode

# ===================================================================
# 测试基建: 三端口替身工厂（AsyncMock spec 契约 + calls 序列记录）
# ===================================================================


def _make_state(agent_id: uuid.UUID, level: IsolationLevel = IsolationLevel.L4_HARD) -> IsolationState:
    """构造隔离状态聚合（守卫只读 current_level——直构造最小形态）。"""
    now = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
    return IsolationState(
        agent_id=agent_id,
        current_level=level,
        initialized_at=now,
        updated_at=now,
        last_trigger_reason="initial_default",
    )


def _make_agent(agent_id: uuid.UUID) -> Agent:
    """构造 CEO Agent 实体（守卫经 role 取白名单配置）。"""
    return Agent(
        agent_id=agent_id,
        role=AgentRole.CEO,
        name="CEO Agent",
        description="首席执行官 Agent",
        domain_knowledge=["宏观趋势"],
        responsibilities=["战略方向"],
    )


def _make_config(allowed_tools: tuple[str, ...] = ("PESTEL 分析", "SWOT-TOWS")) -> AgentConfig:
    """构造合法 CEO 配置（allowed_tools 可控——白名单真源替身）。"""
    return AgentConfig(
        role=AgentRole.CEO,
        name="CEO Agent",
        description="首席执行官 Agent",
        version="1.0.0",
        responsibilities=("战略方向",),
        domain_knowledge=("宏观趋势",),
        preferred_model=None,
        allowed_tools=allowed_tools,
    )


def _make_guard(
    state: Any = None,
    state_error: Exception | None = None,
    agent: Any = None,
    config: Any = None,
    config_error: Exception | None = None,
) -> tuple[IsolationGuardService, dict[str, Any]]:
    """构造守卫服务与三端口替身（calls 序列记录——顺序断言锚）。

    Args:
        state: get_isolation_state 返回值（IsolationState 或 None）。
        state_error: get_isolation_state 抛出异常（443/447 透传用例）。
        agent: agent_repository.get_by_id 返回值（含 role 的实体）。
        config: agent_config_loader.load 返回值（含 allowed_tools）。
        config_error: agent_config_loader.load 抛出异常。

    Returns:
        (守卫服务实例, 替身与 calls 字典)。
    """
    from unittest.mock import AsyncMock

    from src.application.ports.agent_config_loader import AgentConfigLoader
    from src.application.ports.isolation_management import IsolationManagementServicePort
    from src.domain.ports.agent_repository import AgentRepository

    calls: list[str] = []

    isolation_management = AsyncMock(spec=IsolationManagementServicePort)

    async def _get_state(agent_id: uuid.UUID) -> Any:
        calls.append("mgmt.get_state")
        if state_error is not None:
            raise state_error
        return state

    isolation_management.get_isolation_state = AsyncMock(side_effect=_get_state)

    agent_repository = AsyncMock(spec=AgentRepository)

    async def _get_by_id(agent_id: uuid.UUID) -> Any:
        calls.append("repo.get_by_id")
        return agent

    agent_repository.get_by_id = AsyncMock(side_effect=_get_by_id)

    config_loader = AsyncMock(spec=AgentConfigLoader)

    async def _load(role: Any) -> Any:
        calls.append("loader.load")
        if config_error is not None:
            raise config_error
        return config

    config_loader.load = AsyncMock(side_effect=_load)

    guard = IsolationGuardService(
        isolation_management_service=isolation_management,
        agent_repository=agent_repository,
        agent_config_loader=config_loader,
    )
    return guard, {
        "isolation_management": isolation_management,
        "agent_repository": agent_repository,
        "config_loader": config_loader,
        "calls": calls,
    }


# ===================================================================
# ensure_agent_executable: 工作流执行前置检查（fail-closed）
# ===================================================================


class TestEnsureAgentExecutable:
    """ensure_agent_executable 守卫契约（状态入口 + 策略联查返回）。"""

    async def test_l4_state_returns_l4_policy(self) -> None:
        """L4 状态 → 返回 L4 策略（三维度可消费）+ 状态入口恰一次。"""
        agent_id = uuid.uuid4()
        guard, mocks = _make_guard(state=_make_state(agent_id, IsolationLevel.L4_HARD))
        policy = await guard.ensure_agent_executable(agent_id)
        assert policy.prompt_isolation is True
        assert policy.tool_isolation is True
        assert policy.data_isolation is DataIsolationMode.READ_ONLY
        mocks["isolation_management"].get_isolation_state.assert_awaited_once_with(agent_id)

    async def test_l3_state_returns_l3_policy(self) -> None:
        """L3 状态 → 返回 L3 策略（等级随动——策略联查非硬编码）。"""
        agent_id = uuid.uuid4()
        guard, _ = _make_guard(state=_make_state(agent_id, IsolationLevel.L3_SOFT))
        policy = await guard.ensure_agent_executable(agent_id)
        assert policy.tool_isolation is False
        assert policy.data_isolation is DataIsolationMode.RESTRICTED_WRITE

    async def test_443_passthrough(self) -> None:
        """443 透传（状态入口守卫序——原样向上零改写）。"""
        from src.domain.exceptions import AgentNotFoundError

        guard, _ = _make_guard(state_error=AgentNotFoundError(agent_id="missing"))
        with pytest.raises(AgentNotFoundError) as exc_info:
            await guard.ensure_agent_executable(uuid.uuid4())
        assert exc_info.value.code == "EXCEPTION_443"

    async def test_447_passthrough(self) -> None:
        """447 透传（隔离态不可证明即拒绝——fail-closed）。"""
        from src.domain.exceptions import IsolationStateNotInitializedError

        guard, _ = _make_guard(state_error=IsolationStateNotInitializedError(agent_id="missing"))
        with pytest.raises(IsolationStateNotInitializedError) as exc_info:
            await guard.ensure_agent_executable(uuid.uuid4())
        assert exc_info.value.code == "EXCEPTION_447"


# ===================================================================
# ensure_agent_access: 跨 Agent 资源访问守卫
# ===================================================================


class TestEnsureAgentAccess:
    """ensure_agent_access 守卫契约（矩阵消费 + 异常翻译单点）。"""

    async def test_cross_private_raises_448_with_five_context_fields(self) -> None:
        """cross + private → 448 且 context 五字段（reason 含等级名「硬隔离」——
        并发串扰判别锚）。"""
        from src.domain.exceptions import IsolationAccessViolationError

        actor_id, target_id = uuid.uuid4(), uuid.uuid4()
        guard, _ = _make_guard(state=_make_state(actor_id, IsolationLevel.L4_HARD))
        with pytest.raises(IsolationAccessViolationError) as exc_info:
            await guard.ensure_agent_access(actor_id, target_id, IsolationResource.PROFILE, AccessOperation.READ)
        error = exc_info.value
        assert error.code == "EXCEPTION_448"
        assert error.context["actor_agent_id"] == str(actor_id)
        assert error.context["target_agent_id"] == str(target_id)
        assert error.context["resource"] == "profile"
        assert error.context["operation"] == "read"
        assert "硬隔离" in error.context["reason"]

    async def test_cross_private_write_l3_reason_contains_soft_name(self) -> None:
        """cross + private WRITE + L3 → 448 且 reason 含「软隔离」（等级名随动）。"""
        from src.domain.exceptions import IsolationAccessViolationError

        actor_id, target_id = uuid.uuid4(), uuid.uuid4()
        guard, _ = _make_guard(state=_make_state(actor_id, IsolationLevel.L3_SOFT))
        with pytest.raises(IsolationAccessViolationError) as exc_info:
            await guard.ensure_agent_access(actor_id, target_id, IsolationResource.MEMORY, AccessOperation.WRITE)
        assert "软隔离" in exc_info.value.context["reason"]

    async def test_cross_shared_read_allowed_silently(self) -> None:
        """cross + shared READ → 放行静默（断言型守卫——无异常即放行）。"""
        actor_id, target_id = uuid.uuid4(), uuid.uuid4()
        guard, _ = _make_guard(state=_make_state(actor_id, IsolationLevel.L4_HARD))
        await guard.ensure_agent_access(actor_id, target_id, IsolationResource.BLACKBOARD, AccessOperation.READ)

    async def test_cross_shared_write_l4_raises_449(self) -> None:
        """cross + shared WRITE + L4（READ_ONLY）→ 449（reason=data_isolation:read_only）。"""
        from src.domain.exceptions import IsolationOperationForbiddenError

        actor_id, target_id = uuid.uuid4(), uuid.uuid4()
        guard, _ = _make_guard(state=_make_state(actor_id, IsolationLevel.L4_HARD))
        with pytest.raises(IsolationOperationForbiddenError) as exc_info:
            await guard.ensure_agent_access(actor_id, target_id, IsolationResource.BLACKBOARD, AccessOperation.WRITE)
        error = exc_info.value
        assert error.code == "EXCEPTION_449"
        assert error.context["agent_id"] == str(actor_id)
        assert error.context["reason"] == "data_isolation:read_only"

    async def test_cross_shared_write_l2_allowed(self) -> None:
        """cross + shared WRITE + L2（FREE_WRITE）→ 放行（策略表活消费）。"""
        actor_id, target_id = uuid.uuid4(), uuid.uuid4()
        guard, _ = _make_guard(state=_make_state(actor_id, IsolationLevel.L2_COLLAB))
        await guard.ensure_agent_access(actor_id, target_id, IsolationResource.BLACKBOARD, AccessOperation.WRITE)

    async def test_self_private_allowed(self) -> None:
        """self（actor==target）+ private → 放行（自身资源自由读写）。"""
        actor_id = uuid.uuid4()
        guard, _ = _make_guard(state=_make_state(actor_id, IsolationLevel.L4_HARD))
        for operation in (AccessOperation.READ, AccessOperation.WRITE):
            await guard.ensure_agent_access(actor_id, actor_id, IsolationResource.AGENT_STATE, operation)

    async def test_self_shared_write_l4_still_449(self) -> None:
        """self + shared WRITE + L4 → 449（shared 面写不因 self 豁免——
        单主体轴与跨主体轴正交）。"""
        from src.domain.exceptions import IsolationOperationForbiddenError

        actor_id = uuid.uuid4()
        guard, _ = _make_guard(state=_make_state(actor_id, IsolationLevel.L4_HARD))
        with pytest.raises(IsolationOperationForbiddenError):
            await guard.ensure_agent_access(actor_id, actor_id, IsolationResource.BLACKBOARD, AccessOperation.WRITE)

    async def test_actor_state_via_isolation_management_exactly_once(self) -> None:
        """actor 状态获取经 isolation_management_service 恰一次（禁直查仓储——
        443/447 守卫序复用；repo 零调用；cross+private 预期 448 后断言计数）。"""
        from src.domain.exceptions import IsolationAccessViolationError

        actor_id, target_id = uuid.uuid4(), uuid.uuid4()
        guard, mocks = _make_guard(state=_make_state(actor_id, IsolationLevel.L4_HARD))
        with pytest.raises(IsolationAccessViolationError):
            await guard.ensure_agent_access(actor_id, target_id, IsolationResource.PROFILE, AccessOperation.READ)
        mocks["isolation_management"].get_isolation_state.assert_awaited_once_with(actor_id)
        mocks["agent_repository"].get_by_id.assert_not_awaited()
        assert mocks["calls"] == ["mgmt.get_state"]

    async def test_443_passthrough_on_access(self) -> None:
        """443 透传（agent 不在案时任何 ensure_* 均拒）。"""
        from src.domain.exceptions import AgentNotFoundError

        guard, _ = _make_guard(state_error=AgentNotFoundError(agent_id="missing"))
        with pytest.raises(AgentNotFoundError):
            await guard.ensure_agent_access(uuid.uuid4(), uuid.uuid4(), IsolationResource.MEMORY, AccessOperation.READ)

    async def test_447_passthrough_on_access(self) -> None:
        """447 透传（隔离键缺失时任何 ensure_* 均拒）。"""
        from src.domain.exceptions import IsolationStateNotInitializedError

        guard, _ = _make_guard(state_error=IsolationStateNotInitializedError(agent_id="missing"))
        with pytest.raises(IsolationStateNotInitializedError):
            await guard.ensure_agent_access(uuid.uuid4(), uuid.uuid4(), IsolationResource.MEMORY, AccessOperation.READ)


# ===================================================================
# ensure_tool_access: 工具白名单守卫
# ===================================================================


class TestEnsureToolAccess:
    """ensure_tool_access 守卫契约（白名单真源 + 共享池短路）。"""

    async def test_l4_tool_in_allowlist_allowed(self) -> None:
        """L4 + 白名单内 → 放行 + config_loader.load(role) 恰一次（真源通道）。"""
        agent_id = uuid.uuid4()
        guard, mocks = _make_guard(
            state=_make_state(agent_id, IsolationLevel.L4_HARD),
            agent=_make_agent(agent_id),
            config=_make_config(allowed_tools=("PESTEL 分析", "SWOT-TOWS")),
        )
        await guard.ensure_tool_access(agent_id, "PESTEL 分析")
        mocks["config_loader"].load.assert_awaited_once()
        load_call = mocks["config_loader"].load.await_args
        assert load_call.args[0] is AgentRole.CEO

    async def test_l4_tool_outside_allowlist_raises_449(self) -> None:
        """L4 + 白名单外 → 449 context 三字段（reason 含工具名——不泄露白名单明细）。"""
        from src.domain.exceptions import IsolationOperationForbiddenError

        agent_id = uuid.uuid4()
        guard, _ = _make_guard(
            state=_make_state(agent_id, IsolationLevel.L4_HARD),
            agent=_make_agent(agent_id),
            config=_make_config(allowed_tools=("PESTEL 分析",)),
        )
        with pytest.raises(IsolationOperationForbiddenError) as exc_info:
            await guard.ensure_tool_access(agent_id, "不在白名单的工具")
        error = exc_info.value
        assert error.code == "EXCEPTION_449"
        assert set(error.context) == {"agent_id", "operation", "reason"}
        assert error.context["agent_id"] == str(agent_id)
        assert error.context["reason"] == "tool_not_in_allowlist:不在白名单的工具"

    async def test_l3_shared_pool_allows_any_tool_without_config_load(self) -> None:
        """L3（tool_isolation=False）→ 共享池放行 + config_loader 零调用
        （短路优化——共享池不查白名单）。"""
        agent_id = uuid.uuid4()
        guard, mocks = _make_guard(state=_make_state(agent_id, IsolationLevel.L3_SOFT))
        await guard.ensure_tool_access(agent_id, "任意工具名")
        mocks["config_loader"].load.assert_not_awaited()
        mocks["agent_repository"].get_by_id.assert_not_awaited()

    async def test_empty_allowlist_denies_all(self) -> None:
        """空白名单（未配置角色）→ 全拒（fail-closed 安全默认实证）。"""
        from src.domain.exceptions import IsolationOperationForbiddenError

        agent_id = uuid.uuid4()
        guard, _ = _make_guard(
            state=_make_state(agent_id, IsolationLevel.L4_HARD),
            agent=_make_agent(agent_id),
            config=_make_config(allowed_tools=()),
        )
        with pytest.raises(IsolationOperationForbiddenError):
            await guard.ensure_tool_access(agent_id, "PESTEL 分析")

    async def test_443_passthrough_on_tool(self) -> None:
        """443 透传（状态入口先于白名单查询）。"""
        from src.domain.exceptions import AgentNotFoundError

        guard, _ = _make_guard(state_error=AgentNotFoundError(agent_id="missing"))
        with pytest.raises(AgentNotFoundError):
            await guard.ensure_tool_access(uuid.uuid4(), "PESTEL 分析")

    async def test_447_passthrough_on_tool(self) -> None:
        """447 透传（隔离态不可证明即拒绝）。"""
        from src.domain.exceptions import IsolationStateNotInitializedError

        guard, _ = _make_guard(state_error=IsolationStateNotInitializedError(agent_id="missing"))
        with pytest.raises(IsolationStateNotInitializedError):
            await guard.ensure_tool_access(uuid.uuid4(), "PESTEL 分析")

    async def test_isolation_management_precedes_agent_repository(self) -> None:
        """顺序断言: 状态入口（isolation_management）先于 role 取得
        （agent_repository）——443 由 isolation_management 先拦。"""
        agent_id = uuid.uuid4()
        guard, mocks = _make_guard(
            state=_make_state(agent_id, IsolationLevel.L4_HARD),
            agent=_make_agent(agent_id),
            config=_make_config(),
        )
        await guard.ensure_tool_access(agent_id, "PESTEL 分析")
        assert mocks["calls"] == ["mgmt.get_state", "repo.get_by_id", "loader.load"]


class TestGuardPortContract:
    """守卫服务满足 IsolationGuardPort 端口契约（runtime_checkable isinstance）。"""

    def test_guard_implements_port(self) -> None:
        guard, _ = _make_guard()
        assert isinstance(guard, IsolationGuardPort)
