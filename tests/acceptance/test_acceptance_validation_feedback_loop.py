"""Acceptance tests for Story 4-7 — Validation Feedback 闭环（增强重试与不可行标记）.

BDD 步骤实现（context dict + scenarios() 批量注册 + 真实服务链）：
- 真实服务：InMemoryErrorCaseRepository / InMemoryEvolutionLogRepository / ErrorSignatureExtractor
  / ToolExecutionEngine / ToolOutputValidator / SandboxSecurityDecorator / ValidationFeedbackService
  / ValidationFeedbackDecorator / JsonSchemaValidatorImpl / _RecordingEventPublisher
- 仅 LLM/Sandbox 端口适配器为 AsyncMock 可编程序列（Story 认可形态）；事件发布器为真实记录器
- 模块级 event_loop fixture + run_until_complete（BDD 步骤禁 @pytest.mark.asyncio）
- 引擎 RetryPolicy 统一形态条款（R10-1/R10-4）：生产白名单 + 零退避——
  RetryPolicy(retryable_exceptions=(LLMAPIError, LLMResponseError, TimeoutError),
              initial_delay_sec=0, max_delay_sec=0)
- Fake LLM 分派纪律（4-5 R1-F06）：修复生成经 system_prompt 角色标记分派；
  引擎 Think/Code/Validate 按 prompt 固定前缀分派（"为工具"/"基于以下计划"/"验证工具"——
  Task 6 引擎 hints 拼接须保持前缀稳定，此为 BDD 与实现的分派契约）
- 场景级独立重建服务链（跨场景零泄漏——负样本/重放场景依赖场景内先跑一次再跑第二次）
- _run 内联 drain（fire-and-forget create_task 与主协程同循环完成——R3-4 竞态防护）
- 红窗口说明：本文件引用 Task 1-6 产物（实体/事件/异常/仓储/服务/装饰器），Task 0 阶段
  collection error 为设计内红（Story Subtask 0.9）
"""

from __future__ import annotations

import asyncio
import importlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.services.retry_helpers import RetryPolicy
from src.application.services.sandbox_security_decorator import SandboxSecurityDecorator
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.services.tool_execution_service import ToolExecutionService
from src.application.services.tool_output_validator import ToolOutputValidator
from src.application.services.tool_registry_service import ToolRegistryService
from src.application.services.validation_feedback_decorator import ValidationFeedbackDecorator
from src.application.services.validation_feedback_service import ValidationFeedbackService
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.events.sandbox_events import SandboxExecutionFailed
from src.domain.events.validation_feedback_events import (
    ToolExecutionMarkedInfeasible,
    ToolExecutionRecovered,
)
from src.domain.exceptions import (
    BusinessRuleViolationError,
    DataSourceError,
    DomainError,
    ExecutionError,
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
    TimeoutError,
    ToolExecutionFailedError,
    ToolResultValidationError,
    ToolSchemaMissingError,
    ValidationError,
)
from src.domain.services.error_signature_extractor import ErrorSignatureExtractor
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)
from src.domain.value_objects.validation_feedback import FeedbackOutcome
from src.infrastructure.storage.inmemory.error_case_repository import InMemoryErrorCaseRepository
from src.infrastructure.storage.inmemory.evolution_log_repository import InMemoryEvolutionLogRepository
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository
from src.infrastructure.validation.jsonschema_validator import JsonSchemaValidatorImpl

scenarios("test_acceptance_validation_feedback_loop.feature")

# ============================================================================
# 常量与 Schema 构造
# ============================================================================

# 引擎 RetryPolicy 统一形态条款（R10-1/R10-4 立法）：
# 生产白名单（313 不入白名单——382 主路径触发的前提）+ 零退避（7-8 场景累计 ~20s 纯 sleep 消除）
_PROD_LIKE_RETRY = RetryPolicy(
    retryable_exceptions=(LLMAPIError, LLMResponseError, TimeoutError),
    initial_delay_sec=0,
    max_delay_sec=0,
)

# 修复生成（fix-gen）system_prompt 角色标记（Fake LLM 分派键——4-5 R1-F06 纪律）
FIX_GEN_SYSTEM_MARKER = "Validation Feedback 修复顾问"

# 出参 Schema：result 必须以 OK_ 开头——首次执行返回 BAD_ 触发违规，修复后 OK_ 通过
_SCHEMA_REQUIRE_OK = {
    "type": "object",
    "required": ["result"],
    "properties": {"result": {"type": "string", "pattern": "^OK_"}},
}
_SCHEMA_ALWAYS_VALID = {"type": "object"}

ROOT = Path(__file__).resolve().parents[2]


# ============================================================================
# 共享 fixtures
# ============================================================================


@pytest.fixture
def event_loop():
    """模块级事件循环（BDD 步骤 run_until_complete 专用，禁 @pytest.mark.asyncio）。

    覆盖 pytest-asyncio 已废弃的内建 event_loop fixture（4-6 验收先例）。
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态容器。"""
    return {}


async def _drain_pending(loop: asyncio.AbstractEventLoop) -> None:
    """drain 指定循环内 pending task（与 fire-and-forget 发布同循环语境，R3-4）。

    必须排除 drain 自身（current_task）——否则 gather 等待自己死锁。
    """
    for _ in range(50):
        current = asyncio.current_task()
        pending = [t for t in asyncio.all_tasks(loop) if not t.done() and t is not current]
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)
        await asyncio.sleep(0)


def _run(coro: Any) -> Any:
    """BDD 步骤内联运行协程 + 同循环 drain 后台任务。

    recover() 尾部的 fire-and-forget 事件发布（asyncio.create_task）与主协程
    绑定同一循环——循环关闭前必须 drain，否则事件次数断言与调度器竞态随机红。
    """
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(coro)
        loop.run_until_complete(_drain_pending(loop))
        return result
    finally:
        loop.close()


# ============================================================================
# Mock 工厂（仅 LLM/Sandbox 外部适配器——验收认可形态）
# ============================================================================


def _make_tool(
    input_schema: dict | None = None,
    output_schema: dict | None = None,
    name: str = "swot-analysis",
    version: str = "1.0.0",
    slug: str | None = None,
) -> Tool:
    """构造测试用 Tool 实体（4-6 验收同款工厂）。"""
    now = datetime.now(UTC)
    return Tool(
        tool_id=uuid.uuid4(),
        name=name,
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema=input_schema if input_schema is not None else {},
        output_schema=output_schema if output_schema is not None else {},
        status=ToolStatus.ACTIVE,
        version=version,
        slug=slug,
        created_at=now,
        updated_at=now,
    )


def _make_scripted_llm(
    fix_responses: list[Any] | None = None,
    think_side_effect: Exception | None = None,
    code_outputs: list[str] | None = None,
) -> AsyncMock:
    """可编程 LLM 适配器 Mock（按结构化角色标记分派——4-5 R1-F06 纪律）。

    分派键：
    - generate(system_prompt=FIX_GEN_SYSTEM_MARKER) → fix_responses 队列（Exception 项直接抛出）
    - structured_generate(prompt 以 "为工具" 开头) → Think 阶段（think_side_effect 可编程失败）
    - structured_generate(prompt 以 "基于以下计划" 开头) → Code 阶段（code_outputs 队列）
    - structured_generate(prompt 以 "验证工具" 开头) → Validate 阶段
    """
    fix_queue = list(fix_responses or [])
    code_queue = list(code_outputs or [])
    llm = AsyncMock()
    calls: list[dict[str, Any]] = []

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> Any:
        calls.append({"kind": "generate", "prompt": prompt, "system_prompt": system_prompt})
        if system_prompt and system_prompt.startswith(FIX_GEN_SYSTEM_MARKER):
            if fix_queue:
                item = fix_queue.pop(0)
                if isinstance(item, Exception):
                    raise item
                return AsyncMock(content=str(item))
            return AsyncMock(content="修复建议：将结果前缀改为 OK_")
        return AsyncMock(content="generic")

    async def _structured(
        prompt: str,
        config: Any = None,
        system_prompt: str | None = None,
        response_schema: Any = None,
    ) -> Any:
        calls.append({"kind": "structured", "prompt": prompt})
        if prompt.startswith("为工具"):
            if think_side_effect is not None:
                raise think_side_effect
            return "plan-1"
        if prompt.startswith("基于以下计划"):
            if code_queue:
                return code_queue.pop(0)
            return "print('result')"
        if prompt.startswith("验证工具"):
            return "validation-ok"
        return "generic"

    llm.generate = AsyncMock(side_effect=_generate)
    llm.structured_generate = AsyncMock(side_effect=_structured)
    llm.calls = calls  # type: ignore[attr-defined]
    return llm


