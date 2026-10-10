"""应用层 Validation Feedback 闭环编排服务（Story 4.7 AC-2/AC-3/AC-5/AC-6）

ValidationFeedbackService——反馈闭环编排（蓝图见 Story Dev Notes）：

1. 幂等短路：同 trigger_error（execution_id）已有终态演进日志 → 副作用去重 +
   合成结论（INFEASIBLE 语义完整；RECOVERED 携带 replayed 标记——R8-3）
2. 错误上下文提取：cause 链 STDERR（382 主路径）/ violations（389-Schema）/
   LLM 错误消息（389-LLM——violations 双空形态）
3. 增强循环 attempt 1..3（总尝试语义）：
   a. 案例查询 + 五格分类（R9-16：CASE_GUIDED/NEGATIVE_CASE_GUIDED/PURE_LLM
      + 空配方格④ + 碰撞抑制格⑤）
   b. fix-gen（修复建议生成）：prompt 含 STDERR/violations/案例/负样本提示/
      跨尝试失败反馈（R8-1 动作+结果成对）+ 禁止重复指令；失败计为该次
      attempt 失败（非白名单异常收敛——R2-10）
   c. hints 注入（validation_feedback_hints 扩展键——P0-D 模式；格②命中时
      case_summaries 附带负样本提示——R1-F6）
   d. 防放大（R1-F3 ContextVar 形态）：封顶策略由引擎原策略 replace 派生
      （max_attempts=1，保留全部字段）经 retry_policy_override 按 task 覆盖——
      共享引擎状态零写入（TOV 校验重试经 effective 动态读同被封顶）
   e. 重执行经 inner_chain（SSD>TOV>Engine 完整内层链——R9-14 双句柄）
4. mid-attempt 异常分类（R9-13 对称立法）：入环谓词内异常计为该次 attempt 失败；
   谓词外异常中止闭环直传（零观测副作用——R3-3）
5. #17②：3 attempt 全失败且各次根因均为 LLM 瞬时（R10-2 谓词集 = 引擎生产
   白名单同集）→ 直传原触发异常（不标 INFEASIBLE——外部瞬时故障≠任务不可行）
6. 耗尽：内部构造 ValidationFeedbackRetryExhaustedError(399) 信号后转换
   ToolResult(INFEASIBLE)（对外不抛——DAG 按 status 分支感知）
7. 回填：恢复 recovered_count+1 + fix_summary 覆写（非 LLM_TRANSIENT——#17①）；
   耗尽 infeasible_count+1（fix_summary 不动）
8. 事件（fire-and-forget）+ 演进日志（execution_id 幂等 upsert）
"""

from __future__ import annotations

import logging
import time
import uuid as uuid_module
from dataclasses import replace
from typing import Any

from src.application.ports.validation_feedback_service import ValidationFeedbackServicePort
from src.application.services.retry_helpers import RetryPolicy, _call_with_retry, retry_policy_override
from src.application.services.sandbox_security_decorator import extract_stderr_from_cause_chain
from src.application.services.validation_feedback_prompts import FIX_SYSTEM_PROMPT, build_fix_prompt
from src.domain.entities.error_case import ErrorCase
from src.domain.entities.evolution_log_entry import EvolutionLogEntry
from src.domain.events.validation_feedback_events import (
    ToolExecutionMarkedInfeasible,
    ToolExecutionRecovered,
)
from src.domain.exceptions import (
    LLMAPIError,
    LLMResponseError,
    TimeoutError,
    ToolExecutionFailedError,
    ToolResultValidationError,
    ValidationFeedbackRetryExhaustedError,
)
from src.domain.ports.error_case_repository import ErrorCaseRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.evolution_log_repository import EvolutionLogRepositoryPort
from src.domain.ports.llm_client import LLMClientPort
from src.domain.services.error_signature_extractor import ErrorSignatureExtractor
from src.domain.value_objects.tool_execution import ToolResult, ToolResultStatus
from src.domain.value_objects.validation_feedback import (
    FeedbackOutcome,
    FixAttempt,
    FixStrategy,
    TriggerCode,
)

logger = logging.getLogger(__name__)

# #17② 根因判定谓词类型集（R10-2 定稿：引擎生产可重试白名单同集——
# LLM 网络超时属「LLM 瞬时」语义域，排除 TimeoutError 会使超时持续故障误标 INFEASIBLE）
_LLM_TRANSIENT_ROOTS = (LLMAPIError, LLMResponseError, TimeoutError)


# 后台发布任务强引用集合（P0-I 模式关键一半——asyncio 未持引用的 task 可能被
# GC 中途回收，事件静默丢失；schema_event_helpers._background_tasks 同款）
_background_tasks: set = set()


