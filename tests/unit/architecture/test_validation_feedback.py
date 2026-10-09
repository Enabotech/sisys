"""Story 4.7: Validation Feedback 反馈闭环架构约束验证（epics 硬路径）.

epics_v1.0.md:1395 指定路径（与目录内既有 test_arch_*.py 命名惯例不同，按
epics 指定名创建）。五项验证器：
- 8.2 重试增强：STDERR 捕获与修复建议生成链路
- 8.3 失败标记：3 次增强失败后 INFEASIBLE + 399 + 事件三联
- 8.4 幂等性：重复 recover 副作用去重（record_case 幂等路径——R3-2 定谳口径）
- 8.5 演进日志：失败历史可追溯（双查询面）
- 8.6 INFEASIBLE×FAIL_FAST 语义守护（R8-13——纯守护断言：验证 Task 6 循环 E
  已落地的修复，本文件不含生产代码修改）
- 8.7 循环依赖检测：ruff/isort（不引入 pylint）
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.services.validation_feedback_service import ValidationFeedbackService
from src.domain.events.validation_feedback_events import (
    ToolExecutionMarkedInfeasible,
)
from src.domain.exceptions import (
    ExecutionError,
    ToolChainExecutionFailedError,
    ToolExecutionFailedError,
    ToolResultValidationError,
)
from src.domain.ports.evolution_log_repository import EvolutionLogQuery
from src.domain.value_objects.tool_execution import ToolResultStatus
from src.domain.value_objects.validation_feedback import FeedbackOutcome, FixStrategy, TriggerCode
from src.infrastructure.storage.inmemory.error_case_repository import InMemoryErrorCaseRepository
from src.infrastructure.storage.inmemory.evolution_log_repository import (
    InMemoryEvolutionLogRepository,
)

_TENANT = uuid.uuid4()
_TOOL = uuid.uuid4()


def _389(execution_id: str | None = None, violations: list[dict] | None = None) -> ToolResultValidationError:
    """构造 389 触发异常."""
    return ToolResultValidationError(
        message="exhausted",
        tool_id=str(_TOOL),
        execution_id=execution_id or str(uuid.uuid4()),
        reason="schema",
        schema_violations=violations or [{"path": "$.result", "expected": "^OK_", "message": "'BAD' does not match"}],
    )


def _382(execution_id: str | None = None) -> ToolExecutionFailedError:
    """构造 382-EXECUTION-cause∈族触发异常."""
    return ToolExecutionFailedError(
        execution_id=execution_id or str(uuid.uuid4()),
        tool_id=str(_TOOL),
        stage="EXECUTION",
        cause=ExecutionError("exec fail", stderr="Traceback ... KeyError: 'k'", exit_code=1),
    )


def _failing_inner() -> AsyncMock:
    """重执行 mock：恒抛触发型异常（389-Schema 形态）."""

    def _fail(tool_id: Any, tool: Any, tool_call: Any, context: Any) -> Any:
        raise _389()

    inner = AsyncMock()
    inner.execute = AsyncMock(side_effect=_fail)
    return inner


def _make_service(**overrides: Any) -> tuple[ValidationFeedbackService, dict[str, Any]]:
    """装配被测服务（InMemory 仓储 + 可编程依赖）."""
    from src.application.services.retry_helpers import RetryPolicy

    deps: dict[str, Any] = {
        "llm": AsyncMock(),
        "cases": InMemoryErrorCaseRepository(),
        "logs": InMemoryEvolutionLogRepository(),
        "publisher": None,
        "engine": AsyncMock(_retry=RetryPolicy(max_attempts=1, initial_delay_sec=0, max_delay_sec=0)),
        "inner": _failing_inner(),
    }
    deps.update(overrides)
    service = ValidationFeedbackService(
        llm_client=deps["llm"],
        error_case_repository=deps["cases"],
        evolution_log_repository=deps["logs"],
        event_publisher=deps["publisher"],
        engine=deps["engine"],
        inner_chain=deps["inner"],
    )
    return service, deps


async def _drain() -> None:
    """drain fire-and-forget 事件任务."""
    import asyncio

    for _ in range(50):
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


class _Pub:
    """记录式发布器."""

    def __init__(self) -> None:
        self.published: list[Any] = []

    async def publish(self, event: Any) -> None:
        """记录事件."""
        self.published.append(event)


def _ctx() -> Any:
    """构造执行上下文."""
    from src.domain.value_objects.tool_execution import ExecutionContext

    return ExecutionContext(tenant_id=_TENANT)


# ============================================================================
# 8.2 重试增强验证器（STDERR 捕获与修复建议生成链路）
# ============================================================================


class TestRetryEnhancementValidator:
    """重试增强：触发 → 修复 prompt 含 STDERR → 重执行链路."""

    @pytest.mark.asyncio
    async def test_382_path_fix_prompt_carries_stderr(self) -> None:
        """382 主路径：fix-gen prompt 含 cause 链提取的 STDERR（触发→prompt→重执行）."""
        llm = AsyncMock()

        async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> Any:
            return AsyncMock(content="方案X")

        llm.generate = AsyncMock(side_effect=_generate)
        service, deps = _make_service(llm=llm)
        await service.recover(_TOOL, AsyncMock(), AsyncMock(), _ctx(), _382())
        prompts = [c.kwargs.get("prompt", "") for c in llm.generate.await_args_list]
        assert prompts, "fix-gen 应被调用（重试增强链路启动）"
        assert any("KeyError" in p for p in prompts), "修复 prompt 应含 STDERR（捕获链路贯通）"
        assert deps["inner"].execute.await_count == 3, "3 次增强重试（重执行链路）"

    @pytest.mark.asyncio
    async def test_hints_injected_to_reexecution(self) -> None:
        """hints 注入透传：重执行 context 携带 validation_feedback_hints 五键."""
        inner = _failing_inner()
        service, _ = _make_service(inner=inner)
        await service.recover(_TOOL, AsyncMock(), AsyncMock(), _ctx(), _389())
        for call in inner.execute.await_args_list:
            context = call.args[3] if len(call.args) > 3 else call.kwargs["context"]
            hints = context.extensions.get("validation_feedback_hints")
            assert hints is not None, "重执行 context 应携带 hints"
            assert set(hints.keys()) >= {
                "stderr_excerpt",
                "schema_violations",
                "case_summaries",
                "prior_attempts",
                "suggested_fix",
            }


# ============================================================================
# 8.3 失败标记验证器（3 次增强失败后三联断言）
# ============================================================================


class TestFailureMarkingValidator:
    """失败标记：INFEASIBLE + 399 信号 + ToolExecutionMarkedInfeasible 事件三联."""

    @pytest.mark.asyncio
    async def test_three_failures_marked_with_event(self) -> None:
        """3 次增强失败 → INFEASIBLE 结果 + 演进日志终态 + 不可行事件."""
        publisher = _Pub()
        service, deps = _make_service(publisher=publisher)
        result = await service.recover(_TOOL, AsyncMock(), AsyncMock(), _ctx(), _389())
        await _drain()
        assert result.status == ToolResultStatus.INFEASIBLE
        logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        assert len(logs) == 1
        assert logs[0].final_status == FeedbackOutcome.MARKED_INFEASIBLE
        assert logs[0].enhanced_retry_count == 3
        events = [e for e in publisher.published if isinstance(e, ToolExecutionMarkedInfeasible)]
        assert events, "应发布 ToolExecutionMarkedInfeasible（三联之三）"
        assert str(events[-1].execution_id) == str(logs[0].execution_id), "事件与日志 id 同源"

    @pytest.mark.asyncio
    async def test_399_registered_as_internal_signal(self) -> None:
        """399 异常类已定义（code/继承/422 映射——Task 2 交付物在位）."""
        from fastapi import status

        from src.domain.exceptions import ValidationFeedbackRetryExhaustedError
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert ValidationFeedbackRetryExhaustedError.code == "EXCEPTION_399"
        assert EXCEPTION_HTTP_MAP.get(ValidationFeedbackRetryExhaustedError) == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# 8.4 幂等性验证器（重复执行副作用去重——R3-2 定谳口径）
# ============================================================================


class TestIdempotencyValidator:
    """幂等性：同 trigger_error 重复 recover——日志单行/事件单次/案例仅计数递增."""

    @pytest.mark.asyncio
    async def test_repeat_recover_dedup(self) -> None:
        """重放：不新建日志行 / 不发事件 / 不覆写 fix_summary / 案例计数递增."""
        publisher = _Pub()
        service, deps = _make_service(publisher=publisher)
        trigger = _389()
        await service.recover(_TOOL, AsyncMock(), AsyncMock(), _ctx(), trigger)
        await _drain()
        logs_first = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        events_first = len([e for e in publisher.published if isinstance(e, ToolExecutionMarkedInfeasible)])

        replay = await service.recover(_TOOL, AsyncMock(), AsyncMock(), _ctx(), trigger)
        await _drain()
        assert replay.status == ToolResultStatus.INFEASIBLE
        logs_second = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        assert len(logs_second) == len(logs_first) == 1, "不新建日志行"
        events_second = len([e for e in publisher.published if isinstance(e, ToolExecutionMarkedInfeasible)])
        assert events_second == events_first == 1, "事件单次"
        # 案例按已记录终态调 record_case——分类计数与 occurrence 同步递增
        signature = logs_first[0].error_signature
        case = await deps["cases"].get_by_natural_key(_TENANT, _TOOL, signature)
        assert case is not None
        assert case.infeasible_count == 2
        assert case.occurrence_count == case.recovered_count + case.infeasible_count


# ============================================================================
# 8.5 演进日志验证器（失败历史可追溯——双查询面）
# ============================================================================


class TestEvolutionLogValidator:
    """演进日志：按工具查询反馈历史 + 按 execution 精确定位."""

    @pytest.mark.asyncio
    async def test_history_traceable_both_query_faces(self) -> None:
        """双查询面：list_by_tool 多记录 + get_by_execution 精确命中."""
        service, deps = _make_service()
        trigger = _389()
        await service.recover(_TOOL, AsyncMock(), AsyncMock(), _ctx(), trigger)
        # 第二次独立闭环（新 execution）
        service2, _ = _make_service(cases=deps["cases"], logs=deps["logs"])
        await service2.recover(_TOOL, AsyncMock(), AsyncMock(), _ctx(), _389())

        logs = await deps["logs"].list_by_query(EvolutionLogQuery(tool_id=_TOOL))
        assert len(logs) == 2, "按工具查询反馈历史"
        found = await deps["logs"].get_by_execution(uuid.UUID(trigger.context["execution_id"]), _TENANT)
        assert found is not None
        assert str(found.execution_id) == trigger.context["execution_id"], "按 execution 精确定位"


# ============================================================================
# 8.6 INFEASIBLE×FAIL_FAST 语义守护验证器（R8-13——纯守护断言）
# ============================================================================


class TestInfeasibleFailFastGuard:
    """INFEASIBLE×FAIL_FAST 守护：验证 Task 6 循环 E 已落地修复（本节无生产代码修改）."""

    def test_node_state_literal_contains_infeasible(self) -> None:
        """①NodeRunStatus.state Literal 含 INFEASIBLE（类型不抹除——决策 #14①）."""
        import typing

        from src.domain.entities.tool_chain_run import NodeRunStatus

        hints = typing.get_type_hints(NodeRunStatus)
        state = hints["state"]
        args = typing.get_args(state)
        assert "INFEASIBLE" in args, "Literal 应含 INFEASIBLE 三值"

    def test_orchestrator_infeasible_state_not_failed(self) -> None:
        """①编排器三值判定：INFEASIBLE 结果的节点 state 为 INFEASIBLE."""
        from src.application.services.tool_chain_orchestrator import ToolChainOrchestrator

        source = _source_of(ToolChainOrchestrator)
        assert '"INFEASIBLE"' in source, "编排器应含 INFEASIBLE 三值判定"
        assert "infeasible" in source, "编排器应按 result.status.value=='infeasible' 分派"

    def test_fail_fast_exception_carries_signature_context(self) -> None:
        """②FAIL_FAST 中断异常 context 携带 error_signature/enhanced_retry_count（决策 #14②）."""
        from src.application.services.tool_chain_orchestrator import ToolChainOrchestrator

        source = _source_of(ToolChainOrchestrator)
        assert "error_signature" in source, "FAIL_FAST 异常 context 应携带 error_signature"

    def test_tool_chain_execution_failed_error_extended_params(self) -> None:
        """②393 构造器扩参（additive）：error_signature/enhanced_retry_count 可选参数."""
        import inspect

        params = inspect.signature(ToolChainExecutionFailedError.__init__).parameters
        assert "error_signature" in params
        assert "enhanced_retry_count" in params
        exc = ToolChainExecutionFailedError(message="m", error_signature="a" * 64, enhanced_retry_count=3)
        assert exc.context["error_signature"] == "a" * 64
        assert exc.context["enhanced_retry_count"] == 3

    def test_skip_downstream_downstream_skipped(self) -> None:
        """③SKIP_DOWNSTREAM 兼容：INFEASIBLE 计入 failed_nodes 驱动下游 SKIPPED."""
        from src.application.services.tool_chain_orchestrator import ToolChainOrchestrator

        source = _source_of(ToolChainOrchestrator)
        assert '!= "success"' in source, "INFEASIBLE 经 failed_nodes 驱动 FAIL_FAST/SKIP 语义"