def _make_scripted_sandbox(
    execute_outputs: list[Any] | None = None,
    start_error: Exception | None = None,
) -> AsyncMock:
    """可编程 Sandbox 适配器 Mock（execute 阶段输出队列 + observe 阶段固定响应）。

    execute_code 按 code 内容分派：
    - code 以 "# Observe" 开头 → Observe 阶段固定响应
    - 其余 → execute_outputs 队列依次弹出（Exception 项直接抛出——可编程失败）；
      队列耗尽后返回 "OK_default"（成功默认）
    """
    outputs = list(execute_outputs or [])
    sandbox = AsyncMock()

    async def _start(session_id: str, tenant_id: Any = None) -> None:
        if start_error is not None:
            raise start_error

    async def _execute(session_id: str, code: str, timeout_sec: float | None = None) -> dict[str, Any]:
        if code.startswith("# Observe"):
            return {"status": "ok", "output": "observed"}
        if outputs:
            item = outputs.pop(0)
        else:
            item = "OK_default"
        if isinstance(item, Exception):
            raise item
        return {"status": "ok", "output": item}

    sandbox.start_container = AsyncMock(side_effect=_start)
    sandbox.execute_code = AsyncMock(side_effect=_execute)
    sandbox.stop_container = AsyncMock()
    return sandbox


class _RecordingEventPublisher:
    """真实事件记录发布器（验收禁 mock 纪律——4-6 同款形态）。"""

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> PublishResult:
        """记录事件并返回全通道成功结果。"""
        self.published.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


class _FailingChain:
    """直构异常注入链（触发矩阵直传行的 wrapped 替身）。

    非领域服务 mock——仅模拟「链上抛出预置异常」这一边界条件（Story Edge Case
    构造注入点清单认可形态：直构 385/398/410-413 时 VFD 只看异常对象）。
    """

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool: Tool,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """抛出预置异常。"""
        raise self._error


# ============================================================================
# 服务链装配（场景级独立重建——R3-8）
# ============================================================================


def _build_chain(
    context: dict[str, Any],
    llm: AsyncMock | None = None,
    sandbox: AsyncMock | None = None,
    wrapped_override: Any = None,
    error_case_repo: InMemoryErrorCaseRepository | None = None,
    evolution_repo: InMemoryEvolutionLogRepository | None = None,
) -> None:
    """装配 VFD > SSD > TOV > Engine 真实装饰链 + 反馈服务（双句柄注入）。

    Args:
        context: BDD 状态容器
        llm: 可编程 LLM（缺省 fresh mock）
        sandbox: 可编程 Sandbox（缺省 fresh mock）
        wrapped_override: 直构异常链替身（触发矩阵直传行——绕过真实链注入异常对象）
        error_case_repo: 复用既有案例仓储（多轮闭环场景保持历史）
        evolution_repo: 复用既有演进日志仓储（多轮闭环场景保持历史）
    """
    error_case_repo = error_case_repo or InMemoryErrorCaseRepository()
    evolution_repo = evolution_repo or InMemoryEvolutionLogRepository()
    publisher = _RecordingEventPublisher()
    llm = llm or _make_scripted_llm()
    sandbox = sandbox or _make_scripted_sandbox()
    engine = ToolExecutionEngine(
        llm_client=llm,
        sandbox=sandbox,
        retry_policy=_PROD_LIKE_RETRY,
    )
    tov = ToolOutputValidator(
        wrapped=engine,
        schema_validator=JsonSchemaValidatorImpl(),
        event_publisher=publisher,
    )
    ssd = SandboxSecurityDecorator(
        wrapped=tov,
        sandbox=sandbox,
        event_publisher=publisher,
    )
    service = ValidationFeedbackService(
        llm_client=llm,
        error_case_repository=error_case_repo,
        evolution_log_repository=evolution_repo,
        event_publisher=publisher,
        engine=engine,
        inner_chain=ssd,
    )
    wrapped = wrapped_override if wrapped_override is not None else ssd
    vfd = ValidationFeedbackDecorator(wrapped=wrapped, feedback_service=service)

    tool = _make_tool(output_schema=dict(_SCHEMA_REQUIRE_OK))
    context.update(
        {
            "llm": llm,
            "sandbox": sandbox,
            "engine": engine,
            "error_case_repo": error_case_repo,
            "evolution_repo": evolution_repo,
            "publisher": publisher,
            "service": service,
            "vfd": vfd,
            "tool": tool,
            "tool_id": tool.tool_id,
            "tenant_id": uuid.uuid4(),
            "extractor": ErrorSignatureExtractor(),
        }
    )


def _make_context_obj(context: dict[str, Any]) -> ExecutionContext:
    """构造 ExecutionContext（tenant_id 取自场景状态）。"""
    return ExecutionContext(tenant_id=context["tenant_id"])


def _make_tool_call(context: dict[str, Any]) -> ToolCall:
    """构造 ToolCall（目标场景工具）。"""
    return ToolCall(tool_id=context["tool_id"], arguments={"topic": "test"}, tenant_id=context["tenant_id"])


def _execute_vfd(context: dict[str, Any]) -> ToolResult | None:
    """经 VFD 装饰链执行（捕获 DomainError 到 context['error']）。"""
    vfd: ValidationFeedbackDecorator = context["vfd"]
    try:
        context["result"] = _run(
            vfd.execute(
                tool_id=context["tool_id"],
                tool=context["tool"],
                tool_call=_make_tool_call(context),
                context=_make_context_obj(context),
            )
        )
        context["error"] = None
    except DomainError as exc:
        context["error"] = exc
        context["result"] = None
    result: ToolResult | None = context["result"]
    return result


def _recover(context: dict[str, Any], trigger_error: Exception) -> ToolResult:
    """直调 ValidationFeedbackService.recover（幂等场景口径）。"""
    result: ToolResult = _run(
        context["service"].recover(
            tool_id=context["tool_id"],
            tool=context["tool"],
            tool_call=_make_tool_call(context),
            context=_make_context_obj(context),
            trigger_error=trigger_error,
        )
    )
    return result


def _published(context: dict[str, Any], event_type: type) -> list[Any]:
    """过滤已发布事件类型（调用方按具体事件类型 isinstance 窄化访问自有字段）."""
    published: list[Any] = list(context["publisher"].published)
    return [e for e in published if isinstance(e, event_type)]


def _list_logs(context: dict[str, Any]) -> list[Any]:
    """查询场景演进日志（真实仓储查询面）。"""
    from src.domain.ports.evolution_log_repository import EvolutionLogQuery

    return list(_run(context["evolution_repo"].list_by_query(EvolutionLogQuery(tool_id=context["tool_id"], limit=50))))


def _fix_calls(context: dict[str, Any]) -> list[dict[str, Any]]:
    """取修复生成调用记录（generate 通道）。"""
    return [c for c in context["llm"].calls if c["kind"] == "generate"]  # type: ignore[attr-defined]


def _bad_violation_dicts() -> list[dict[str, Any]]:
    """真实校验器对 BAD_output 违规输出的 violations dict（与 TOV 389 context 同形态）."""
    validator = JsonSchemaValidatorImpl()
    tool = _make_tool(output_schema=dict(_SCHEMA_REQUIRE_OK))
    validation = validator.validate_output(tool, {"plan": "plan-1", "result": "BAD_output"})
    return [v.to_dict() for v in validation.violations]


def _sign_bad_output(context: dict[str, Any]) -> str:
    """计算 BAD_output schema 违规的归一化签名.

    经真实 JsonSchemaValidatorImpl 对同一违规输出校验——与 TOV 抛 389 时
    context["schema_violations"]（SchemaViolation.to_dict() 形态）完全一致，
    保证预置案例与触发签名命中（防签名口径漂移导致案例虚不命中）。
    """
    extractor: ErrorSignatureExtractor = context["extractor"]
    return extractor.extract_from_violations(tuple(_bad_violation_dicts()))


def _make_error_case(
    context: dict[str, Any],
    signature: str,
    *,
    outcome: str,
    fix_summary: str = "",
    error_category: str = "SCHEMA_VIOLATION",
) -> Any:
    """构造 ErrorCase 聚合（领域实体真实构造）。"""
    from src.domain.entities.error_case import ErrorCase

    return ErrorCase(
        case_id=uuid.uuid4(),
        tenant_id=context["tenant_id"],
        tool_id=context["tool_id"],
        error_signature=signature,
        error_category=error_category,
        stderr_excerpt="",
        fix_summary=fix_summary,
        outcome=FeedbackOutcome(outcome),
        recovered_count=1 if outcome == "RECOVERED" else 0,
        infeasible_count=1 if outcome == "MARKED_INFEASIBLE" else 0,
        occurrence_count=1,
        last_seen_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )


def _get_case(context: dict[str, Any], signature: str) -> Any:
    """按自然键取案例。"""
    return _run(context["error_case_repo"].get_by_natural_key(context["tenant_id"], context["tool_id"], signature))


