"""应用层单 Agent 工作流执行用例（Story 5-3 — 单 Agent 标准工作流）

RunAgentWorkflowUseCase——run-task 全链编排：守卫（443/441）→ 档案加载
（5-2 用例复用）→ 上下文装配（单向装配——材料传参）→ SingleAgentWorkflow
图执行（阻塞语义）→ 结果组装（AgentWorkflowResult 五字段）。

编排步骤（5-2 六步形态对齐）：
1. 存在性守卫（443 最先——不存在实体的 role 无从判定）
2. 角色守卫（441——非 CEO 角色的档案目录不存在，先 441 才可达）
3. 档案加载（agent_profile_use_case.execute——AgentProfileLoadResult 六档案
   + tools_l1 + 计量，5-2 交付复用）
4. 上下文装配（agent_workflow_service.build_context(profile_result, task)
   ——单向装配：用例加载档案后传材料，服务不自行调 profile use case）
5. 图执行（submit_graph("SingleAgentWorkflow", parameters)——阻塞语义：
   submit 返回即终态，get_graph_status 单次断言终态；**parameters["agent_id"]
   必须 str(agent_id) 序列化**——引擎收敛位 UUID(str) 构造，UUID 实例直塞
   实测抛 AttributeError）
6. 结果组装（get_graph_result 取终态 state——chain/evidence **直读 state
   中的 VO 实例**（适配器写入的就是 VO、InMemorySaver 无序列化，禁做
   dict→VO 反序列化层）；executed_phases 自终态 state 直读；workflow_status
   同源 evidence.status——FlowStatus 仅系统错误通道不进业务判定）

发布职责（DC-6）：AgentDecided 由引擎承担（用例零 publish——防双发）。

Raises 契约（传播语义）：
- AgentNotFoundError(443): get_by_id 返回 None
- AgentRoleNotSupportedError(441): 非 MVP 开放角色
- AgentWorkflowError(444)/ChainOfThoughtValidationError(445): 引擎 DomainError
  透传（用例零改写）
"""

from __future__ import annotations

import logging
from uuid import UUID

from src.application.ports.agent_workflow import AgentWorkflowResult, AgentWorkflowServicePort
from src.application.use_cases.agent_instantiation import SUPPORTED_ROLES
from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
from src.domain.exceptions import AgentNotFoundError, AgentRoleNotSupportedError
from src.domain.ports.agent_engine import AgentEnginePort
from src.domain.ports.agent_repository import AgentRepository
from src.domain.value_objects.flow_status import FlowStatus

logger = logging.getLogger(__name__)

# MVP 开放角色唯一真源（SUPPORTED_ROLES 复用 5-1/5-2 常量——V1 扩 CFO 只改一处）


class RunAgentWorkflowUseCase:
    """单 Agent 工作流执行用例（run-task 全链编排）

    R2 组合端口四依赖具名：agent_repository（守卫）/ agent_profile_use_case
    （档案加载——5-2 交付复用）/ agent_engine（图执行）/ agent_workflow_service
    （上下文装配——build_context 材料传参）。
    """

    def __init__(
        self,
        agent_repository: AgentRepository,
        agent_profile_use_case: LoadAgentProfileUseCase,
        agent_engine: AgentEnginePort,
        agent_workflow_service: AgentWorkflowServicePort,
    ) -> None:
        """初始化执行用例（四依赖注入——编排模板对齐 5-2 六步形态）

        Args:
            agent_repository: Agent 仓储端口（存在性守卫）
            agent_profile_use_case: 档案加载用例（LoadAgentProfileUseCase）
            agent_engine: Agent 引擎端口（SingleAgentWorkflow 图执行）
            agent_workflow_service: 六阶段工作流服务端口（上下文装配）
        """
        self._repository = agent_repository
        self._profile_use_case = agent_profile_use_case
        self._agent_engine = agent_engine
        self._workflow_service = agent_workflow_service

    async def execute(self, agent_id: UUID, task: str) -> AgentWorkflowResult:
        """执行单 Agent 工作流（守卫 → 装配 → 图执行 → 结果组装）

        Args:
            agent_id: 目标 Agent 实例标识（instantiate 产出的实体 id）
            task: 任务描述原文

        Returns:
            AgentWorkflowResult 五字段（chain/evidence/workflow_status/
            retry_count/executed_phases）

        Raises:
            AgentNotFoundError: EXCEPTION_443（get_by_id 返回 None）
            AgentRoleNotSupportedError: EXCEPTION_441（非 MVP 开放角色）
            AgentWorkflowError: EXCEPTION_444（引擎透传——用例零改写）
            ChainOfThoughtValidationError: EXCEPTION_445（引擎透传）
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

        # 3. 档案加载（5-2 用例复用——六档案 + tools_l1 + 计量）
        profile_result = await self._profile_use_case.execute(agent_id=agent_id)

        # 4. 上下文装配（单向装配——材料传参，服务不自行加载档案）
        workflow_context = self._workflow_service.build_context(profile_result, task)

        # 5. 图执行（阻塞语义——submit 返回即终态；agent_id 必须 str 序列化）
        parameters = {
            "agent_id": str(agent_id),
            "task": task,
            "context": workflow_context,
        }
        graph_run_id = await self._agent_engine.submit_graph("SingleAgentWorkflow", parameters)
        status = await self._agent_engine.get_graph_status(graph_run_id)
        if status != FlowStatus.COMPLETED:
            logger.error("工作流图执行未完成 [run_id=%s status=%s]", graph_run_id, status)

        # 6. 结果组装（get_graph_result 终态 state——VO 实例直读，禁反序列化层）
        final_state = await self._agent_engine.get_graph_result(graph_run_id)
        if final_state is None:
            # 引擎失败路径（DomainError 已透传的上抛场景之外——系统错误兜底）
            from src.domain.exceptions.agent_exceptions import AgentWorkflowError

            raise AgentWorkflowError(
                agent_id=str(agent_id),
                phase="package",
                reason=f"图执行终态 state 缺失 [run_id={graph_run_id} status={status}]",
            )

        evidence = final_state["evidence"]
        chain = final_state["chain"]
        logger.info(
            "单 Agent 工作流执行完成: agent_id=%s status=%s phases=%s",
            agent_id,
            evidence.status,
            final_state.get("executed_phases"),
        )
        return AgentWorkflowResult(
            chain=chain,
            evidence=evidence,
            workflow_status=evidence.status,
            retry_count=final_state.get("retry_count", 0),
            executed_phases=tuple(final_state.get("executed_phases", ())),
        )


__all__ = ["RunAgentWorkflowUseCase"]
