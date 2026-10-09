"""Story 4.7: ValidationFeedbackService 闭环编排单元测试.

TDD 三循环（循环 A：触发判定矩阵九行 + attempt 1→3 + 耗尽转换；循环 B：修复
生成/防放大/案例回填；循环 C：幂等短路）。

单测 Mock 纪律：inner_chain/engine 为可编程 stub（AsyncMock 录制），LLM 为
可编程 AsyncMock——按 Mock/Fake/Real 三层策略（单元测试 Mock 端口）。

TDD 红→绿：本文件先于 src/application/services/validation_feedback_service.py
实现（Subtask 5.1）。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.validation_feedback_service import ValidationFeedbackService
from src.domain.exceptions import (
    BusinessRuleViolationError,
    DataSourceError,
    ExecutionError,
    LLMAPIError,
    LLMConfigError,
    TimeoutError,
    ToolExecutionFailedError,
    ToolResultValidationError,
    ToolSchemaMissingError,
    ValidationError,
)
from src.domain.value_objects.tool_execution import ToolResultStatus

_TENANT = uuid.uuid4()
_TOOL = uuid.uuid4()
_SIG = "1" * 64


def _389(violations: list[dict] | None = None, execution_id: str | None = None) -> ToolResultValidationError:
    """构造 389 触发异常（violations=None 填默认；[] 显式空 = LLM 瞬时子路径形态）."""
    if violations is None:
        violations = [{"path": "result", "expected": "^OK_", "message": "'BAD_output' does not match '^OK_'"}]
    return ToolResultValidationError(
        message="exhausted",
        tool_id=str(_TOOL),
        execution_id=execution_id or str(uuid.uuid4()),
        reason="schema",
        schema_violations=violations,
    )


def _382(
    cause: Exception | None = None,
    stage: str = "EXECUTION",
    execution_id: str | None = None,
) -> ToolExecutionFailedError:
    """构造 382 触发异常（默认 cause 为 313）."""
    if cause is None:
        cause = ExecutionError("exec fail", stderr="Traceback ... KeyError: 'data'", exit_code=1)
    return ToolExecutionFailedError(
        execution_id=execution_id or str(uuid.uuid4()),
        tool_id=str(_TOOL),
        stage=stage,
        cause=cause,
    )


def _make_llm(fix_responses: list[Any] | None = None) -> AsyncMock:
    """可编程 LLM（fix-gen 通道）."""
    fix_queue = list(fix_responses or [])
    llm = AsyncMock()

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> Any:
        if system_prompt and system_prompt.startswith("Validation Feedback 修复顾问"):
            if fix_queue:
                item = fix_queue.pop(0)
                if isinstance(item, Exception):
                    raise item
                return AsyncMock(content=str(item))
            return AsyncMock(content="修复建议：将 result 前缀改为 OK_")
        return AsyncMock(content="generic")

    llm.generate = AsyncMock(side_effect=_generate)
    llm.structured_generate = AsyncMock(return_value="generic")
    return llm


def _make_service(
    *,
    llm: AsyncMock | None = None,
    inner_chain: AsyncMock | None = None,
    engine: Any = None,
    cases: Any = None,
    logs: Any = None,
    publisher: Any = None,
) -> tuple[ValidationFeedbackService, dict[str, Any]]:
    """装配被测服务 + 依赖容器.

    默认依赖：InMemory 双仓储 + 可编程 LLM/inner_chain + 生产白名单形态引擎。
    """
    from src.application.services.retry_helpers import RetryPolicy
    from src.infrastructure.storage.inmemory.error_case_repository import InMemoryErrorCaseRepository
    from src.infrastructure.storage.inmemory.evolution_log_repository import (
        InMemoryEvolutionLogRepository,
    )

    llm = llm or _make_llm()
    cases = cases or InMemoryErrorCaseRepository()
    logs = logs or InMemoryEvolutionLogRepository()
    if engine is None:
        engine = AsyncMock()
        engine._retry = RetryPolicy(
            retryable_exceptions=(LLMAPIError, TimeoutError),
            initial_delay_sec=0,
            max_delay_sec=0,
        )
    if inner_chain is None:
        inner_chain = AsyncMock()
    publisher = publisher if publisher is not None else None
    service = ValidationFeedbackService(
        llm_client=llm,
        error_case_repository=cases,
        evolution_log_repository=logs,
        event_publisher=publisher,
        engine=engine,
        inner_chain=inner_chain,
    )
    return service, {"llm": llm, "cases": cases, "logs": logs, "engine": engine, "inner_chain": inner_chain}


# ============================================================================
# 循环 A：触发判定矩阵（九行——R8-4）
# ============================================================================


class TestTriggerMatrixNineRows:
    """触发判定九行：仅 389（两子路径）与 382-EXECUTION-cause∈ExecutionError 族入环."""

    def test_row_1a_389_schema_enters(self) -> None:
        """行 1a：389（Schema 违规子路径——violations 直接在 context）入环."""
        assert ValidationFeedbackService.should_enter_feedback_loop(_389()) is True

    def test_row_1b_389_llm_transient_enters(self) -> None:
        """行 1b：389（LLM 瞬时子路径——cause 链 389←383←LLM）入环."""
        from src.domain.exceptions import ToolExecutionRetryExhaustedError

        retry_exc = ToolExecutionRetryExhaustedError(
            message="exhausted", execution_id="e", tool_id="t", cause=LLMAPIError("503")
        )
        trigger = _389(violations=[])
        try:
            raise trigger from retry_exc
        except ToolResultValidationError as chained:
            assert ValidationFeedbackService.should_enter_feedback_loop(chained) is True

    def test_row_2_382_execution_cause_in_family_enters(self) -> None:
        """行 2：382-EXECUTION 且 cause ∈ ExecutionError 族（313/316/317）入环."""
        assert ValidationFeedbackService.should_enter_feedback_loop(_382()) is True
        from src.domain.exceptions import SandboxResourceLimitExceededError, SandboxTimeoutError

        assert (
            ValidationFeedbackService.should_enter_feedback_loop(
                _382(cause=SandboxTimeoutError("timeout", session_id="s", timeout_sec=1.0))
            )
            is True
        )
        assert (
            ValidationFeedbackService.should_enter_feedback_loop(
                _382(cause=SandboxResourceLimitExceededError("oom", session_id="s", limit_type="mem"))
            )
            is True
        )

    def test_row_3_382_execution_cause_not_in_family_rejected(self) -> None:
        """行 3：382-EXECUTION 且 cause ∉ 族（332/102/103/裸异常——兜底宽捕获混入形态）直传."""
        for cause in (LLMConfigError("missing key"), RuntimeError("engine bug"), KeyError("k")):
            assert ValidationFeedbackService.should_enter_feedback_loop(_382(cause=cause)) is False

    def test_row_4_382_sandbox_start_rejected(self) -> None:
        """行 4：382-SANDBOX_START（312/315）直传."""
        sandbox_start = _382(stage="SANDBOX_START", cause=RuntimeError("pull"))
        assert ValidationFeedbackService.should_enter_feedback_loop(sandbox_start) is False

    def test_row_5_385_rejected(self) -> None:
        """行 5：ToolExecutionTimeoutError（385）直传."""
        from src.domain.exceptions import ToolExecutionTimeoutError

        assert (
            ValidationFeedbackService.should_enter_feedback_loop(
                ToolExecutionTimeoutError(execution_id="e", tool_id="t", elapsed_sec=9.9)
            )
            is False
        )

    def test_row_6_207_rejected(self) -> None:
        """行 6：BusinessRuleViolationError（207）直传."""
        assert ValidationFeedbackService.should_enter_feedback_loop(BusinessRuleViolationError(message="whitelist")) is False

    def test_row_7_201_rejected(self) -> None:
        """行 7：ValidationError（201）直传."""
        assert ValidationFeedbackService.should_enter_feedback_loop(ValidationError(message="marker syntax")) is False

    def test_row_8_410_413_rejected(self) -> None:
        """行 8：DataSourceError 族（410-413）直传."""
        assert ValidationFeedbackService.should_enter_feedback_loop(DataSourceError(message="down")) is False

    def test_row_9_398_rejected(self) -> None:
        """行 9：ToolSchemaMissingError（398）直传（4.3 定义 4.7 消费契约）."""
        assert ValidationFeedbackService.should_enter_feedback_loop(ToolSchemaMissingError(message="missing")) is False


class TestEnhancedAttemptsTotalThree:
    """增强尝试总数 3（总尝试语义非 3+1）+ 耗尽转换."""

    @pytest.mark.asyncio
    async def test_exhaustion_yields_infeasible_with_3_attempts(self) -> None:
        """3 次尝试全失败 → INFEASIBLE 结果 + 演进日志 enhanced_retry_count=3."""
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_382())
        service, deps = _make_service(inner_chain=inner)

        result = await service.recover(
            tool_id=_TOOL,
            tool=AsyncMock(),
            tool_call=AsyncMock(),
            context=_make_ctx(),
            trigger_error=_382(),
        )
        assert result.status == ToolResultStatus.INFEASIBLE
        assert result.retry_count == 3
        # 重执行调用次数 == 3（每次 attempt 一次；fix-gen 成功后才执行）
        assert inner.execute.await_count == 3
        # 演进日志
        from src.domain.ports.evolution_log_repository import EvolutionLogQuery

        logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        assert len(logs) == 1
        assert logs[0].enhanced_retry_count == 3
        assert logs[0].final_status == "MARKED_INFEASIBLE"

    @pytest.mark.asyncio
    async def test_exhaustion_output_carries_failure_summary(self) -> None:
        """INFEASIBLE output 携带 error_signature/stderr 摘要/尝试次数."""
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_382())
        service, _ = _make_service(inner_chain=inner)

        result = await service.recover(
            tool_id=_TOOL,
            tool=AsyncMock(),
            tool_call=AsyncMock(),
            context=_make_ctx(),
            trigger_error=_382(),
        )
        assert result.output["error_signature"]
        assert result.output["enhanced_retry_count"] == 3


def _make_ctx() -> Any:
    """构造执行上下文."""
    from src.domain.value_objects.tool_execution import ExecutionContext

    return ExecutionContext(tenant_id=_TENANT)


async def _drain_tasks() -> None:
    """drain fire-and-forget 事件任务（R3-4——事件次数断言前竞态防护）."""
    for _ in range(50):
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


# ============================================================================
# 循环 B：修复生成 + 防放大 + 案例回填
# ============================================================================


class TestFixPromptAssembly:
    """修复 prompt 组装（CASE_GUIDED/PURE_LLM/负样本/跨尝试反馈——R8-1）."""

    @pytest.mark.asyncio
    async def test_prompt_contains_stderr_and_violations(self) -> None:
        """382 主路径：prompt 含 STDERR；389-Schema：prompt 含 violations."""
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_382())
        service, deps = _make_service(inner_chain=inner)
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_382())
        prompts = [c.kwargs.get("prompt", "") for c in deps["llm"].generate.await_args_list]
        assert prompts
        assert any("KeyError" in p for p in prompts), "prompt 应含 STDERR 摘要"

    @pytest.mark.asyncio
    async def test_prompt_contains_case_fix_summary_case_guided(self) -> None:
        """命中 RECOVERED 案例且 fix_summary 非空 → 注入配方 + strategy=CASE_GUIDED."""
        from src.domain.entities.error_case import ErrorCase
        from src.domain.value_objects.validation_feedback import FeedbackOutcome

        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(inner_chain=inner)
        signature = _violation_signature()
        await deps["cases"].record_case(
            ErrorCase(
                tenant_id=_TENANT,
                tool_id=_TOOL,
                error_signature=signature,
                error_category="SCHEMA_VIOLATION",
                fix_summary="将 result 前缀改为 OK_",
                outcome=FeedbackOutcome.RECOVERED,
                recovered_count=1,
                infeasible_count=0,
                occurrence_count=1,
                last_seen_at=datetime.now(UTC),
            )
        )
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389())
        prompts = [c.kwargs.get("prompt", "") for c in deps["llm"].generate.await_args_list]
        assert any("将 result 前缀改为 OK_" in p for p in prompts)
        await _assert_first_strategy(deps, "CASE_GUIDED")

    @pytest.mark.asyncio
    async def test_prompt_negative_hint_and_full_3_attempts(self) -> None:
        """命中 MARKED_INFEASIBLE 且 category 匹配 → 负样本提示 + 全量 3 次（R8-2）."""
        from src.domain.entities.error_case import ErrorCase
        from src.domain.value_objects.validation_feedback import FeedbackOutcome

        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(inner_chain=inner)
        signature = _violation_signature()
        await deps["cases"].record_case(
            ErrorCase(
                tenant_id=_TENANT,
                tool_id=_TOOL,
                error_signature=signature,
                error_category="SCHEMA_VIOLATION",
                outcome=FeedbackOutcome.MARKED_INFEASIBLE,
                recovered_count=0,
                infeasible_count=2,
                occurrence_count=2,
                last_seen_at=datetime.now(UTC),
            )
        )
        result = await service.recover(
            tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()
        )
        prompts = [c.kwargs.get("prompt", "") for c in deps["llm"].generate.await_args_list]
        assert any("不可行" in p for p in prompts), "负样本提示应注入"
        assert result.retry_count == 3, "全量 3 次不缩减"
        await _assert_first_strategy(deps, "NEGATIVE_CASE_GUIDED")

    @pytest.mark.asyncio
    async def test_no_hit_pure_llm(self) -> None:
        """无命中 → PURE_LLM（无案例注入）."""
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(inner_chain=inner)
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389())
        await _assert_first_strategy(deps, "PURE_LLM")

    @pytest.mark.asyncio
    async def test_recovered_hit_with_empty_fix_summary_pure_llm(self) -> None:
        """格④：命中 RECOVERED 但 fix_summary 空（LLM_TRANSIENT 首例）→ PURE_LLM 无注入."""
        from src.domain.entities.error_case import ErrorCase
        from src.domain.value_objects.validation_feedback import FeedbackOutcome

        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(inner_chain=inner)
        signature = _violation_signature()
        await deps["cases"].record_case(
            ErrorCase(
                tenant_id=_TENANT,
                tool_id=_TOOL,
                error_signature=signature,
                error_category="LLM_TRANSIENT",
                fix_summary="",
                outcome=FeedbackOutcome.RECOVERED,
                recovered_count=1,
                infeasible_count=0,
                occurrence_count=1,
                last_seen_at=datetime.now(UTC),
            )
        )
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389())
        await _assert_first_strategy(deps, "PURE_LLM")

    @pytest.mark.asyncio
    async def test_collision_category_mismatch_suppresses_negative(self) -> None:
        """格⑤：命中 MARKED_INFEASIBLE 但 category 不匹配 → PURE_LLM（碰撞抑制）."""
        from src.domain.entities.error_case import ErrorCase
        from src.domain.value_objects.validation_feedback import FeedbackOutcome

        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(inner_chain=inner)
        signature = _violation_signature()
        await deps["cases"].record_case(
            ErrorCase(
                tenant_id=_TENANT,
                tool_id=_TOOL,
                error_signature=signature,
                error_category="EXCEPTION_313",  # 当前触发分类 SCHEMA_VIOLATION——不匹配
                outcome=FeedbackOutcome.MARKED_INFEASIBLE,
                recovered_count=0,
                infeasible_count=1,
                occurrence_count=1,
                last_seen_at=datetime.now(UTC),
            )
        )
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389())
        prompts = [c.kwargs.get("prompt", "") for c in deps["llm"].generate.await_args_list]
        assert not any("不可行" in p for p in prompts)
        await _assert_first_strategy(deps, "PURE_LLM")

    @pytest.mark.asyncio
    async def test_attempt_k_prompt_carries_prior_attempts_feedback(self) -> None:
        """R8-1：attempt k 的 prompt 含 attempt 1..k-1 的 stderr/detail/suggested_fix
        摘要 + 禁止重复失败方案指令；空方案条目渲染为「未产出方案（生成失败）」不进清单（R9-20）."""
        fix_responses = [LLMAPIError("503"), "方案B：改输出结构", "方案C：换数据源"]
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(llm=_make_llm(fix_responses=fix_responses), inner_chain=inner)
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389())
        prompts = [c.kwargs.get("prompt", "") for c in deps["llm"].generate.await_args_list]
        assert len(prompts) == 3
        # attempt 3 的 prompt 应含 attempt 2 的方案摘要（动作半边）+ 禁止重复指令
        assert any("方案B" in p for p in prompts[1:])
        assert any("禁止重复" in p for p in prompts[1:])


class TestFixGenerationFailure:
    """fix-gen 失败处置（含非白名单异常收敛——R2-10）."""

    @pytest.mark.asyncio
    async def test_fix_gen_llm_failure_counts_attempt_failure(self) -> None:
        """LLM 失败计为该次 attempt 失败（detail=llm_generation_failed）且不重执行."""
        fix_responses = [LLMAPIError("503"), "方案B", "方案C"]
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(llm=_make_llm(fix_responses=fix_responses), inner_chain=inner)
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389())
        from src.domain.ports.evolution_log_repository import EvolutionLogQuery

        logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        attempts = logs[0].fix_attempts
        assert attempts[0].detail == "llm_generation_failed"
        assert attempts[0].attempt_execution_id == ""
        assert len(attempts) == 3
        # fix-gen 失败的 attempt 无重执行：inner 调用数 = 2（attempt 2/3）
        assert inner.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_fix_gen_non_whitelist_failure_converges(self) -> None:
        """非白名单异常（响应构造缺陷）同样计为 attempt 失败（detail 区分类型）——防裸穿."""
        fix_responses = [RuntimeError("malformed response"), "方案B", "方案C"]
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(llm=_make_llm(fix_responses=fix_responses), inner_chain=inner)
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389())
        from src.domain.ports.evolution_log_repository import EvolutionLogQuery

        logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        attempts = logs[0].fix_attempts
        assert attempts[0].detail.startswith("fix_generation_failed")


class TestMidAttemptClassification:
    """mid-attempt 异常分类（R9-13 对称立法——与触发面九行完全同构）."""

    @pytest.mark.asyncio
    async def test_mid_attempt_382_in_family_counts_failure(self) -> None:
        """①浮出 382-cause∈族 → 计为该次 attempt 失败（detail=retry_failed）继续."""
        service, deps = _make_service(inner_chain=AsyncMock(execute=AsyncMock(side_effect=_382())))
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389())
        from src.domain.ports.evolution_log_repository import EvolutionLogQuery

        logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        assert logs[0].fix_attempts[0].detail == "retry_failed"

    @pytest.mark.asyncio
    async def test_mid_attempt_infra_failure_aborts_and_reraises(self) -> None:
        """②浮出不满足入环谓词的异常（StorageError 形态 382-cause∉族）→ 中止直传零观测副作用."""
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_382(cause=RuntimeError("disk full")))
        service, deps = _make_service(inner_chain=inner)
        with pytest.raises(ToolExecutionFailedError):
            await service.recover(
                tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()
            )
        from src.domain.ports.evolution_log_repository import EvolutionLogQuery

        logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        assert not logs, "中止路径零观测副作用"

    @pytest.mark.asyncio
    async def test_mid_attempt_201_aborts_and_reraises(self) -> None:
        """②abort 构造：浮出 201（LLM code 产物含裸 $）→ 中止直传."""
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=ValidationError(message="marker syntax"))
        service, _ = _make_service(inner_chain=inner)
        with pytest.raises(ValidationError):
            await service.recover(
                tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()
            )


class TestLlmPersistentDirectRaise:
    """#17②：3 attempt 全失败且各次根因均为 LLM 瞬时 → 直传原触发（零观测副作用）."""

    @pytest.mark.asyncio
    async def test_all_fix_gen_llm_api_failures_reraise_original(self) -> None:
        """fix-gen 三连 LLMAPIError → 直传原 389 不标 INFEASIBLE."""
        fix_responses = [LLMAPIError("503")] * 3
        service, deps = _make_service(llm=_make_llm(fix_responses=fix_responses), inner_chain=AsyncMock())
        with pytest.raises(ToolResultValidationError):
            await service.recover(
                tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()
            )
        from src.domain.ports.evolution_log_repository import EvolutionLogQuery

        logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        assert not logs

    @pytest.mark.asyncio
    async def test_all_fix_gen_timeout_failures_reraise_original(self) -> None:
        """TimeoutError 形态（R10-2 谓词集成员——LLM 网络超时）同样直传."""
        fix_responses = [TimeoutError("net timeout")] * 3
        service, _ = _make_service(llm=_make_llm(fix_responses=fix_responses), inner_chain=AsyncMock())
        with pytest.raises(ToolResultValidationError):
            await service.recover(
                tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()
            )

    @pytest.mark.asyncio
    async def test_mixed_failure_roots_mark_infeasible(self) -> None:
        """混合根因（fix-gen 失败 + 重执行失败）→ 正常标记 INFEASIBLE."""
        fix_responses = [LLMAPIError("503"), "方案B", "方案C"]
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_382())
        service, _ = _make_service(llm=_make_llm(fix_responses=fix_responses), inner_chain=inner)
        result = await service.recover(
            tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()
        )
        assert result.status == ToolResultStatus.INFEASIBLE

    @pytest.mark.asyncio
    async def test_retry_failed_with_llm_root_all_three_reraises(self) -> None:
        """重执行 retry_failed 且根因全 LLM 瞬时（389←383←LLM 链）→ 直传（R9-15 根因导向）."""
        from src.domain.exceptions import ToolExecutionRetryExhaustedError

        def _llm_chain_389() -> ToolResultValidationError:
            retry_exc = ToolExecutionRetryExhaustedError(
                message="exhausted", execution_id="e", tool_id="t", cause=LLMAPIError("429")
            )
            trigger = _389(violations=[])
            try:
                raise trigger from retry_exc
            except ToolResultValidationError as chained:
                return chained

        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_llm_chain_389())
        service, _ = _make_service(inner_chain=inner)
        with pytest.raises(ToolResultValidationError):
            await service.recover(
                tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()
            )