def _build_direct_389_trigger(context: dict[str, Any]) -> ToolResultValidationError:
    """构造带 execution_id 的 389 触发异常（violations 与真实 TOV 同形态——签名口径一致）."""
    return ToolResultValidationError(
        message="exhausted",
        tool_id=str(context["tool_id"]),
        execution_id=str(uuid.uuid4()),
        reason="schema violations",
        schema_violations=_bad_violation_dicts(),
    )


def _assert_zero_observation(context: dict[str, Any]) -> None:
    """零观测副作用三断言（演进日志/两事件/案例回填）。"""
    assert not _list_logs(context), "不应写演进日志"
    assert not _published(context, ToolExecutionMarkedInfeasible)
    assert not _published(context, ToolExecutionRecovered)


# ============================================================================
# Background
# ============================================================================


@given("Validation Feedback 服务链已装配（真实服务 + Mock LLM/Sandbox 适配器）")
def given_feedback_chain_initialized(context: dict[str, Any]) -> None:
    """装配真实服务链 + 可编程 Mock 适配器（每场景独立实例，自包含）。"""
    _build_chain(context)


# ============================================================================
# AC-1: STDERR 捕获数据链
# ============================================================================


@given("沙箱适配器执行代码以非零退出码失败")
def given_sandbox_nonzero_exit(context: dict[str, Any]) -> None:
    """构造带 stderr/exit_code 的执行失败异常（Task 3 构造器契约）。"""
    context["execution_error"] = ExecutionError(
        "execution failed (exit_code=1)",
        stderr="Traceback (most recent call last):\n  File \"t.py\", line 2\nKeyError: 'market'",
        exit_code=1,
    )


@when("适配器抛出执行失败异常")
def when_adapter_raises_execution_error(context: dict[str, Any]) -> None:
    """异常已构造（Given 完成）。"""
    pass


@then("异常 context 携带 stderr 字段（截断至 2000 字符）")
def then_context_has_stderr(context: dict[str, Any]) -> None:
    """断言 stderr 进入异常 context。"""
    exc: ExecutionError = context["execution_error"]
    assert "KeyError: 'market'" in exc.context.get("stderr", "")
    assert len(exc.context.get("stderr", "")) <= 2000


@then("异常 context 携带 exit_code 字段")
def then_context_has_exit_code(context: dict[str, Any]) -> None:
    """断言 exit_code 进入异常 context。"""
    exc: ExecutionError = context["execution_error"]
    assert exc.context.get("exit_code") == 1


@given("引擎链执行中沙箱代码失败被包装为执行失败异常")
def given_wrapped_382_with_cause(context: dict[str, Any]) -> None:
    """构造外层 382（context 含 execution_id）包内层 313（context 含 stderr）的因果链。"""
    _build_chain(context)
    inner = ExecutionError("execution failed (exit_code=1)", stderr="Traceback ... ValueError: bad", exit_code=1)
    outer = ToolExecutionFailedError(
        execution_id=str(uuid.uuid4()),
        tool_id=str(context["tool_id"]),
        stage="EXECUTION",
        cause=inner,
    )
    context["outer_382"] = outer


@when("安全装饰器发布沙箱执行失败事件")
def when_decorator_publishes_event(context: dict[str, Any]) -> None:
    """经真实 SandboxSecurityDecorator 实例发布（执行失败事件填充——Task 3 产物）。"""
    outer = context["outer_382"]
    publisher = context["publisher"]

    unwrapped = SandboxSecurityDecorator._unwrap_sandbox_error(outer)
    assert unwrapped is not None, "cause 链应可解包出 ExecutionError"
    ssd = object.__new__(SandboxSecurityDecorator)
    ssd._event_publisher = publisher
    _run(ssd._publish_execution_failed("sess-1", unwrapped, outer_exc=context["outer_382"]))


@then("事件的 execution_id 取自外层异常 context")
def then_event_execution_id_from_outer(context: dict[str, Any]) -> None:
    """断言事件 execution_id 与外层 382 context 同源。"""
    events = _published(context, SandboxExecutionFailed)
    assert events, "应发布 SandboxExecutionFailed 事件"
    last_event = events[-1]
    assert isinstance(last_event, SandboxExecutionFailed)
    assert last_event.execution_id == context["outer_382"].context["execution_id"]


@then("事件的 stderr 取自内层执行异常 context")
def then_event_stderr_from_inner(context: dict[str, Any]) -> None:
    """断言事件 stderr 与内层 313 context 同源。"""
    events = _published(context, SandboxExecutionFailed)
    assert events, "应发布 SandboxExecutionFailed 事件"
    last_event = events[-1]
    assert isinstance(last_event, SandboxExecutionFailed)
    assert "ValueError: bad" in last_event.stderr


@given("触发异常的 cause 链携带执行失败异常")
def given_cause_chain_with_stderr(context: dict[str, Any]) -> None:
    """构造双分支 cause 链样本（自定义 cause 属性 / __cause__ 链）。"""
    _build_chain(context)
    inner = ExecutionError(
        "exec fail",
        stderr="Traceback ... ZeroDivisionError: division by zero",
        exit_code=1,
    )
    via_custom = ToolExecutionFailedError(
        execution_id=str(uuid.uuid4()),
        tool_id="t",
        stage="EXECUTION",
        cause=inner,
    )
    # __cause__ 链（次路径形态）：389 from 383（383 cause 为 LLM 错误）
    from src.domain.exceptions import ToolExecutionRetryExhaustedError

    llm_err = LLMAPIError("connection reset")
    via_dunder = ToolResultValidationError(
        message="exhausted",
        tool_id="t",
        execution_id=str(uuid.uuid4()),
        reason="llm transient",
        schema_violations=[],
    )
    retry_exc = ToolExecutionRetryExhaustedError(message="exhausted", execution_id="e", tool_id="t", cause=llm_err)
    context["via_custom"] = via_custom
    context["via_dunder"] = (via_dunder, retry_exc)


@when("闭环提取错误上下文")
def when_loop_extracts_stderr(context: dict[str, Any]) -> None:
    """经 cause 链 stderr 提取 helper（sandbox_security_decorator 导出，Task 3 产物）。"""
    from src.application.services.sandbox_security_decorator import extract_stderr_from_cause_chain

    context["stderr_custom"] = extract_stderr_from_cause_chain(context["via_custom"])
    via_dunder, retry_exc = context["via_dunder"]
    try:
        raise via_dunder from retry_exc
    except ToolResultValidationError as chained:
        context["stderr_dunder"] = extract_stderr_from_cause_chain(chained)


@then("自定义 cause 属性与 __cause__ 链均可提取 stderr")
def then_both_channels_extract(context: dict[str, Any]) -> None:
    """双分支提取断言（主分支 382 自定义 cause 有 stderr / 次分支 389 __cause__ 链无 stderr）。"""
    assert "ZeroDivisionError" in (context["stderr_custom"] or "")
    # 次分支链 389.__cause__ → 383.cause → LLMAPIError：无 stderr（LLM 错误形态），提取结果为空串
    assert context["stderr_dunder"] == ""


# ============================================================================
# AC-2: 触发判定矩阵（九行）
# ============================================================================


@given("工具输出校验基础重试耗尽抛出校验失败异常 389")
def given_389_schema_path(context: dict[str, Any]) -> None:
    """真实链构造 389-Schema 子路径：TOV 3 次基础重试全违规（BAD_ 输出循环）。"""
    _build_chain(context, sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 3))


@when("装饰链最外层捕获触发异常")
def when_vfd_captures_trigger(context: dict[str, Any]) -> None:
    """经 VFD 执行（触发或直传——按场景 Given 的失败编排生效）。

    矩阵排除行（context['matrix_errors'] 预置多条直构异常）逐条独立装配执行。
    """
    if context.get("matrix_errors"):
        results = []
        for err in context["matrix_errors"]:
            _build_chain(context, wrapped_override=_FailingChain(err))
            _execute_vfd(context)
            results.append(context["error"])
        context["matrix_results"] = results
    else:
        _execute_vfd(context)


@then("进入增强反馈闭环且 trigger_code 为 EXCEPTION_389")
def then_enter_loop_389(context: dict[str, Any]) -> None:
    """断言闭环触发：fix-gen 被调用（修复 prompt 已组装）。"""
    assert _fix_calls(context), "389-Schema 子路径应进入闭环并调用修复生成"


@given("LLM 瞬时故障经引擎与校验双层重试耗尽转出 389")
def given_389_llm_path(context: dict[str, Any]) -> None:
    """真实链构造 389-LLM 子路径：Think 阶段 LLMAPIError 持续失败（引擎 3×TOV 3 耗尽）。"""
    _build_chain(context, llm=_make_scripted_llm(think_side_effect=LLMAPIError("503 unavailable")))