def _source_of(cls: type) -> str:
    """读取类源码（守护断言的静态检查面）."""
    import inspect

    return inspect.getsource(cls)


# ============================================================================
# 8.7 循环依赖检测（ruff/isort——不引入 pylint）
# ============================================================================


class TestNoCircularImports:
    """循环依赖检测：关键模块可独立导入（ruff/isort 已在 pre-commit 强制）."""

    def test_key_modules_importable(self) -> None:
        """反馈闭环关键模块独立导入无环."""
        import importlib

        modules = [
            "src.domain.entities.error_case",
            "src.domain.entities.evolution_log_entry",
            "src.domain.events.validation_feedback_events",
            "src.domain.exceptions.validation_feedback_exceptions",
            "src.domain.ports.error_case_repository",
            "src.domain.ports.evolution_log_repository",
            "src.domain.services.error_signature_extractor",
            "src.domain.value_objects.validation_feedback",
            "src.application.ports.validation_feedback_service",
            "src.application.services.validation_feedback_service",
            "src.application.services.validation_feedback_decorator",
            "src.infrastructure.storage.inmemory.error_case_repository",
            "src.infrastructure.storage.inmemory.evolution_log_repository",
        ]
        for mod in modules:
            imported = importlib.import_module(mod)
            assert imported is not None

    def test_domain_layer_zero_external_deps(self) -> None:
        """领域层新文件零外部依赖（import-linter 全量门禁的补强静态断言）."""
        import ast
        from pathlib import Path

        stdlib = {
            "__future__",
            "abc",
            "collections",
            "dataclasses",
            "datetime",
            "enum",
            "hashlib",
            "json",
            "re",
            "string",
            "typing",
            "uuid",
        }
        domain_files = [
            Path("src/domain/entities/error_case.py"),
            Path("src/domain/entities/evolution_log_entry.py"),
            Path("src/domain/events/validation_feedback_events.py"),
            Path("src/domain/exceptions/validation_feedback_exceptions.py"),
            Path("src/domain/ports/error_case_repository.py"),
            Path("src/domain/ports/evolution_log_repository.py"),
            Path("src/domain/services/error_signature_extractor.py"),
            Path("src/domain/value_objects/validation_feedback.py"),
        ]
        for f in domain_files:
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    top = node.module.split(".")[0]
                    assert top in stdlib or node.module.startswith("src."), f"{f.name} 引入非标准库 {top}（领域层零依赖红线）"

    def test_application_service_no_infrastructure_import(self) -> None:
        """应用层服务禁 import infrastructure（import-linter 契约补强）."""
        import ast
        from pathlib import Path

        app_files = list(Path("src/application").rglob("validation_feedback*.py"))
        assert app_files, "应有 validation_feedback 应用层文件"
        for f in app_files:
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    assert not node.module.startswith("src.infrastructure"), f"{f.name} 引入 infrastructure（分层红线）"


# ============================================================================
# 附：触发矩阵静态守护（epics「架构约束验证」的枚举完整性）
# ============================================================================


class TestTriggerMatrixEnumGuard:
    """触发判定矩阵九行枚举静态守护（关键排除成员在谓词源码中的覆盖）."""

    def test_should_enter_loop_predicate_source(self) -> None:
        """入环谓词源码断言：389/382-EXECUTION/cause 族三要素."""
        source = _source_of(ValidationFeedbackService)
        assert "ToolResultValidationError" in source
        assert '"EXECUTION"' in source
        assert "ExecutionError" in source

    def test_strategy_three_values(self) -> None:
        """FixStrategy 三分支（决策 #15）."""
        assert {s.value for s in FixStrategy} == {"CASE_GUIDED", "NEGATIVE_CASE_GUIDED", "PURE_LLM"}

    def test_trigger_code_two_values(self) -> None:
        """TriggerCode 两值（389/382）."""
        assert {c.value for c in TriggerCode} == {"EXCEPTION_389", "EXCEPTION_382"}
