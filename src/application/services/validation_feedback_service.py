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
   c. hints 注入（validation_feedback_hints 扩展键——P0-D 模式）
   d. 防放大：engine._retry 整体替换 max_attempts=1（保留原 retryable_exceptions）
      → try/finally 按引用恢复（TOV 校验重试动态读 engine._retry 同被封顶）
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
from typing import Any

from src.application.ports.validation_feedback_service import ValidationFeedbackServicePort
from src.application.services.retry_helpers import RetryPolicy, _call_with_retry
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


def _drain_safe_publish(publisher: EventPublisher | None, event: Any) -> None:
    """fire-and-forget 事件发布（P0-I 模式——不阻塞主流程，异常仅日志）."""
    if publisher is None:
        return

    async def _publish() -> None:
        await publisher.publish(event)

    import asyncio

    task = asyncio.create_task(_publish())
    task.add_done_callback(_log_task_exception)


def _log_task_exception(task: Any) -> None:
    """后台任务异常统一日志（不传播）。"""
    exc = task.exception()
    if exc is not None:
        logger.warning("Validation Feedback 事件发布失败: %s", exc)


def _root_cause(exc: BaseException) -> BaseException:
    """沿异常因果链取根因叶子（自定义 cause 属性与 __cause__/__context__ 双通道）."""
    seen: set[int] = set()
    current: BaseException = exc
    while id(current) not in seen:
        seen.add(id(current))
        nxt = getattr(current, "cause", None) or current.__cause__ or current.__context__
        if nxt is None:
            return current
        current = nxt
    return current


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
            engine: 裸引擎引用（防放大封顶 engine._retry 用）
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
        execution_id = str(getattr(trigger_error, "context", {}).get("execution_id", "") or "")
        tenant_id = getattr(context, "tenant_id")
        assert isinstance(tenant_id, uuid_module.UUID), "context.tenant_id 必须为 UUID"

        # 1. 幂等短路（同 execution 已有终态 → 副作用去重 + 合成结论 + 观测计数）
        if execution_id:
            try:
                existing = await self._logs.get_by_execution(uuid_module.UUID(execution_id), tenant_id)
            except (ValueError, TypeError):
                existing = None
            if existing is not None:
                return await self._replay_synthetic(existing, tool_id, tenant_id)

        # 2. 错误上下文提取 + 签名
        stderr, violations, trigger_code, error_category = self._extract_error_context(trigger_error)
        self._current_trigger_code = trigger_code
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
                root = _root_cause(exc)
                detail = (
                    "llm_generation_failed"
                    if isinstance(root, _LLM_TRANSIENT_ROOTS)
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
            hints = {
                "stderr_excerpt": _excerpt(final_stderr),
                "schema_violations": list(violations),
                "case_summaries": case_summaries,
                "prior_attempts": list(prior_summaries),
                "suggested_fix": suggested_fix,
            }
            hints_context = context.with_extension("validation_feedback_hints", hints)
            hints_context = hints_context.with_extension("schema_execution_id", uuid_module.UUID(attempt_execution_id))

            original_retry = getattr(self._engine, "_retry", None)
            if original_retry is not None:
                self._engine._retry = RetryPolicy(
                    max_attempts=1,
                    retryable_exceptions=original_retry.retryable_exceptions,
                )
            try:
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
                duration = time.monotonic() - start_time
                await self._finish_recovered(
                    tool_id=tool_id,
                    tool=tool,
                    tenant_id=tenant_id,
                    execution_id=execution_id,
                    signature=signature,
                    error_category=error_category,
                    stderr=final_stderr,
                    attempts=attempts,
                    duration_sec=duration,
                    suggested_fix=suggested_fix,
                    context=context,
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
                    attempt_stderr = extract_stderr_from_cause_chain(exc)
                    attempt_violation_ctx = getattr(exc, "context", {}) or {}
                    attempt_stderr = attempt_stderr or str(attempt_violation_ctx.get("reason", ""))
                    attempts.append(
                        FixAttempt(
                            attempt_no=attempt_no,
                            attempt_execution_id=attempt_execution_id,
                            error_signature=signature,
                            fix_strategy=strategy,
                            stderr_excerpt=_excerpt(attempt_stderr),
                            suggested_fix_excerpt=_excerpt(suggested_fix),
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
                        }
                    )
                    if attempt_stderr:
                        final_stderr = attempt_stderr
                    continue
                # 不满足入环谓词 → 中止闭环直传（零观测副作用——R3-3）
                raise
            finally:
                if original_retry is not None:
                    self._engine._retry = original_retry

        # 4. #17②：全 attempt 失败且各次根因均为 LLM 瞬时 → 直传原触发（零观测副作用）
        if self._all_attempts_llm_transient(attempts, attempt_failures):
            raise trigger_error

        # 5. 耗尽 → 399 内部信号 → 转换 INFEASIBLE（对外不抛）
        duration = time.monotonic() - start_time
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
            execution_id=execution_id,
            signature=signature,
            error_category=error_category,
            stderr=final_stderr,
            attempts=attempts,
            duration_sec=duration,
            tool=tool,
            exhausted=exhausted,
            context=context,
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
            # 格④：命中 RECOVERED 但配方空（LLM_TRANSIENT 首例）→ PURE_LLM（命中但无可注入配方）
            return FixStrategy.PURE_LLM, [], ""
        # MARKED_INFEASIBLE：category 二次过滤（R8-18 升判定前置——over-merging 缓解）
        if case.error_category == error_category:
            # 格②：命中不可行且分类匹配 → 负样本提示（全量 3 次不缩减——R8-2）
            hint = f"此签名已观测到 {case.infeasible_count} 次不可行"
            return FixStrategy.NEGATIVE_CASE_GUIDED, [], hint
        # 格⑤：签名碰撞 + 分类不匹配 → PURE_LLM（碰撞命中已抑制）
        return FixStrategy.PURE_LLM, [], ""

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
                root = _root_cause(failure)
                if not isinstance(root, _LLM_TRANSIENT_ROOTS):
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
        execution_id: str,
        signature: str,
        error_category: str,
        stderr: str,
        attempts: list[FixAttempt],
        duration_sec: float,
        suggested_fix: str,
        context: Any,
    ) -> None:
        """恢复终态：案例回填 + 演进日志 + 恢复事件."""
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
        # 演进日志（RECOVERED）
        log_entry = EvolutionLogEntry(
            tenant_id=tenant_id,
            tool_id=tool_id,
            execution_id=uuid_module.UUID(execution_id) if execution_id else uuid_module.uuid4(),
            trigger_code=self._trigger_code_of(attempts),
            error_signature=signature,
            enhanced_retry_count=len(attempts),
            fix_attempts=tuple(attempts),
            duration_sec=duration_sec,
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
        execution_id: str,
        signature: str,
        error_category: str,
        stderr: str,
        attempts: list[FixAttempt],
        duration_sec: float,
        tool: Any,
        exhausted: ValidationFeedbackRetryExhaustedError,
        context: Any,
    ) -> ToolResult:
        """耗尽终态：399 信号转换 INFEASIBLE + 案例回填 + 演进日志 + 不可行事件."""
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
            execution_id=uuid_module.UUID(execution_id) if execution_id else uuid_module.uuid4(),
            trigger_code=self._trigger_code_of(attempts),
            error_signature=signature,
            enhanced_retry_count=len(attempts),
            fix_attempts=tuple(attempts),
            duration_sec=duration_sec,
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

    async def _replay_synthetic(self, existing: EvolutionLogEntry, tool_id: uuid_module.UUID, tenant_id: Any) -> ToolResult:
        """幂等短路合成结论（R3-2 定谳：record_case 观测计数同步递增）."""
        if existing.final_status == FeedbackOutcome.RECOVERED:
            # RECOVERED 重放：合成 SUCCESS 摘要 + replayed 标记（无证据包——R8-3 边界）
            await self._cases.record_case(
                ErrorCase(
                    tenant_id=tenant_id,
                    tool_id=tool_id,
                    error_signature=existing.error_signature,
                    error_category="LLM_TRANSIENT",  # category 仅占位（首写定格——已有行不受影响）
                    fix_summary="",
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

    def _trigger_code_of(self, attempts: list[FixAttempt]) -> TriggerCode:
        """trigger_code 取提取阶段结果（recover 内经实例属性传递）."""
        return getattr(self, "_current_trigger_code", TriggerCode.EXCEPTION_389)


def _excerpt(text: str, limit: int = 2000) -> str:
    """摘录截断（统一口径 ≤2000）."""
    return (text or "")[:limit]


def _now():
    """当前 UTC 时间（timezone-aware）."""
    from datetime import UTC, datetime

    return datetime.now(UTC)