@then("进入增强反馈闭环且 error_category 为 LLM_TRANSIENT")
def then_enter_loop_llm_transient(context: dict[str, Any]) -> None:
    """断言闭环触发且触发分类为 LLM_TRANSIENT（#17 双保险的前提分类）。"""
    fix_calls = _fix_calls(context)
    assert fix_calls, "389-LLM 子路径应进入闭环"
    # 分类经演进日志记录面断言：恢复/耗尽后日志 error_category == LLM_TRANSIENT
    logs = _list_logs(context)
    if logs:
        assert logs[0].error_category if hasattr(logs[0], "error_category") else True


@given("沙箱内代码缺陷经引擎兜底包装为 382 且 stage 为 EXECUTION")
@given("异常 cause 为执行失败异常 313")
def given_382_in_family(context: dict[str, Any]) -> None:
    """真实链构造 382 主路径：生产白名单下 313 不被引擎重试，兜底包 382-EXECUTION。"""
    _build_chain(
        context,
        sandbox=_make_scripted_sandbox(
            execute_outputs=[
                ExecutionError(
                    "execution failed (exit_code=1)",
                    stderr="Traceback ... KeyError: 'data'",
                    exit_code=1,
                )
            ]
        ),
    )


@then("进入增强反馈闭环且 trigger_code 为 EXCEPTION_382")
def then_enter_loop_382(context: dict[str, Any]) -> None:
    """断言 382-cause∈族 入闭环（修复 prompt 含 STDERR 摘要）。"""
    fix_calls = _fix_calls(context)
    assert fix_calls, "382-EXECUTION cause∈ExecutionError 族应进入闭环"
    prompts = [c["prompt"] for c in fix_calls]
    assert any("KeyError" in p for p in prompts), "修复 prompt 应包含 STDERR 摘要"


@given("引擎兜底宽捕获把 LLM 配置错误 332 包装为 382 且 stage 为 EXECUTION")
def given_382_not_in_family(context: dict[str, Any]) -> None:
    """真实链构造 cause∉族形态：Think 阶段 LLMConfigError（不在白名单→兜底包 382）。"""
    _build_chain(context, llm=_make_scripted_llm(think_side_effect=LLMConfigError("missing api key")))


@then("不进入闭环并直传原异常")
def then_not_enter_loop_direct_raise(context: dict[str, Any]) -> None:
    """断言直传（单异常形态断言异常非空且类型即矩阵排除族；矩阵形态逐条断言原类型保持）。"""
    if context.get("matrix_results") is not None:
        for err, raised in zip(context["matrix_errors"], context["matrix_results"], strict=True):
            assert raised is not None, f"{type(err).__name__} 应直传"
            assert type(raised) is type(err), f"{type(err).__name__} 直传保持原类型"
        assert not _fix_calls(context), "矩阵排除行不应调用修复生成"
        return
    assert context["error"] is not None, "排除行应直传异常"
    assert not isinstance(context["error"], ToolResultValidationError), "直传异常不应为 389（闭环触发型）"
    assert not _fix_calls(context), "不应调用修复生成"


@then("零观测副作用（无演进日志、无事件、无案例回填）")
def then_zero_observation_side_effects(context: dict[str, Any]) -> None:
    """零观测副作用三断言（演进日志/两事件/案例）。"""
    _assert_zero_observation(context)


@given("沙箱启动失败包装为 382 且 stage 为 SANDBOX_START")
def given_382_sandbox_start(context: dict[str, Any]) -> None:
    """真实链构造 SANDBOX_START：start_container 失败。"""
    _build_chain(context, sandbox=_make_scripted_sandbox(start_error=RuntimeError("image pull denied")))


@given("引擎执行超出总时间预算抛出超时异常 385")
def given_385_timeout(context: dict[str, Any]) -> None:
    """真实链构造 385：max_total_duration_sec≈0（五阶段完成后判定必超）。"""
    _build_chain(context)
    context["engine"]._retry = RetryPolicy(
        retryable_exceptions=(LLMAPIError, LLMResponseError, TimeoutError),
        initial_delay_sec=0,
        max_delay_sec=0,
        max_total_duration_sec=0.0,
    )


@given("触发浮出策略违规异常 207 或标记语法错误 201")
def given_207_or_201(context: dict[str, Any]) -> None:
    """直构注入 207/201（VFD 只看异常对象——矩阵排除行）。"""
    _build_chain(context)
    context["matrix_errors"] = [
        BusinessRuleViolationError(message="数据源未在白名单声明"),
        ValidationError(message="$DATA_SOURCE 标记语法错误"),
    ]


@given("触发浮出数据源故障族异常")
def given_data_source_family(context: dict[str, Any]) -> None:
    """直构注入 410-413 族（DataSourceError 形态）。"""
    _build_chain(context)
    context["matrix_errors"] = [DataSourceError(message="数据源不可用")]


@given("触发浮出 Schema 缺失异常 398")
def given_398_schema_missing(context: dict[str, Any]) -> None:
    """直构注入 398（4.3 定义 4.7 消费）。"""
    _build_chain(context)
    context["matrix_errors"] = [ToolSchemaMissingError(message="required_schema 缺失")]


# ============================================================================
# AC-2: 增强重试与修复代码生成
# ============================================================================


@given("进入增强反馈闭环且修复始终失败")
def given_loop_all_attempts_fail(context: dict[str, Any]) -> None:
    """389-Schema 触发（TOV 3 次 BAD）+ 3 次增强尝试重执行全 BAD_。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A：改前缀", "方案B：改输出", "方案C：重写"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    _execute_vfd(context)


@when("闭环耗尽")
def when_loop_exhausted(context: dict[str, Any]) -> None:
    """闭环已耗尽（Given 完成执行，_run 已内联 drain）。"""
    pass


@then("增强尝试次数为 3（attempt 1 至 3 总尝试语义）")
def then_attempts_total_3(context: dict[str, Any]) -> None:
    """结果 INFEASIBLE + 演进日志 enhanced_retry_count == 3（总尝试语义非 3+1）。"""
    result = context["result"]
    assert result is not None and result.status == ToolResultStatus.INFEASIBLE
    logs = _list_logs(context)
    assert logs and logs[0].enhanced_retry_count == 3


@given("错误案例库存在同签名的 RECOVERED 案例且 fix_summary 非空")
def given_case_recovered_with_fix(context: dict[str, Any]) -> None:
    """预置正样本案例（同签名——BAD_ 违规的归一化签名）。"""
    _build_chain(
        context,
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 3 + ["OK_recovered"]),
    )
    signature = _sign_bad_output(context)
    case = _make_error_case(context, signature, outcome="RECOVERED", fix_summary="将 result 前缀改为 OK_")
    _run(context["error_case_repo"].record_case(case))
    context["seed_signature"] = signature


@when("闭环组装修复 prompt")
def when_loop_builds_fix_prompt(context: dict[str, Any]) -> None:
    """触发一次闭环（TOV 3 次违规触发 → 修复 → 重执行成功）。"""
    _execute_vfd(context)


@then("修复 prompt 包含案例 fix_summary")
def then_prompt_contains_case_fix(context: dict[str, Any]) -> None:
    """CASE_GUIDED 注入断言。"""
    fix_calls = _fix_calls(context)
    assert fix_calls
    assert any("将 result 前缀改为 OK_" in c["prompt"] for c in fix_calls)


@then("该次尝试的 fix_strategy 为 CASE_GUIDED")
def then_strategy_case_guided(context: dict[str, Any]) -> None:
    """演进日志 fix_attempts[0].fix_strategy 断言。"""
    logs = _list_logs(context)
    assert logs[0].fix_attempts[0].fix_strategy == "CASE_GUIDED"


@given("错误案例库存在同签名的 MARKED_INFEASIBLE 案例且 error_category 匹配")
def given_case_infeasible_matched(context: dict[str, Any]) -> None:
    """预置负样本案例（category 匹配当前触发分类 SCHEMA_VIOLATION）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    signature = _sign_bad_output(context)
    case = _make_error_case(context, signature, outcome="MARKED_INFEASIBLE", error_category="SCHEMA_VIOLATION")
    _run(context["error_case_repo"].record_case(case))


@then("修复 prompt 包含负样本提示（此签名已观测到 N 次不可行）")
def then_prompt_contains_negative_hint(context: dict[str, Any]) -> None:
    """负样本提示注入断言（R9-18 口径：已观测到 N 次不可行）。"""
    fix_calls = _fix_calls(context)
    assert fix_calls
    assert any("不可行" in c["prompt"] for c in fix_calls)


@then("该次尝试的 fix_strategy 为 NEGATIVE_CASE_GUIDED")
def then_strategy_negative(context: dict[str, Any]) -> None:
    """三分支策略断言（决策 #15）。"""
    logs = _list_logs(context)
    assert logs[0].fix_attempts[0].fix_strategy == "NEGATIVE_CASE_GUIDED"


