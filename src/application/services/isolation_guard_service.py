"""三重隔离守卫服务（Story 5.5 — Agent 三重硬隔离保证）

PEP（Policy Enforcement Point）实现: IO 编排（隔离状态经
IsolationManagementServicePort[443→447 守卫序复用——禁绕过直查仓储] +
白名单经 AgentConfigLoader[AgentConfig.allowed_tools 真源] + role 经
AgentRepository）+ 判定核心消费（domain 纯函数矩阵——唯一判定源，本层禁重写
矩阵逻辑）+ 异常翻译单点（决策对象 → 448/449 按 violation 分码，reason
对称透传 decision.reason——并发串扰判别锚）。

R2 三依赖组合注入: isolation_management_service（应用端口——状态+守卫序复用）+
agent_repository（domain R1 基础端口——role 取得）+ agent_config_loader
（应用端口——白名单真源）。

Author:
    agimtech <enabotech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

import uuid

from src.application.ports.agent_config_loader import AgentConfigLoader
from src.application.ports.isolation_guard import IsolationGuardPort
from src.application.ports.isolation_management import IsolationManagementServicePort
from src.domain.exceptions import (
    AgentNotFoundError,
    IsolationAccessViolationError,
    IsolationOperationForbiddenError,
)
from src.domain.ports.agent_repository import AgentRepository
from src.domain.value_objects.isolation_access import (
    AccessOperation,
    IsolationResource,
    IsolationViolationKind,
    decide_isolation_access,
    decide_tool_access,
)
from src.domain.value_objects.isolation_policy import IsolationPolicy, get_isolation_policy

__all__ = ["IsolationGuardService"]


class IsolationGuardService(IsolationGuardPort):
    """三重隔离守卫服务（三方法——入口检查/资源访问/工具白名单）。"""

    def __init__(
        self,
        isolation_management_service: IsolationManagementServicePort,
        agent_repository: AgentRepository,
        agent_config_loader: AgentConfigLoader,
    ) -> None:
        """初始化守卫服务（R2 三依赖组合注入）。

        Args:
            isolation_management_service: 隔离管理服务端口（状态获取 + 443→447
                守卫序复用——禁绕过直查隔离仓储）。
            agent_repository: Agent 仓储端口（ensure_tool_access 经 get_by_id
                取 role——白名单配置寻址键）。
            agent_config_loader: Agent 配置加载端口（白名单真源——
                AgentConfig.allowed_tools 经角色配置加载）。
        """
        self._isolation_management = isolation_management_service
        self._agent_repository = agent_repository
        self._agent_config_loader = agent_config_loader

    async def ensure_agent_executable(self, agent_id: uuid.UUID) -> IsolationPolicy:
        """工作流执行前置检查（fail-closed）。

        Args:
            agent_id: 待执行工作流的 Agent 标识。

        Returns:
            该 Agent 当前等级的隔离策略（调用方可消费三维度）。

        Raises:
            AgentNotFoundError: 443——Agent 不存在（透传）。
            IsolationStateNotInitializedError: 447——隔离状态缺失（透传）。
        """
        state = await self._isolation_management.get_isolation_state(agent_id)
        return get_isolation_policy(state.current_level)

    async def ensure_agent_access(
        self,
        actor_agent_id: uuid.UUID,
        target_agent_id: uuid.UUID,
        resource: IsolationResource,
        operation: AccessOperation,
    ) -> None:
        """跨 Agent 资源访问守卫（Prompt/数据面——矩阵消费 + 异常翻译单点）。

        Args:
            actor_agent_id: 发起访问的 Agent 标识（判定取 actor 侧策略——单边语义）。
            target_agent_id: 被访问的 Agent 标识。
            resource: 资源归属分类。
            operation: 访问操作（读/写）。

        Raises:
            AgentNotFoundError: 443——actor 不存在（透传）。
            IsolationStateNotInitializedError: 447——actor 隔离状态缺失（透传）。
            IsolationAccessViolationError: 448——跨 Agent 私有资源访问越权。
            IsolationOperationForbiddenError: 449——共享面写被等级策略禁止。
        """
        # actor 状态获取经隔离管理端口（443→447 守卫序复用——禁直查隔离仓储）
        state = await self._isolation_management.get_isolation_state(actor_agent_id)
        policy = get_isolation_policy(state.current_level)
        decision = decide_isolation_access(
            policy,
            cross_agent=(actor_agent_id != target_agent_id),
            resource=resource,
            operation=operation,
        )
        if decision.allowed:
            return
        if decision.violation is IsolationViolationKind.ACCESS_VIOLATION:
            raise IsolationAccessViolationError(  # 448（跨主体越权——context 五字段）
                actor_agent_id=str(actor_agent_id),
                target_agent_id=str(target_agent_id),
                resource=resource.value,
                operation=operation.value,
                reason=decision.reason,  # 判定依据含等级名——并发串扰判别锚
            )
        raise IsolationOperationForbiddenError(  # 449（单主体等级策略禁止——共享面写）
            agent_id=str(actor_agent_id),
            operation=operation.value,
            reason=decision.reason,  # data_isolation:{mode} 形态
        )

    async def ensure_tool_access(self, agent_id: uuid.UUID, tool_name: str) -> None:
        """工具白名单守卫（工具面——白名单真源经配置通道）。

        Args:
            agent_id: 请求执行工具的 Agent 标识。
            tool_name: 工具名（中文显示名——TOOL_CATALOG 真源形态）。

        Raises:
            AgentNotFoundError: 443——Agent 不存在（透传）。
            IsolationStateNotInitializedError: 447——隔离状态缺失（透传）。
            IsolationOperationForbiddenError: 449——白名单外工具
                （reason=tool_not_in_allowlist:{tool_name}）。
        """
        # 状态入口先于 role 取得（443 由隔离管理守卫序先拦——顺序契约）
        state = await self._isolation_management.get_isolation_state(agent_id)
        policy = get_isolation_policy(state.current_level)
        if not policy.tool_isolation:
            return  # 共享池短路（L3/L2/L1）——不取 role 不查白名单
        agent = await self._agent_repository.get_by_id(agent_id)
        if agent is None:  # 类型契约显式收窄（状态入口 443 先拦是常态序——双仓储实例下防御一致）
            raise AgentNotFoundError(agent_id=str(agent_id))
        config = await self._agent_config_loader.load(agent.role)
        decision = decide_tool_access(policy, tool_name=tool_name, allowed_tools=config.allowed_tools)
        if decision.allowed:
            return
        raise IsolationOperationForbiddenError(
            agent_id=str(agent_id),
            operation="execute",
            reason=decision.reason,  # tool_not_in_allowlist:{tool_name} 形态
        )