class TestAmplificationGuard:
    """防放大（R1-F3 ContextVar 形态）：窗口内 effective 封顶 1 + 白名单保持 + 引擎零触碰."""

    @pytest.mark.asyncio
    async def test_engine_retry_capped_and_restored_by_reference(self) -> None:
        """封顶窗口内 effective_retry_policy(engine._retry).max_attempts==1（白名单保持）；
        窗口外覆盖清零；engine._retry 全程未被触碰（共享状态零写入——并发安全形态）."""
        from src.application.services.retry_helpers import RetryPolicy, effective_retry_policy

        original = RetryPolicy(
            retryable_exceptions=(LLMAPIError, TimeoutError), initial_delay_sec=0, max_delay_sec=0, max_attempts=3
        )
        engine = AsyncMock()
        engine._retry = original
        observed: list[RetryPolicy] = []
        outside_window: list[RetryPolicy] = []

        async def _inner_execute(*args: Any, **kwargs: Any) -> Any:
            observed.append(effective_retry_policy(engine._retry))
            raise _382()

        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_inner_execute)
        service, _ = _make_service(engine=engine, inner_chain=inner)
        outside_window.append(effective_retry_policy(engine._retry))
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_382())
        outside_window.append(effective_retry_policy(engine._retry))
        assert observed, "重执行应发生"
        for policy in observed:
            assert policy.max_attempts == 1, "封顶窗口内 effective max_attempts 应为 1"
            assert policy.retryable_exceptions == (LLMAPIError, TimeoutError), "原白名单保持"
        for policy in outside_window:
            assert policy is original, "窗口外无覆盖（recover 前后读到的都是基础策略原对象）"
        assert engine._retry is original, "engine._retry 全程未被触碰（ContextVar 零共享写入）"

    @pytest.mark.asyncio
    async def test_concurrent_recover_no_engine_pollution(self) -> None:
        """并发双 recover（真实 TOV 包录制引擎——TOV/服务双侧写迁移的并发回归，
        R1-F3）结束后引擎策略零污染、窗口内各自 effective 封顶互不串扰."""
        import asyncio

        from src.application.ports.schema_validator import SchemaValidatorPort
        from src.application.services.retry_helpers import RetryPolicy, effective_retry_policy
        from src.application.services.tool_output_validator import ToolOutputValidator
        from src.application.services.validation_feedback_service import ValidationFeedbackService
        from src.domain.value_objects.tool_execution import ToolResult, ToolResultStatus
        from src.infrastructure.storage.inmemory.error_case_repository import InMemoryErrorCaseRepository
        from src.infrastructure.storage.inmemory.evolution_log_repository import InMemoryEvolutionLogRepository

        original = RetryPolicy(max_attempts=3, initial_delay_sec=0, max_delay_sec=0)
        observed: list[RetryPolicy] = []

        class _RecordingEngine:
            """录制引擎：记录调用时刻的 effective 策略并返回成功结果."""

            def __init__(self) -> None:
                self._retry = original

            async def execute(self, *args: Any, **kwargs: Any) -> ToolResult:
                observed.append(effective_retry_policy(self._retry))
                await asyncio.sleep(0)  # 制造两个 recover 的交错窗口
                return ToolResult(tool_id=_TOOL, status=ToolResultStatus.SUCCESS, output={"plan": "p", "result": "OK_x"})

        engine = _RecordingEngine()
        schema_validator = MagicMock(spec=SchemaValidatorPort)
        schema_validator.validate_output.return_value = MagicMock(is_valid=True, violations=())
        inner_chain = ToolOutputValidator(wrapped=engine, schema_validator=schema_validator)
        service = ValidationFeedbackService(
            llm_client=_make_llm(fix_responses=["方案A", "方案B"]),
            error_case_repository=InMemoryErrorCaseRepository(),
            evolution_log_repository=InMemoryEvolutionLogRepository(),
            event_publisher=None,
            engine=engine,
            inner_chain=inner_chain,
        )
        results = await asyncio.gather(
            service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()),
            service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()),
        )
        assert all(r.status == ToolResultStatus.SUCCESS for r in results)
        assert len(observed) == 2, "两次重执行各自到达引擎"
        for policy in observed:
            assert policy.max_attempts == 1, "窗口内 effective 封顶 1（并发下各自生效）"
            assert policy.retryable_exceptions == original.retryable_exceptions, "白名单保持"
        assert engine._retry is original, "并发 recover 结束后引擎策略对象未被替换"
        assert engine._retry.max_attempts == 3, "无永久封顶污染（交错恢复竞态已消除）"