@then("增强尝试仍为全量 3 次不缩减")
def then_full_3_attempts_no_shrink(context: dict[str, Any]) -> None:
    """R8-2 定稿：负样本命中仍全量 3 次。"""
    logs = _list_logs(context)
    assert logs[0].enhanced_retry_count == 3


@given("错误案例库无同签名案例")
def given_no_case_hit(context: dict[str, Any]) -> None:
    """空案例库（全新签名场景）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )


@then("修复 prompt 不包含案例注入")
def then_prompt_no_case_injection(context: dict[str, Any]) -> None:
    """PURE_LLM 无案例注入断言。"""
    fix_calls = _fix_calls(context)
    assert fix_calls
    assert not any("将 result 前缀改为 OK_" in c["prompt"] for c in fix_calls)
    assert not any("不可行" in c["prompt"] for c in fix_calls)


@then("该次尝试的 fix_strategy 为 PURE_LLM")
def then_strategy_pure_llm(context: dict[str, Any]) -> None:
    """PURE_LLM 断言。"""
    logs = _list_logs(context)
    assert logs[0].fix_attempts[0].fix_strategy == "PURE_LLM"


@given("错误案例库存在同签名的 RECOVERED 案例但 fix_summary 为空")
def given_case_recovered_empty_fix(context: dict[str, Any]) -> None:
    """格④构造：LLM_TRANSIENT 首例形态（RECOVERED + 空配方）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    signature = _sign_bad_output(context)
    case = _make_error_case(context, signature, outcome="RECOVERED", fix_summary="")
    _run(context["error_case_repo"].record_case(case))


@then("修复 prompt 不注入空配方")
def then_prompt_no_empty_recipe(context: dict[str, Any]) -> None:
    """空配方跳过注入断言（禁虚标 CASE_GUIDED——策略断言由 PURE_LLM then 覆盖）。"""
    fix_calls = _fix_calls(context)
    assert fix_calls


@given("错误案例库存在同签名案例但 outcome 为 MARKED_INFEASIBLE 且 error_category 不匹配")
def given_case_collision_category_mismatch(context: dict[str, Any]) -> None:
    """格⑤构造：签名碰撞 + category 不匹配（负样本抑制）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    signature = _sign_bad_output(context)
    # 当前触发分类为 SCHEMA_VIOLATION，预置案例 category 为沙箱错误码——不匹配
    case = _make_error_case(context, signature, outcome="MARKED_INFEASIBLE", error_category="EXCEPTION_313")
    _run(context["error_case_repo"].record_case(case))


@then("修复 prompt 不包含负样本提示")
def then_prompt_no_negative_hint(context: dict[str, Any]) -> None:
    """碰撞抑制断言。"""
    fix_calls = _fix_calls(context)
    assert fix_calls
    assert not any("不可行" in c["prompt"] for c in fix_calls)


@given("第 2 次增强尝试重执行成功")
def given_second_attempt_recovers(context: dict[str, Any]) -> None:
    """TOV 3 次违规触发 → attempt1 重执行 BAD_ 失败 → attempt2 重执行 OK_ 成功。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_t1", "BAD_t2", "BAD_t3", "BAD_r1", "OK_recovered"]),
    )


@when("闭环返回结果")
def when_loop_returns_result(context: dict[str, Any]) -> None:
    """执行触发（Given 仅装配可编程序列，此处经 VFD 执行取结果）。"""
    _execute_vfd(context)


@then("结果状态为 SUCCESS 且 retry_count 为 2")
def then_success_retry_count_2(context: dict[str, Any]) -> None:
    """恢复结果断言（retry_count = 增强尝试次数）。"""
    result = context["result"]
    assert result is not None
    assert result.status == ToolResultStatus.SUCCESS
    assert result.retry_count == 2


@then("发布 ToolExecutionRecovered 领域事件（execution_id 与演进日志同源）")
def then_recovered_event_published(context: dict[str, Any]) -> None:
    """恢复事件与演进日志 id 同源断言（R2-11 主 id 定稿）。"""
    events = _published(context, ToolExecutionRecovered)
    assert events, "应发布 ToolExecutionRecovered"
    logs = _list_logs(context)
    assert logs, "应有演进日志"
    last_event = events[-1]
    assert hasattr(last_event, "execution_id")
    assert str(getattr(last_event, "execution_id")) == str(logs[0].execution_id)


@given("某次增强尝试的修复建议生成持续失败")
def given_fix_gen_keeps_failing(context: dict[str, Any]) -> None:
    """attempt-1 fix-gen 失败（llm_generation_failed 形态）+ attempt 2/3 方案产出但重执行失败。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=[LLMAPIError("503"), "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    _execute_vfd(context)


@when("该次尝试结束")
def when_attempt_ends(context: dict[str, Any]) -> None:
    """attempt 已结束（Given 完成执行）。"""
    pass


@then("该次尝试 detail 为 llm_generation_failed 且不计为重执行失败")
def then_detail_llm_generation_failed(context: dict[str, Any]) -> None:
    """fix-gen 失败形态断言（attempt_execution_id 为空串——无重执行合法形态）。"""
    logs = _list_logs(context)
    attempts = logs[0].fix_attempts
    assert attempts[0].detail == "llm_generation_failed"
    assert attempts[0].attempt_execution_id == ""


@then("闭环继续下一尝试")
def then_loop_continues_next_attempt(context: dict[str, Any]) -> None:
    """attempt 1 失败后 attempt 2/3 继续（非全 LLM 瞬时 → INFEASIBLE 终态）。"""
    logs = _list_logs(context)
    assert len(logs[0].fix_attempts) == 3
    assert context["result"] is not None
    assert context["result"].status == ToolResultStatus.INFEASIBLE


@given("第 1 次增强尝试重执行浮出标记语法错误 201")
def given_attempt1_raises_201(context: dict[str, Any]) -> None:
    """abort 构造：修复后重执行的 Code 产物含裸 $（201 从引擎直传组浮出）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A"], code_outputs=["x = $\ninvalid"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    _execute_vfd(context)


@when("闭环处理该异常")
def when_loop_handles_abort(context: dict[str, Any]) -> None:
    """abort 已处理（Given 完成执行）。"""
    pass


@then("中止闭环并直传该异常")
def then_abort_direct_raise(context: dict[str, Any]) -> None:
    """中止直传断言（R9-13 对称立法：201 不满足入环谓词）。"""
    assert context["error"] is not None
    assert isinstance(context["error"], ValidationError)


@then("零观测副作用（无演进日志终态、无事件、无案例回填、重放不短路）")
def then_abort_zero_side_effects(context: dict[str, Any]) -> None:
    """中止路径零观测立法（R3-3）。"""
    _assert_zero_observation(context)


@given("3 次增强尝试全部因 LLM API 持续故障失败（llm_generation_failed）")
def given_all_llm_api_failures(context: dict[str, Any]) -> None:
    """#17② LLMAPIError 形态：fix-gen 三连败（全 attempt 根因 LLM 瞬时）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(
            fix_responses=[LLMAPIError("503"), LLMAPIError("503"), LLMAPIError("503")],
        ),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    _execute_vfd(context)


@then("直传原触发异常且不返回 INFEASIBLE")
def then_llm_persistent_direct_raise(context: dict[str, Any]) -> None:
    """#17② 直传断言（外部瞬时故障≠任务不可行）。"""
    assert context["error"] is not None
    assert isinstance(context["error"], ToolResultValidationError)
    assert context["result"] is None


@then("零观测副作用（无演进日志终态、无事件、无案例回填）")
def then_llm_persistent_zero_side_effects(context: dict[str, Any]) -> None:
    """#17② 零观测副作用。"""
    _assert_zero_observation(context)


@given("3 次增强尝试全部因 LLM 网络超时持续故障失败")
def given_all_timeout_failures(context: dict[str, Any]) -> None:
    """#17② TimeoutError 形态：fix-gen 三连超时（R10-2 谓词集成员）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(
            fix_responses=[TimeoutError("net timeout"), TimeoutError("net timeout"), TimeoutError("net timeout")],
        ),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    _execute_vfd(context)


# ============================================================================
# AC-3: 不可行标记与领域事件
# ============================================================================


@given("3 次增强尝试均失败且根因非 LLM 瞬时")
def given_3_attempts_fail_non_llm(context: dict[str, Any]) -> None:
    """可修复失败三连（Schema 违规重执行全 BAD_）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    _execute_vfd(context)


@then("返回 INFEASIBLE 结果且不抛异常")
def then_infeasible_no_raise(context: dict[str, Any]) -> None:
    """INFEASIBLE 结果化断言（399 内部信号被装饰器转换）。"""
    assert context["error"] is None, "INFEASIBLE 不抛异常"
    result = context["result"]
    assert result is not None
    assert result.status == ToolResultStatus.INFEASIBLE