def _drain_safe_publish(publisher: EventPublisher | None, event: Any) -> None:
    """fire-and-forget 事件发布（P0-I 模式——不阻塞主流程，异常仅日志）."""
    if publisher is None:
        return

    async def _publish() -> None:
        await publisher.publish(event)

    import asyncio

    task = asyncio.create_task(_publish())
    _background_tasks.add(task)
    # 释放回调先注册先执行（R2-A：被取消 task 的 exception() 抛 CancelledError，
    # 若 discard 后置则永不执行——引用滞留 + 回调异常噪音；schema_event_helpers
    # :206-207 先例同款双回调形态）
    task.add_done_callback(_background_tasks.discard)
    task.add_done_callback(_log_task_exception)


def _log_task_exception(task: Any) -> None:
    """后台任务异常统一日志（不传播；被取消的 task 静默跳过）."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning("Validation Feedback 事件发布失败: %s", exc)


async def drain_feedback_events(timeout: float = 5.0) -> None:
    """排空 Validation Feedback 后台发布任务（CR-R3-4 统一治理——与
    drain_schema_events 共用 drain_background_tasks 参数化实现）.

    在 graceful shutdown / 测试 fixture teardown 时调用——含跨 loop stale
    task 引用清理（pytest 每测试新 loop 形态下防 set 滞留）。

    Args:
        timeout: 等待超时秒数（默认 5.0）
    """
    from src.application.services.schema_event_helpers import drain_background_tasks

    await drain_background_tasks(_background_tasks, timeout=timeout, op_name="drain_feedback_events")


def _chain_contains_llm_transient(exc: BaseException) -> bool:
    """异常因果链上任一节点属 LLM 瞬时族（R10-2 谓词：链中 last_exc ∈ 白名单同集）.

    仅遍历**显式因果链**（自定义 cause 属性 + ``raise ... from`` 的 __cause__），
    刻意不遍历 ``__context__`` 隐式链（R1-F2）：recover 在 VFD except 块内被
    await 时，期间 raise 的任何内层异常其 __context__ 都回指触发异常——389-LLM
    触发场景下经该通道会扫到触发链自身的 LLM 节点，非 LLM 根因的 attempt 失败
    被误判为 LLM 瞬时（#17② 误直传、该标的 INFEASIBLE 被放走）。生产链全程
    显式（引擎 382 ``cause=``、TOV ``raise ... from``、383 ``cause=last_exc``），
    弃用 __context__ 不丢真信号。与 extract_stderr_from_cause_chain 的三通道
    宽容语义不对称是刻意的：stderr 提取误报代价低（多提取一段文本），根因判定
    误报代价高（终态语义反转）。
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, _LLM_TRANSIENT_ROOTS):
            return True
        current = getattr(current, "cause", None) or current.__cause__
    return False


