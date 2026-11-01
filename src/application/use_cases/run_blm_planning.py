"""应用层 BLM 规划执行用例（Story 6-1 — RunBlmPlanningUseCase）

七步编排平移 RunAgentWorkflowUseCase 模式（5-3 同构）：
存在守卫 443 → 角色守卫 441 → 隔离 fail-closed 447 → 档案加载 →
build_planning_context → PlanningStarted 发布（三守卫通过后、submit_graph 前
——守卫前发布则失败 run 留孤儿事件）→ submit_graph("SpBlmGraph") →
终态 state 直读组装（全降级 481 抛出点钦定在此）。

图身份：SpBlmGraph（8 节点 7 直连边——OD-4 落位钦定，
Epic 10 Story 10-1 同文件扩展阶段 3-6）。
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from src.application.ports.blm_planning import BlmPlanningResult, BlmPlanningServicePort
from src.application.use_cases.agent_instantiation import SUPPORTED_ROLES
from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
from src.domain.events.planning_events import PlanningStarted
from src.domain.exceptions.agent_exceptions import (
    AgentNotFoundError,
    AgentRoleNotSupportedError,
)
from src.domain.exceptions.planning_exceptions import PlanningExecutionError
from src.domain.ports.agent_engine import AgentEnginePort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.value_objects.blm_phases import BLM_TOTAL_STEPS
from src.domain.value_objects.flow_status import FlowStatus

logger = logging.getLogger(__name__)


class RunBlmPlanningUseCase:
    """BLM 前两阶段规划执行用例（七步编排）。

    依赖注入（六依赖——isolation_guard 必填无默认，缺守卫即 TypeError
    fail-closed，5-3 先例）：
    - agent_repository: Agent 仓储（存在性守卫）
    - agent_profile_use_case: 档案加载用例（5-2 复用）
    - agent_engine: 图执行引擎（submit_graph 通道）
    - blm_planning_service: BLM 阶段服务（build_planning_context + 图节点消费）
    - isolation_guard: 隔离守卫（fail-closed 447）
    - event_publisher: 事件发布器（PlanningStarted）
    """

    def __init__(
        self,
        agent_repository: Any,
        agent_profile_use_case: LoadAgentProfileUseCase,
        agent_engine: AgentEnginePort,
        blm_planning_service: BlmPlanningServicePort,
        isolation_guard: Any,
        event_publisher: EventPublisher,
    ) -> None:
        """构造 BLM 规划执行用例。

        Args:
            agent_repository: Agent 仓储端口。
            agent_profile_use_case: 档案加载用例。
            agent_engine: 图引擎端口。
            blm_planning_service: BLM 阶段服务端口。
            isolation_guard: 隔离守卫端口。
            event_publisher: 事件发布端口。
        """
        self._repository = agent_repository
        self._profile_use_case = agent_profile_use_case
        self._agent_engine = agent_engine
        self._blm_service = blm_planning_service
        self._isolation_guard = isolation_guard
        self._event_publisher = event_publisher

    async def execute(
        self,
        agent_id: uuid.UUID,
        task: str,
        plan_id: str | None = None,
    ) -> BlmPlanningResult:
        """执行 BLM 前两阶段规划（七步编排）。

        Args:
            agent_id: 执行 Agent 标识（CEO 单角色 MVP）。
            task: 规划任务描述。
            plan_id: 规划任务标识（缺省新铸——CLI --plan-id 透传路径）。

        Returns:
            BlmPlanningResult 结果 DTO（阶段 1+2 全部产物）。

        Raises:
            AgentNotFoundError: 443——Agent 不存在。
            AgentRoleNotSupportedError: 441——角色不支持（SUPPORTED_ROLES 限定）。
            IsolationStateNotInitializedError: 447——隔离状态未初始化（fail-closed）。
            PlanningExecutionError: 481——图终态缺失或全部 8 步降级。
        """
        started = time.monotonic()
        # 步 1：存在性守卫（443）
        agent = await self._repository.get_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id=str(agent_id))

        # 步 2：角色守卫（441——SUPPORTED_ROLES 不扩展，AC-2 红线）
        if agent.role not in SUPPORTED_ROLES:
            raise AgentRoleNotSupportedError(
                role=agent.role.value,
                supported_roles=tuple(sorted(supported.value for supported in SUPPORTED_ROLES)),
            )

        # 步 3：隔离 fail-closed（447）
        await self._isolation_guard.ensure_agent_executable(agent_id)

        # 步 4：档案加载（5-2 复用）
        profile_result = await self._profile_use_case.execute(agent_id=agent_id)

        # 步 5：BLM 上下文装配（检索证据在各阶段方法内异步检索——R1-12① 口径）
        resolved_plan_id = plan_id or str(uuid.uuid4())
        context = self._blm_service.build_planning_context(profile_result, task, plan_id=resolved_plan_id)

        # 步 6：PlanningStarted 发布（三守卫通过后、submit_graph 前——Task 0.6② 钦定）
        await self._publish_planning_started(agent_id=agent_id, plan_id=resolved_plan_id, task=task)

        # 步 7：图执行 + 终态组装
        parameters: dict[str, Any] = {
            "agent_id": str(agent_id),  # agent_id 必须 str 序列化（5-3 直承遗产）
            "plan_id": resolved_plan_id,
            "task": task,
            "context": context,
        }
        graph_run_id = await self._agent_engine.submit_graph("SpBlmGraph", parameters)
        status = await self._agent_engine.get_graph_status(graph_run_id)
        if status != FlowStatus.COMPLETED:
            logger.error("BLM 规划图执行未完成 [run_id=%s status=%s]", graph_run_id, status)

        final_state = await self._agent_engine.get_graph_result(graph_run_id)
        if final_state is None:
            raise PlanningExecutionError(
                agent_id=str(agent_id),
                plan_id=resolved_plan_id,
                reason=f"图执行终态 state 缺失 [run_id={graph_run_id}]",
            )

        return self._assemble_result(final_state, agent_id=agent_id, plan_id=resolved_plan_id, started=started)

    async def _publish_planning_started(self, agent_id: uuid.UUID, plan_id: str, task: str) -> None:
        """发布 PlanningStarted 事件（发布失败不阻断流程——记录日志）。"""
        try:
            await self._event_publisher.publish(PlanningStarted(plan_id=plan_id, agent_id=agent_id))
        except Exception:
            logger.exception("PlanningStarted 发布失败 [plan_id=%s]", plan_id)

    def _assemble_result(
        self,
        final_state: dict[str, Any],
        *,
        agent_id: uuid.UUID,
        plan_id: str,
        started: float,
    ) -> BlmPlanningResult:
        """终态 state 直读组装（5-3 同构）+ 全降级 481 抛出点。

        Args:
            final_state: 图终态 state（VO 实例直读——禁 dict→VO 反序列化）。
            agent_id: 执行 Agent 标识。
            plan_id: 规划任务标识。
            started: 执行起始 monotonic 时间戳。

        Returns:
            BlmPlanningResult 结果 DTO。

        Raises:
            PlanningExecutionError: 481——全部 8 步降级（终态组装处钦定抛出点；
                部分降级如 7/8 返回成功 DTO 成文语义）。
        """
        degraded_steps = tuple(final_state.get("degraded_steps", ()))
        if len(degraded_steps) >= BLM_TOTAL_STEPS:
            raise PlanningExecutionError(
                agent_id=str(agent_id),
                plan_id=plan_id,
                reason=f"全部 {BLM_TOTAL_STEPS} 步降级（阶段 1+六子步骤+synthesis）——流程失败终态",
            )

        execution_ms = int((time.monotonic() - started) * 1000)
        return BlmPlanningResult(
            plan_id=plan_id,
            agent_id=agent_id,
            gap_artifacts=final_state["gap_artifacts"],
            insight_steps=tuple(final_state.get("insight_step_results", ())),
            synthesis=final_state["synthesis"],
            degraded_steps=degraded_steps,
            execution_ms=execution_ms,
        )


__all__ = ["RunBlmPlanningUseCase"]
