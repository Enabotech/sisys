"""应用层单 Agent 六阶段工作流服务（Story 5-3 — 单 Agent 标准工作流）

AgentWorkflowService——六阶段标准工作流（感知→规划→执行→验证→反思→证据
打包）的阶段逻辑服务。实现 AgentWorkflowServicePort（端口定义见
src/application/ports/agent_workflow.py——Task 0 规范唯一真源）；LangGraph
图节点适配器经端口调用本服务（编排与逻辑分离——DC-1）。

设计决策：
- R2 组合端口四依赖：llm_client + tool_execution_service（执行阶段工具调用
  唯一通道——直调 engine/sandbox 会绕过 4-3 校验/4-7 反馈闭环/4-4 沙箱
  安全装饰）+ skill_loader（L2 SOP 按需）+ tool_registry_service（名字→实体
  ——ToolMetadata 无 tool_id 字段，DC-10）
- 温度分档五档（TEMPERATURE_PROFILE：perceive 0.3/plan 0.2/verify 0.1/
  reflect 0.4/package 终局 0.1——规划反思略高发散、验证低温确定；无 execute
  档：工作流服务 execute 阶段无独立 LLM 调用，原子循环的 Think 由 plan
  产物承载——DC-8）
- per-call timeout 显式 ≤8s（全链 10s 预算内单阶段上限；禁依赖 from_env
  默认 600s——辩论 12s 先例的紧缩版）
- LLM 异常包装 444 携带 phase（LLMConfigError/CancelledError 透传——4-5
  辩论纪律先例）；structured_generate 返回 isinstance 守卫（非 Schema 实例
  包 444——red_blue L350-356 先例）
- execute 阶段级聚合 + 历史聚合（读 state 旧 execution 追加合并——防重试轮
  键覆盖丢前轮轨迹，R2-F5）
- package_evidence 终局思维链合成（DC-2：组装覆写 + 终局单次
  structured_generate(ChainOfThoughtSchema)——input_summary←perceive 产物、
  tools_used←真实轨迹覆写禁 LLM 复述、reflection/constraints_check/
  final_answer←终局合成；VO 构造 242 捕获改写 445 携 missing_fields——异常
  契约三层次序②，数据断供自然走该路径）
- ExecutionContext 构造注记：trace_id 默认空串——空串散列进同一版本桶
  （tool_version_service 灰度路由语义），run 级 trace_id 归 5.7 追踪接入，
  MVP 空串可接受
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import uuid
from typing import Any

from src.application.ports.agent_workflow import (
    ExecutionResult,
    PackageOutcome,
    PerceptionResult,
    PlanResult,
    ReflectionResult,
    VerificationResult,
    WorkflowContext,
)
from src.application.services.agent_workflow_context import build_context as _assemble_context
from src.application.services.agent_workflow_prompts import (
    build_final_synthesis_prompt,
    build_perceive_prompt,
    build_plan_prompt,
    build_reflect_prompt,
    build_verify_prompt,
)
from src.application.services.agent_workflow_schemas import (
    ChainOfThoughtSchema,
    PerceptionSchema,
    PlanSchema,
    ReflectionSchema,
    VerificationSchema,
)
from src.domain.exceptions import (
    EntityValidationError,
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
    ServiceUnavailableError,
    TimeoutError,
)
from src.domain.exceptions.agent_exceptions import (
    AgentWorkflowError,
    ChainOfThoughtValidationError,
)
from src.domain.ports.llm_client import LLMClientPort, LLMConfig
from src.domain.value_objects.chain_of_thought import ChainOfThought
from src.domain.value_objects.task_evidence import TaskEvidencePackage
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
)

logger = logging.getLogger(__name__)

# 温度阶梯（五档——DC-8；架构测试绊线断言对齐——禁止调用方覆盖）
TEMPERATURE_PROFILE: dict[str, float] = {
    "perceive": 0.3,
    "plan": 0.2,
    "verify": 0.1,
    "reflect": 0.4,
    "package": 0.1,
}

# 单次 LLM 调用超时上限（秒）——必须显式传递，禁止依赖 LLMConfig.from_env 默认 600s
# （全链 P95<10s 预算内单阶段上限——DC-7/DC-8）
_DEFAULT_PER_CALL_TIMEOUT_SEC = 8.0


class AgentWorkflowService:
    """单 Agent 六阶段工作流服务（AgentWorkflowServicePort 实现）

    六阶段方法由图节点适配器调用（节点返回 dict 部分更新——谓词键由适配器
    写入）；阶段逻辑/prompt 构造/LLM 调用/工具编排全在本服务。
    """

    def __init__(
        self,
        llm_client: LLMClientPort,
        tool_execution_service: Any,
        skill_loader: Any,
        tool_registry_service: Any,
        isolation_guard: Any,
        per_call_timeout_sec: float = _DEFAULT_PER_CALL_TIMEOUT_SEC,
        base_config: LLMConfig | None = None,
    ) -> None:
        """初始化工作流服务（R2 组合端口五依赖——isolation_guard 为 Story 5.5 追加）

        Args:
            llm_client: LLM 客户端端口（六阶段 structured_generate）
            tool_execution_service: 工具执行服务端口（执行阶段唯一调用通道）
            skill_loader: 技能加载端口（L2 SOP 按需加载）
            tool_registry_service: 工具注册服务端口（tool_name→Tool 实体）
            isolation_guard: 三重隔离守卫端口（Story 5.5——execute 工具位白名单
                全量预检；必填无默认：构造缺守卫即 TypeError——守卫可被绕过
                是安全缺口，弃 None 容忍）
            per_call_timeout_sec: 单次 LLM 调用超时上限（默认 8.0s）
            base_config: 每次调用的基底配置（连接字段 endpoint/api_key/model 随基底
                继承——温度分档基于基底派生完整配置，防丢连接字段）
        """
        self._llm_client = llm_client
        self._tool_execution_service = tool_execution_service
        self._skill_loader = skill_loader
        self._tool_registry_service = tool_registry_service
        self._isolation_guard = isolation_guard
        self._per_call_timeout_sec = per_call_timeout_sec
        self._base_config = base_config

    # ------------------------------------------------------------------
    # 装配入口
    # ------------------------------------------------------------------

    def build_context(self, profile_result: Any, task: str) -> WorkflowContext:
        """装配工作流上下文（单向装配——委托 agent_workflow_context.build_context）。

        Args:
            profile_result: 档案加载结果（AgentProfileLoadResult）
            task: 任务描述原文

        Returns:
            WorkflowContext 装配产物（五字段）
        """
        return _assemble_context(profile_result, task)

    # ------------------------------------------------------------------
    # 六阶段
    # ------------------------------------------------------------------

    async def perceive(self, state: dict[str, Any]) -> PerceptionResult:
        """感知阶段（任务上下文摘要）。

        Args:
            state: 工作流状态（含 context）

        Returns:
            感知结果（summary）
        """
        context: WorkflowContext = state["context"]
        prompt = build_perceive_prompt(context.task)
        schema = await self._structured_call(
            "perceive", prompt, PerceptionSchema, context.system_prompt, str(state.get("agent_id", ""))
        )
        return PerceptionResult(summary=schema.summary)

    async def plan(self, state: dict[str, Any]) -> PlanResult:
        """规划阶段（任务分解与工具匹配——重试轮回灌 revised_plan，R2-F4）。

        Args:
            state: 工作流状态（含 context 与可选 reflection 产物）

        Returns:
            规划结果（steps + selected_tools）
        """
        context: WorkflowContext = state["context"]
        reflection: ReflectionResult | None = state.get("reflection")
        prompt = build_plan_prompt(
            context.task,
            revised_plan=reflection.revised_plan if reflection else "",
            error_analysis=reflection.error_analysis if reflection else "",
        )
        schema = await self._structured_call("plan", prompt, PlanSchema, context.system_prompt, str(state.get("agent_id", "")))
        steps = tuple((step.description, step.tool_name, dict(step.arguments)) for step in schema.steps)
        return PlanResult(steps=steps, selected_tools=tuple(schema.selected_tools))

    async def execute(self, state: dict[str, Any]) -> ExecutionResult:
        """执行阶段（阶段级聚合——按 plan 步骤逐步经工具执行服务）。

        每步原子循环映射（DC-8/DC-10）：Think 已由 plan 产物承载；Code/
        Execute 走 tool_execution_service.execute（装饰链承载 4-3 校验与
        4-4 沙箱安全）；Observe 记录 ToolResult（轨迹/快照/引用聚合）；
        Validate 由工具装饰链 OutputValidator 承载。历史聚合：读 state 旧
        execution 追加合并（重试轮不丢前轮轨迹——R2-F5）。

        Args:
            state: 工作流状态（含 plan 产物与旧 execution 轨迹）

        Returns:
            执行结果（跨重试轮聚合的轨迹/快照/摘要/引用）
        """
        context: WorkflowContext = state["context"]
        plan: PlanResult | None = state.get("plan")
        previous: ExecutionResult | None = state.get("execution")

        tool_trace: list[str] = list(previous.tool_trace if previous else ())
        artifacts: list[tuple[str, str]] = list(previous.artifacts_snapshot if previous else ())
        step_summaries: list[str] = list(previous.step_summaries if previous else ())
        citations: list[str] = list(previous.citations if previous else ())

        if plan is None:
            return ExecutionResult(
                tool_trace=tuple(tool_trace),
                artifacts_snapshot=tuple(artifacts),
                step_summaries=tuple(step_summaries),
                citations=tuple(citations),
            )

        # Story 5.5 三重硬隔离: plan 全量工具名预检（all-or-nothing fail-closed——
        # 进执行循环前逐名 ensure_tool_access，任一白名单外工具 449 先于首个工具执行
        # [杜绝「前 N 步已执行、第 N+1 步才拒」的部分执行副作用]；449 先于工具存在性
        # [白名单外名不炸 ToolNotFound 而炸 449——判别锚，guard 不查注册表]；预检经
        # 守卫全链[每名含状态/实体/配置三次 IO]，判定核心纯函数零 IO）。state["agent_id"]
        # 是 str 形态（schemas L67 必填 + 用例恒置键——缺键即 KeyError 诚实契约
        # 信号）——进循环前 UUID 显式转换一次
        agent_uuid = uuid.UUID(state["agent_id"])
        for _, preflight_tool_name, _ in plan.steps:
            if preflight_tool_name:
                await self._isolation_guard.ensure_tool_access(agent_uuid, preflight_tool_name)

        for description, tool_name, arguments in plan.steps:
            if not tool_name:
                step_summaries.append(f"{description}（直接推理，无工具调用）")
                continue
            # 名字→实体（DC-10：ToolMetadata 无 tool_id 字段，经注册端口查询；
            # ToolNotFoundError 原样传播——统一异常体系）
            tool = self._tool_registry_service.get_tool(tool_name=tool_name)
            tool_call = ToolCall(
                tool_id=tool.tool_id,
                arguments=dict(arguments),
                tenant_id=context.tenant_id,
            )
            execution_context = ExecutionContext(
                tenant_id=context.tenant_id,
                trace_id="",  # run 级 trace_id 归 5.7 追踪接入（MVP 空串进同一版本桶）
            )
            result = await self._tool_execution_service.execute(tool.tool_id, tool_call, execution_context)
            tool_trace.append(f"{tool.name}:{tool.version}")
            artifact_name = f"{tool.slug or tool.name}_output"
            artifacts.append((artifact_name, json.dumps(result.output, ensure_ascii=False, default=str)))
            step_summaries.append(f"{description}：{result.status.value}")
            if result.evidence_package is not None:
                citations.extend(result.evidence_package.citations)

        return ExecutionResult(
            tool_trace=tuple(tool_trace),
            artifacts_snapshot=tuple(artifacts),
            step_summaries=tuple(step_summaries),
            citations=tuple(citations),
        )

    async def verify(self, state: dict[str, Any]) -> VerificationResult:
        """验证阶段（结构化检查——执行产物摘要入 prompt）。

        Args:
            state: 工作流状态（含 execution 聚合产物）

        Returns:
            验证结果（passed/confidence/rationale）
        """
        context: WorkflowContext = state["context"]
        execution: ExecutionResult | None = state.get("execution")
        execution_summary = "\n".join(execution.step_summaries) if execution and execution.step_summaries else "（无执行步骤）"
        prompt = build_verify_prompt(context.task, execution_summary)
        schema = await self._structured_call(
            "verify", prompt, VerificationSchema, context.system_prompt, str(state.get("agent_id", ""))
        )
        return VerificationResult(
            passed=schema.passed,
            confidence=schema.confidence,
            rationale=schema.rationale,
        )

    async def reflect(self, state: dict[str, Any]) -> ReflectionResult:
        """反思阶段（验证失败依据入 prompt——错误分析与修正计划）。

        Args:
            state: 工作流状态（含 verification 失败产物）

        Returns:
            反思结果（revised/error_analysis/revised_plan）
        """
        context: WorkflowContext = state["context"]
        verification: VerificationResult | None = state.get("verification")
        rationale = verification.rationale if verification else "（无验证依据）"
        prompt = build_reflect_prompt(context.task, rationale)
        schema = await self._structured_call(
            "reflect", prompt, ReflectionSchema, context.system_prompt, str(state.get("agent_id", ""))
        )
        return ReflectionResult(
            revised=schema.revised,
            error_analysis=schema.error_analysis,
            revised_plan=schema.revised_plan,
        )

    async def package_evidence(self, state: dict[str, Any]) -> PackageOutcome:
        """证据打包阶段（终局思维链合成 + 九字段证据组装——DC-2）。

        终局合成一次 structured_generate(ChainOfThoughtSchema)（prompt 携带
        各阶段产物摘要）；组装覆写：input_summary←perceive 产物、tools_used←
        真实工具轨迹（覆写 LLM 复述值）、reflection/constraints_check/
        final_answer←终局合成。VO 构造 EntityValidationError(242) 捕获改写
        445 携 missing_fields（数据断供自然走该路径——perception 缺失时
        input_summary 为空串被 VO 拦截）。

        Args:
            state: 工作流终态前状态（全阶段产物 + 最终 verification）

        Returns:
            复合产物（evidence + chain）
        """
        context: WorkflowContext = state["context"]
        agent_id = str(state.get("agent_id", ""))
        perception: PerceptionResult | None = state.get("perception")
        plan: PlanResult | None = state.get("plan")
        execution: ExecutionResult | None = state.get("execution")
        verification: VerificationResult | None = state.get("verification")
        reflection: ReflectionResult | None = state.get("reflection")

        # 终局单次合成（prompt 携带各阶段产物摘要——含反思修正素材：
        # 重试路径的 error_analysis/revised_plan 是「总结修正过程」的
        # 事实来源，缺失即逼 LLM 虚构，违反核心约束「不得虚构数据」）
        synthesis_prompt = build_final_synthesis_prompt(
            task=context.task,
            perception_summary=perception.summary if perception else "",
            execution_summary="\n".join(execution.step_summaries) if execution else "",
            verification_rationale=verification.rationale if verification else "",
            reflection_summary=(
                f"错误分析：{reflection.error_analysis}；修正计划：{reflection.revised_plan}" if reflection else ""
            ),
            retry_count=int(state.get("retry_count", 0)),
        )
        chain_schema = await self._structured_call(
            "package", synthesis_prompt, ChainOfThoughtSchema, context.system_prompt, agent_id
        )

        # 组装覆写（DC-2：覆写制——禁 LLM 复述 input_summary/tools_used）
        try:
            chain = ChainOfThought(
                input_summary=perception.summary if perception else "",
                reflection=chain_schema.reflection,
                tools_used=execution.tool_trace if execution else (),
                constraints_check=chain_schema.constraints_check,
                final_answer=chain_schema.final_answer,
            )
        except EntityValidationError as error:
            # 三层次序②：VO 构造守卫 242 → 改写 445 携 missing_fields
            missing = error.context.get("field")
            raise ChainOfThoughtValidationError(
                agent_id=agent_id,
                missing_fields=(missing,) if isinstance(missing, str) else (),
                cause=error,
            ) from error

        # 九字段证据组装（status 依最终 verification_passed——R1-F17 判定规则）
        passed = verification.passed if verification else False
        evidence = TaskEvidencePackage(
            input_hash=hashlib.sha256(context.task.encode()).hexdigest(),
            task_breakdown=tuple(step[0] for step in plan.steps) if plan else (),
            tool_trace=execution.tool_trace if execution else (),
            artifacts_snapshot=execution.artifacts_snapshot if execution else (),
            confidence=verification.confidence if verification else 0.0,
            confidence_rationale=verification.rationale if verification else "",
            citations=execution.citations if execution else (),
            status="completed" if passed else "failed",
            failure_reason="" if passed else (verification.rationale if verification else ""),
        )
        return PackageOutcome(evidence=evidence, chain=chain)

    # ------------------------------------------------------------------
    # 内部：LLM 调用（温度分档 + 异常契约）
    # ------------------------------------------------------------------

    def _build_call_config(self, phase: str) -> LLMConfig:
        """构造单次调用配置（温度分档 + per-call timeout，连接字段随基底继承）。

        Args:
            phase: 阶段名（TEMPERATURE_PROFILE 五档键）

        Returns:
            派生的 LLMConfig（temperature/timeout 覆写，其余字段继承基底）
        """
        base = self._base_config or LLMConfig()
        return dataclasses.replace(
            base,
            temperature=TEMPERATURE_PROFILE[phase],
            timeout=self._per_call_timeout_sec,
        )

    async def _structured_call(
        self,
        phase: str,
        prompt: str,
        schema_cls: type,
        system_prompt: str,
        agent_id: str = "",
    ) -> Any:
        """阶段 LLM 结构化调用（444 包装 + 透传纪律 + isinstance 守卫）。

        Args:
            phase: 阶段名（perceive/plan/execute/verify/reflect/package——444
                context 区分锚点）
            prompt: user prompt
            schema_cls: 结构化 Schema 类（身份分派锚）
            system_prompt: 共用 system prompt（装配产物）
            agent_id: 实体 Agent 标识（444 context 观测锚——异常契约
                {agent_id, phase, reason} 三键完备性）

        Returns:
            Schema 实例（isinstance 守卫后的产物）

        Raises:
            AgentWorkflowError: LLM 族异常包装（444 携 phase）或返回非 Schema
                实例（red_blue L350-356 先例）
            LLMConfigError: 配置错误透传不包装
            asyncio.CancelledError: 协程取消透传（父任务取消语义保护）
        """
        import asyncio

        config = self._build_call_config(phase)
        try:
            result = await self._llm_client.structured_generate(
                prompt=prompt,
                response_schema=schema_cls,
                config=config,
                system_prompt=system_prompt,
            )
        except LLMConfigError:
            # 配置错误透传不包装（4-5 辩论纪律先例）
            raise
        except asyncio.CancelledError:
            # 协程取消透传（父任务取消语义保护）
            raise
        except (LLMAPIError, LLMResponseError, TimeoutError, ServiceUnavailableError) as error:
            raise AgentWorkflowError(
                agent_id=agent_id,
                phase=phase,
                reason=f"{phase} 阶段 LLM 调用失败: {error}",
                cause=error,
            ) from error
        if not isinstance(result, schema_cls):
            raise AgentWorkflowError(
                agent_id=agent_id,
                phase=phase,
                reason=f"LLM 返回结果不是 {schema_cls.__name__} 实例（实际 {type(result).__name__}）",
            )
        return result


__all__ = ["AgentWorkflowService", "TEMPERATURE_PROFILE"]