class ValidationFeedbackService(ValidationFeedbackServicePort):
    """Validation Feedback 闭环编排服务（增强重试与不可行标记）."""

    ENHANCED_MAX_ATTEMPTS = 3

    def __init__(
        self,
        llm_client: LLMClientPort,
        error_case_repository: ErrorCaseRepositoryPort,
        evolution_log_repository: EvolutionLogRepositoryPort,
        event_publisher: EventPublisher | None,
        engine: Any,
        inner_chain: Any,
    ) -> None:
        """初始化服务（双句柄注入——SSOT 表行为准）.

        Args:
            llm_client: LLM 客户端端口（fix-gen 用）
            error_case_repository: 错误案例库端口
            evolution_log_repository: 演进日志端口
            event_publisher: 事件发布端口（None 跳过事件）
            engine: 裸引擎引用（防放大封顶策略的 replace 派生基线——只读）
            inner_chain: 重执行用完整内层链（SSD>TOV>Engine）
        """
        self._llm = llm_client
        self._cases = error_case_repository
        self._logs = evolution_log_repository
        self._publisher = event_publisher
        self._engine = engine
        self._inner_chain = inner_chain
        self._extractor = ErrorSignatureExtractor()

    # ---- 触发判定（九行矩阵前 3 行——其余行「不捕获自然上浮」由装饰器层实现）----

    @staticmethod
    def should_enter_feedback_loop(trigger_error: BaseException) -> bool:
        """入环谓词（R8-4 九行矩阵的入环两行）.

        Args:
            trigger_error: 触发异常

        Returns:
            389（两子路径）或 382-EXECUTION 且 cause ∈ ExecutionError 族 → True
        """
        from src.domain.exceptions import ExecutionError

        if isinstance(trigger_error, ToolResultValidationError):
            return True
        if isinstance(trigger_error, ToolExecutionFailedError):
            if trigger_error.context.get("stage") == "EXECUTION":
                return isinstance(trigger_error.cause, ExecutionError)
            return False
        return False

    # ---- 主入口 ----

    async def recover(
        self,
        tool_id: uuid_module.UUID,
        tool: Any,
        tool_call: Any,
        context: Any,
        trigger_error: Exception,
    ) -> ToolResult:
        """执行完整反馈闭环（编排蓝图见模块 docstring）."""
        start_time = time.monotonic()
        # execution_id 入口一次性 UUID 归一（R1-F11）：畸形串按无 id 处理——统一
        # 短路查询与终态落库两处行为，消除「查询侧有守卫、落库侧裸 UUID() 抛
        # ValueError 逃逸」的防御不一致
        raw_execution_id = str(getattr(trigger_error, "context", {}).get("execution_id", "") or "")
        try:
            execution_uuid = uuid_module.UUID(raw_execution_id) if raw_execution_id else None
        except ValueError:
            execution_uuid = None
        execution_id = str(execution_uuid) if execution_uuid is not None else ""
        tenant_id = getattr(context, "tenant_id")

        # 1. 幂等短路（同 execution 已有**终态** → 副作用去重 + 合成结论 + 观测计数）。
        # 短路条件收窄（技术债清偿 A 类）：ABORTED 行是中止遥测非终态结论——
        # 中止后重放应全量重跑（与 #17② 零终态路径同理——R9-17 期望行为），
        # 重跑成功/耗尽后 save 按 execution_id upsert 覆盖中止行
        if execution_uuid is not None:
            existing = await self._logs.get_by_execution(execution_uuid, tenant_id)
            if existing is not None and existing.final_status != FeedbackOutcome.ABORTED:
                return await self._replay_synthetic(existing, tool_id, tenant_id)

        # 2. 错误上下文提取 + 签名
        stderr, violations, trigger_code, error_category = self._extract_error_context(trigger_error)
        if violations:
            signature = self._extractor.extract_from_violations(violations)
        elif stderr:
            signature = self._extractor.extract(stderr)
        else:
            # 389-LLM 子路径：violations/stderr 双空——签名走触发异常消息归一化
            signature = self._extractor.extract(str(trigger_error))

        # 3. 增强循环 attempt 1..3
        attempts: list[FixAttempt] = []
        attempt_failures: list[BaseException | None] = []
        prior_summaries: list[dict[str, Any]] = []
        final_stderr = stderr
        for attempt_no in range(1, self.ENHANCED_MAX_ATTEMPTS + 1):
            # a. 案例查询 + 五格分类
            case = await self._cases.get_by_natural_key(tenant_id, tool_id, signature)
            strategy, case_summaries, negative_hint = self._classify_case(case, error_category)

            # b. fix-gen（修复建议生成）
            fix_prompt = build_fix_prompt(
                tool_name=getattr(tool, "name", str(tool_id)),
                stderr_excerpt=final_stderr,
                schema_violations=list(violations),
                case_summaries=case_summaries,
                negative_hint=negative_hint,
                prior_attempts=prior_summaries,
                tool_call_arguments=getattr(tool_call, "arguments", None),
            )
            try:
                response = await _call_with_retry(
                    lambda: self._llm.generate(prompt=fix_prompt, system_prompt=FIX_SYSTEM_PROMPT),
                    RetryPolicy(max_attempts=1),
                    op_name="validation_feedback_fix_gen",
                )
                suggested_fix = str(getattr(response, "content", "") or "")
            except Exception as exc:
                # 非白名单异常同样计为该次 attempt 失败（R2-10 收敛——防裸穿打破
                # INFEASIBLE 不抛契约），detail 区分类型
                detail = (
                    "llm_generation_failed"
                    if _chain_contains_llm_transient(exc)
                    else f"fix_generation_failed:{type(exc).__name__}"
                )
                attempts.append(
                    FixAttempt(
                        attempt_no=attempt_no,
                        error_signature=signature,
                        fix_strategy=strategy,
                        succeeded=False,
                        detail=detail,
                        stderr_excerpt=_excerpt(final_stderr),
                        suggested_fix_excerpt="",
                    )
                )
                attempt_failures.append(exc)
                prior_summaries.append(
                    {"attempt_no": attempt_no, "detail": detail, "stderr_excerpt": "", "suggested_fix_excerpt": ""}
                )
                continue

            # c/d/e. hints 注入 + 防放大 + 重执行（经 inner_chain）
            attempt_execution_id = str(uuid_module.uuid4())
            # 负样本提示并入引擎侧 case_summaries（R1-F6：Subtask 0.12「Think stage
            # 消费 case_summaries（含负样本提示）」的生产者侧兑现——引擎 Think
            # prompt 仅读该键）。fix-gen prompt 的 case_summaries 参数仍传原值
            # （该参数渲染在「历史成功修复案例」标题下，负样本提示混入属语义
            # 错标；fix-gen 经独立 negative_hint 参数渲染）
            engine_case_summaries = case_summaries + (
                [negative_hint] if strategy == FixStrategy.NEGATIVE_CASE_GUIDED and negative_hint else []
            )
            hints = {
                "stderr_excerpt": _excerpt(final_stderr),
                "schema_violations": list(violations),
                "case_summaries": engine_case_summaries,
                "prior_attempts": list(prior_summaries),
                "suggested_fix": suggested_fix,
            }
            hints_context = context.with_extension("validation_feedback_hints", hints)
            hints_context = hints_context.with_extension("schema_execution_id", uuid_module.UUID(attempt_execution_id))

            # 防放大（R1-F3 ContextVar 形态）：封顶策略由引擎原策略 dataclasses.replace
            # 派生（保留 retryable_exceptions/backoff/duration 全部字段——旧形态
            # RetryPolicy(max_attempts=1, ...) 会把 backoff/duration 重置为默认值），
            # 经 per-task ContextVar 覆盖生效——共享引擎状态零写入，并发 recover
            # 互不污染（旧「保存→整体替换→finally 按引用恢复」在进程级共享引擎上
            # 存在交错恢复致 max_attempts 永久=1 的竞态）
            original_retry = getattr(self._engine, "_retry", None)
            capped_retry = replace(original_retry, max_attempts=1) if isinstance(original_retry, RetryPolicy) else None
            try:
                if capped_retry is not None:
                    with retry_policy_override(capped_retry):
                        result = await self._inner_chain.execute(tool_id, tool, tool_call, hints_context)
                else:
                    result = await self._inner_chain.execute(tool_id, tool, tool_call, hints_context)
                # 成功 → 回填 + 事件 + 日志(RECOVERED) + 返回
                attempt = FixAttempt(
                    attempt_no=attempt_no,
                    attempt_execution_id=attempt_execution_id,
                    error_signature=signature,
                    fix_strategy=strategy,
                    stderr_excerpt=_excerpt(final_stderr),
                    suggested_fix_excerpt=_excerpt(suggested_fix),
                    succeeded=True,
                    detail="recovered",
                )
                attempts.append(attempt)
                await self._finish_recovered(
                    tool_id=tool_id,
                    tool=tool,
                    tenant_id=tenant_id,
                    execution_uuid=execution_uuid,
                    signature=signature,
                    trigger_code=trigger_code,
                    error_category=error_category,
                    stderr=final_stderr,
                    attempts=attempts,
                    start_time=start_time,
                    suggested_fix=suggested_fix,
                )
                return ToolResult(
                    tool_id=tool_id,
                    status=ToolResultStatus.SUCCESS,
                    output=result.output,
                    evidence_package=result.evidence_package,
                    retry_count=attempt_no,
                )
            except Exception as exc:
                # mid-attempt 分类（R9-13 对称立法——与触发面九行完全同构）
                if self.should_enter_feedback_loop(exc):
                    # 计为该次 attempt 失败（detail=retry_failed），提取该次 stderr 反馈
                    # + 该次新 schema violations（CR-R1-22 清偿：mid-attempt 389 的
                    # 违规详情不再丢弃——进 FixAttempt 与跨尝试反馈通道）
                    attempt_stderr = extract_stderr_from_cause_chain(exc)
                    attempt_violation_ctx = getattr(exc, "context", {}) or {}
                    attempt_stderr = attempt_stderr or str(attempt_violation_ctx.get("reason", ""))
                    attempt_violations = tuple(attempt_violation_ctx.get("schema_violations", ()) or ())
                    attempts.append(
                        FixAttempt(
                            attempt_no=attempt_no,
                            attempt_execution_id=attempt_execution_id,
                            error_signature=signature,
                            fix_strategy=strategy,
                            stderr_excerpt=_excerpt(attempt_stderr),
                            suggested_fix_excerpt=_excerpt(suggested_fix),
                            violations_excerpt=attempt_violations,
                            succeeded=False,
                            detail="retry_failed",
                        )
                    )
                    attempt_failures.append(exc)
                    prior_summaries.append(
                        {
                            "attempt_no": attempt_no,
                            "detail": "retry_failed",
                            "stderr_excerpt": _excerpt(attempt_stderr),
                            "suggested_fix_excerpt": _excerpt(suggested_fix),
                            "violations_excerpt": list(attempt_violations[:3]),
                        }
                    )
                    if attempt_stderr:
                        final_stderr = attempt_stderr
                    continue
                # 不满足入环谓词 → 中止闭环直传（技术债清偿 A 类：重开 R3-3 的
                # 中止半边——写 ABORTED 中止遥测行后直传原异常；不回填案例库、
                # 不发事件、重放不短路（短路条件已收窄为终态行））
                await self._finish_aborted(
                    tool_id=tool_id,
                    tenant_id=tenant_id,
                    execution_uuid=execution_uuid,
                    signature=signature,
                    trigger_code=trigger_code,
                    attempts=attempts,
                    start_time=start_time,
                    tool=tool,
                )
                raise

        # 4. #17②：全 attempt 失败且各次根因均为 LLM 瞬时 → 直传原触发（零观测副作用）
        if self._all_attempts_llm_transient(attempts, attempt_failures):
            raise trigger_error

        # 5. 耗尽 → 399 内部信号 → 转换 INFEASIBLE（对外不抛）
        last_failure = attempt_failures[-1] if attempt_failures else trigger_error
        exhausted = ValidationFeedbackRetryExhaustedError(
            execution_id=execution_id or None,
            tool_id=str(tool_id),
            enhanced_retry_count=self.ENHANCED_MAX_ATTEMPTS,
            error_signature=signature,
            cause=last_failure if isinstance(last_failure, Exception) else None,
        )
        return await self._finish_infeasible(
            tool_id=tool_id,
            tenant_id=tenant_id,
            execution_uuid=execution_uuid,
            signature=signature,
            trigger_code=trigger_code,
            error_category=error_category,
            stderr=final_stderr,
            attempts=attempts,
            start_time=start_time,
            tool=tool,
            exhausted=exhausted,
        )

    # ---- 内部编排 ----

    def _extract_error_context(self, trigger_error: Exception) -> tuple[str, tuple[dict, ...], TriggerCode, str]:
        """提取错误上下文（STDERR/violations/trigger_code/error_category——R3-9 赋值规则）.

        Returns:
            (stderr, violations, trigger_code, error_category) 四元组
        """
        if isinstance(trigger_error, ToolResultValidationError):
            violations = tuple(trigger_error.context.get("schema_violations", ()) or ())
            stderr = ""
            if violations:
                trigger_code = TriggerCode.EXCEPTION_389
                error_category = "SCHEMA_VIOLATION"
            else:
                # 389-LLM 子路径：cause 链无 STDERR（LLM 错误形态）
                trigger_code = TriggerCode.EXCEPTION_389
                error_category = "LLM_TRANSIENT"
            return stderr, violations, trigger_code, error_category
        # 382-EXECUTION-cause∈ExecutionError 族（入环谓词已保证）
        stderr = extract_stderr_from_cause_chain(trigger_error)
        from src.domain.exceptions import ExecutionError

        cause = getattr(trigger_error, "cause", None)
        error_category = getattr(cause, "code", "EXCEPTION_313") if isinstance(cause, ExecutionError) else "EXCEPTION_313"
        return stderr, (), TriggerCode.EXCEPTION_382, error_category

    def _classify_case(self, case: ErrorCase | None, error_category: str) -> tuple[FixStrategy, list[str], str]:
        """案例五格分类（R9-16 全枚举）.

        Returns:
            (fix_strategy, case_summaries, negative_hint) 三元组
        """
        if case is None:
            return FixStrategy.PURE_LLM, [], ""
        if case.outcome == FeedbackOutcome.RECOVERED:
            if case.fix_summary:
                # 格①：命中 RECOVERED 且配方非空 → CASE_GUIDED
                return FixStrategy.CASE_GUIDED, [case.fix_summary], ""
            # 格④：命中 RECOVERED 但配方空（LLM_TRANSIENT 首例）→ 可观测载体
            # PURE_LLM_NO_RECIPE（CR-R1-24 清偿：原注释升格枚举——演进日志可区分）
            return FixStrategy.PURE_LLM_NO_RECIPE, [], ""
        # MARKED_INFEASIBLE：category 二次过滤（R8-18 升判定前置——over-merging 缓解）
        if case.error_category == error_category:
            # 格②：命中不可行且分类匹配 → 负样本提示（全量 3 次不缩减——R8-2）
            hint = f"此签名已观测到 {case.infeasible_count} 次不可行"
            return FixStrategy.NEGATIVE_CASE_GUIDED, [], hint
        # 格⑤：签名碰撞 + 分类不匹配 → 可观测载体 PURE_LLM_COLLISION（CR-R1-24 清偿）
        return FixStrategy.PURE_LLM_COLLISION, [], ""

    def _all_attempts_llm_transient(self, attempts: list[FixAttempt], failures: list[BaseException | None]) -> bool:
        """#17② 判定：全部 attempt 失败且各次根因均为 LLM 瞬时（根因导向——R9-15/R10-2）."""
        if not attempts:
            return False
        for attempt, failure in zip(attempts, failures, strict=False):
            if failure is None:
                return False
            if attempt.detail == "llm_generation_failed":
                continue  # fix-gen LLM 失败（构造时已判定为 LLM 族）
            if attempt.detail == "retry_failed":
                if not _chain_contains_llm_transient(failure):
                    return False
                continue
            return False
        return True

    async def _finish_recovered(
        self,
        *,
        tool_id: uuid_module.UUID,
        tool: Any,
        tenant_id: Any,
        execution_uuid: uuid_module.UUID | None,
        signature: str,
        trigger_code: TriggerCode,
        error_category: str,
        stderr: str,
        attempts: list[FixAttempt],
        start_time: float,
        suggested_fix: str,
    ) -> None:
        """恢复终态：案例回填 + 演进日志 + 恢复事件.

        duration 在案例回填之后计量（CR-R1-23 清偿——覆盖终态副作用中的回填段；
        物理边界：日志行自身写库与事件发布时长不可计入本行 duration_sec）。"""
        # 回填：recovered_count+1；fix_summary 覆写（仅非 LLM_TRANSIENT——#17①）
        existing = await self._cases.get_by_natural_key(tenant_id, tool_id, signature)
        if error_category == "LLM_TRANSIENT":
            fix_summary = existing.fix_summary if existing is not None else ""
        else:
            # 覆写内容来源（R3-9）：成功 attempt 的 suggested_fix + 错误摘要一句
            error_line = stderr.splitlines()[-1] if stderr else str(error_category)
            fix_summary = _excerpt(f"{suggested_fix}（修复错误：{error_line}）")
        await self._cases.record_case(
            ErrorCase(
                tenant_id=tenant_id,
                tool_id=tool_id,
                error_signature=signature,
                error_category=error_category,
                stderr_excerpt=_excerpt(stderr),
                fix_summary=fix_summary,
                outcome=FeedbackOutcome.RECOVERED,
                recovered_count=1,
                infeasible_count=0,
                occurrence_count=1,
                last_seen_at=_now(),
            )
        )
        # 演进日志（RECOVERED）——duration 含案例回填段（CR-R1-23）
        log_entry = EvolutionLogEntry(
            tenant_id=tenant_id,
            tool_id=tool_id,
            execution_id=execution_uuid or uuid_module.uuid4(),
            trigger_code=trigger_code,
            error_signature=signature,
            enhanced_retry_count=len(attempts),
            fix_attempts=tuple(attempts),
            duration_sec=time.monotonic() - start_time,
            final_status=FeedbackOutcome.RECOVERED,
            tool_version=getattr(tool, "version", "") or "",
        )
        await self._logs.save(log_entry)
        # 恢复事件（主 id 同源）
        _drain_safe_publish(
            self._publisher,
            ToolExecutionRecovered(
                execution_id=log_entry.execution_id,
                tool_id=tool_id,
                tenant_id=tenant_id,
                tool_version=log_entry.tool_version,
                error_signature=signature,
                enhanced_retry_count=len(attempts),
            ),
        )

    async def _finish_infeasible(
        self,
        *,
        tool_id: uuid_module.UUID,
        tenant_id: Any,
        execution_uuid: uuid_module.UUID | None,
        signature: str,
        trigger_code: TriggerCode,
        error_category: str,
        stderr: str,
        attempts: list[FixAttempt],
        start_time: float,
        tool: Any,
        exhausted: ValidationFeedbackRetryExhaustedError,
    ) -> ToolResult:
        """耗尽终态：399 信号转换 INFEASIBLE + 案例回填 + 演进日志 + 不可行事件.

        duration 在案例回填之后计量（CR-R1-23 清偿——同 _finish_recovered 口径）。"""
        # 回填：infeasible_count+1（fix_summary 不动——repo 端规则）
        await self._cases.record_case(
            ErrorCase(
                tenant_id=tenant_id,
                tool_id=tool_id,
                error_signature=signature,
                error_category=error_category,
                stderr_excerpt=_excerpt(stderr),
                fix_summary="",
                outcome=FeedbackOutcome.MARKED_INFEASIBLE,
                recovered_count=0,
                infeasible_count=1,
                occurrence_count=1,
                last_seen_at=_now(),
            )
        )
        log_entry = EvolutionLogEntry(
            tenant_id=tenant_id,
            tool_id=tool_id,
            execution_id=execution_uuid or uuid_module.uuid4(),
            trigger_code=trigger_code,
            error_signature=signature,
            enhanced_retry_count=len(attempts),
            fix_attempts=tuple(attempts),
            duration_sec=time.monotonic() - start_time,  # 含案例回填段（CR-R1-23）
            final_status=FeedbackOutcome.MARKED_INFEASIBLE,
            tool_version=getattr(tool, "version", "") or "",
        )
        await self._logs.save(log_entry)
        _drain_safe_publish(
            self._publisher,
            ToolExecutionMarkedInfeasible(
                execution_id=log_entry.execution_id,
                tool_id=tool_id,
                tenant_id=tenant_id,
                tool_version=log_entry.tool_version,
                error_signature=signature,
                enhanced_retry_count=len(attempts),
                failure_summary=_excerpt(f"{stderr}\n{exhausted.message}"),
            ),
        )
        return ToolResult(
            tool_id=tool_id,
            status=ToolResultStatus.INFEASIBLE,
            output={
                "error_signature": signature,
                "stderr_excerpt": _excerpt(stderr),
                "enhanced_retry_count": len(attempts),
            },
            retry_count=len(attempts),
        )

    async def _finish_aborted(
        self,
        *,
        tool_id: uuid_module.UUID,
        tenant_id: Any,
        execution_uuid: uuid_module.UUID | None,
        signature: str,
        trigger_code: TriggerCode,
        attempts: list[FixAttempt],
        start_time: float,
        tool: Any,
    ) -> None:
        """中止遥测（技术债清偿 A 类——ABORTED 第三值）：写 ABORTED 演进日志行
        后由调用方直传原异常.

        观测面边界（重开 R3-3 的中止半边）：仅演进日志行（已耗 attempt 遥测不再
        丢弃）；不回填案例库（ErrorCase 域收窄排除 ABORTED）、不发领域事件、
        重放不短路（全量重跑后 upsert 覆盖本行）。
        """
        log_entry = EvolutionLogEntry(
            tenant_id=tenant_id,
            tool_id=tool_id,
            execution_id=execution_uuid or uuid_module.uuid4(),
            trigger_code=trigger_code,
            error_signature=signature,
            enhanced_retry_count=len(attempts),
            fix_attempts=tuple(attempts),
            duration_sec=time.monotonic() - start_time,
            final_status=FeedbackOutcome.ABORTED,
            tool_version=getattr(tool, "version", "") or "",
        )
        await self._logs.save(log_entry)
        logger.info(
            "Validation Feedback 闭环中止（ABORTED 遥测）: execution_id=%s 已耗尝试=%d",
            log_entry.execution_id,
            len(attempts),
        )

    async def _replay_synthetic(self, existing: EvolutionLogEntry, tool_id: uuid_module.UUID, tenant_id: Any) -> ToolResult:
        """幂等短路合成结论（R3-2 定谳：record_case 观测计数同步递增）."""
        if existing.final_status == FeedbackOutcome.RECOVERED:
            # RECOVERED 重放：合成 SUCCESS 摘要 + replayed 标记（无证据包——R8-3 边界）
            # fix_summary 透传既有行（R1-F1）：record_case 对 RECOVERED 取传入值覆写，
            # 传空串会把已沉淀修复配方清空（AC-6 短路路径「不覆写 fix_summary」）
            case = await self._cases.get_by_natural_key(tenant_id, tool_id, existing.error_signature)
            replay_fix_summary = case.fix_summary if case is not None else ""
            await self._cases.record_case(
                ErrorCase(
                    tenant_id=tenant_id,
                    tool_id=tool_id,
                    error_signature=existing.error_signature,
                    error_category="LLM_TRANSIENT",  # category 仅占位（首写定格——已有行不受影响）
                    fix_summary=replay_fix_summary,
                    outcome=FeedbackOutcome.RECOVERED,
                    recovered_count=1,
                    infeasible_count=0,
                    occurrence_count=1,
                    last_seen_at=_now(),
                )
            )
            return ToolResult(
                tool_id=tool_id,
                status=ToolResultStatus.SUCCESS,
                output={
                    "replayed": True,
                    "error_signature": existing.error_signature,
                    "enhanced_retry_count": existing.enhanced_retry_count,
                },
                retry_count=existing.enhanced_retry_count,
            )
        # INFEASIBLE 重放：合成结论（无 replayed 标记——R9-18 不对称登记）
        await self._cases.record_case(
            ErrorCase(
                tenant_id=tenant_id,
                tool_id=tool_id,
                error_signature=existing.error_signature,
                error_category="LLM_TRANSIENT",  # 占位同上
                fix_summary="",
                outcome=FeedbackOutcome.MARKED_INFEASIBLE,
                recovered_count=0,
                infeasible_count=1,
                occurrence_count=1,
                last_seen_at=_now(),
            )
        )
        return ToolResult(
            tool_id=tool_id,
            status=ToolResultStatus.INFEASIBLE,
            output={
                "error_signature": existing.error_signature,
                "stderr_excerpt": "",
                "enhanced_retry_count": existing.enhanced_retry_count,
            },
            retry_count=existing.enhanced_retry_count,
        )