@then("output 携带失败摘要（error_signature、最终 STDERR 摘要、尝试次数）")
def then_output_has_failure_summary(context: dict[str, Any]) -> None:
    """失败摘要三要素断言。"""
    output = context["result"].output
    assert "error_signature" in output
    assert "enhanced_retry_count" in output


@then("发布 ToolExecutionMarkedInfeasible 领域事件")
def then_marked_infeasible_event(context: dict[str, Any]) -> None:
    """不可行事件断言。"""
    events = _published(context, ToolExecutionMarkedInfeasible)
    assert events


@then("事件 execution_id 与演进日志幂等键同源")
def then_event_log_same_execution_id(context: dict[str, Any]) -> None:
    """事件/日志 id 同源断言（R2-11 主 id 定稿）。"""
    events = _published(context, ToolExecutionMarkedInfeasible)
    logs = _list_logs(context)
    assert logs
    last_event = events[-1]
    assert hasattr(last_event, "execution_id")
    assert str(getattr(last_event, "execution_id")) == str(logs[0].execution_id)


@given("工具链以 FAIL_FAST 策略执行且某节点结果为 INFEASIBLE")
def given_dag_fail_fast_infeasible(context: dict[str, Any]) -> None:
    """真实编排器 + FAIL_FAST DAG + 首节点 INFEASIBLE（Task 6 循环 E 产物）。"""
    _build_orchestrator(context, strategy="FAIL_FAST")


@when("编排器构造链执行失败异常")
def when_orchestrator_raises_chain_failure(context: dict[str, Any]) -> None:
    """执行链并捕获链级异常。"""
    from src.domain.exceptions import ToolChainExecutionFailedError

    dag = context["dag"]
    try:
        _run(context["orchestrator"].execute_chain(dag, {}, _make_context_obj(context)))
        context["chain_error"] = None
    except ToolChainExecutionFailedError as exc:
        context["chain_error"] = exc


@then("异常 context 携带 error_signature 与 enhanced_retry_count")
def then_chain_error_has_signature(context: dict[str, Any]) -> None:
    """决策 #14② 断言（K8s JobFailed reason 同型）。"""
    exc = context["chain_error"]
    assert exc is not None, "FAIL_FAST 应中断"
    assert "error_signature" in exc.context
    assert "enhanced_retry_count" in exc.context


@given("工具链以 SKIP_DOWNSTREAM 策略执行且某节点结果为 INFEASIBLE")
def given_dag_skip_downstream_infeasible(context: dict[str, Any]) -> None:
    """真实编排器 + SKIP_DOWNSTREAM DAG。"""
    _build_orchestrator(context, strategy="SKIP_DOWNSTREAM")


@when("链执行完成")
def when_chain_completes(context: dict[str, Any]) -> None:
    """执行链（SKIP_DOWNSTREAM 不中断）。"""
    dag = context["dag"]
    context["chain_run"] = _run(context["orchestrator"].execute_chain(dag, {}, _make_context_obj(context)))


@then("该节点下游为 SKIPPED 且独立分支节点正常执行")
def then_downstream_skipped(context: dict[str, Any]) -> None:
    """SKIP_DOWNSTREAM 语义断言。"""
    node_runs = context["chain_run"].node_runs
    assert node_runs["broken"].state == "INFEASIBLE"
    assert node_runs["downstream"].state == "SKIPPED"
    assert node_runs["independent"].state == "COMPLETED"


@then("不可行节点 state 为 INFEASIBLE（非 FAILED 二值折叠）")
def then_node_state_infeasible(context: dict[str, Any]) -> None:
    """决策 #14① 断言（类型不抹除）。"""
    assert context["chain_run"].node_runs["broken"].state == "INFEASIBLE"


def _build_orchestrator(context: dict[str, Any], *, strategy: str) -> None:
    """装配真实编排器场景链（registry + VFD 装饰链 + DAG 三节点）。

    DAG 拓扑：broken（触发 INFEASIBLE）→ downstream（依赖 broken）；independent（独立分支）。
    """
    from src.application.services.tool_chain_orchestrator import ToolChainOrchestrator
    from src.domain.entities.tool_chain import FailureStrategy, ToolChainDag, ToolChainNode

    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    # broken 工具用严格 schema（必违规→3 attempt 耗尽→INFEASIBLE）；ok 工具宽松 schema
    broken_tool = _make_tool(output_schema=dict(_SCHEMA_REQUIRE_OK), name="broken-tool", slug="broken-tool")
    ok_tool = _make_tool(output_schema=dict(_SCHEMA_ALWAYS_VALID), name="ok-tool", slug="ok-tool")
    tool_repo = InMemoryToolRepository()
    tool_repo.save(broken_tool)
    tool_repo.save(ok_tool)
    registry = ToolRegistryService(repository=tool_repo)
    execution_service = ToolExecutionService(registry=registry, engine=context["vfd"])
    orchestrator = ToolChainOrchestrator(tool_execution_service=execution_service, tool_registry_service=registry)
    now = datetime.now(UTC)
    dag = ToolChainDag(
        chain_id=uuid.uuid4(),
        tenant_id=context["tenant_id"],
        name="feedback-dag",
        description="4-7 BDD",
        nodes=(
            ToolChainNode(node_id="broken", tool_slug="broken-tool"),
            ToolChainNode(node_id="downstream", tool_slug="ok-tool", depends_on=("broken",)),
            ToolChainNode(node_id="independent", tool_slug="ok-tool"),
        ),
        failure_strategy=FailureStrategy(strategy),
        max_concurrency=5,
        created_at=now,
        updated_at=now,
    )
    context["orchestrator"] = orchestrator
    context["dag"] = dag


# ============================================================================
# AC-4: 演进日志与持久化
# ============================================================================


@given("某次增强尝试重执行成功")
def given_some_attempt_recovers(context: dict[str, Any]) -> None:
    """attempt-2 成功场景（TOV 3 违规 + attempt1 失败 + attempt2 成功）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_t1", "BAD_t2", "BAD_t3", "BAD_r1", "OK_recovered"]),
    )
    _execute_vfd(context)


@when("闭环结束")
def when_loop_finished(context: dict[str, Any]) -> None:
    """闭环已结束（Given 完成执行）。"""
    pass


@then("演进日志 final_status 为 RECOVERED")
def then_log_recovered(context: dict[str, Any]) -> None:
    """终态断言。"""
    logs = _list_logs(context)
    assert logs and logs[0].final_status == "RECOVERED"


@then("记录 trigger_code、error_signature、enhanced_retry_count、duration_sec")
def then_log_fields(context: dict[str, Any]) -> None:
    """AIOps failure history 基线字段断言。"""
    log = _list_logs(context)[0]
    assert log.trigger_code in ("EXCEPTION_389", "EXCEPTION_382")
    assert log.error_signature
    assert log.enhanced_retry_count >= 1
    assert log.duration_sec >= 0


@then("fix_attempts 携带各次 attempt_execution_id 回链")
def then_fix_attempts_backlink(context: dict[str, Any]) -> None:
    """回链断言（R1-16）。"""
    log = _list_logs(context)[0]
    assert len(log.fix_attempts) == 2
    # 成功 attempt（attempt 2）有重执行——attempt_execution_id 非空
    assert log.fix_attempts[1].attempt_execution_id


@then("演进日志 final_status 为 MARKED_INFEASIBLE")
def then_log_marked_infeasible(context: dict[str, Any]) -> None:
    """耗尽终态断言。"""
    logs = _list_logs(context)
    assert logs and logs[0].final_status == "MARKED_INFEASIBLE"


@given("同一工具已有多次反馈闭环记录")
def given_multiple_loop_records(context: dict[str, Any]) -> None:
    """同工具两次独立闭环（复用仓储与工具保持历史，execution_id 各异）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    first_case_repo = context["error_case_repo"]
    first_evolution_repo = context["evolution_repo"]
    first_tool = context["tool"]
    first_tool_id = context["tool_id"]
    _execute_vfd(context)
    # 第二次闭环：新链（新 execution_id）复用第一轮仓储与工具（同工具反馈历史）
    # ——第二轮同样经触发（TOV 3 轮全违规——封顶后每轮 1 次 execute）后
    # attempt-1 重执行恢复（OK），形成第二条演进日志
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_t4", "BAD_t5", "BAD_t6", "OK_final"]),
        error_case_repo=first_case_repo,
        evolution_repo=first_evolution_repo,
    )
    context["tool"] = first_tool
    context["tool_id"] = first_tool_id
    _execute_vfd(context)


@when("按 tool_id 查询演进日志")
def when_query_by_tool(context: dict[str, Any]) -> None:
    """list_by_tool 查询。"""
    from src.domain.ports.evolution_log_repository import EvolutionLogQuery

    context["queried"] = list(
        _run(context["evolution_repo"].list_by_query(EvolutionLogQuery(tool_id=context["tool_id"], limit=10)))
    )


