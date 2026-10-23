"""三重隔离守卫端口（Story 5.5 — Agent 三重硬隔离保证）

R2 应用层具体应用端口（组合注入下层端口）: 守卫服务（PEP——Policy
Enforcement Point）承载 IO 编排（隔离状态经 isolation_management_service
[443→447 守卫序复用] + 白名单经 agent_config_loader[AgentConfig.allowed_tools
真源] + role 经 agent_repository），判定核心消费 domain 纯函数矩阵
（decide_isolation_access / decide_tool_access——PDP 唯一判定源，本层禁重写
矩阵逻辑），异常翻译单点（决策对象 → 448/449 按 violation 分码）。

返回契约: ensure_agent_executable 返回 IsolationPolicy 供调用方消费三维度；
另两方法为断言型守卫——放行静默返回 None、拒绝即抛异常（DC-3 弃用
check/ensure 双套 API 的既定形态）。

Author:
    agimtech <enabotech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource
from src.domain.value_objects.isolation_policy import IsolationPolicy

__all__ = ["IsolationGuardPort"]


@runtime_checkable
class IsolationGuardPort(Protocol):
    """三重隔离守卫端口（三方法——入口检查/资源访问/工具白名单）。

    守卫透传契约: 全部方法的状态获取经 IsolationManagementServicePort
    （443→447 守卫序全继承——隔离键缺失时任何 ensure_* 均拒）。
    """

    async def ensure_agent_executable(self, agent_id: uuid.UUID) -> IsolationPolicy:
        """工作流执行前置检查（fail-closed）。

        内部: get_isolation_state(agent_id)（443→447 守卫序全继承）→
        get_isolation_policy(state.current_level) 返回策略（调用方可消费
        三维度——prompt/tool/data）。

        Args:
            agent_id: 待执行工作流的 Agent 标识。

        Returns:
            该 Agent 当前等级的隔离策略。

        Raises:
            AgentNotFoundError: 443——Agent 不存在（透传）。
            IsolationStateNotInitializedError: 447——隔离状态缺失（透传；
                隔离态不可证明即拒绝执行——fail-closed）。
        """
        ...

    async def ensure_agent_access(
        self,
        actor_agent_id: uuid.UUID,
        target_agent_id: uuid.UUID,
        resource: IsolationResource,
        operation: AccessOperation,
    ) -> None:
        """跨 Agent 资源访问守卫（Prompt/数据面）。

        内部: actor 状态获取（经 isolation_management_service——443/447 透传）→
        decide_isolation_access(policy, cross_agent=(actor != target), ...) →
        拒绝时按判定 violation 抛 448/449。放行静默返回 None。

        Args:
            actor_agent_id: 发起访问的 Agent 标识。
            target_agent_id: 被访问的 Agent 标识。
            resource: 资源归属分类。
            operation: 访问操作（读/写）。

        Raises:
            AgentNotFoundError: 443——actor 不存在（透传）。
            IsolationStateNotInitializedError: 447——actor 隔离状态缺失（透传）。
            IsolationAccessViolationError: 448——跨 Agent 私有资源访问越权
                （context 五字段含 reason 等级名——并发串扰判别锚）。
            IsolationOperationForbiddenError: 449——共享面写被等级策略禁止
                （READ_ONLY/RESTRICTED_WRITE 等级——reason=data_isolation:{mode}）。
        """
        ...

    async def ensure_tool_access(self, agent_id: uuid.UUID, tool_name: str) -> None:
        """工具白名单守卫（工具面）。

        内部: 状态获取（443/447 透传）→ agent（经 agent_repository.get_by_id
        取 role）→ config = agent_config_loader.load(agent.role) →
        decide_tool_access(policy, tool_name, allowed_tools=config.allowed_tools) →
        拒绝抛 449。tool_isolation=False（L3/L2/L1 共享池）短路放行——
        不取 role 不查白名单。

        Args:
            agent_id: 请求执行工具的 Agent 标识。
            tool_name: 工具名（中文显示名——TOOL_CATALOG 真源形态）。

        Raises:
            AgentNotFoundError: 443——Agent 不存在（透传）。
            IsolationStateNotInitializedError: 447——隔离状态缺失（透传）。
            IsolationOperationForbiddenError: 449——白名单外工具
                （reason=tool_not_in_allowlist:{tool_name}；白名单明细不进
                context，经配置通道可查）。
        """
        ...