class TestCaseBackfill:
    """案例回填（恢复/耗尽/LLM_TRANSIENT 不覆写——#17①）."""

    @pytest.mark.asyncio
    async def test_recovery_backfills_recovered_and_fix_summary(self) -> None:
        """恢复成功：recovered_count+1 + fix_summary 覆写（suggested_fix 派生）."""
        from src.domain.value_objects.tool_execution import ToolResult, ToolResultStatus

        ok = ToolResult(tool_id=_TOOL, status=ToolResultStatus.SUCCESS, output={"plan": "p", "result": "OK_x"})
        inner = AsyncMock()
        inner.execute = AsyncMock(return_value=ok)
        service, deps = _make_service(inner_chain=inner, llm=_make_llm(fix_responses=["方案：改前缀为 OK_"]))
        result = await service.recover(
            tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()
        )
        assert result.status == ToolResultStatus.SUCCESS
        assert result.retry_count == 1
        signature = _violation_signature()
        case = await deps["cases"].get_by_natural_key(_TENANT, _TOOL, signature)
        assert case is not None
        assert case.recovered_count == 1
        assert "OK_" in case.fix_summary or case.fix_summary, "fix_summary 覆写为成功方案派生"

    @pytest.mark.asyncio
    async def test_exhaustion_backfills_infeasible_keeps_summary(self) -> None:
        """耗尽：infeasible_count+1 且 fix_summary 不动."""
        from src.domain.entities.error_case import ErrorCase
        from src.domain.value_objects.validation_feedback import FeedbackOutcome

        signature = _violation_signature()
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(inner_chain=inner)
        await deps["cases"].record_case(
            ErrorCase(
                tenant_id=_TENANT,
                tool_id=_TOOL,
                error_signature=signature,
                error_category="SCHEMA_VIOLATION",
                fix_summary="历史配方",
                outcome=FeedbackOutcome.RECOVERED,
                recovered_count=1,
                infeasible_count=0,
                occurrence_count=1,
                last_seen_at=datetime.now(UTC),
            )
        )
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389())
        case = await deps["cases"].get_by_natural_key(_TENANT, _TOOL, signature)
        assert case is not None
        assert case.infeasible_count == 1
        assert case.fix_summary == "历史配方"

    @pytest.mark.asyncio
    async def test_llm_transient_category_recovery_no_overwrite(self) -> None:
        """#17①：LLM_TRANSIENT 类成功不覆写 fix_summary（防伪配方污染）."""
        from src.domain.value_objects.tool_execution import ToolResult, ToolResultStatus

        signature = _llm_message_signature()
        # 预置 LLM_TRANSIENT 首例（RECOVERED + 空配方）
        ok = ToolResult(tool_id=_TOOL, status=ToolResultStatus.SUCCESS, output={"plan": "p", "result": "r"})
        inner = AsyncMock()
        inner.execute = AsyncMock(return_value=ok)
        service, deps = _make_service(inner_chain=inner)
        await service.recover(
            tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389(violations=[])
        )
        case = await deps["cases"].get_by_natural_key(_TENANT, _TOOL, signature)
        assert case is not None
        assert case.error_category == "LLM_TRANSIENT"
        assert case.fix_summary == "", "LLM_TRANSIENT 成功不覆写 fix_summary"