def _excerpt(text: str, limit: int = 2000) -> str:
    """摘录截断（统一口径 ≤2000）."""
    return (text or "")[:limit]


def _now():
    """当前 UTC 时间（timezone-aware）."""
    from datetime import UTC, datetime

    return datetime.now(UTC)


# ============================================================================
# 组合根链构造工厂（R10-3 落点：「组合根零私有函数」纪律——组装逻辑归域模块，
# 组合根一行委托；build_tool_execution_engine 先例同款）
# ============================================================================


def build_inner_execution_chain(resolver: Any, *, max_concurrent_containers: int) -> tuple[Any, Any]:
    """组装内层执行链 SSD > TOV > Engine（重执行用——validation_feedback 双句柄之一）.

    Args:
        resolver: 组合根 resolver（Any 注入——避免 application 层反向依赖组合根）
        max_concurrent_containers: 沙箱并发配额（组合根解析配置后传入——分层红线）

    Returns:
        (ssd_chain, engine) 二元组——engine 为链内最内层引擎实例
        （SCOPED 生命周期下与 resolver.resolve("tool_execution_engine") 同实例）
    """
    from src.application.services.sandbox_security_decorator import SandboxSecurityDecorator
    from src.application.services.tool_output_validator import ToolOutputValidator

    engine = resolver.resolve("tool_execution_engine")
    tov = ToolOutputValidator(
        wrapped=engine,
        schema_validator=resolver.resolve("schema_validator"),
        event_publisher=resolver.resolve("event_publisher"),
    )
    ssd = SandboxSecurityDecorator(
        wrapped=tov,
        sandbox=resolver.resolve("sandbox_executor"),
        session_repo=resolver.resolve("sandbox_session_repository"),
        event_publisher=resolver.resolve("event_publisher"),
        max_concurrent_containers=max_concurrent_containers,
    )
    return ssd, engine


