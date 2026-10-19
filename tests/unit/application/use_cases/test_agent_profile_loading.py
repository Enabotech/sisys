"""LoadAgentProfileUseCase 单元测试（Story 5-2 — Agent 身份档案加载）

覆盖档案加载用例六步编排（Mock 端口——单元层允许；InMemoryEventBus 成功路径
用真实类）：
- 编排顺序断言：get_by_id → 存在性守卫 → 角色守卫 → loader.load →
  list_active_skills → publish（Mock calls 序 + _TracingEventBus 记录 publish 段）
- 存在性守卫：get_by_id 返回 None → AgentNotFoundError(443) 且 loader 未被调用
  （守卫顺序契约：不存在实体的 role 无从判定——存在性必须最先）
- 角色守卫：非 CEO 实体 → AgentRoleNotSupportedError(441) 且 loader 未被调用
- loader 失败（442）传播
- list_active_skills 恰被调用一次且返回值进入 DTO tools_l1（透传不断言过滤）
- token 计量口径：(identity + soul + L1 拼接视图 chars) // 4
- 发布失败两分支（AsyncMock(spec=EventPublisher)——raise / is_success=False）：
  结果均仍返回且不回滚
- 返回 DTO 四字段；事件 active_skill_count 与 DTO 同源派生

Run with:
    poetry run pytest tests/unit/application/use_cases/test_agent_profile_loading.py -v
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from src.application.ports.agent_profile_loader import AgentProfileLoader
from src.application.ports.skill_loader import ToolMetadata
from src.application.ports.skill_selector import SkillSelectorPort
from src.domain.entities.agent import Agent, AgentRole
from src.domain.events.agent_events import AgentProfileLoaded
from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.exceptions import (
    AgentNotFoundError,
    AgentProfileError,
    AgentRoleNotSupportedError,
)
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.event_publisher import EventPublisher
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

if TYPE_CHECKING:
    # 类型注解专用（from __future__ annotations 惰性求值）——运行时零 import，
    # 不违反 Story 5-2 新模块延迟 import 纪律
    from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase


class _TracingEventBus(InMemoryEventBus):
    """记录发布调用序的 InMemoryEventBus 子类（编排顺序断言用——5-1 L50-69 先例）。

    子类化而非实例方法赋值（method-assign 抑制注释红线——以类型安全的
    override 记录调用序，published_events/isinstance 语义完整继承）。
    """

    def __init__(self, calls: list[str]) -> None:
        """初始化追踪总线。

        Args:
            calls: 共享调用序列（与 loader/selector 闭包写入同一清单）
        """
        super().__init__()
        self._traced_calls = calls

    async def publish(self, event: DomainEvent) -> PublishResult:
        """发布事件并先记录调用序（对齐 InMemoryEventBus.publish 签名）。"""
        self._traced_calls.append("publish")
        return await super().publish(event)


def _make_agent(role: AgentRole = AgentRole.CEO) -> Agent:
    """工厂：构造持久化态 Agent 实体（Mock get_by_id 返回值）。"""
    return Agent(
        agent_id=uuid.uuid4(),
        role=role,
        name=f"{role.value.upper()} Agent",
        description="测试实体",
    )


def _make_profile_vo(agent_id: uuid.UUID, role: AgentRole):
    """工厂：构造合法 AgentProfile（延迟 import——Story 5-2 新模块纪律）。"""
    from src.domain.value_objects.agent_profile import AgentProfile

    return AgentProfile(
        agent_id=agent_id,
        role=role,
        identity="IDENTITY 内容——CEO 战略方向最终决策高管协调",
        code_of_conduct="CODE 内容——证据优先角色隔离",
        soul="SOUL 内容——高管决策视角宏观趋势竞争格局",
        user_preferences="USER 内容——结论先行",
        memory="MEMORY 内容——静态种子占位",
        heartbeat="HEARTBEAT 内容——每日频率占位",
    )


def _make_metadata(slug: str) -> ToolMetadata:
    """工厂：构造 ACTIVE ToolMetadata（L1 元数据替身）。"""
    return ToolMetadata(
        tool_name=f"工具 {slug}",
        slug=slug,
        category="strategic_selection",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        description=f"{slug} 的中文描述",
        status="active",
    )


def _make_use_case(
    agent: Agent | None = None,
    loader_error: Exception | None = None,
    selector_error: Exception | None = None,
    publisher: EventPublisher | None = None,
    tools: tuple[ToolMetadata, ...] | None = None,
) -> tuple[
    "LoadAgentProfileUseCase",
    AsyncMock,
    AsyncMock,
    AsyncMock,
    EventPublisher | InMemoryEventBus,
    list[str],
]:
    """构造用例 + Mock 端口 + 调用序记录。

    Returns:
        (用例, loader mock, repository mock, selector mock, 事件发布器, 调用序列)
    """
    from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase

    calls: list[str] = []
    agent = agent if agent is not None else _make_agent()

    loader = AsyncMock(spec=AgentProfileLoader)

    async def _load(role: AgentRole, agent_id: uuid.UUID):
        calls.append("load")
        if loader_error is not None:
            raise loader_error
        return _make_profile_vo(agent_id, role)

    loader.load = AsyncMock(side_effect=_load)

    repository = AsyncMock(spec=AgentRepository)

    async def _get_by_id(agent_id: uuid.UUID):
        calls.append("get_by_id")
        return agent

    repository.get_by_id = AsyncMock(side_effect=_get_by_id)

    selector = AsyncMock(spec=SkillSelectorPort)
    selector_tools = tools if tools is not None else tuple(_make_metadata(f"slug-{i}") for i in range(3))

    async def _list_active_skills() -> tuple[ToolMetadata, ...]:
        calls.append("list_active_skills")
        if selector_error is not None:
            raise selector_error
        return selector_tools

    selector.list_active_skills = AsyncMock(side_effect=_list_active_skills)

    event_bus = publisher if publisher is not None else _TracingEventBus(calls)

    use_case = LoadAgentProfileUseCase(
        profile_loader=loader,
        repository=repository,
        skill_selector=selector,
        event_publisher=event_bus,
    )
    return use_case, loader, repository, selector, event_bus, calls


# ===================================================================
# 成功编排（顺序与 DTO 契约）
# ===================================================================


class TestSuccessfulOrchestration:
    """六步编排顺序 + DTO 四字段 + 事件字段。"""

    async def test_orchestration_order(self) -> None:
        """调用序：get_by_id → load → list_active_skills → publish（守卫在 load 前）。"""
        use_case, loader, _, _, _, calls = _make_use_case()
        await use_case.execute(agent_id=_make_agent().agent_id)
        assert calls == ["get_by_id", "load", "list_active_skills", "publish"], (
            "编排顺序契约：存在性守卫(get_by_id) → 加载(load) → L1 组装(list_active_skills) → 发布(publish)"
        )

    async def test_result_dto_four_fields(self) -> None:
        """返回 DTO 含 agent_id/role/profile/tools_l1/startup_context_tokens。"""
        from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult

        agent = _make_agent()
        use_case, _, _, _, _, _ = _make_use_case(agent=agent)
        result = await use_case.execute(agent_id=agent.agent_id)
        assert isinstance(result, AgentProfileLoadResult)
        assert result.agent_id == agent.agent_id
        assert result.role == AgentRole.CEO
        assert result.profile.agent_id == agent.agent_id
        assert "CEO" in result.profile.identity
        assert isinstance(result.tools_l1, tuple) and len(result.tools_l1) == 3
        assert isinstance(result.startup_context_tokens, int) and result.startup_context_tokens > 0

    async def test_list_active_skills_called_once_passthrough(self) -> None:
        """list_active_skills 恰被调用一次且其返回值原样进入 DTO（过滤逻辑单点在 SkillSelector）。"""
        tools = tuple(_make_metadata(f"slug-{i}") for i in range(5))
        use_case, _, _, selector, _, _ = _make_use_case(tools=tools)
        result = await use_case.execute(agent_id=_make_agent().agent_id)
        selector.list_active_skills.assert_awaited_once()
        assert result.tools_l1 == tools

    async def test_token_metering_formula(self) -> None:
        """计量口径：(identity + soul + L1 拼接视图) chars // 4（拼接后一次计量）。"""
        tools = tuple(_make_metadata(f"slug-{i}") for i in range(3))
        use_case, _, _, _, _, _ = _make_use_case(tools=tools)
        result = await use_case.execute(agent_id=_make_agent().agent_id)
        l1_view = "\n".join(f"{meta.tool_name}: {meta.description}" for meta in tools)
        expected = (len(result.profile.identity) + len(result.profile.soul) + len(l1_view)) // 4
        assert result.startup_context_tokens == expected

    async def test_event_published_with_four_fields(self) -> None:
        """InMemoryEventBus 捕获 AgentProfileLoaded 且四字段正确（active_skill_count 同源派生）。"""
        agent = _make_agent()
        use_case, _, _, _, event_bus, _ = _make_use_case(agent=agent)
        result = await use_case.execute(agent_id=agent.agent_id)

        # 类型守卫收窄（默认路径即 _TracingEventBus，运行时恒真——published_events
        # 仅 InMemoryEventBus 族持有，显式 isinstance 消除联合类型歧义）
        assert isinstance(event_bus, InMemoryEventBus)
        events = [e for e in event_bus.published_events if isinstance(e, AgentProfileLoaded)]
        assert events, "未发布 AgentProfileLoaded 事件"
        event = events[-1]
        assert event.agent_id == agent.agent_id
        assert event.role == AgentRole.CEO.value
        assert event.startup_context_tokens == result.startup_context_tokens
        assert event.active_skill_count == len(result.tools_l1), "active_skill_count 与 DTO 同源派生"
        assert event.aggregate_type == "Agent"