class TestRecoveredEventAndLog:
    """恢复成功路径：ToolExecutionRecovered 事件 + RECOVERED 演进日志."""

    @pytest.mark.asyncio
    async def test_recovery_publishes_event_and_writes_log(self) -> None:
        """事件 id 与日志 execution_id 同源（主 id）。"""
        from src.domain.events.validation_feedback_events import ToolExecutionRecovered
        from src.domain.value_objects.tool_execution import ToolResult, ToolResultStatus

        ok = ToolResult(tool_id=_TOOL, status=ToolResultStatus.SUCCESS, output={"plan": "p", "result": "OK_x"})
        inner = AsyncMock()
        inner.execute = AsyncMock(return_value=ok)

        class _Pub:
            def __init__(self) -> None:
                self.published: list = []

            async def publish(self, event) -> None:
                self.published.append(event)

        publisher = _Pub()
        service, deps = _make_service(inner_chain=inner, publisher=publisher)
        result = await service.recover(
            tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389()
        )
        assert result.status == ToolResultStatus.SUCCESS
        from src.domain.ports.evolution_log_repository import EvolutionLogQuery

        logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        assert logs and logs[0].final_status == "RECOVERED"
        await _drain_tasks()
        events = [e for e in publisher.published if isinstance(e, ToolExecutionRecovered)]
        assert events
        assert str(events[-1].execution_id) == str(logs[0].execution_id)

    @pytest.mark.asyncio
    async def test_exhaustion_publishes_marked_infeasible_event(self) -> None:
        """耗尽发布 ToolExecutionMarkedInfeasible 事件（INFEASIBLE 不抛异常）."""
        from src.domain.events.validation_feedback_events import ToolExecutionMarkedInfeasible

        class _Pub:
            def __init__(self) -> None:
                self.published: list = []

            async def publish(self, event) -> None:
                self.published.append(event)

        publisher = _Pub()
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_382())
        service, _ = _make_service(inner_chain=inner, publisher=publisher)
        result = await service.recover(
            tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_382()
        )
        assert result.status == ToolResultStatus.INFEASIBLE
        await _drain_tasks()
        events = [e for e in publisher.published if isinstance(e, ToolExecutionMarkedInfeasible)]
        assert events


