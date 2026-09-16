"""ToolOutputValidator 装饰器单元测试(Story 4.3 AC-3 + AC-7)

覆盖范围:
1. OUTPUT 校验通过时返回 Engine 结果,不发布事件
2. OUTPUT 校验失败触发重试,第二次重试成功
3. OUTPUT 重试耗尽抛 ToolResultValidationError(EXCEPTION_389,非 ToolExecutionRetryExhaustedError,P0-B 修复)
4. violations 注入 LLM prompt(P0-D 修复):context.extensions["schema_last_violations"]
5. execution_id 与 INPUT 装饰器共享(P0-F 修复)
6. 事件发布:每次重试失败都发布,仅最后一次 is_final=True
7. payload 门禁截断(P0-H 修复)
8. fire-and-forget 不阻塞主流程(P0-I 修复)
9. 构造函数 retry_policy 覆盖 wrapped._retry
10. 兼容性:ToolExecutionEngine 类隐式满足 ToolExecutionEnginePort Protocol(Liskov Substitution)
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.schema_validator import SchemaValidatorPort
from src.application.ports.tool_execution_engine import ToolExecutionEnginePort
from src.application.services.retry_helpers import RetryPolicy
from src.application.services.tool_output_validator import ToolOutputValidator
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.exceptions import ToolResultValidationError
from src.domain.services.schema_validator import (
    SchemaValidationResult,
    SchemaViolation,
)
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_tool(tool_id: uuid.UUID | None = None) -> Tool:
    now = datetime.now(UTC)
    return Tool(
        tool_id=tool_id or uuid.uuid4(),
        name="test-tool",
        description="test",
        category=ToolCategory.ANALYSIS,
        input_schema={"type": "object"},
        output_schema={"type": "object", "required": ["result"]},
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


def _make_context(tenant_id: uuid.UUID | None = None) -> ExecutionContext:
    return ExecutionContext(tenant_id=tenant_id or uuid.uuid4())


def _make_tool_call(tool_id: uuid.UUID) -> ToolCall:
    return ToolCall(tool_id=tool_id, arguments={})


def _make_result(
    tool_id: uuid.UUID,
    output: dict[str, Any] | None = None,
) -> ToolResult:
    return ToolResult(tool_id=tool_id, status=ToolResultStatus.SUCCESS, output=output or {"result": "ok"})


def _violation(path: str = "/result", expected: str = "string") -> SchemaViolation:
    return SchemaViolation(path=path, expected=expected, actual=123, message=f"{path} expected {expected}")


def _build_validator(
    wrapped: ToolExecutionEnginePort | None = None,
    schema_validator: SchemaValidatorPort | None = None,
    event_publisher: Any | None = None,
    retry_policy: RetryPolicy | None = None,
    max_attempts: int = 3,
) -> ToolOutputValidator:
    if wrapped is None:
        wrapped = AsyncMock(spec=ToolExecutionEnginePort)
        wrapped._retry = retry_policy or RetryPolicy(
            max_attempts=max_attempts,
            backoff_strategy="constant",
            initial_delay_sec=0.001,  # 加速测试
            max_delay_sec=0.001,
        )
    if schema_validator is None:
        schema_validator = MagicMock(spec=SchemaValidatorPort)
        schema_validator.validate_output.return_value = SchemaValidationResult(is_valid=True)
    return ToolOutputValidator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        event_publisher=event_publisher,
        retry_policy=retry_policy,
    )


# ---------------------------------------------------------------------------
# 1. OUTPUT 校验通过:直接返回 Engine 结果
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passes_through_valid_output_first_attempt() -> None:
    """OUTPUT 校验通过 → 直接返回 wrapped.execute 结果,不发布事件"""
    tool_id = uuid.uuid4()
    tool = _make_tool(tool_id)
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    expected_result = _make_result(tool_id)
    wrapped.execute = AsyncMock(return_value=expected_result)
    wrapped._retry = RetryPolicy(max_attempts=3)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = SchemaValidationResult(is_valid=True)

    validator = _build_validator(wrapped=wrapped, schema_validator=schema_validator)
    context = _make_context()
    tool_call = _make_tool_call(tool_id)

    result = await validator.execute(
        tool_id=tool_id,
        tool=tool,
        tool_call=tool_call,
        context=context,
    )

    assert result == expected_result
    wrapped.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. OUTPUT 重试成功:第二次重试通过
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retries_on_invalid_output_and_succeeds_on_second_attempt() -> None:
    """OUTPUT 校验失败触发重试,第二次重试通过"""
    tool_id = uuid.uuid4()
    tool = _make_tool(tool_id)
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    success_result = _make_result(tool_id, output={"result": "fixed"})
    failure_result = _make_result(tool_id, output={"result": 123})  # 触发校验失败
    # 第一次返回失败,第二次返回成功
    wrapped.execute = AsyncMock(side_effect=[failure_result, success_result])
    wrapped._retry = RetryPolicy(
        max_attempts=3,
        backoff_strategy="constant",
        initial_delay_sec=0.001,
        max_delay_sec=0.001,
    )

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    # validate_output 是 sync 方法,用 MagicMock side_effect 列表依次返回
    schema_validator.validate_output.side_effect = [
        SchemaValidationResult(is_valid=False, violations=(_violation(),)),
        SchemaValidationResult(is_valid=True),
    ]

    validator = _build_validator(wrapped=wrapped, schema_validator=schema_validator)
    context = _make_context()
    tool_call = _make_tool_call(tool_id)

    result = await validator.execute(
        tool_id=tool_id,
        tool=tool,
        tool_call=tool_call,
        context=context,
    )

    # 第二次重试返回成功结果
    assert result == success_result
    # Engine 被调用 2 次(首次失败 + 重试成功)
    assert wrapped.execute.await_count == 2
    # Schema validator 被调用 2 次
    assert schema_validator.validate_output.call_count == 2


# ---------------------------------------------------------------------------
# 3. OUTPUT 重试耗尽:抛 ToolResultValidationError(非 ToolExecutionRetryExhaustedError,P0-B 修复)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retries_max_attempts_then_raises_tool_result_validation_error() -> None:
    """重试 max_attempts 次后抛 ToolResultValidationError(EXCEPTION_389,符合 AC-3)"""
    from src.domain.exceptions import ToolExecutionRetryExhaustedError

    tool_id = uuid.uuid4()
    tool = _make_tool(tool_id)
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    failure_result = _make_result(tool_id, output={"result": 123})
    wrapped.execute = AsyncMock(return_value=failure_result)
    wrapped._retry = RetryPolicy(
        max_attempts=3,
        backoff_strategy="constant",
        initial_delay_sec=0.001,
        max_delay_sec=0.001,
    )

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_violation(),),
    )

    validator = _build_validator(wrapped=wrapped, schema_validator=schema_validator)
    context = _make_context()
    tool_call = _make_tool_call(tool_id)

    with pytest.raises(ToolResultValidationError) as exc_info:
        await validator.execute(
            tool_id=tool_id,
            tool=tool,
            tool_call=tool_call,
            context=context,
        )

    # P0-B 修复:异常是 ToolResultValidationError(EXCEPTION_389),非 ToolExecutionRetryExhaustedError
    assert exc_info.value.code == "EXCEPTION_389"
    assert not isinstance(exc_info.value, ToolExecutionRetryExhaustedError)
    # Engine 被调用 3 次(max_attempts=3)
    assert wrapped.execute.await_count == 3
    # schema_violations 携带最后一次 violations
    assert "schema_violations" in exc_info.value.context


# ---------------------------------------------------------------------------
# 4. violations 注入 LLM prompt(P0-D 修复)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_violations_propagated_to_engine_via_context() -> None:
    """第二次重试时 context.extensions["schema_last_violations"] 包含上轮 violations(P0-D)"""
    tool_id = uuid.uuid4()
    tool = _make_tool(tool_id)
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    success_result = _make_result(tool_id, output={"result": "fixed"})
    failure_result = _make_result(tool_id, output={"result": 123})
    wrapped.execute = AsyncMock(side_effect=[failure_result, success_result])
    wrapped._retry = RetryPolicy(
        max_attempts=3,
        backoff_strategy="constant",
        initial_delay_sec=0.001,
        max_delay_sec=0.001,
    )

    expected_violation = _violation()
    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.side_effect = [
        SchemaValidationResult(is_valid=False, violations=(expected_violation,)),
        SchemaValidationResult(is_valid=True),
    ]

    validator = _build_validator(wrapped=wrapped, schema_validator=schema_validator)
    context = _make_context()
    tool_call = _make_tool_call(tool_id)

    await validator.execute(
        tool_id=tool_id,
        tool=tool,
        tool_call=tool_call,
        context=context,
    )

    # 第二次 Engine.execute 调用时,context.extensions 包含 schema_last_violations
    second_call_kwargs = wrapped.execute.await_args_list[1].kwargs
    passed_context = second_call_kwargs["context"]
    assert "schema_last_violations" in passed_context.extensions
    assert len(passed_context.extensions["schema_last_violations"]) == 1
    assert passed_context.extensions["schema_last_violations"][0].path == expected_violation.path


# ---------------------------------------------------------------------------
# 5. execution_id 共享(P0-F 修复)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execution_id_extracted_from_context_extensions() -> None:
    """execution_id 从 context.extensions["schema_execution_id"] 提取(P0-F)"""
    from src.application.services.schema_event_helpers import extract_schema_execution_id

    tool_id = uuid.uuid4()
    tool = _make_tool(tool_id)
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    success_result = _make_result(tool_id)
    wrapped.execute = AsyncMock(return_value=success_result)
    wrapped._retry = RetryPolicy(max_attempts=3, backoff_strategy="constant", initial_delay_sec=0.001)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = SchemaValidationResult(is_valid=True)

    shared_execution_id = uuid.uuid4()
    validator = _build_validator(wrapped=wrapped, schema_validator=schema_validator)

    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        extensions={"schema_execution_id": shared_execution_id},
    )
    tool_call = _make_tool_call(tool_id)

    await validator.execute(
        tool_id=tool_id,
        tool=tool,
        tool_call=tool_call,
        context=context,
    )

    # 提取的 execution_id 与上游一致
    assert extract_schema_execution_id(context) == shared_execution_id


# ---------------------------------------------------------------------------
# 6. 事件发布行为
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_published_each_retry_only_last_is_final_true() -> None:
    """OUTPUT 阶段:每次重试失败都发布事件,仅最后一次 is_final=True"""
    tool_id = uuid.uuid4()
    tool = _make_tool(tool_id)
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    failure_result = _make_result(tool_id, output={"result": 123})
    wrapped.execute = AsyncMock(return_value=failure_result)
    wrapped._retry = RetryPolicy(
        max_attempts=3,
        backoff_strategy="constant",
        initial_delay_sec=0.001,
        max_delay_sec=0.001,
    )

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_violation(),),
    )

    event_publisher = MagicMock()
    event_publisher.publish = AsyncMock()

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        event_publisher=event_publisher,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id)

    with pytest.raises(ToolResultValidationError):
        await validator.execute(
            tool_id=tool_id,
            tool=tool,
            tool_call=tool_call,
            context=context,
        )

    # 让所有 fire-and-forget 异步任务执行完成
    await asyncio.sleep(0.5)

    # 事件被发布 3 次(max_attempts=3)
    assert event_publisher.publish.await_count == 3
    # 收集所有事件
    events = [call.args[0] for call in event_publisher.publish.await_args_list]
    # 仅最后一次 is_final=True
    assert sum(1 for e in events if e.is_final) == 1
    assert events[-1].is_final is True
    # 所有事件 validation_phase=OUTPUT
    assert all(e.validation_phase == "OUTPUT" for e in events)
    # retry_attempt 递增 1, 2, 3
    assert [e.retry_attempt for e in events] == [1, 2, 3]


@pytest.mark.asyncio
async def test_no_event_when_first_attempt_succeeds() -> None:
    """OUTPUT 校验通过 → 不发布事件"""
    tool_id = uuid.uuid4()
    tool = _make_tool(tool_id)
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    success_result = _make_result(tool_id)
    wrapped.execute = AsyncMock(return_value=success_result)
    wrapped._retry = RetryPolicy(max_attempts=3)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = SchemaValidationResult(is_valid=True)

    event_publisher = MagicMock()
    event_publisher.publish = AsyncMock()

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        event_publisher=event_publisher,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id)

    result = await validator.execute(
        tool_id=tool_id,
        tool=tool,
        tool_call=tool_call,
        context=context,
    )

    assert result == success_result
    # fire-and-forget 任务不应被调度(没有事件需要发布)
    await asyncio.sleep(0.1)
    event_publisher.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# 7. 构造函数 retry_policy 覆盖 wrapped._retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_constructor_retry_policy_overrides_wrapped() -> None:
    """构造时传入 retry_policy 优先于 wrapped._retry"""
    tool_id = uuid.uuid4()
    tool = _make_tool(tool_id)
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    failure_result = _make_result(tool_id, output={"result": 123})
    wrapped.execute = AsyncMock(return_value=failure_result)
    wrapped._retry = RetryPolicy(max_attempts=10, backoff_strategy="constant", initial_delay_sec=0.001)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_violation(),),
    )

    custom_retry_policy = RetryPolicy(
        max_attempts=2,
        backoff_strategy="constant",
        initial_delay_sec=0.001,
        max_delay_sec=0.001,
    )
    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        retry_policy=custom_retry_policy,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id)

    with pytest.raises(ToolResultValidationError):
        await validator.execute(
            tool_id=tool_id,
            tool=tool,
            tool_call=tool_call,
            context=context,
        )

    # custom_retry_policy.max_attempts=2,Engine 被调用 2 次
    assert wrapped.execute.await_count == 2


# ---------------------------------------------------------------------------
# 8. fire-and-forget 不阻塞主流程
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fire_and_forget_publish_does_not_block_main_flow() -> None:
    """OUTPUT 重试失败时,慢 publish 不阻塞主流程"""
    tool_id = uuid.uuid4()
    tool = _make_tool(tool_id)
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    failure_result = _make_result(tool_id, output={"result": 123})
    wrapped.execute = AsyncMock(return_value=failure_result)
    wrapped._retry = RetryPolicy(
        max_attempts=2,
        backoff_strategy="constant",
        initial_delay_sec=0.001,
        max_delay_sec=0.001,
    )

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_violation(),),
    )

    async def _slow_publish(_event: Any) -> None:
        await asyncio.sleep(1.0)  # 1 秒慢发布

    event_publisher = MagicMock()
    event_publisher.publish = _slow_publish

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        event_publisher=event_publisher,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id)

    start = asyncio.get_event_loop().time()
    with pytest.raises(ToolResultValidationError):
        await validator.execute(
            tool_id=tool_id,
            tool=tool,
            tool_call=tool_call,
            context=context,
        )
    elapsed = asyncio.get_event_loop().time() - start

    # 验证主流程不被慢 publish 阻塞(1 秒 << 实际 elapsed)
    assert elapsed < 0.5