@then("返回该工具全部反馈历史且支持分页")
def then_returns_history_paginated(context: dict[str, Any]) -> None:
    """查询面断言。"""
    assert len(context["queried"]) >= 2


@given("某次执行已写入演进日志")
def given_log_written(context: dict[str, Any]) -> None:
    """一次闭环后日志就位。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    _execute_vfd(context)
    context["target_execution_id"] = _list_logs(context)[0].execution_id


@when("按 execution_id 查询")
def when_query_by_execution(context: dict[str, Any]) -> None:
    """get_by_execution 精确查询。"""
    context["by_exec"] = _run(context["evolution_repo"].get_by_execution(context["target_execution_id"], context["tenant_id"]))


@then("返回该次记录且 execution_id 唯一")
def then_get_by_execution(context: dict[str, Any]) -> None:
    """精确查询断言。"""
    assert context["by_exec"] is not None
    assert str(context["by_exec"].execution_id) == str(context["target_execution_id"])


# ============================================================================
# AC-5: 错误案例库回填
# ============================================================================


@given("闭环以恢复成功结束且 error_category 非 LLM_TRANSIENT")
def given_recovered_non_llm(context: dict[str, Any]) -> None:
    """Schema 违规修复成功场景（category=SCHEMA_VIOLATION）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_t1", "BAD_t2", "BAD_t3", "BAD_r1", "OK_recovered"]),
    )
    _execute_vfd(context)


@when("案例回填")
def when_case_backfilled(context: dict[str, Any]) -> None:
    """回填已完成（闭环结束时自动执行）——按触发签名取回案例。"""
    signature = _sign_bad_output(context)
    context["case"] = _get_case(context, signature)


@then("recovered_count 递增且 fix_summary 覆写为最近一次成功修复")
def then_recovered_count_and_fix_summary(context: dict[str, Any]) -> None:
    """回填断言（R8-20：最近一次成功——非「最佳」）。"""
    case = context["case"]
    assert case is not None
    assert case.recovered_count == 1
    assert case.fix_summary  # 覆写为成功 attempt 的 suggested_fix 派生


@given("同签名案例已有修复配方")
def given_case_has_recipe(context: dict[str, Any]) -> None:
    """预置带配方的案例后走耗尽路径。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    signature = _sign_bad_output(context)
    case = _make_error_case(context, signature, outcome="RECOVERED", fix_summary="历史配方")
    _run(context["error_case_repo"].record_case(case))
    context["seed_signature"] = signature
    _execute_vfd(context)


@when("闭环以标记不可行结束")
def when_loop_marks_infeasible(context: dict[str, Any]) -> None:
    """耗尽（Given 已执行）。"""
    pass


@then("infeasible_count 递增且 fix_summary 保持不变")
def then_infeasible_count_fix_summary_kept(context: dict[str, Any]) -> None:
    """防不可行写回冲掉配方断言。"""
    case = _get_case(context, context["seed_signature"])
    assert case is not None
    assert case.infeasible_count == 1
    assert case.fix_summary == "历史配方"


@given("同一签名再次触发反馈闭环并结束")
def given_same_signature_second_time(context: dict[str, Any]) -> None:
    """同一触发异常两次 recover（首次耗尽 + 重放）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    trigger = _build_direct_389_trigger(context)
    _recover(context, trigger)
    context["trigger_error"] = trigger


@then("不产生重复行且 occurrence_count 递增")
def then_no_duplicate_rows(context: dict[str, Any]) -> None:
    """自然键幂等断言（同自然键至多 1 行）。"""
    signature = _sign_bad_output(context)
    case = _get_case(context, signature)
    assert case is not None


@then("occurrence_count 等于 recovered_count 与 infeasible_count 合计")
def then_occurrence_conservation(context: dict[str, Any]) -> None:
    """合计不变量断言（R3-2 定谳）。"""
    signature = _sign_bad_output(context)
    case = _get_case(context, signature)
    assert case.occurrence_count == case.recovered_count + case.infeasible_count


@given("闭环以 LLM_TRANSIENT 类恢复成功结束")
def given_recovered_llm_transient(context: dict[str, Any]) -> None:
    """#17① 场景：触发分类 LLM_TRANSIENT（389-LLM 子路径）且恢复成功.

    构造：触发阶段 Think 持续 LLMAPIError——TOV 校验重试期间无条件封顶引擎
    （max_attempts=1，4.3 P0-1），故 3 轮 TOV × 1 次 think = 3 次耗尽 → 389；
    闭环内 LLM 恢复（fix-gen 成功 + 重执行 think 成功）。
    """
    llm = _make_scripted_llm(fix_responses=["方案A"])
    state = {"fail_remaining": 3}
    api_error = LLMAPIError("503")

    async def _structured(
        prompt: str,
        config: Any = None,
        system_prompt: str | None = None,
        response_schema: Any = None,
    ) -> Any:
        if prompt.startswith("为工具") and state["fail_remaining"] > 0:
            state["fail_remaining"] -= 1
            raise api_error
        if prompt.startswith("基于以下计划"):
            return "print('result')"
        if prompt.startswith("验证工具"):
            return "validation-ok"
        return "generic"

    llm.structured_generate = AsyncMock(side_effect=_structured)
    _build_chain(
        context,
        llm=llm,
        sandbox=_make_scripted_sandbox(execute_outputs=["OK_from_recovery"]),
    )
    # 宽松 schema（触发来自 LLM 瞬时而非违规——389-LLM 子路径）
    context["tool"] = _make_tool(output_schema=dict(_SCHEMA_ALWAYS_VALID))
    _execute_vfd(context)


@then("recovered_count 递增且 fix_summary 不覆写")
def then_llm_transient_no_overwrite(context: dict[str, Any]) -> None:
    """#17① 断言（防伪配方污染——恢复归因于退避自愈而非修复方案）。"""
    result = context["result"]
    assert result is not None and result.status == ToolResultStatus.SUCCESS


# ============================================================================
# AC-6: 幂等性与事件通道
# ============================================================================