# ============================================================================
# 循环 C：幂等与 evolution log
# ============================================================================


class TestIdempotentRecover:
    """同 trigger_error 重复 recover：副作用去重 + 合成结论（R3-2 定谳）."""

    @pytest.mark.asyncio
    async def test_repeat_infeasible_dedup_and_synthetic(self) -> None:
        """INFEASIBLE 终态重放：日志 1 行/事件 1 次 + 合成结论 + 案例同步递增."""
        from src.domain.events.validation_feedback_events import ToolExecutionMarkedInfeasible

        class _Pub:
            def __init__(self) -> None:
                self.published: list = []

            async def publish(self, event) -> None:
                self.published.append(event)

        publisher = _Pub()
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(inner_chain=inner, publisher=publisher)
        trigger = _389()

        first = await service.recover(
            tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=trigger
        )
        assert first.status == ToolResultStatus.INFEASIBLE
        await _drain_tasks()
        events_after_first = len([e for e in publisher.published if isinstance(e, ToolExecutionMarkedInfeasible)])

        replay = await service.recover(
            tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=trigger
        )
        assert replay.status == ToolResultStatus.INFEASIBLE
        await _drain_tasks()
        from src.domain.ports.evolution_log_repository import EvolutionLogQuery

        logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        assert len(logs) == 1
        events_after_replay = len([e for e in publisher.published if isinstance(e, ToolExecutionMarkedInfeasible)])
        assert events_after_replay == events_after_first == 1
        # 案例分类计数同步递增（首跑 + 重放 = 2）
        signature = _violation_signature()
        case = await deps["cases"].get_by_natural_key(_TENANT, _TOOL, signature)
        assert case is not None
        assert case.infeasible_count == 2
        assert case.occurrence_count == case.recovered_count + case.infeasible_count

    @pytest.mark.asyncio
    async def test_repeat_recovered_synthetic_with_replayed_marker(self) -> None:
        """RECOVERED 终态重放：合成 SUCCESS 摘要 + replayed 标记 + 无证据包（R8-3）
        + 案例配方存续与计数递增（R1-F1：短路路径不覆写 fix_summary）."""
        from src.domain.value_objects.tool_execution import ToolResult, ToolResultStatus

        ok = ToolResult(tool_id=_TOOL, status=ToolResultStatus.SUCCESS, output={"plan": "p", "result": "OK_x"})
        inner = AsyncMock()
        inner.execute = AsyncMock(return_value=ok)
        service, deps = _make_service(inner_chain=inner)
        trigger = _389()

        first = await service.recover(
            tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=trigger
        )
        assert first.status == ToolResultStatus.SUCCESS
        signature = _violation_signature()
        case_after_first = await deps["cases"].get_by_natural_key(_TENANT, _TOOL, signature)
        assert case_after_first is not None
        assert case_after_first.fix_summary, "首次恢复应沉淀修复配方"

        replay = await service.recover(
            tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=trigger
        )
        assert replay.status == ToolResultStatus.SUCCESS
        assert replay.output.get("replayed") is True
        assert replay.evidence_package is None
        # R1-F1 回归断言：重放后配方保持原值（不覆写）+ recovered_count 同步递增
        case_after_replay = await deps["cases"].get_by_natural_key(_TENANT, _TOOL, signature)
        assert case_after_replay is not None
        assert case_after_replay.fix_summary == case_after_first.fix_summary, (
            "RECOVERED 重放不得清空已沉淀修复配方（AC-6 短路路径不覆写 fix_summary）"
        )
        assert case_after_replay.recovered_count == 2, "重放观测计数同步递增（R3-2）"

    @pytest.mark.asyncio
    async def test_no_execution_id_no_shortcircuit(self) -> None:
        """触发异常无 execution_id（边缘形态）→ 幂等键缺失仍可运行（不短路）."""
        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_382(execution_id=None))
        service, _ = _make_service(inner_chain=inner)
        result = await service.recover(
            tool_id=_TOOL,
            tool=AsyncMock(),
            tool_call=AsyncMock(),
            context=_make_ctx(),
            trigger_error=_382(execution_id=None),
        )
        assert result.status == ToolResultStatus.INFEASIBLE

    @pytest.mark.asyncio
    async def test_malformed_execution_id_no_crash_fresh_log_id(self) -> None:
        """畸形 execution_id 串（R1-F11）→ 入口归一按无 id 处理：不崩溃、不命中
        短路、耗尽落库日志行 id 为新铸 UUID（旧行为在落库处裸 UUID() 抛 ValueError）."""
        from src.domain.ports.evolution_log_repository import EvolutionLogQuery

        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())  # 3 次耗尽路径
        service, deps = _make_service(inner_chain=inner)

        result = await service.recover(
            tool_id=_TOOL,
            tool=AsyncMock(),
            tool_call=AsyncMock(),
            context=_make_ctx(),
            trigger_error=_389(execution_id="not-a-uuid"),
        )
        assert result.status == ToolResultStatus.INFEASIBLE, "畸形 id 不应致裸 ValueError 逃逸（INFEASIBLE 不抛契约）"
        logs = list(await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL, tenant_id=_TENANT)))
        assert len(logs) == 1, "耗尽终态日志落库 1 行"
        try:
            uuid.UUID(str(logs[0].execution_id))
        except ValueError as exc:  # pragma: no cover - 断言失败路径
            pytest.fail(f"日志行 id 应为新铸合法 UUID，实际: {logs[0].execution_id!r} ({exc})")


