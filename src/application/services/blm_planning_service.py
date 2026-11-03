"""应用层 BLM 规划服务（Story 6-1 — BlmPlanningService）

BlmPlanningServicePort 实现——BLM 前两阶段（业绩差距分析 + 市场洞察六
子步骤 + 综合）的阶段/子步骤执行。R2 规则：组合注入既有基础端口
（LLMClientPort/ToolExecutionService/工具注册/IsolationGuardPort/
HybridSearchPort/EventPublisher/SnapshotRepositoryProtocol）。

每步时序钦定（DC-3）：确定性工具候选（语义配置表白名单）→ 工具先行执行
（失败/未选 → 直接推理）→ 检索证据 + 工具输出注入 → 单次结构化 LLM 调用。

瞬时故障两级设计（R3-2 钦定——服务内重试，非 per-node RetryPolicy）：
每步 asyncio 单次重试循环（瞬时 LLM 失败）→ 仍败则步级降级。

步级降级（AC-6①⑤）：
- 449（IsolationOperationForbiddenError）/380（ToolNotFoundError）/工具执行
  失败 → 降工具、直接推理续行（LLM 仍执行——产物非空，degraded=True 记
  工具面降级原因）
- LLM 调用失败（重试后仍败）→ degraded=True + 空 summary/findings（完整信封）
- 检索连接失败 → degraded=True + 原因记检索失败（空结果=正常空证据不降级
  ——R3-6 判别语义）

降级下游三规则（AC-6⑥）：降级产物以「[降级]+原因」注入下游 prompt；
synthesize_insights 结论必须列举 degraded 输入；阶段 1 全降级阶段 2 照常。

步骤边界快照（DC-6）：各方法末尾写快照（session_id=BLM_PLANNING_SESSION_
PREFIX+plan_id，经 SnapshotRepositoryProtocol——pipeline hset latest+TTL
在存储实现内部）+ 发布 BlmStageCompleted（reliable——DC-8）。
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Mapping

from src.application.ports.blm_planning import (
    BLM_PLANNING_SESSION_PREFIX,
    BLM_PLANNING_SNAPSHOT_STAGE,
    BlmPlanningContext,
    BlmPlanningServicePort,
)
from src.application.ports.chain_of_thought_archive import (
    SYNTHESIS_DISPLAY_NAME,
    SYNTHESIS_ROLE_PREFIX,
    ChainOfThoughtArchiveServicePort,
    ChainRecord,
    StepChainMaterial,
)
from src.application.services.agent_workflow_context import MVP_TENANT_ID
from src.application.services.blm_planning_prompts import (
    BLM_PER_CALL_TIMEOUT_SEC,
    BLM_TEMPERATURE_PROFILE,
    MARKET_INSIGHT_STEP_CONFIG,
    MARKET_INSIGHT_STEP_SCHEMA,
    PERFORMANCE_GAP_CONFIG,
    GapAnalysisSchema,
    InsightSynthesisSchema,
    MarketInsightSchemaBase,
    build_insight_step_prompt,
    build_performance_gap_prompt,
    build_synthesis_prompt,
    summarize_gap_for_downstream,
    summarize_step_for_downstream,
)
from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.events.planning_events import BlmStageCompleted
from src.domain.exceptions import LLMConfigError
from src.domain.exceptions.agent_exceptions import (
    AgentWorkflowError,
    IsolationOperationForbiddenError,
)
from src.domain.exceptions.planning_exceptions import PlanningStateError
from src.domain.exceptions.tool_exceptions import ToolNotFoundError
from src.domain.ports.llm_client import LLMClientPort, LLMConfig
from src.domain.value_objects.blm_phases import (
    BLM_TOTAL_STEPS,
    BlmPhase,
    BlmTimelineEntry,
    InsightStepResult,
    InsightSynthesis,
    MarketInsightStep,
    PerformanceGapArtifacts,
    make_timeline_entry,
)

logger = logging.getLogger(__name__)

#: 服务内瞬时故障重试次数（两级设计第一级——R3-2 钦定：每步单次重试）
_TRANSIENT_RETRY_ATTEMPTS: int = 1

#: 检索证据注入上限（上下文膨胀防线——R6 风险缓解）
_MAX_EVIDENCE_TEXTS: int = 5

#: 证据/工具输出文本截断长度（字符）
_EVIDENCE_TEXT_MAX_CHARS: int = 300


class _PlanRunState:
    """单规划任务的内存累积器（timeline/degraded/步骤计数——快照投影源）。

    快照存储是持久真源（latest），本累积器仅承载单 run 内的状态组装；
    服务实例跨 run 复用时按 plan_id 键控隔离。
    """

    def __init__(self, plan_id: str) -> None:
        self.plan_id = plan_id
        self.phase: BlmPhase = BlmPhase.PERFORMANCE_GAP
        self.current_step: str = "performance_gap"
        self.completed_steps: int = 0
        self.degraded_steps: list[str] = []
        self.timeline: list[BlmTimelineEntry] = []
        self.chain_records: list[ChainRecord] = []  # 6-4 思维链累积位（不进快照——OD-8）

    def record_step(self, step: str, started_at: datetime, summary: str, *, degraded: bool) -> None:
        """记录步骤完成（timeline 追加 + 计数推进 + current_step/phase 更新）。"""
        self.timeline.append(make_timeline_entry(step, started_at, summary, degraded=degraded))
        self.completed_steps = min(self.completed_steps + 1, BLM_TOTAL_STEPS)
        self.current_step = step
        if step == "performance_gap":
            self.phase = BlmPhase.MARKET_INSIGHT
        if degraded:
            self.degraded_steps.append(step)

    def to_state_data(self) -> dict[str, Any]:
        """投影快照 state_data（序列化契约 SSOT——端口文件钦定）。"""
        return {
            "plan_id": self.plan_id,
            "phase": self.phase.value,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "total_steps": BLM_TOTAL_STEPS,
            "degraded_steps": list(self.degraded_steps),
            "timeline": [entry.to_dict() for entry in self.timeline],
        }


class BlmPlanningService(BlmPlanningServicePort):
    """BLM 规划服务（阶段/子步骤执行 + 步骤边界快照 + 事件发布）。"""

    def __init__(
        self,
        llm_client: LLMClientPort,
        tool_execution_service: Any,
        tool_registry_service: Any,
        isolation_guard: Any,
        hybrid_search: Any,
        search_collection: str,
        event_publisher: Any,
        snapshot_repository: Any,
        base_config: LLMConfig | None = None,
        chain_archive_service: ChainOfThoughtArchiveServicePort | None = None,
    ) -> None:
        """构造 BLM 规划服务。

        Args:
            llm_client: LLM 客户端端口（结构化调用）。
            tool_execution_service: 工具执行服务（5-3 链复用）。
            tool_registry_service: 工具注册服务（get_tool）。
            isolation_guard: 隔离守卫（ensure_tool_access——449 预检）。
            hybrid_search: 混合检索端口（search——市场洞察取数）。
            search_collection: 检索 collection 名（租户隔离装配）。
            event_publisher: 事件发布器（BlmStageCompleted）。
            snapshot_repository: 快照存储端口（步骤边界 latest 写入）。
            base_config: LLM 基底配置（温度/超时覆写基底——缺省 LLMConfig()）。
            chain_archive_service: 思维链归档服务（6-4 挂接——可选尾参，
                None 时零挂接与现状逐字节等价；本类 base_config+LangGraphEngine
                双尾参先例同形态）。
        """
        self._llm = llm_client
        self._tool_execution_service = tool_execution_service
        self._tool_registry_service = tool_registry_service
        self._isolation_guard = isolation_guard
        self._hybrid_search = hybrid_search
        self._search_collection = search_collection
        self._event_publisher = event_publisher
        self._snapshot_repository = snapshot_repository
        self._base_config = base_config or LLMConfig()
        self._chain_archive_service = chain_archive_service
        self._runs: dict[str, _PlanRunState] = {}
        self._last_context_cache: BlmPlanningContext | None = None

    # ------------------------------------------------------------------
    # 公开只读探针（装配链复用面——验收/集成场景真实发布链路重构造注入）
    # ------------------------------------------------------------------

    @property
    def tool_execution_service(self) -> Any:
        """工具执行服务探针。"""
        return self._tool_execution_service

    @property
    def tool_registry_service(self) -> Any:
        """工具注册服务探针。"""
        return self._tool_registry_service

    @property
    def isolation_guard(self) -> Any:
        """隔离守卫探针。"""
        return self._isolation_guard

    @property
    def hybrid_search(self) -> Any:
        """混合检索探针。"""
        return self._hybrid_search

    @property
    def snapshot_repository(self) -> Any:
        """快照存储探针。"""
        return self._snapshot_repository

    @property
    def active_plan_ids(self) -> tuple[str, ...]:
        """活跃规划任务标识（执行中轮询探测面——测试消费）。"""
        return tuple(self._runs)

    # ------------------------------------------------------------------
    # 上下文装配
    # ------------------------------------------------------------------

    def build_planning_context(
        self,
        profile_result: Any,
        task: str,
        plan_id: str,
        tenant_id: str = "",
    ) -> BlmPlanningContext:
        """装配 BLM 规划上下文（同步——检索证据在各阶段方法内异步检索）。"""
        return BlmPlanningContext(
            plan_id=plan_id,
            agent_id=getattr(profile_result, "agent_id", ""),
            profile_result=profile_result,
            task=task,
            tenant_id=tenant_id,
            retrieved_evidence=(),
        )

    # ------------------------------------------------------------------
    # 阶段 1：业绩差距分析
    # ------------------------------------------------------------------

    async def run_performance_gap_analysis(self, context: BlmPlanningContext) -> PerformanceGapArtifacts:
        """执行阶段 1 业绩差距分析（每步时序 DC-3 + 两级重试 + 步级降级）。

        Raises:
            PlanningStateError: 482——同 plan_id 重跑（run 钦定唯一入口守卫——
                首次 run 事件已发布/快照已写，重跑将污染 timeline 与降级计数；
                重试语义=新 plan_id）。
        """
        started_at = datetime.now(UTC)
        existing_state = self._runs.get(context.plan_id)
        if existing_state is not None and existing_state.completed_steps > 0:
            raise PlanningStateError(
                plan_id=context.plan_id,
                transition="rerun_performance_gap",
                message=(f"同 plan_id 重跑被拒绝（首次 run 已推进 {existing_state.completed_steps} 步——重试请用新 plan_id）"),
            )
        run_state = self._ensure_run_state(context.plan_id)

        tool_output, tool_degrade_reason, _tool_slug = await self._execute_candidate_tools(
            PERFORMANCE_GAP_CONFIG.tool_candidates, context
        )
        evidence_texts, retrieval_degrade_reason, _evidence_refs = await self._retrieve_evidence(
            PERFORMANCE_GAP_CONFIG.retrieval_query_template.format(task=context.task)
        )
        prompt = build_performance_gap_prompt(
            task=context.task,
            evidence_texts=evidence_texts,
            tool_output_summary=tool_output,
        )

        degraded = False
        degrade_reason = ""
        schema_result: GapAnalysisSchema | None = None
        try:
            schema_result = await self._structured_call_with_retry("performance_gap", prompt, GapAnalysisSchema, context)
        except AgentWorkflowError as error:
            degraded = True
            degrade_reason = f"LLM 调用失败：{error.context.get('reason', error)}"
            logger.warning("阶段 1 LLM 降级 [plan_id=%s]: %s", context.plan_id, error)
        for reason in (retrieval_degrade_reason, tool_degrade_reason):
            if reason:
                degraded = True
                degrade_reason = degrade_reason or reason

        if schema_result is not None:
            artifacts = PerformanceGapArtifacts(
                financial_gap=schema_result.financial_gap,
                operational_gap=schema_result.operational_gap,
                root_causes=tuple(schema_result.root_causes),
                portfolio_health=schema_result.portfolio_health,
                degraded=degraded,
                degrade_reason=degrade_reason,
            )
            summary = artifacts.financial_gap
        else:
            artifacts = PerformanceGapArtifacts(
                financial_gap="",
                operational_gap="",
                root_causes=(),
                portfolio_health="",
                degraded=True,
                degrade_reason=degrade_reason,
            )
            summary = ""

        run_state.record_step("performance_gap", started_at, summary, degraded=degraded)
        await self._write_snapshot_and_publish(context, stage="performance_gap", summary_excerpt=summary)
        # 6-4 挂接段：步骤产物就绪 → 组装素材（gap 型——artifacts 六属性+轨迹素材）→ 归档
        await self._compose_and_archive_chain(
            context,
            "performance_gap",
            StepChainMaterial(
                stage="performance_gap",
                display_name=PERFORMANCE_GAP_CONFIG.display_name,
                role_prefix=PERFORMANCE_GAP_CONFIG.role_prefix,
                task=context.task,
                evidence_count=len(evidence_texts),
                tool_slug=_tool_slug,
                evidence_refs=_evidence_refs,
                summary=summary,
                findings_count=len(artifacts.root_causes),
                degraded=degraded,
                degrade_reason=degrade_reason,
                payload=dataclasses.asdict(artifacts),
                structured_ok=bool(artifacts.financial_gap),
            ),
        )
        return artifacts

    # ------------------------------------------------------------------
    # 阶段 2：市场洞察六子步骤
    # ------------------------------------------------------------------

    async def run_insight_step(
        self,
        step: MarketInsightStep,
        context: BlmPlanningContext,
        prior_outputs: Mapping[str, Any],
    ) -> InsightStepResult:
        """执行市场洞察单子步骤（每步时序 DC-3）。"""
        started_at = datetime.now(UTC)
        run_state = self._ensure_run_state(context.plan_id)
        config = MARKET_INSIGHT_STEP_CONFIG[step]

        prior_steps = tuple(prior_outputs.get("insight_steps", ()))
        prior_summaries = "\n".join(summarize_step_for_downstream(r) for r in prior_steps)
        degradation_notes = tuple(f"{r.step}（{r.degrade_reason}）" for r in prior_steps if r.degraded)
        # 阶段 1 产物跨阶段传导（AC-6⑥ 规则 1——gap 降级态以「[降级]+原因」标注注入）
        gap_artifacts = prior_outputs.get("performance_gap")
        gap_summary = summarize_gap_for_downstream(gap_artifacts) if gap_artifacts is not None else ""

        tool_output, tool_degrade_reason, tool_slug = await self._execute_candidate_tools(config.tool_candidates, context)
        evidence_texts, retrieval_degrade_reason, evidence_refs = await self._retrieve_evidence(
            config.retrieval_query_template.format(task=context.task)
        )
        prompt = build_insight_step_prompt(
            step=step,
            task=context.task,
            evidence_texts=evidence_texts,
            tool_output_summary=tool_output,
            prior_outputs_summary=prior_summaries,
            degradation_notes=degradation_notes,
            gap_summary=gap_summary,
        )

        degraded = False
        degrade_reason = ""
        schema_result: MarketInsightSchemaBase | None = None
        # 六步类型化分派（SSOT 映射查表——零 if-else 硬编码；每步专属 Schema，
        # 校验失败/超时/异常统一走步级降级——AC-4）
        schema_cls = MARKET_INSIGHT_STEP_SCHEMA[step]
        try:
            schema_result = await self._structured_call_with_retry(step.value, prompt, schema_cls, context)
        except AgentWorkflowError as error:
            degraded = True
            degrade_reason = f"LLM 调用失败：{error.context.get('reason', error)}"
            logger.warning("子步骤 %s LLM 降级 [plan_id=%s]: %s", step.value, context.plan_id, error)
        for reason in (retrieval_degrade_reason, tool_degrade_reason):
            if reason:
                degraded = True
                degrade_reason = degrade_reason or reason

        if schema_result is not None:
            result = InsightStepResult(
                step=step.value,
                summary=schema_result.summary,
                findings=tuple(schema_result.findings),
                tool_used=tool_slug,
                evidence_refs=evidence_refs,
                degraded=degraded,
                degrade_reason=degrade_reason,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                structured_output=schema_result.model_dump(),
            )
            summary_excerpt = schema_result.summary
        else:
            result = InsightStepResult(
                step=step.value,
                summary="",
                findings=(),
                tool_used=tool_slug,
                evidence_refs=evidence_refs,
                degraded=True,
                degrade_reason=degrade_reason,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            summary_excerpt = ""

        run_state.record_step(step.value, started_at, summary_excerpt, degraded=result.degraded)
        # per-step Checkpoint 快照骨架（AC-2——先于 latest 写入；失败容错不阻断）
        await self._write_step_checkpoint(context, step, result)
        await self._write_snapshot_and_publish(context, stage=f"market_insight_{step.value}", summary_excerpt=summary_excerpt)
        # 6-4 挂接段：两快照之后、return 之前（六子型素材——信封+轨迹双源采集）。
        # R2-F2：payload=structured_output 产物原样（部分降级不丢弃真实产物）；
        # 仅产物缺席（LLM 失败支 structured_output None）用降级信封。
        await self._compose_and_archive_chain(
            context,
            f"market_insight_{step.value}",
            StepChainMaterial(
                stage=f"market_insight_{step.value}",
                display_name=config.display_name,
                role_prefix=config.role_prefix,
                task=context.task,
                evidence_count=len(evidence_texts),
                tool_slug=tool_slug,
                evidence_refs=evidence_refs,
                summary=result.summary,
                findings_count=len(result.findings),
                degraded=result.degraded,
                degrade_reason=result.degrade_reason,
                payload=(
                    result.structured_output
                    if result.structured_output is not None
                    else {"degraded": True, "degrade_reason": result.degrade_reason}
                ),
                structured_ok=result.structured_output is not None,
            ),
        )
        return result

    # ------------------------------------------------------------------
    # 综合
    # ------------------------------------------------------------------

    async def synthesize_insights(
        self, step_outputs: Mapping[str, Any], context: BlmPlanningContext | None = None
    ) -> InsightSynthesis:
        """综合六子步骤产物（单次聚合调用——degraded_inputs 必须列举）。

        阶段 1 降级源纳入 degraded_inputs（AC-6⑥ 规则 3——综合报告携带标记）；
        synthesis 自身空结论/降级时 degraded_inputs 自含 "market_insight_synthesis"
        （R3-4 钦定——两分支对称）。
        """
        started_at = datetime.now(UTC)
        steps = tuple(step_outputs.get("insight_steps", ()))
        summaries = tuple(r.summary if not r.degraded else f"[降级]（{r.degrade_reason}）" for r in steps)
        degraded_inputs = tuple(r.step for r in steps if r.degraded)
        # 阶段 1 降级源前置列举（AC-6⑥ 规则 3——None/缺键安全，服务直调形态容错）
        gap_artifacts = step_outputs.get("performance_gap")
        if gap_artifacts is not None and getattr(gap_artifacts, "degraded", False):
            degraded_inputs = ("performance_gap", *degraded_inputs)

        effective_context = context or self._last_context_cache
        if effective_context is None:
            logger.warning("synthesize_insights 缺少上下文锚（无步骤先行调用）")
            return InsightSynthesis(conclusions=(), degraded_inputs=(*degraded_inputs, "market_insight_synthesis"))
        run_state = self._ensure_run_state(effective_context.plan_id)

        prompt = build_synthesis_prompt(summaries, degraded_inputs)
        try:
            schema_result = await self._structured_call_with_retry(
                "market_insight_synthesis",
                prompt,
                InsightSynthesisSchema,
                effective_context,
            )
            if schema_result.conclusions:
                synthesis = InsightSynthesis(
                    conclusions=tuple(schema_result.conclusions),
                    degraded_inputs=degraded_inputs,
                )
                summary_excerpt = schema_result.conclusions[0]
            else:
                # LLM 成功但空结论——视同 synthesis 降级（R3-4 自含标记对称化）
                synthesis = InsightSynthesis(
                    conclusions=(),
                    degraded_inputs=(*degraded_inputs, "market_insight_synthesis"),
                )
                summary_excerpt = ""
        except AgentWorkflowError as error:
            # synthesis 自身降级：conclusions=空 + degraded_inputs 自含标记（R3-4 钦定）
            logger.warning("综合洞察 LLM 降级: %s", error)
            synthesis = InsightSynthesis(
                conclusions=(),
                degraded_inputs=(*degraded_inputs, "market_insight_synthesis"),
            )
            summary_excerpt = ""

        run_state.record_step("market_insight_synthesis", started_at, summary_excerpt, degraded=not synthesis.conclusions)
        await self._write_snapshot_and_publish(
            effective_context, stage="market_insight_synthesis", summary_excerpt=summary_excerpt
        )
        # 6-4 挂接段：synthesis 型素材（模块常量语义——语义配置表无 synthesis 行；
        # 无工具无检索——tool_slug 恒空/证据恒 0；degraded=not conclusions 与
        # record_step 口径同源）
        await self._compose_and_archive_chain(
            effective_context,
            "market_insight_synthesis",
            StepChainMaterial(
                stage="market_insight_synthesis",
                display_name=SYNTHESIS_DISPLAY_NAME,
                role_prefix=SYNTHESIS_ROLE_PREFIX,
                task=effective_context.task,
                evidence_count=0,
                tool_slug="",
                evidence_refs=(),
                summary="",
                findings_count=len(synthesis.conclusions),
                degraded_inputs_count=len(synthesis.degraded_inputs),
                degraded=not synthesis.conclusions,
                degrade_reason="" if synthesis.conclusions else "综合结论为空（LLM 降级或空结论）",
                payload=dataclasses.asdict(synthesis),
                structured_ok=bool(synthesis.conclusions),
            ),
        )
        return synthesis

    # ------------------------------------------------------------------
    # 图 state 投影（节点适配器消费）
    # ------------------------------------------------------------------

    def project_timeline(self, plan_id: str) -> list[dict[str, Any]]:
        """投影 timeline（图 state 的 timeline 键——适配器直写全量勿二次合并）。"""
        run_state = self._runs.get(plan_id)
        if run_state is None:
            return []
        return [entry.to_dict() for entry in run_state.timeline]

    def project_degraded_steps(self, plan_id: str) -> list[str]:
        """投影降级步骤清单（图 state 的 degraded_steps 键）。"""
        run_state = self._runs.get(plan_id)
        return list(run_state.degraded_steps) if run_state else []

    def project_chain_records(self, plan_id: str) -> list[ChainRecord]:
        """投影思维链归档记录（图 state 的 chain_records 键——6-4 回传三件套②）。

        degraded_steps/timeline 同构第三投影：节点适配器直写全量勿二次合并
        （R1-F1）；未挂接（尾参 None）或未执行步骤时恒空清单。
        """
        run_state = self._runs.get(plan_id)
        return list(run_state.chain_records) if run_state else []

    async def _compose_and_archive_chain(
        self,
        context: BlmPlanningContext,
        stage: str,
        material: StepChainMaterial,
    ) -> None:
        """思维链挂接段（6-4——三方法末尾共用：UUID 守卫 → 组装归档 → 累积）。

        降级语义（OD-5 可观测面非流程面）：
        - 尾参 None（未注入）→ 直接返回（零挂接——与现状逐字节等价守护）；
        - plan_id 畸形（非 UUID——CLI --plan-id 无守卫透传形态）→ 该步 chain
          缺席 + warning 降级续行（R3-F4 守卫，裸 ValueError 逃逸违红线）；
        - compose 返回 None（445 组装失败）→ 跳过追加（chain 缺席台账——R1-F5）；
        - 返回 ChainRecord（含 archived=False 284 台账）→ 追加 run_state（R1-F1①
          累积进 per-run 状态非方法返回值——三方法返回 VO 零改动）。
        """
        if self._chain_archive_service is None:
            return
        try:
            plan_uuid = uuid.UUID(context.plan_id)
        except (ValueError, TypeError, AttributeError):
            logger.warning(
                "思维链挂接段 plan_id 非 UUID 形态（该步 chain 缺席+降级续行）[stage=%s plan_id=%r]",
                stage,
                context.plan_id,
            )
            return
        record = None
        try:
            record = await self._chain_archive_service.compose_and_archive_step_chain(plan_uuid, stage, material)
        except Exception:
            # 观测面兜底（CR1-F6——OD-5 完整捕获面）：compose 内层已精确捕获
            # 242（→445→None 缺席台账）与 284（→archived=False 台账），此处
            # 兜底的是未来演化/底层未包装的意外异常形态——宽捕降级续行不杀
            # run（八步领域产物不因观测面失败丢弃）；日志形态对齐同文件
            # _write_snapshot_and_publish 容错先例（logger.exception 带堆栈）。
            logger.exception(
                "思维链挂接段意外异常（该步 chain 缺席+降级续行）[stage=%s plan_id=%s]",
                stage,
                context.plan_id,
            )
            return
        if record is None:
            return
        run_state = self._runs.get(context.plan_id)
        if run_state is not None:
            run_state.chain_records.append(record)

    # ------------------------------------------------------------------
    # 内部：LLM 结构化调用（444 纪律 + 两级重试）
    # ------------------------------------------------------------------

    def _build_call_config(self, step_key: str) -> LLMConfig:
        """构造调用配置（温度=配置表档 + timeout=8s——连接字段随基底继承）。"""
        return dataclasses.replace(
            self._base_config,
            temperature=BLM_TEMPERATURE_PROFILE[step_key],
            timeout=BLM_PER_CALL_TIMEOUT_SEC,
        )

    def _build_system_prompt(self, context: BlmPlanningContext | None) -> str:
        """构造 system 面 prompt（DC-5：档案 tools_l1 全量注入——R2 幻觉名缓解）。

        5-3 先例形态（agent_workflow_prompts.build_l1_view 取 tool_name——
        R2-1 字段口径对齐）；tools_l1 缺失/为空时返回空串（structured_generate
        按空串退化 user-only）。
        """
        if context is None:
            return ""
        profile_result = getattr(context, "profile_result", None)
        tools_l1 = getattr(profile_result, "tools_l1", None) or ()
        names = [str(getattr(tool, "tool_name", "")) for tool in tools_l1]
        names = [name for name in names if name]
        if not names:
            return ""
        return "你是 CEO 战略规划 Agent（BLM 前两阶段执行者）。可用分析工具清单（TOOLS L1 全量）：\n- " + "\n- ".join(names)

    async def _structured_call_with_retry(
        self, step_key: str, prompt: str, schema_cls: type, context: BlmPlanningContext | None
    ) -> Any:
        """结构化调用 + 服务内单次重试（瞬时 LLM/网络失败——两级设计第一级）。

        Args:
            step_key: 步骤标识（温度档查表键）。
            prompt: 提示词（user 面）。
            schema_cls: 结构化输出 Schema 类。
            context: 规划上下文（异常上下文锚 + system 面档案来源）。

        Returns:
            Schema 实例。

        Raises:
            AgentWorkflowError: 444 包装（重试后仍失败/结构守卫失败/LLM 配置
                错误——调用方捕获转步级降级）。
        """
        config = self._build_call_config(step_key)
        system_prompt = self._build_system_prompt(context) or None
        agent_id_str = str(getattr(context, "agent_id", "")) if context else ""
        attempts = _TRANSIENT_RETRY_ATTEMPTS + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                result = await self._llm.structured_generate(
                    prompt=prompt,
                    response_schema=schema_cls,
                    config=config,
                    system_prompt=system_prompt,
                )
                if not isinstance(result, schema_cls):
                    raise AgentWorkflowError(
                        agent_id=agent_id_str,
                        phase=step_key,
                        reason=f"LLM 返回结果不是 {schema_cls.__name__} 实例（实际 {type(result).__name__}）",
                    )
                return result
            except AgentWorkflowError:
                raise  # 结构守卫失败非瞬时——不重试
            except asyncio.CancelledError:
                raise
            except LLMConfigError as error:
                # 配置错误非瞬时——不重试，直接步级降级且原因如实（AC-6① 流程继续语义）
                raise AgentWorkflowError(
                    agent_id=agent_id_str,
                    phase=step_key,
                    reason=f"LLM 配置错误（不重试）: {error}",
                ) from error
            except Exception as error:  # 瞬时故障（LLMAPIError/网络/超时族）
                last_error = error
                logger.warning("BLM 步骤 %s 第 %d 次调用失败（%s），瞬时重试", step_key, attempt + 1, error)
        raise AgentWorkflowError(
            agent_id=agent_id_str,
            phase=step_key,
            reason=f"{step_key} 步骤 LLM 调用失败（含 {_TRANSIENT_RETRY_ATTEMPTS} 次重试）: {last_error}",
            cause=last_error,
        )

    # ------------------------------------------------------------------
    # 内部：工具候选执行（先行——449/380 步级捕获）
    # ------------------------------------------------------------------

    async def _execute_candidate_tools(
        self, tool_candidates: tuple[str, ...], context: BlmPlanningContext
    ) -> tuple[str, str, str]:
        """确定性工具候选先行执行（DC-3 时序第一环）。

        白名单逐工具尝试（449 预检 → get_tool → 执行），首个成功产出即返回；
        工具面失败（449/380/解析失败）降工具转直接推理——返回降级原因（步骤
        级 degraded 标记），LLM 产出仍执行（直接推理续行）；执行异常则尝试
        下一个候选，环耗尽仍有执行失败时聚合记降级原因（与 449/380 语义
        对称——真执行失败不得静默）。

        Returns:
            (工具输出摘要, 工具面降级原因, 实际执行工具 slug) 三元组——降级
            原因为空串表示工具正常；slug 为空串表示直接推理（未执行工具）。
        """
        agent_uuid = self._resolve_agent_uuid(context)
        failed_names: list[str] = []
        for tool_name in tool_candidates:
            try:
                if agent_uuid is not None:
                    await self._isolation_guard.ensure_tool_access(agent_uuid, tool_name)
                tool = self._tool_registry_service.get_tool(tool_name=tool_name)
            except IsolationOperationForbiddenError as error:
                logger.warning("工具 %s 预检 449 拒绝（直接推理续行）: %s", tool_name, error.context)
                return "", f"工具 {tool_name} 隔离预检拒绝（449）", ""
            except ToolNotFoundError as error:
                logger.warning("工具 %s 未注册（380——直接推理续行）: %s", tool_name, error.context)
                return "", f"工具 {tool_name} 未注册（380）", ""
            except Exception as error:
                logger.warning("工具 %s 解析失败（直接推理续行）: %s", tool_name, error)
                return "", f"工具 {tool_name} 解析失败：{error}", ""
            try:
                from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall

                # MVP 固定单租户标识（5-3 先例平移——agent_workflow_context.py:39；
                # 多租户扩展归后续 Story，R1-F21）
                tenant_id = MVP_TENANT_ID
                tool_call = ToolCall(tool_id=tool.tool_id, arguments={"task": context.task}, tenant_id=tenant_id)
                execution_context = ExecutionContext(tenant_id=tenant_id, trace_id="")
                result = await self._tool_execution_service.execute(tool.tool_id, tool_call, execution_context)
                output_text = str(getattr(result, "output", ""))[:_EVIDENCE_TEXT_MAX_CHARS]
                tool_slug = tool.slug or tool.name  # slug 口径钦定（VO 契约——缺失回落显示名）
                return f"工具 {tool.name} 输出：{output_text}", "", tool_slug
            except Exception as error:
                logger.warning("工具 %s 执行失败（尝试下一候选）: %s", tool_name, error)
                failed_names.append(tool_name)
                continue
        if failed_names:
            return "", f"工具候选全部执行失败：{'、'.join(failed_names)}", ""
        return "", "", ""

    @staticmethod
    def _resolve_agent_uuid(context: BlmPlanningContext) -> uuid.UUID | None:
        """从上下文解析 Agent UUID（隔离预检参数——畸形值 None 跳过预检）。"""
        raw = getattr(context, "agent_id", None)
        if isinstance(raw, uuid.UUID):
            return raw
        try:
            return uuid.UUID(str(raw)) if raw else None
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # 内部：检索（连接失败=降级 / 空结果=正常空证据——R3-6 判别语义）
    # ------------------------------------------------------------------

    async def _retrieve_evidence(self, query: str) -> tuple[tuple[str, ...], str, tuple[str, ...]]:
        """异步检索证据片段。

        文本键双源兼容提取：测试语料 payload["text"] 与生产链 payload["content"]
        （chunk_indexing_handler 写入键）——键 SSOT 统一登记 deferred，双键期
        双命中。

        Returns:
            (证据文本元组, 检索降级原因, 证据引用清单) 三元组——连接失败时
            原因为非空串（该步降级）；空结果时证据为空元组且原因为空串
            （正常空证据）；引用清单为命中条目 id 的 str 归一序列。
        """
        try:
            results = await self._hybrid_search.search(
                collection=self._search_collection, query_text=query, limit=_MAX_EVIDENCE_TEXTS
            )
        except Exception as error:
            logger.warning("检索取数失败（该步降级）: %s", error)
            return (), f"检索取数失败：{error}", ()
        texts: list[str] = []
        refs: list[str] = []
        for item in results or []:
            payload = item.get("payload") or {} if isinstance(item, dict) else {}
            text = str(payload.get("text") or payload.get("content") or "")[:_EVIDENCE_TEXT_MAX_CHARS]
            if text:
                texts.append(text)
                refs.append(str(item.get("id", "")))
            if len(texts) >= _MAX_EVIDENCE_TEXTS:
                break
        return tuple(texts), "", tuple(refs)

    # ------------------------------------------------------------------
    # 内部：快照写 + 事件发布（各方法末尾——DC-6/DC-8）
    # ------------------------------------------------------------------

    async def _write_step_checkpoint(
        self, context: BlmPlanningContext, step: MarketInsightStep, result: InsightStepResult
    ) -> None:
        """per-step Checkpoint 快照写入（Story 6-2——6-3 恢复点位数据面骨架）。

        与 latest（_write_snapshot_and_publish）的职责边界：latest=读侧状态面
        （GetBlmPlanningStatusUseCase 消费，七键全量投影）；per-step=恢复点位面
        （每子步骤一份，state_data 七键契约见端口文件第三级登记——
        structured_output 键恒在；其值为 None 当且仅当 LLM 调用/校验失败，
        工具/检索面降级而 LLM 调用成功时为该步类型化产物（与 summary/findings
        非空对称——代码审查 R1-F1 收窄口径）；completed_steps 为含该步的
        已完成步骤标识清单（timeline 条目 step 字段同源——六子步骤为裸
        step 值、performance_gap/synthesis 为 stage 形态，首步即含
        performance_gap）。写入失败容错不阻断流程
        （与 latest 同语义——步级容错）；TTL 沿用 CheckpointSnapshot 既有
        默认 86400（6-3 升级 30 天完整形态）。

        Args:
            context: BLM 规划上下文（plan_id 归属锚）。
            step: 该子步骤枚举（session_id 后缀与 stage_id 构造源）。
            result: 该步信封（summary/structured_output/degraded 投影源）。
        """
        run_state = self._runs.get(context.plan_id)
        if run_state is None:
            return
        try:
            await self._snapshot_repository.save(
                CheckpointSnapshot(
                    session_id=f"{BLM_PLANNING_SESSION_PREFIX}{context.plan_id}:{step.value}",
                    stage_id=f"market_insight_{step.value}",
                    state_data={
                        "step": step.value,
                        "plan_id": context.plan_id,
                        "summary": result.summary,
                        "structured_output": result.structured_output,
                        "degraded": result.degraded,
                        "degrade_reason": result.degrade_reason,
                        "completed_steps": [entry.step for entry in run_state.timeline],
                    },
                )
            )
        except Exception:
            logger.exception("per-step 快照写入失败 [plan_id=%s step=%s]", context.plan_id, step.value)

    async def _write_snapshot_and_publish(self, context: BlmPlanningContext, *, stage: str, summary_excerpt: str) -> None:
        """步骤边界：快照 latest 写入 + BlmStageCompleted 发布（失败不阻断流程）。"""
        self._last_context_cache = context
        run_state = self._runs.get(context.plan_id)
        if run_state is not None:
            try:
                await self._snapshot_repository.save(
                    CheckpointSnapshot(
                        session_id=f"{BLM_PLANNING_SESSION_PREFIX}{run_state.plan_id}",
                        stage_id=BLM_PLANNING_SNAPSHOT_STAGE,
                        state_data=run_state.to_state_data(),
                    )
                )
            except Exception:
                logger.exception("BLM 快照写入失败 [plan_id=%s]", context.plan_id)
        try:
            agent_uuid = self._resolve_agent_uuid(context)
            await self._event_publisher.publish(
                BlmStageCompleted(
                    plan_id=context.plan_id,
                    agent_id=agent_uuid if agent_uuid is not None else uuid.uuid4(),
                    stage=stage,
                    summary_excerpt=summary_excerpt,
                )
            )
        except Exception:
            logger.exception("BlmStageCompleted 发布失败 [plan_id=%s stage=%s]", context.plan_id, stage)

    def _ensure_run_state(self, plan_id: str) -> _PlanRunState:
        """取/建规划任务的内存累积器。"""
        if plan_id not in self._runs:
            self._runs[plan_id] = _PlanRunState(plan_id)
        return self._runs[plan_id]


__all__ = ["BlmPlanningService"]