# ===================================================================
# 存在性守卫（443——必须最先）
# ===================================================================


class TestExistenceGuard:
    """get_by_id 返回 None → 443 且后续未触达。"""

    async def test_agent_not_found_raises_443(self) -> None:
        """随机 agent_id 查无 → AgentNotFoundError(443) 且 context 携带 str 形态 agent_id。"""
        from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase

        loader = AsyncMock(spec=AgentProfileLoader)
        repository = AsyncMock(spec=AgentRepository)
        repository.get_by_id = AsyncMock(return_value=None)
        selector = AsyncMock(spec=SkillSelectorPort)
        use_case = LoadAgentProfileUseCase(
            profile_loader=loader,
            repository=repository,
            skill_selector=selector,
            event_publisher=InMemoryEventBus(),
        )

        agent_id = uuid.uuid4()
        with pytest.raises(AgentNotFoundError) as exc_info:
            await use_case.execute(agent_id=agent_id)
        assert exc_info.value.code == "EXCEPTION_443"
        assert exc_info.value.context["agent_id"] == str(agent_id), "raise 侧 str(agent_id) 形态"

    async def test_agent_not_found_loader_not_called(self) -> None:
        """443 守卫先于档案加载——loader/selector 均未被调用。"""
        from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase

        loader = AsyncMock(spec=AgentProfileLoader)
        repository = AsyncMock(spec=AgentRepository)
        repository.get_by_id = AsyncMock(return_value=None)
        selector = AsyncMock(spec=SkillSelectorPort)
        use_case = LoadAgentProfileUseCase(
            profile_loader=loader,
            repository=repository,
            skill_selector=selector,
            event_publisher=InMemoryEventBus(),
        )

        with pytest.raises(AgentNotFoundError):
            await use_case.execute(agent_id=uuid.uuid4())
        loader.load.assert_not_awaited()
        selector.list_active_skills.assert_not_awaited()