class TestLlmTransientPredicateExplicitChainOnly:
    """#17② 谓词仅走显式因果链（R1-F2）——生产动态上下文回归.

    生产形态：recover() 在 VFD 的 except 块内被 await（sys.exc_info()=trigger
    贯穿全程），期间 raise 的内层异常其 __context__ 隐式回指触发异常——389-LLM
    触发场景下若谓词遍历 __context__，非 LLM 根因失败会被误判为 LLM 瞬时
    （该标 INFEASIBLE 的代码缺陷被直传放走）。修复后仅走显式链。
    """

    def _trigger_389_llm_chain(self) -> ToolResultValidationError:
        """构造 389-LLM 触发链（生产同构：389 --raise from--> 383 --cause--> LLMAPIError）."""
        from src.domain.exceptions import ToolExecutionRetryExhaustedError

        retry_exc = ToolExecutionRetryExhaustedError(
            execution_id="e", tool_id=str(_TOOL), retry_count=3, cause=LLMAPIError("503")
        )
        try:
            raise _389(violations=[]) from retry_exc
        except ToolResultValidationError as chained:
            return chained

    def test_explicit_cause_chain_hits(self) -> None:
        """fix-gen 形态：383.cause=LLMAPIError（自定义 cause 属性）→ True."""
        from src.application.services.validation_feedback_service import _chain_contains_llm_transient
        from src.domain.exceptions import ToolExecutionRetryExhaustedError

        exc = ToolExecutionRetryExhaustedError(execution_id="e", tool_id=str(_TOOL), retry_count=3, cause=LLMAPIError("503"))
        assert _chain_contains_llm_transient(exc) is True

    def test_raise_from_chain_hits(self) -> None:
        """重执行形态：389 --__cause__--> 383 --cause--> LLM → True."""
        from src.application.services.validation_feedback_service import _chain_contains_llm_transient

        assert _chain_contains_llm_transient(self._trigger_389_llm_chain()) is True

    def test_mid_attempt_code_defect_in_except_block_not_llm(self) -> None:
        """生产动态上下文（负样本·红转绿锚点）：mid-attempt 382(cause=313，
        inner 先 raise 再包装)在 trigger 的 except 块内浮出——__context__ 回指
        389-LLM 触发链，但根因是代码缺陷 → 必须判 False（修复前经 __context__ 误判 True）."""
        from src.application.services.validation_feedback_service import _chain_contains_llm_transient

        trigger = self._trigger_389_llm_chain()
        try:
            raise trigger
        except ToolResultValidationError:
            try:
                inner = ExecutionError("NameError: x is not defined", stderr="Traceback...", exit_code=1)
                raise inner
            except ExecutionError as inner_exc:
                mid = _382(cause=inner_exc)
                try:
                    raise mid
                except ToolExecutionFailedError as exc:
                    assert mid.cause is not None and mid.cause.__context__ is trigger, "前置自检：__context__ 回指触发异常"
                    assert _chain_contains_llm_transient(exc) is False, "代码缺陷根因不得经 __context__ 误判为 LLM 瞬时"

    def test_fix_gen_typeerror_in_except_block_not_llm(self) -> None:
        """fix-gen 非 LLM 异常（如 TypeError，无 cause）在 except 块内 raise——
        __context__ 回指触发链 → 必须判 False（防 detail 误标 llm_generation_failed）."""
        from src.application.services.validation_feedback_service import _chain_contains_llm_transient

        trigger = self._trigger_389_llm_chain()
        try:
            raise trigger
        except ToolResultValidationError:
            try:
                raise TypeError("response construction defect")
            except TypeError as exc:
                assert exc.__context__ is trigger, "前置自检：__context__ 确实回指触发异常"
                assert _chain_contains_llm_transient(exc) is False, "非 LLM 根因不得误标 llm_generation_failed"


