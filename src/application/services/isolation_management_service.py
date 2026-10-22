"""应用层 EIP 隔离管理服务模块（Story 5.4 — EIP 弹性隔离协议基础）

实现 IsolationManagementServicePort（应用层服务，R2——组合注入三 domain 端口
+ 一个同层应用端口四依赖）:
- isolation_repository（domain 端口——隔离状态持久化）
- agent_repository（domain 端口——443 存在性守卫）
- event_publisher（domain 端口——切换事件发布）
- agent_config_loader（应用端口——switch 重置 TTL 真源 AgentConfig.state_ttl，R1-F01）

守卫序契约（DC-5）:
- get/switch: Agent 存在(443) → 隔离状态存在(447) → 等级合法(446 实体内聚)
- 等级合法性校验内聚实体（initialize/switch_to 两入口统一——CLI 只做
  字符串→枚举转换守卫，服务不重复校验向上透传）

no-op 语义（DC-5）: switch_to 返回 False → switched=False + 零仓储写 +
零事件发布（幂等；「切换」事件语义要求前后等级相异；TTL 不刷新——查询型
重复调用不得无限续期）。

事件发布失败容错（DC-10）: 记日志不回滚——状态已切换是事实、事件是通知；
真实失败面为 PublishResult.is_success == False（DualChannelEventBus 捕获异常
返回失败结果不抛出）与 raise 两分支（InstantiateAgentUseCase 先例同款）。
"""

from __future__ import annotations

import logging
from typing import Sequence
from uuid import UUID

from src.application.ports.agent_config_loader import AgentConfigLoader
from src.application.ports.isolation_management import (
    IsolationManagementServicePort,
    IsolationSwitchResult,
)
from src.domain.entities.isolation_state import IsolationState
from src.domain.events.enums import IsolationLevel
from src.domain.events.isolation_events import IsolationLevelSwitched
from src.domain.exceptions import AgentNotFoundError, IsolationStateNotInitializedError
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.isolation_repository import IsolationRepository

logger = logging.getLogger(__name__)