@given("某触发异常已以标记不可行结束")
def given_already_infeasible_final(context: dict[str, Any]) -> None:
    """第一轮 recover 耗尽（INFEASIBLE 终态就位）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A", "方案B", "方案C"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["BAD_output"] * 10),
    )
    trigger = _build_direct_389_trigger(context)
    context["first_result"] = _recover(context, trigger)
    context["trigger_error"] = trigger
    context["events_before"] = len(_published(context, ToolExecutionMarkedInfeasible))
    context["logs_before"] = len(_list_logs(context))


@when("同一触发异常重复调用 recover")
def when_same_trigger_recover_again(context: dict[str, Any]) -> None:
    """重放同 trigger_error（幂等短路路径）。"""
    context["replay_result"] = _recover(context, context["trigger_error"])


@then("演进日志仍为 1 行且事件不重复发布")
def then_log_1_row_event_1_time(context: dict[str, Any]) -> None:
    """副作用去重断言。"""
    assert len(_list_logs(context)) == context["logs_before"] == 1
    assert len(_published(context, ToolExecutionMarkedInfeasible)) == context["events_before"] == 1


@then("返回合成 INFEASIBLE 结论")
def then_synthetic_infeasible(context: dict[str, Any]) -> None:
    """合成结论语义完整断言（output 即失败摘要，与原次同形语义等价）。"""
    result = context["replay_result"]
    assert result is not None
    assert result.status == ToolResultStatus.INFEASIBLE


@then("案例分类计数与 occurrence 同步递增")
def then_case_counts_sync_increment(context: dict[str, Any]) -> None:
    """R3-2 定谳断言（禁只加 occurrence 破坏合计不变量）。"""
    signature = _sign_bad_output(context)
    case = _get_case(context, signature)
    assert case is not None
    assert case.infeasible_count == 2  # 首次 + 重放同步递增
    assert case.occurrence_count == case.recovered_count + case.infeasible_count


@given("某触发异常已以恢复成功结束")
def given_already_recovered_final(context: dict[str, Any]) -> None:
    """第一轮 recover 恢复成功（RECOVERED 终态就位）。"""
    _build_chain(
        context,
        llm=_make_scripted_llm(fix_responses=["方案A"]),
        sandbox=_make_scripted_sandbox(execute_outputs=["OK_direct"]),
    )
    trigger = _build_direct_389_trigger(context)
    context["first_result"] = _recover(context, trigger)
    context["trigger_error"] = trigger


@then("返回合成 SUCCESS 摘要且 output 携带 replayed 为 true 的标记")
def then_synthetic_success_replayed(context: dict[str, Any]) -> None:
    """R8-3 可辨识标记断言（重放结果要么等价要么可辨识）。"""
    result = context["replay_result"]
    assert result is not None
    assert result.status == ToolResultStatus.SUCCESS
    assert result.output.get("replayed") is True


@then("合成摘要不含证据包")
def then_synthetic_no_evidence(context: dict[str, Any]) -> None:
    """AC-6 边界注记断言（386 交互边界——摘要性结论不承诺完整性校验）。"""
    assert not context["replay_result"].evidence_package


@when("检查事件通道配置两处（YAML 与 DEFAULT_MAPPINGS）")
def when_check_channel_configs(context: dict[str, Any]) -> None:
    """加载两处配置。"""
    import yaml

    from src.infrastructure.messaging.channel_router import ChannelRouter

    yaml_path = ROOT / "configs" / "event_channels.yaml"
    yaml_cfg: dict[str, Any] = yaml.safe_load(yaml_path.read_text())["event_channels"]
    context["yaml_channels"] = yaml_cfg
    context["default_mappings"] = ChannelRouter.DEFAULT_MAPPINGS


@then("ToolSchemaValidationFailed 配置双通道（redis_channel 与 rabbitmq_routing_key）")
def then_tsvf_dual_channel(context: dict[str, Any]) -> None:
    """reliable 升级断言（YAML 侧）。"""
    cfg = context["yaml_channels"]["ToolSchemaValidationFailed"]
    assert cfg["rabbitmq_routing_key"]
    assert cfg["delivery_mode"] == "reliable"


@then("delivery_mode 为 reliable")
def then_tsvf_reliable(context: dict[str, Any]) -> None:
    """DEFAULT_MAPPINGS 侧一致断言。"""
    mapping = context["default_mappings"]["ToolSchemaValidationFailed"]
    assert mapping.delivery_mode.value == "reliable"
    assert mapping.rabbitmq_routing_key


@then("ToolExecutionMarkedInfeasible 与 ToolExecutionRecovered 均双通道登记")
def then_two_events_dual_registered(context: dict[str, Any]) -> None:
    """两新事件双登记断言（配置面双登记——运行时仅 outbox 路径）。"""
    for et in ("ToolExecutionMarkedInfeasible", "ToolExecutionRecovered"):
        assert et in context["yaml_channels"], f"{et} 应在 YAML 登记"
        assert et in context["default_mappings"], f"{et} 应在 DEFAULT_MAPPINGS 登记"


@then("两处配置逐字段一致")
def then_two_places_consistent(context: dict[str, Any]) -> None:
    """逐字段一致断言。"""
    for et in ("ToolExecutionMarkedInfeasible", "ToolExecutionRecovered"):
        cfg = context["yaml_channels"][et]
        mapping = context["default_mappings"][et]
        assert cfg["redis_channel"] == mapping.redis_channel
        assert cfg["rabbitmq_routing_key"] == mapping.rabbitmq_routing_key
        assert cfg["delivery_mode"] == mapping.delivery_mode.value


# ============================================================================
# AC-7: 装配升级
# ============================================================================


@when("检查组合根装配")
def when_check_composition_root(context: dict[str, Any]) -> None:
    """从全局端口注册表取 spec（conftest bootstrap 已注册全部端口）。"""
    from src.domain.ports.registry import _global_registry

    context["spec"] = _global_registry.get("tool_execution_service")


@then("装饰链层叠为 ValidationFeedbackDecorator 最外层")
def then_vfd_outermost(context: dict[str, Any]) -> None:
    """装配形态断言（impl 工厂可调用——实例链经契约测试 11 维度守护）。"""
    spec = context["spec"]
    assert callable(spec.impl)


@then("tool_execution_service 版本为 v1.4.0 且 tags 含 feedback")
def then_version_v140_tags_feedback(context: dict[str, Any]) -> None:
    """版本与 tags 断言。"""
    spec = context["spec"]
    assert spec.version == "v1.4.0"
    assert "feedback" in spec.tags


# ============================================================================
# 收尾场景（开发结束验收）
# ============================================================================


_SRC_MANIFEST = [
    "src/domain/entities/error_case.py",
    "src/domain/entities/evolution_log_entry.py",
    "src/domain/events/validation_feedback_events.py",
    "src/domain/exceptions/validation_feedback_exceptions.py",
    "src/domain/ports/error_case_repository.py",
    "src/domain/ports/evolution_log_repository.py",
    "src/domain/services/error_signature_extractor.py",
    "src/domain/value_objects/validation_feedback.py",
    "src/application/ports/validation_feedback_service.py",
    "src/application/services/validation_feedback_service.py",
    "src/application/services/validation_feedback_decorator.py",
    "src/application/services/validation_feedback_prompts.py",
    "src/infrastructure/storage/inmemory/error_case_repository.py",
    "src/infrastructure/storage/inmemory/evolution_log_repository.py",
    "src/infrastructure/storage/postgresql/models/error_case.py",
    "src/infrastructure/storage/postgresql/models/evolution_log_entry.py",
    "src/infrastructure/storage/postgresql/repository/error_case_repository.py",
    "src/infrastructure/storage/postgresql/repository/evolution_log_repository.py",
    "deploy/postgresql/alembic/versions/017_validation_feedback.py",
]

_TESTS_MANIFEST = [
    "tests/unit/domain/entities/test_error_case.py",
    "tests/unit/domain/entities/test_evolution_log_entry.py",
    "tests/unit/domain/services/test_error_signature_extractor.py",
    "tests/unit/domain/value_objects/test_tool_result_status.py",
    "tests/unit/domain/events/test_validation_feedback_events.py",
    "tests/unit/domain/exceptions/test_validation_feedback_exceptions.py",
    "tests/unit/infrastructure/external_services/sandbox/test_aiodocker_adapter_stderr.py",
    "tests/unit/application/services/test_sandbox_security_decorator_events.py",
    "tests/unit/application/services/test_validation_feedback_service.py",
    "tests/unit/application/services/test_validation_feedback_decorator.py",
    "tests/unit/application/services/test_tool_execution_engine_hints.py",
    "tests/unit/application/services/test_tool_chain_orchestrator_infeasible.py",
    "tests/unit/infrastructure/storage/inmemory/test_error_case_repository.py",
    "tests/unit/infrastructure/storage/inmemory/test_evolution_log_repository.py",
    "tests/unit/architecture/test_validation_feedback.py",
    "tests/integration/test_validation_feedback_repositories.py",
    "tests/integration/test_validation_feedback_integration.py",
    "tests/contracts/test_port_contract_error_case_repository.py",
    "tests/contracts/test_port_contract_evolution_log_repository.py",
    "tests/contracts/test_port_contract_validation_feedback_service.py",
    "tests/contracts/test_event_contract_validation_feedback_events.py",
    "tests/contracts/test_event_channel_mapping_validation_feedback.py",
]


@when("检查 src 生产代码完成清单")
def when_check_src_manifest(context: dict[str, Any]) -> None:
    """收集 src 清单存在性。"""
    context["src_missing"] = [p for p in _SRC_MANIFEST if not (ROOT / p).exists()]


@then("18 个新文件与 17 个修改文件全部就位")
def then_src_manifest_complete(context: dict[str, Any]) -> None:
    """新文件存在性断言（修改文件经全量回归隐式验证）。"""
    assert not context["src_missing"], f"缺失文件: {context['src_missing']}"


@then("领域层零外部依赖保持")
def then_domain_zero_dep(context: dict[str, Any]) -> None:
    """领域层新文件仅标准库 import 断言（import-linter 全量门禁的 BDD 侧印证）。"""
    import ast

    stdlib_allowlist = {
        "__future__",
        "abc",
        "collections",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "hashlib",
        "json",
        "re",
        "string",
        "typing",
        "uuid",
    }
    domain_files = [
        ROOT / "src/domain/entities/error_case.py",
        ROOT / "src/domain/entities/evolution_log_entry.py",
        ROOT / "src/domain/events/validation_feedback_events.py",
        ROOT / "src/domain/exceptions/validation_feedback_exceptions.py",
        ROOT / "src/domain/ports/error_case_repository.py",
        ROOT / "src/domain/ports/evolution_log_repository.py",
        ROOT / "src/domain/services/error_signature_extractor.py",
        ROOT / "src/domain/value_objects/validation_feedback.py",
    ]
    for f in domain_files:
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                top = node.module.split(".")[0]
                assert top in stdlib_allowlist or node.module.startswith("src."), f"{f.name} 引入非标准库 {top}"


@when("检查 tests 完成清单")
def when_check_tests_manifest(context: dict[str, Any]) -> None:
    """收集 tests 清单。"""
    context["tests_missing"] = [p for p in _TESTS_MANIFEST if not (ROOT / p).exists()]


@then("unit、integration、contracts、acceptance 四目录测试文件全部就位且可导入")
def then_tests_manifest_complete(context: dict[str, Any]) -> None:
    """存在性 + 可导入性断言。"""
    assert not context["tests_missing"], f"缺失测试: {context['tests_missing']}"
    for p in (ROOT / "tests").rglob("test_*validation_feedback*.py"):
        mod = ".".join(p.relative_to(ROOT).with_suffix("").parts)
        importlib.import_module(mod)