class TestNegativeHintReachesEngineHints:
    """格②命中时负样本提示并入引擎侧 case_summaries（R1-F6——Subtask 0.12 生产者兑现）."""

    @pytest.mark.asyncio
    async def test_negative_hint_in_engine_case_summaries(self) -> None:
        """格②（NEGATIVE_CASE_GUIDED）时 hints['case_summaries'] 携带负样本提示
        （引擎 Think stage 唯一消费面）；fix-gen prompt 的 case_summaries 不含
        （防「历史成功修复案例」标题语义错标）."""
        from src.domain.entities.error_case import ErrorCase
        from src.domain.value_objects.validation_feedback import FeedbackOutcome

        inner = AsyncMock()
        inner.execute = AsyncMock(side_effect=_389())
        service, deps = _make_service(inner_chain=inner)
        signature = _violation_signature()
        await deps["cases"].record_case(
            ErrorCase(
                tenant_id=_TENANT,
                tool_id=_TOOL,
                error_signature=signature,
                error_category="SCHEMA_VIOLATION",
                outcome=FeedbackOutcome.MARKED_INFEASIBLE,
                recovered_count=0,
                infeasible_count=2,
                occurrence_count=2,
                last_seen_at=datetime.now(UTC),
            )
        )
        await service.recover(tool_id=_TOOL, tool=AsyncMock(), tool_call=AsyncMock(), context=_make_ctx(), trigger_error=_389())
        contexts = [c.args[3] for c in inner.execute.call_args_list if len(c.args) >= 4]
        assert contexts, "重执行应发生"
        for ctx in contexts:
            hints = (ctx.extensions or {}).get("validation_feedback_hints") or {}
            assert any("不可行" in str(s) for s in hints.get("case_summaries", [])), (
                "引擎侧 case_summaries 应含负样本提示（Think stage 唯一感知通道）"
            )


# ============================================================================
# 内部辅助
# ============================================================================


def _violation_signature() -> str:
    """389 默认 violations 的归一化签名（真实提取器）."""
    from src.domain.services.error_signature_extractor import ErrorSignatureExtractor

    return ErrorSignatureExtractor.extract_from_violations(
        (
            {
                "path": "result",
                "expected": "^OK_",
                "message": "'BAD_output' does not match '^OK_'",
            },
        )
    )


def _llm_message_signature() -> str:
    """389-LLM 子路径（violations 空）的签名——LLM 错误消息归一化."""
    from src.domain.services.error_signature_extractor import ErrorSignatureExtractor

    return ErrorSignatureExtractor.extract("exhausted")


async def _assert_first_strategy(deps: dict[str, Any], expected: str) -> None:
    """断言演进日志首 attempt 的 fix_strategy（async 测试内直接 await）."""
    from src.domain.ports.evolution_log_repository import EvolutionLogQuery

    logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
    logs = list(logs)
    assert logs, "应有演进日志"
    assert logs[0].fix_attempts[0].fix_strategy == expected