# ===================================================================
# 角色守卫（441 复用——先于档案加载）
# ===================================================================


class TestRoleGuard:
    """非 CEO 实体 → 441 且 loader 未被调用。"""

    async def test_cfo_agent_raises_441(self) -> None:
        """CFO 实体 → AgentRoleNotSupportedError(441)。"""
        use_case, _, _, _, _, _ = _make_use_case(agent=_make_agent(role=AgentRole.CFO))
        with pytest.raises(AgentRoleNotSupportedError) as exc_info:
            await use_case.execute(agent_id=uuid.uuid4())
        assert exc_info.value.code == "EXCEPTION_441"

    async def test_role_guard_before_load(self) -> None:
        """角色守卫先于档案加载（非 CEO 档案目录不存在，先 441 才可达）。"""
        use_case, loader, _, selector, _, calls = _make_use_case(agent=_make_agent(role=AgentRole.CFO))
        with pytest.raises(AgentRoleNotSupportedError):
            await use_case.execute(agent_id=uuid.uuid4())
        loader.load.assert_not_awaited()
        selector.list_active_skills.assert_not_awaited()
        assert calls == ["get_by_id"], "守卫先于加载——仅存在性检查被触达"


# ===================================================================
# loader 失败传播（442）
# ===================================================================


class TestLoaderFailurePropagation:
    """档案加载失败（442）传播不吞。"""

    async def test_profile_error_propagates(self) -> None:
        use_case, _, _, _, _, _ = _make_use_case(loader_error=AgentProfileError(reason="档案文件缺失"))
        with pytest.raises(AgentProfileError) as exc_info:
            await use_case.execute(agent_id=uuid.uuid4())
        assert exc_info.value.code == "EXCEPTION_442"


# ===================================================================
# 发布失败两分支（不回滚——AsyncMock(spec=EventPublisher) 注入）
# ===================================================================


class TestPublishFailureDoesNotRollback:
    """发布失败两分支：结果仍返回（先加载后发布，失败仅记日志）。

    真实总线的失败面从用例不可达（新 event_id 不触发去重、成功路径
    is_success 恒 True）——失败分支必须 AsyncMock(spec=EventPublisher) 注入
    （5-1 test_agent_instantiation.py L261-283 先例）。
    """

    async def test_publish_raise_path_returns_result(self) -> None:
        """raise 路径（side_effect=RuntimeError）→ 不抛、结果仍返回。"""
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock(side_effect=RuntimeError("bus broken"))
        use_case, loader, _, _, _, _ = _make_use_case(publisher=publisher)
        await use_case.execute(agent_id=_make_agent().agent_id)  # 不抛
        loader.load.assert_awaited_once(), "发布失败不得回滚已完成的加载"

    async def test_publish_is_success_false_path_returns_result(self) -> None:
        """is_success=False 路径（空 results 的 PublishResult）→ 不抛、结果仍返回。"""
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock(
            return_value=PublishResult(event_id=str(uuid.uuid4()), results=(ChannelResult("x", False, "err"),))
        )
        use_case, _, _, _, _, _ = _make_use_case(publisher=publisher)
        result = await use_case.execute(agent_id=_make_agent().agent_id)  # 不抛
        assert result.startup_context_tokens > 0, "is_success=False 路径业务结果完整返回"