class _ChainBundle(tuple):
    """链构造产物三元组（outer/service/engine）——具名访问轻量形态."""

    @property
    def outer(self) -> Any:
        """装饰链最外层（VFD）——tool_execution_service 的 engine 注入位."""
        return self[0]

    @property
    def service(self) -> "ValidationFeedbackService":
        """反馈闭环服务（validation_feedback_service 端口产物）."""
        from typing import cast

        return cast("ValidationFeedbackService", self[1])

    @property
    def engine(self) -> Any:
        """链内最内层引擎（双句柄之一——防放大封顶用）."""
        return self[2]


def build_tool_execution_chain(resolver: Any, *, max_concurrent_containers: int) -> _ChainBundle:
    """组装完整装饰链 VFD > SSD > TOV > Engine + 反馈服务（Story 4.7 装配）.

    双句柄定稿（R9-14）：service 持有 engine 引用（封顶用）与 inner_chain
    （重执行用＝SSD>TOV>Engine 完整内层链）——重执行禁走裸引擎（绕过 SSD
    安全防护与 TOV 出参校验会把违规 output 标 RECOVERED）。

    Args:
        resolver: 组合根 resolver
        max_concurrent_containers: 沙箱并发配额（组合根解析后传入）

    Returns:
        _ChainBundle(outer=VFD, service=ValidationFeedbackService, engine=引擎)
    """
    from src.application.services.validation_feedback_decorator import ValidationFeedbackDecorator

    ssd, engine = build_inner_execution_chain(resolver, max_concurrent_containers=max_concurrent_containers)
    service = ValidationFeedbackService(
        llm_client=resolver.resolve("llm_client"),
        error_case_repository=resolver.resolve("error_case_repository"),
        evolution_log_repository=resolver.resolve("evolution_log_repository"),
        event_publisher=resolver.resolve("event_publisher"),
        engine=engine,
        inner_chain=ssd,
    )
    return _ChainBundle(
        (
            ValidationFeedbackDecorator(wrapped=ssd, feedback_service=service),
            service,
            engine,
        )
    )


__all__ = [
    "ValidationFeedbackService",
    "build_inner_execution_chain",
    "build_tool_execution_chain",
    "build_validation_feedback_service",
]


def build_validation_feedback_service(resolver: Any, *, max_concurrent_containers: int) -> "ValidationFeedbackService":
    """组装反馈闭环服务（validation_feedback_service 端口产物——组合根一行委托）.

    技术债清偿（CR-R1-28/M4）：委托 build_tool_execution_chain 取 .service——
    消除与链内构造块的逐字重复（service 构造唯一 SSOT 在链工厂）；副作用为
    多构建一个 outer VFD 装饰对象（SCOPED 下双链实例形态不变）。

    Args:
        resolver: 组合根 resolver
        max_concurrent_containers: 沙箱并发配额

    Returns:
        ValidationFeedbackService 实例
    """
    return build_tool_execution_chain(resolver, max_concurrent_containers=max_concurrent_containers).service
