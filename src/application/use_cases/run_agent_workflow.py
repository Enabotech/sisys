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
- IsolationStateNotInitializedError(447): 入口隔离检查（Story 5.5——隔离态
  不可证明即拒绝执行，fail-closed 先于档案加载）
- AgentWorkflowError(444)/ChainOfThoughtValidationError(445): 引擎 DomainError
  透传（用例零改写）
"""

from __future__ import annotations

import logging
from uuid import UUID

from opentelemetry.trace import get_current_span

from src.application.ports.agent_evaluation import AgentEvaluationPort
from src.application.ports.agent_tracing import SpanAttributeKeys, SpanNames
from src.application.ports.agent_workflow import AgentWorkflowResult, AgentWorkflowServicePort
from src.application.ports.isolation_guard import IsolationGuardPort
from src.application.tracing import trace
from src.application.use_cases.agent_instantiation import SUPPORTED_ROLES
from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
from src.domain.exceptions import AgentEvaluationError, AgentNotFoundError, AgentRoleNotSupportedError, LLMConfigError
from src.domain.ports.agent_engine import AgentEnginePort
from src.domain.ports.agent_repository import AgentRepository
from src.domain.value_objects.flow_status import FlowStatus

logger = logging.getLogger(__name__)

# MVP 开放角色唯一真源（SUPPORTED_ROLES 复用 5-1/5-2 常量——V1 扩 CFO 只改一处）


class RunAgentWorkflowUseCase:
    """单 Agent 工作流执行用例（run-task 全链编排）

    R2 组合端口五依赖具名：agent_repository（守卫）/ agent_profile_use_case
    （档案加载——5-2 交付复用）/ agent_engine（图执行）/ agent_workflow_service
    （上下文装配——build_context 材料传参）/ isolation_guard（入口隔离检查——
    Story 5.5 三重硬隔离，fail-closed 必填弃 None 容忍：守卫可被绕过是安全缺口）。
    """

    def __init__(
        self,
        agent_repository: AgentRepository,
        agent_profile_use_case: LoadAgentProfileUseCase,
        agent_engine: AgentEnginePort,
        agent_workflow_service: AgentWorkflowServicePort,
        isolation_guard: IsolationGuardPort,
        evaluation_harness: AgentEvaluationPort | None = None,
    ) -> None:
        """初始化执行用例（六依赖注入——编排模板对齐 5-2 六步形态）

        Args:
            agent_repository: Agent 仓储端口（存在性守卫）
            agent_profile_use_case: 档案加载用例（LoadAgentProfileUseCase）
            agent_engine: Agent 引擎端口（SingleAgentWorkflow 图执行）
            agent_workflow_service: 六阶段工作流服务端口（上下文装配）
            isolation_guard: 三重隔离守卫端口（Story 5.5——入口 fail-closed 检查，
                必填无默认：RunAgentWorkflowUseCase 构造缺守卫即 TypeError）
            evaluation_harness: 评估端口（Story 5.8——可选依赖 None 默认：评估是
                可观测附加面，未注入时评估块整体跳过，存量五参构造零破坏——
                DC-5 六依赖向后兼容形态）
        """
        self._repository = agent_repository
        self._profile_use_case = agent_profile_use_case
        self._agent_engine = agent_engine
        self._workflow_service = agent_workflow_service
        self._isolation_guard = isolation_guard
        self._evaluation_harness = evaluation_harness

    @trace(SpanNames.AGENT_EXECUTION)
    async def execute(self, agent_id: UUID, task: str) -> AgentWorkflowResult:
        """执行单 Agent 工作流（守卫 → 装配 → 图执行 → 结果组装）——agent_execution 根 span（Story 5.7）

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

        # 3. 入口隔离检查（Story 5.5 三重硬隔离——fail-closed：隔离态不可证明即拒绝执行；
        #    441 后档案加载前（DC-6）——447 时零档案读取零图执行零事件；返回策略
        #    MVP 暂不消费，前置 fail-closed 是目的）
        await self._isolation_guard.ensure_agent_executable(agent_id)

        # 4. 档案加载（5-2 用例复用——六档案 + tools_l1 + 计量）
        profile_result = await self._profile_use_case.execute(agent_id=agent_id)

        # 5. 上下文装配（单向装配——材料传参，服务不自行加载档案）
        workflow_context = self._workflow_service.build_context(profile_result, task)

        # 6. 图执行（阻塞语义——submit 返回即终态；agent_id 必须 str 序列化）
        parameters = {
            "agent_id": str(agent_id),
            "task": task,
            "context": workflow_context,
        }
        graph_run_id = await self._agent_engine.submit_graph("SingleAgentWorkflow", parameters)
        status = await self._agent_engine.get_graph_status(graph_run_id)
        if status != FlowStatus.COMPLETED:
            logger.error("工作流图执行未完成 [run_id=%s status=%s]", graph_run_id, status)

        # 7. 结果组装（get_graph_result 终态 state——VO 实例直读，禁反序列化层）
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
        result = AgentWorkflowResult(
            chain=chain,
            evidence=evidence,
            workflow_status=evidence.status,
            retry_count=final_state.get("retry_count", 0),
            executed_phases=tuple(final_state.get("executed_phases", ())),
        )
        # Story 5.7 — 根 span MVP 十项业务属性写入（get_current_span 面；is_recording
        # 守卫——NoOp/未启用时 span 空转零开销；数据源：agent 实体[role/name] +
        # profile_result[startup_context_tokens + len(tools_l1) 派生 active_skill_count
        # ——agent_events.py L83 同源口径] + result[status/retry_count/executed_phases]
        # + result.evidence[confidence/input_hash]）
        span = get_current_span()
        if span.is_recording():
            span.set_attribute(SpanAttributeKeys.AGENT_ID, str(agent_id))
            span.set_attribute(SpanAttributeKeys.AGENT_ROLE, agent.role.value)
            span.set_attribute(SpanAttributeKeys.AGENT_NAME, agent.name)
            span.set_attribute(SpanAttributeKeys.AGENT_STARTUP_CONTEXT_TOKENS, profile_result.startup_context_tokens)
            span.set_attribute(SpanAttributeKeys.AGENT_ACTIVE_SKILL_COUNT, len(profile_result.tools_l1))
            span.set_attribute(SpanAttributeKeys.WORKFLOW_STATUS, result.workflow_status)
            span.set_attribute(SpanAttributeKeys.WORKFLOW_RETRY_COUNT, result.retry_count)
            span.set_attribute(SpanAttributeKeys.WORKFLOW_EXECUTED_PHASES, result.executed_phases)
            span.set_attribute(SpanAttributeKeys.EVAL_CONFIDENCE, result.evidence.confidence)
            span.set_attribute(SpanAttributeKeys.EVIDENCE_INPUT_HASH, result.evidence.input_hash)
        # Story 5.8 评估块（OD-2[5.7] 兑现——eval.* 三键生产填值；可观测附加面哲学：
        # 评估失败降级 warning 跳过不阻断主链，三键缺席不写哨兵值——0.0 可能是
        # 合法幻觉分；overall 不写 span——三键经权重常量可派生，5.7 键表零改动。
        # 降级 catch 面含 LLMConfigError（CR1-F1）：332 的现实可达源是运行期
        # UDMR/LLM env 半配置态经 local 分支（健康回退或 local_first/合规强制
        # 本地——主链 build_default 忽略 local_first 照常走 cloud，评估 local
        # 分支 from_env 缺 endpoint/key 即 332）非开发期代码错误——评估管线内
        # 一切失败不阻断主链（附加面边界=catch 边界）；主链六阶段的 332 显性
        # 失败语义不变）
        if self._evaluation_harness is not None:
            try:
                evaluation_result = await self._evaluation_harness.evaluate(result)
                if span.is_recording():
                    span.set_attribute(SpanAttributeKeys.EVAL_HALLUCINATION_SCORE, evaluation_result.hallucination_score)
                    span.set_attribute(SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE, evaluation_result.context_relevance)
                    span.set_attribute(SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY, evaluation_result.confidence_accuracy)
            except (AgentEvaluationError, LLMConfigError) as error:
                logger.warning("评估降级跳过（可观测附加面——评估失败不阻断工作流）: %s", error)
        return result


__all__ = ["RunAgentWorkflowUseCase"]