class IsolationManagementService(IsolationManagementServicePort):
    """EIP 隔离管理服务（三方法: initialize/get/switch——同聚合同关注点 DC-4）

    Attributes:
        _isolation_repository: 隔离状态仓储端口（组合根 isolation_repository）
        _agent_repository: Agent 仓储端口（组合根 agent_repository——443 守卫）
        _event_publisher: 事件发布端口（组合根 event_publisher）
        _agent_config_loader: 配置加载端口（组合根 agent_config_loader——TTL 真源）
    """

    def __init__(
        self,
        isolation_repository: IsolationRepository,
        agent_repository: AgentRepository,
        event_publisher: EventPublisher,
        agent_config_loader: AgentConfigLoader,
    ) -> None:
        """初始化服务（R2 组合四依赖——三 domain 端口 + 同层应用端口）

        Args:
            isolation_repository: 隔离状态仓储端口
            agent_repository: Agent 仓储端口（443 存在性守卫）
            event_publisher: 事件发布端口
            agent_config_loader: 配置加载端口（switch 重置 TTL 真源）
        """
        self._isolation_repository = isolation_repository
        self._agent_repository = agent_repository
        self._event_publisher = event_publisher
        self._agent_config_loader = agent_config_loader

    async def initialize_agent_isolation(
        self, agent_id: UUID, default_level: IsolationLevel, ttl_seconds: int
    ) -> IsolationState:
        """初始化隔离状态（upsert——前置条件: agent 已持久化，无 443 前置守卫）

        Raises:
            IsolationLevelNotSupportedError: 非法等级（EXCEPTION_446——实体工厂守卫透传）
            AgentConfigError: TTL 越界（EXCEPTION_440——仓储防御校验透传）
            StorageError: 存储故障（EXCEPTION_103——透传）
        """
        state = IsolationState.initialize(agent_id, default_level)
        await self._isolation_repository.save(state, ttl=ttl_seconds)
        logger.info(
            "隔离状态初始化: agent_id=%s level=%s ttl=%d",
            agent_id,
            default_level.value,
            ttl_seconds,
        )
        return state

    async def get_isolation_state(self, agent_id: UUID) -> IsolationState:
        """查询隔离状态（隔离检查入口——守卫序 443 → 447）

        Raises:
            AgentNotFoundError: Agent 不存在（EXCEPTION_443）
            IsolationStateNotInitializedError: 隔离状态缺失（EXCEPTION_447）
            StorageError: 存储故障（EXCEPTION_103——透传）
        """
        agent = await self._agent_repository.get_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id=str(agent_id))
        state = await self._isolation_repository.get_by_agent_id(agent_id)
        if state is None:
            raise IsolationStateNotInitializedError(agent_id=str(agent_id))
        return state

    async def switch_isolation_level(
        self,
        agent_id: UUID,
        target_level: IsolationLevel,
        trigger_reason: str,
        approval_chain: Sequence[str] = (),
    ) -> IsolationSwitchResult:
        """切换隔离等级（守卫序 443 → 447 → 446 实体内聚 + no-op 零副作用）

        Raises:
            AgentNotFoundError: Agent 不存在（EXCEPTION_443）
            IsolationStateNotInitializedError: 隔离状态缺失（EXCEPTION_447）
            IsolationLevelNotSupportedError: 等级非法（EXCEPTION_446——实体 switch_to）
            EntityValidationError: trigger_reason 空/空白（EXCEPTION_242——实体不变量透传）
            AgentConfigError: 配置加载失败/TTL 越界（EXCEPTION_440）
            StorageError: 存储故障（EXCEPTION_103——透传）
        """
        agent = await self._agent_repository.get_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id=str(agent_id))
        state = await self._isolation_repository.get_by_agent_id(agent_id)
        if state is None:
            raise IsolationStateNotInitializedError(agent_id=str(agent_id))

        previous_level = state.current_level
        switched = state.switch_to(target_level, trigger_reason)
        if not switched:
            # no-op: 零仓储写零事件（幂等——TTL 不刷新，查询型重复调用不得无限续期）
            logger.info("隔离等级同等级 no-op: agent_id=%s level=%s", agent_id, target_level.value)
            return IsolationSwitchResult(switched=False, state=state, event=None)

        # TTL 真源（R1-F01）: 复用 443 守卫已取 agent → config.state_ttl
        # （agent_config_loader 同层应用端口注入——零第二真源零额外 Redis 读）
        config = await self._agent_config_loader.load(agent.role)
        await self._isolation_repository.save(state, ttl=config.state_ttl)

        event = IsolationLevelSwitched(
            agent_id=agent_id,
            previous_level=previous_level,
            target_level=target_level,
            trigger_reason=trigger_reason,
            approval_chain=list(approval_chain),  # kw_only 必填形态（DC-6）+ 显式转发
            switch_timestamp=state.updated_at,  # 单钟纪律: 事件时刻=状态变更时刻（对齐 initialize 单 now 双用叙事）
        )
        try:
            publish_result = await self._event_publisher.publish(event)
        except Exception:
            # 发布失败记日志不回滚（DC-10——状态已切换是事实、事件是通知；
            # exc_info=True 记录完整异常链，无需绑定异常变量）
            logger.warning("隔离切换事件发布失败（状态已切换）: agent_id=%s", agent_id, exc_info=True)
        else:
            if publish_result is not None and not publish_result.is_success:
                # 真实总线失败面（DualChannelEventBus 捕获异常返回失败结果不抛出）
                logger.warning(
                    "隔离切换事件发布失败结果（状态已切换）: agent_id=%s channels=%s",
                    agent_id,
                    publish_result.results,
                )
        logger.info(
            "隔离等级切换: agent_id=%s %s -> %s（原因: %s）",
            agent_id,
            previous_level.value,
            target_level.value,
            trigger_reason,
        )
        return IsolationSwitchResult(switched=True, state=state, event=event)


__all__ = ["IsolationManagementService"]
