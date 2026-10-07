"""应用层红蓝辩论编排服务模块

Story 4.5 — 单 Agent 多视角辩论 MVP 的编排核心：
双视角并发生成（gather）→ 分化度门控 → 风险视图合成 → 事件发布。

编排八步（AC-7）：
1. 创建 DebateSession（IDLE→GENERATING）并 save——编排全程每次状态迁移后均 save
2. 红蓝并发 asyncio.gather（温度阶梯：红 0.8 发散 / 蓝 0.5 收敛）；任一失败 →
   取消兄弟任务 + session FAILED + save + 包装 DebateGenerationError
3. Schema → 领域 VO 转换（to_domain，应用层职责）
4. 分化度门控：evaluate_overlap → ≥0.95 抛 DebateLowDivergenceError（FAILED+save）；
   0.80 ≤ 重叠率 < 0.95 记入 warnings 继续
5. GENERATING→SYNTHESIZING + save；合成调用（T=0.2）；失败 → FAILED + save +
   DebateSynthesisError；VO 构造抛 EntityValidationError(242) → FAILED + save + 透传
6. Schema → RiskView VO（overlap_rate/warnings 服务端注入，不信任 LLM 输出分化度）
7. 回填 session 四字段（red/blue/risk_view/completed_at）→ SYNTHESIZING→COMPLETED + save
8. 发布 DebateCompleted（双形态失败均不覆写结果）→ 返回 DebateResult

延迟预算三段式（诚实声明）：
① 无重试路径上界 = max(红,蓝) 12s + 合成 12s + 编排 <1s ≈ 25s < 30s
② LitellmLLMClient 内置 tenacity 重试（默认 3 次 + 指数退避 1~4s），含重试最坏
  ≈ 39s/调用——超 30s 时表现为 BDD 30s 硬超时先行截断，属已声明的接受风险
③ P95 分布统计随 Story 5.7 落地，本 Story 以单点计时 + 上界论证交付证据
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import UTC, datetime

from src.application.services.debate_prompts import (
    PERSPECTIVE_PROMPT_MAP,
    SYNTHESIS_SYSTEM_PROMPT,
    SYNTHESIS_USER_TEMPLATE,
)
from src.application.services.debate_schemas import (
    PerspectiveAnalysisSchema,
    RiskViewSchema,
)
from src.domain.entities.debate_session import (
    DebateSession,
    DebateSessionState,
)
from src.domain.events.debate_events import DebateCompleted
from src.domain.exceptions import (
    DebateGenerationError,
    DebateLowDivergenceError,
    DebateSynthesisError,
    EntityValidationError,
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
    ServiceUnavailableError,
    TimeoutError,
)
from src.domain.ports.debate_session_repository import DebateSessionRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.llm_client import LLMClientPort, LLMConfig
from src.domain.services.debate_evaluator import DebateEvaluator
from src.domain.value_objects.debate import (
    DebatePerspective,
    DebateQuality,
    DebateResult,
    DebateTopic,
    PerspectiveAnalysis,
)
from src.domain.value_objects.tool_execution import ExecutionContext

logger = logging.getLogger(__name__)

# 温度阶梯（FR-SP-10 V1 三阶段一致，架构测试绊线断言对齐——禁止调用方覆盖）
TEMPERATURE_PROFILE: dict[str, float] = {"red": 0.8, "blue": 0.5, "synthesis": 0.2}
# 分化度硬阈值：重叠率 ≥ 0.95 抛 DebateLowDivergenceError
OVERLAP_HARD_THRESHOLD = 0.95
# 分化度警告阈值：0.80 ≤ 重叠率 < 0.95 输出 RiskView.warnings
OVERLAP_WARNING_THRESHOLD = 0.80

# 单次 LLM 调用超时上限（秒）——必须显式传递，禁止依赖 LLMConfig.from_env 默认 600s
_DEFAULT_PER_CALL_TIMEOUT_SEC = 12.0


class RedBlueDebateService:
    """红蓝辩论编排服务（单 Agent 多视角 MVP）

    编排 LLMClientPort（三档温度）+ DebateEvaluator（分化度门控）+
    DebateSessionRepositoryPort（状态可观测）+ EventPublisher（完成通知）。
    """

    def __init__(
        self,
        llm_client: LLMClientPort,
        evaluator: DebateEvaluator,
        session_repository: DebateSessionRepositoryPort,
        event_publisher: EventPublisher,
        per_call_timeout_sec: float = _DEFAULT_PER_CALL_TIMEOUT_SEC,
        base_config: LLMConfig | None = None,
    ) -> None:
        """初始化辩论服务（四端口组合注入）

        Args:
            llm_client: LLM 客户端端口（温度经 LLMConfig 分档传参）
            evaluator: 辩论质量评估器（分化度门控）
            session_repository: 辩论会话仓储（状态追踪）
            event_publisher: 事件发布端口（DebateCompleted 通知）
            per_call_timeout_sec: 单次 LLM 调用超时上限（默认 12.0s）
            base_config: 每次调用的基底配置（连接字段 endpoint/api_key/model 随基底
                继承，per-call 仅覆写 temperature/timeout；None 时用 LLMConfig 默认值
                ——Fake 单测不读连接字段，真实场景须提供，否则触发 LLMConfigError）
        """
        self._llm_client = llm_client
        self._evaluator = evaluator
        self._session_repository = session_repository
        self._event_publisher = event_publisher
        self._per_call_timeout_sec = per_call_timeout_sec
        self._base_config = base_config

    async def run_debate(self, topic: DebateTopic, context: ExecutionContext) -> DebateResult:
        """执行红蓝辩论（编排八步，见模块 docstring）

        Args:
            topic: 争议议题（含租户与背景）
            context: 执行上下文（会话/追踪）

        Returns:
            DebateResult 辩论结果

        Raises:
            DebateGenerationError: 视角 LLM 生成失败（EXCEPTION_420）
            DebateSynthesisError: 合成 LLM 调用失败（EXCEPTION_421）
            DebateLowDivergenceError: 重叠率 ≥ 0.95 分化不足（EXCEPTION_422）
            EntityValidationError: 结构化输出违反领域不变量时透传
                （EXCEPTION_242——数据契约违反而非 LLM 调用失败，
                session 已转 FAILED 落库；Schema 层条目校验加严后
                该路径退居防御深度，防端口实现返回手工构造的非法实例）
        """
        started = time.perf_counter()
        session = DebateSession(
            debate_id=topic.debate_id,
            tenant_id=topic.tenant_id,
            title=topic.title,
        )
        session.transition_to(DebateSessionState.GENERATING)
        await self._session_repository.save(session)

        # ---- 步骤 2+3：红蓝并发生成 + Schema→VO 转换 ----
        red_analysis, blue_analysis = await self._generate_perspectives(topic, session)

        # ---- 步骤 4：分化度门控 ----
        overlap_rate = self._evaluator.evaluate_overlap(red_analysis, blue_analysis)
        warnings: tuple[str, ...] = ()
        if overlap_rate >= OVERLAP_HARD_THRESHOLD:
            session.failure_reason = f"红蓝重叠率 {overlap_rate:.2f} ≥ {OVERLAP_HARD_THRESHOLD}，视角分化不足"
            self._fail_session(session)
            await self._session_repository.save(session)
            raise DebateLowDivergenceError(
                debate_id=str(topic.debate_id),
                overlap_rate=overlap_rate,
                red_summary=self._summarize_arguments(red_analysis),
                blue_summary=self._summarize_arguments(blue_analysis),
            )
        if overlap_rate >= OVERLAP_WARNING_THRESHOLD:
            warnings = (f"红蓝重叠率 {overlap_rate:.2f} ≥ {OVERLAP_WARNING_THRESHOLD}，视角分化偏弱",)

        # ---- 步骤 5：进入合成阶段 ----
        session.transition_to(DebateSessionState.SYNTHESIZING)
        await self._session_repository.save(session)
        risk_schema = await self._synthesize_risk_view(topic, session, red_analysis, blue_analysis)

        # ---- 步骤 6：Schema → RiskView VO（服务端注入 overlap_rate/warnings）----
        try:
            risk_view = risk_schema.to_domain(overlap_rate=overlap_rate, warnings=warnings)
        except EntityValidationError:
            # 数据契约违反（Pydantic 过但领域不变量败）——透传 242，不包装为 421
            session.failure_reason = "风险视图领域不变量校验失败"
            self._fail_session(session)
            await self._session_repository.save(session)
            raise

        # ---- 步骤 7：回填四字段 → COMPLETED ----
        session.red_analysis = red_analysis
        session.blue_analysis = blue_analysis
        session.risk_view = risk_view
        session.completed_at = datetime.now(UTC)
        session.transition_to(DebateSessionState.COMPLETED)
        await self._session_repository.save(session)

        duration_ms = round((time.perf_counter() - started) * 1000)
        quality = DebateQuality(overlap_rate=overlap_rate)
        result = DebateResult(
            debate_id=topic.debate_id,
            topic_title=topic.title,
            red_analysis=red_analysis,
            blue_analysis=blue_analysis,
            risk_view=risk_view,
            quality=quality,
            duration_ms=duration_ms,
        )

        # ---- 步骤 8：发布事件（双形态失败均不覆写结果）----
        await self._publish_completion(topic, result)
        return result

    async def get_debate_result(self, debate_id: uuid.UUID) -> DebateResult | None:
        """按辩论会话 ID 重建结果（仅 COMPLETED 会话）

        Args:
            debate_id: 辩论会话 ID

        Returns:
            DebateResult 重建结果；未知名 / 非 COMPLETED（含 FAILED——无 risk_view
            数学上不可重建）返回 None
        """
        session = await self._session_repository.get_by_id(debate_id)
        if session is None or session.state is not DebateSessionState.COMPLETED:
            return None
        assert session.risk_view is not None  # COMPLETED 终态不变量保证
        assert session.red_analysis is not None and session.blue_analysis is not None
        assert session.completed_at is not None
        return DebateResult(
            debate_id=session.debate_id,
            topic_title=session.title,
            red_analysis=session.red_analysis,
            blue_analysis=session.blue_analysis,
            risk_view=session.risk_view,
            quality=DebateQuality(
                overlap_rate=session.risk_view.overlap_rate,
                gain_rate=None,
                repetition_rate=None,
            ),
            duration_ms=round((session.completed_at - session.started_at).total_seconds() * 1000),
        )

    # ------------------------------------------------------------------
    # 私有编排步骤（方法化，Task 7 重构产物）
    # ------------------------------------------------------------------

    async def _generate_perspectives(
        self,
        topic: DebateTopic,
        session: DebateSession,
    ) -> tuple[PerspectiveAnalysis, PerspectiveAnalysis]:
        """红蓝双视角并发生成（步骤 2+3：gather + Schema→VO）

        独立立场方法论：双方 prompt 仅含议题与背景，不含对方输出。

        Args:
            topic: 争议议题
            session: 辩论会话（失败时转 FAILED）

        Returns:
            (红视角分析, 蓝视角分析) 领域 VO 元组

        Raises:
            DebateGenerationError: 任一视角生成失败（兄弟任务已取消）
        """
        red_task = asyncio.create_task(self._generate_single_perspective(topic, DebatePerspective.RED_AGGRESSIVE))
        blue_task = asyncio.create_task(self._generate_single_perspective(topic, DebatePerspective.BLUE_CONSERVATIVE))
        try:
            red_schema, blue_schema = await asyncio.gather(red_task, blue_task)
        except (Exception, asyncio.CancelledError):
            # gather 默认首异常即传播且不取消兄弟任务——显式取消防孤儿任务
            for task in (red_task, blue_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(red_task, blue_task, return_exceptions=True)
            self._fail_session(session, red_task, blue_task)
            await self._session_repository.save(session)
            raise
        try:
            return (
                red_schema.to_domain(DebatePerspective.RED_AGGRESSIVE),
                blue_schema.to_domain(DebatePerspective.BLUE_CONSERVATIVE),
            )
        except EntityValidationError:
            # 数据契约违反（Pydantic 过但领域不变量败）——透传 242，不包装为 420，
            # 与合成路径（run_debate 风险视图转换）对称的四步归宿（R1-F02）
            session.failure_reason = "视角结构化输出领域不变量校验失败"
            self._fail_session(session)
            await self._session_repository.save(session)
            raise

    async def _generate_single_perspective(
        self,
        topic: DebateTopic,
        perspective: DebatePerspective,
    ) -> PerspectiveAnalysisSchema:
        """单视角 LLM 结构化生成（含异常包装为 DebateGenerationError）

        Args:
            topic: 争议议题
            perspective: 目标视角（红/蓝）

        Returns:
            视角分析 Schema 实例

        Raises:
            DebateGenerationError: LLM 调用不可恢复失败（cause 链保留底层异常）
        """
        prompt_entry = PERSPECTIVE_PROMPT_MAP[perspective]
        temperature = TEMPERATURE_PROFILE["red" if perspective is DebatePerspective.RED_AGGRESSIVE else "blue"]
        user_prompt = prompt_entry["user_prompt_template"].format(
            title=topic.title,
            background=topic.background or "（无背景材料）",
        )
        config = self._build_call_config(temperature)
        try:
            result = await self._llm_client.structured_generate(
                prompt=user_prompt,
                response_schema=PerspectiveAnalysisSchema,
                config=config,
                system_prompt=prompt_entry["system_prompt"],
            )
        except LLMConfigError:
            # 配置错误透传不包装
            raise
        except asyncio.CancelledError:
            # 协程取消透传（父任务取消语义保护）
            raise
        except (LLMAPIError, LLMResponseError, TimeoutError, ServiceUnavailableError) as e:
            raise DebateGenerationError(
                debate_id=str(topic.debate_id),
                perspective=perspective.value,
                topic_title=topic.title,
                message=f"{perspective.value} 视角生成失败: {e}",
                cause=e,
            ) from e
        except EntityValidationError as e:
            # Pydantic 校验失败经 LLM 客户端包装后到达，此处统一 420 归口
            raise DebateGenerationError(
                debate_id=str(topic.debate_id),
                perspective=perspective.value,
                topic_title=topic.title,
                message=f"{perspective.value} 视角结构化输出校验失败",
                cause=e,
            ) from e
        except Exception as e:
            raise DebateGenerationError(
                debate_id=str(topic.debate_id),
                perspective=perspective.value,
                topic_title=topic.title,
                message=f"{perspective.value} 视角生成未知失败: {type(e).__name__}",
                cause=e,
            ) from e
        if not isinstance(result, PerspectiveAnalysisSchema):
            raise DebateGenerationError(
                debate_id=str(topic.debate_id),
                perspective=perspective.value,
                topic_title=topic.title,
                message="LLM 返回结果不是 PerspectiveAnalysisSchema 实例",
            )
        return result

    async def _synthesize_risk_view(
        self,
        topic: DebateTopic,
        session: DebateSession,
        red_analysis: PerspectiveAnalysis,
        blue_analysis: PerspectiveAnalysis,
    ) -> RiskViewSchema:
        """风险全景视图合成调用（步骤 5：T=0.2，裁判 prompt 注入红蓝论点 JSON）

        Args:
            topic: 争议议题
            session: 辩论会话（失败时转 FAILED）
            red_analysis: 红方视角分析
            blue_analysis: 蓝方视角分析

        Returns:
            RiskViewSchema 实例

        Raises:
            DebateSynthesisError: 合成调用不可恢复失败
        """

        user_prompt = SYNTHESIS_USER_TEMPLATE.format(
            red_analysis=json.dumps(
                {
                    "stance": red_analysis.stance,
                    "arguments": list(red_analysis.arguments),
                    "risks": list(red_analysis.risks),
                    "recommendations": list(red_analysis.recommendations),
                    "confidence": red_analysis.confidence,
                },
                ensure_ascii=False,
            ),
            blue_analysis=json.dumps(
                {
                    "stance": blue_analysis.stance,
                    "arguments": list(blue_analysis.arguments),
                    "risks": list(blue_analysis.risks),
                    "recommendations": list(blue_analysis.recommendations),
                    "confidence": blue_analysis.confidence,
                },
                ensure_ascii=False,
            ),
        )
        config = self._build_call_config(TEMPERATURE_PROFILE["synthesis"])
        try:
            result = await self._llm_client.structured_generate(
                prompt=user_prompt,
                response_schema=RiskViewSchema,
                config=config,
                system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            )
        except LLMConfigError:
            raise
        except asyncio.CancelledError:
            raise
        except (LLMAPIError, LLMResponseError, TimeoutError, ServiceUnavailableError) as e:
            session.failure_reason = f"风险视图合成失败: {e}"
            self._fail_session(session)
            await self._session_repository.save(session)
            raise DebateSynthesisError(
                debate_id=str(topic.debate_id),
                topic_title=topic.title,
                message=f"风险视图合成失败: {e}",
                cause=e,
            ) from e
        except Exception as e:
            session.failure_reason = f"风险视图合成未知失败: {type(e).__name__}"
            self._fail_session(session)
            await self._session_repository.save(session)
            raise DebateSynthesisError(
                debate_id=str(topic.debate_id),
                topic_title=topic.title,
                message=f"风险视图合成未知失败: {type(e).__name__}",
                cause=e,
            ) from e
        if not isinstance(result, RiskViewSchema):
            session.failure_reason = "LLM 返回结果不是 RiskViewSchema 实例"
            self._fail_session(session)
            await self._session_repository.save(session)
            raise DebateSynthesisError(
                debate_id=str(topic.debate_id),
                topic_title=topic.title,
                message="LLM 返回结果不是 RiskViewSchema 实例",
            )
        return result

    async def _publish_completion(
        self,
        topic: DebateTopic,
        result: DebateResult,
    ) -> None:
        """发布 DebateCompleted 事件（步骤 8：双形态失败均不覆写结果）

        Args:
            topic: 争议议题
            result: 辩论结果
        """
        event = DebateCompleted(
            debate_id=result.debate_id,
            tenant_id=topic.tenant_id,
            topic_title=result.topic_title,
            red_stance=result.red_analysis.stance,
            blue_stance=result.blue_analysis.stance,
            consensus_count=len(result.risk_view.consensus_areas),
            disagreement_count=len(result.risk_view.disagreement_areas),
            overlap_rate=result.risk_view.overlap_rate,
            overall_risk_level=result.risk_view.overall_risk_level,
            duration_ms=result.duration_ms,
            temperature_profile=dict(TEMPERATURE_PROFILE),
        )
        try:
            publish_result = await self._event_publisher.publish(event)
            # 契约内形态：EventPublisher 返回 PublishResult（不抛异常）
            if publish_result is None or not publish_result.is_success:
                logger.warning(
                    "DebateCompleted 事件发布未成功（debate_id=%s），辩论结果不受影响",
                    result.debate_id,
                )
        except Exception:
            # 契约外防御形态：publish 调用本身抛异常——不覆写辩论结果
            logger.warning(
                "DebateCompleted 事件发布异常（debate_id=%s），辩论结果不受影响",
                result.debate_id,
                exc_info=True,
            )

    def _summarize_arguments(self, analysis: PerspectiveAnalysis) -> str:
        """视角论点摘要（异常 context 用，截断由异常构造器承担）"""
        return "".join(analysis.arguments)

    def _build_call_config(self, temperature: float) -> LLMConfig:
        """构造单次调用配置（温度阶梯 + per-call timeout，连接字段随基底继承）

        LLMClientPort 客户端契约为 config 整体替换（cfg = config or self._config），
        故温度分档必须基于 base_config 派生完整配置，避免丢失 endpoint/api_key
        等连接字段（真实集成测试捕获的缺陷形态）。

        Args:
            temperature: 本阶段温度（红 0.8 / 蓝 0.5 / 合成 0.2）

        Returns:
            派生的 LLMConfig（temperature/timeout 覆写，其余字段继承基底）
        """
        import dataclasses

        base = self._base_config or LLMConfig()
        return dataclasses.replace(
            base,
            temperature=temperature,
            timeout=self._per_call_timeout_sec,
        )

    def _fail_session(self, session: DebateSession, *tasks: asyncio.Task) -> None:
        """会话转 FAILED（终态守卫 + 失败原因兜底）

        Args:
            session: 辩论会话
            *tasks: 触发失败的关联任务（仅用于提取异常信息，已完成任务的
                exception 若未被消费则在此检索，防 never retrieved 警告）
        """
        for task in tasks:
            if task.done() and not task.cancelled():
                exc = task.exception()
                if exc is not None and session.failure_reason is None:
                    session.failure_reason = str(exc)
        if session.state is not DebateSessionState.FAILED:
            if session.failure_reason is None:
                session.failure_reason = "辩论编排失败"
            session.transition_to(DebateSessionState.FAILED)


__all__ = [
    "OVERLAP_HARD_THRESHOLD",
    "OVERLAP_WARNING_THRESHOLD",
    "RedBlueDebateService",
    "TEMPERATURE_PROFILE",
]
