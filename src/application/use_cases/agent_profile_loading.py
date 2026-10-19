"""应用层档案加载用例（Story 5-2 — Agent 身份档案加载）

LoadAgentProfileUseCase——Agent 身份档案加载的应用服务编排：
**agent 存在性守卫（443）→ 角色守卫（441）→ 六档案加载（442）→ L1 组装 →
token 计量 → 发布 AgentProfileLoaded 事件**。

守卫顺序契约（5-1「守卫先于加载」教训的级联应用）：
- 存在性必须最先——不存在实体的 role 无从判定
- 角色守卫先于档案加载——非 CEO 角色的档案目录不存在，先 441 才可达

编排模板：agent_instantiation.py（5-1）——事件发布两分支（is_success==False
普通 logger.error / raise 分支 exc_info=True——两分支形态照旧不统一）失败均
记日志不回滚（先加载后发布）。

token 计量口径（DC-3 口径②）：startup_context_tokens = (IDENTITY + SOUL +
L1 拼接视图) chars // 4——L1 视图为 "\n".join(f"{tool_name}: {description}")
拼接文本（TOOLS.md 内容子集），非 TOOLS.md 全文口径。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from src.application.ports.agent_profile_loader import AgentProfileLoader
from src.application.ports.skill_loader import ToolMetadata
from src.application.ports.skill_selector import SkillSelectorPort
from src.application.use_cases.agent_instantiation import SUPPORTED_ROLES
from src.domain.entities.agent import AgentRole
from src.domain.events.agent_events import AgentProfileLoaded
from src.domain.exceptions import AgentNotFoundError, AgentRoleNotSupportedError
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.event_publisher import EventPublisher
from src.domain.value_objects.agent_profile import AgentProfile

logger = logging.getLogger(__name__)

# MVP 开放角色唯一真源（复用 5-1 常量——V1 开 CFO 只改一处）：SUPPORTED_ROLES


@dataclass(frozen=True)
class AgentProfileLoadResult:
    """档案加载用例结果 DTO（对齐 AgentInstantiationResult L46-56 先例）。

    Attributes:
        agent_id: 档案归属的 Agent 实例标识
        role: Agent 角色
        profile: 六档案（domain VO——不含 ToolMetadata，DC-7 分层裁定）
        tools_l1: L1 元数据清单（仅 active，application 层类型——ACTIVE 过滤
            单点在 SkillSelector，用例透传）
        startup_context_tokens: IDENTITY+SOUL+TOOLS_L1 拼接后一次 //4 合计计量
    """

    agent_id: uuid.UUID
    role: AgentRole
    profile: AgentProfile
    tools_l1: tuple[ToolMetadata, ...]
    startup_context_tokens: int


def _estimate_tokens(text: str) -> int:
    """token 计量启发式（chars // 4——与 InMemorySkillLoader._estimate_tokens 同款口径）。

    Args:
        text: 待计量文本

    Returns:
        int: 估算 token 数（中文低估口径：0.25 token/字符——真实 tokenizer
            语义下预算偏松，5.3 注入 LLM 前需按真实 tokenizer 复算）
    """
    return len(text) // 4


class LoadAgentProfileUseCase:
    """Agent 身份档案加载用例（幂等只读——纯读 + 发布事件，不改变被读状态）。

    六步编排：存在性守卫 → 角色守卫 → 六档案加载 → L1 组装 → token 计量 →
    发布事件（发布失败记日志不回滚）。

    Attributes:
        _profile_loader: 档案加载端口（六档案 → AgentProfile）
        _repository: Agent 仓储端口（get_by_id 存在性守卫）
        _skill_selector: Skill 选择器端口（ACTIVE 全量 L1 清单——DC-8 注入
            Selector 而非直组 skill_loader：ACTIVE 过滤逻辑单点在 Selector）
        _event_publisher: 事件发布端口
    """

    def __init__(
        self,
        profile_loader: AgentProfileLoader,
        repository: AgentRepository,
        skill_selector: SkillSelectorPort,
        event_publisher: EventPublisher,
    ) -> None:
        """初始化用例。

        Args:
            profile_loader: 档案加载端口
            repository: Agent 仓储端口
            skill_selector: Skill 选择器端口
            event_publisher: 事件发布端口
        """
        self._profile_loader = profile_loader
        self._repository = repository
        self._skill_selector = skill_selector
        self._event_publisher = event_publisher

    async def execute(self, agent_id: uuid.UUID) -> AgentProfileLoadResult:
        """执行档案加载六步编排。

        Args:
            agent_id: 目标 Agent 实例标识（档案归属锚点）

        Returns:
            AgentProfileLoadResult: profile + tools_l1 + 启动上下文计量

        Raises:
            AgentNotFoundError: EXCEPTION_443——agent_id 在仓储中不存在（键不
                存在或 TTL 过期后重放旧 agent_id）
            AgentRoleNotSupportedError: EXCEPTION_441——实体角色不在
                SUPPORTED_ROLES（MVP 仅 CEO）
            AgentProfileError: EXCEPTION_442——档案加载失败（加载器传播）
            SkillNotFoundError: EXCEPTION_387——L1 组装失败（TOOLS.md L1 索引
                与 skill_manifest 漂移、或 TOOLS.md 不可读被降级回退空索引时，
                枚举 slug 查元数据未命中；SkillSelector 传播不静默——Skill
                资产缺陷归 skill 异常族，非 442 第 8 类——R3-F2）
        """
        # 1. 存在性守卫（必须最先——不存在实体的 role 无从判定）
        agent = await self._repository.get_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id=str(agent_id))

        # 2. 角色守卫（先于档案加载——非 CEO 角色的档案目录不存在，先 441 才可达）
        if agent.role not in SUPPORTED_ROLES:
            raise AgentRoleNotSupportedError(
                role=agent.role.value,
                supported_roles=tuple(sorted(supported.value for supported in SUPPORTED_ROLES)),
            )

        # 3. 六档案加载（442 失败由加载器传播）
        profile = await self._profile_loader.load(role=agent.role, agent_id=agent_id)

        # 4. L1 组装（ACTIVE 过滤逻辑单点在 SkillSelector——用例一次调用消费）
        tools = await self._skill_selector.list_active_skills()

        # 5. token 计量（IDENTITY+SOUL+L1 拼接视图一次 //4——DC-3 口径②）
        l1_view = "\n".join(f"{meta.tool_name}: {meta.description}" for meta in tools)
        startup_context_tokens = _estimate_tokens(profile.identity + profile.soul + l1_view)

        # 6. 发布事件（失败记日志不回滚——先加载后发布；重复调用重复发布，
        #    事件带 event_id 消费方可按其幂等去重，「幂等只读」指不改变被读状态）
        event = AgentProfileLoaded(
            agent_id=agent_id,
            role=agent.role.value,
            startup_context_tokens=startup_context_tokens,
            active_skill_count=len(tools),
        )
        try:
            publish_result = await self._event_publisher.publish(event)
            if publish_result is not None and not publish_result.is_success:
                logger.error(
                    "AgentProfileLoaded 事件发布未成功: agent_id=%s channels=%s",
                    agent_id,
                    publish_result.results,
                )
        except Exception as exc:
            # 事件发布失败不阻塞业务结果（对齐 agent_instantiation 先例）
            logger.error("Failed to publish AgentProfileLoaded event: %s", exc, exc_info=True)

        return AgentProfileLoadResult(
            agent_id=agent_id,
            role=agent.role,
            profile=profile,
            tools_l1=tools,
            startup_context_tokens=startup_context_tokens,
        )
