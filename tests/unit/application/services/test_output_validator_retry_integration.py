"""ToolOutputValidator 81x 放大修复测试(Round 2 P0-1 修复守护)

覆盖范围:
1. 装饰器 execute 期间 wrapped._retry.max_attempts 被临时改为 1
2. 重试成功路径:_retry 恢复原值
3. 重试耗尽异常路径:finally 块恢复 _retry 原值
4. 重试耗尽抛 ToolResultValidationError 而非 ToolExecutionRetryExhaustedError
"""

from __future__ import annotations

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
from src.domain.exceptions import (
    ToolExecutionRetryExhaustedError,
    ToolResultValidationError,
)
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)


def _make_tool() -> Tool:
    now = datetime.now(UTC)
    return Tool(
        tool_id=uuid.uuid4(),
        name="t",
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema={},
        output_schema={"type": "object"},
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


def _make_context() -> ExecutionContext:
    return ExecutionContext(tenant_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_engine_retry_max_attempts_temporarily_set_to_one() -> None:
    """装饰器 execute 期间,wrapped._retry.max_attempts 必须被改为 1(防 81x LLM 放大)

    验证:OUTPUT 重试期间,Engine 内层 LLM 调用只会发生 1 次(不再是 3 次)
    """
    tool_id = uuid.uuid4()
    tool = _make_tool()
    original_retry = RetryPolicy(max_attempts=3, backoff_strategy="constant")
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    wrapped._retry = original_retry
    success_result = ToolResult(tool_id=tool_id, status=ToolResultStatus.SUCCESS, output={"x": "ok"})
    # 用 side_effect 检查 _retry 在 execute 期间的状态
    observed_retry_during_exec = []

    async def _capture_execute(**kwargs: Any) -> ToolResult:
        # 在 execute 执行期间观察 wrapped._retry
        observed_retry_during_exec.append(wrapped._retry.max_attempts)
        return success_result

    wrapped.execute = AsyncMock(side_effect=_capture_execute)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    # 第一次校验失败,第二次成功 → 触发重试
    schema_validator.validate_output.side_effect = [
        MagicMock(is_valid=False, violations=()),
        MagicMock(is_valid=True),
    ]

    validator = ToolOutputValidator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        event_publisher=None,
        retry_policy=RetryPolicy(max_attempts=2, backoff_strategy="constant", initial_delay_sec=0.001),
    )
    context = _make_context()
    tool_call = ToolCall(tool_id=tool_id, arguments={})

    await validator.execute(
        tool_id=tool_id,
        tool=tool,
        tool_call=tool_call,
        context=context,
    )

    # 装饰器 execute 期间,wrapped._retry.max_attempts 应被改为 1
    assert all(v == 1 for v in observed_retry_during_exec), f"执行期间 max_attempts 应为 1,实际: {observed_retry_during_exec}"

    # 装饰器 execute 完成后,wrapped._retry 必须恢复原值(防御性编程验证)
    assert wrapped._retry.max_attempts == original_retry.max_attempts, (
        f"_retry 必须恢复原值,实际 max_attempts={wrapped._retry.max_attempts}"
    )
    assert wrapped._retry.max_attempts == 3


@pytest.mark.asyncio
async def test_engine_retry_restored_after_exception_path() -> None:
    """重试耗尽抛 ToolResultValidationError 异常后,finally 块仍恢复 _retry 原值"""
    tool_id = uuid.uuid4()
    tool = _make_tool()
    original_retry = RetryPolicy(max_attempts=5)
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    wrapped._retry = original_retry
    failure_result = ToolResult(tool_id=tool_id, status=ToolResultStatus.SUCCESS, output={"x": 1})
    wrapped.execute = AsyncMock(return_value=failure_result)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = MagicMock(
        is_valid=False,
        violations=(),
    )

    validator = ToolOutputValidator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        event_publisher=None,
        retry_policy=RetryPolicy(max_attempts=2, backoff_strategy="constant", initial_delay_sec=0.001),
    )
    context = _make_context()
    tool_call = ToolCall(tool_id=tool_id, arguments={})

    with pytest.raises(ToolResultValidationError):
        await validator.execute(
            tool_id=tool_id,
            tool=tool,
            tool_call=tool_call,
            context=context,
        )

    # 即使异常路径,finally 块仍恢复 _retry 原值(防御性编程)
    assert wrapped._retry.max_attempts == original_retry.max_attempts == 5


@pytest.mark.asyncio
async def test_engine_retry_handles_when_wrapped_has_no_retry_attr() -> None:
    """wrapped 无 _retry 属性时(getattr default None),不抛 AttributeError"""
    tool_id = uuid.uuid4()
    tool = _make_tool()
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    # 关键:不设置 wrapped._retry
    if hasattr(wrapped, "_retry"):
        delattr(wrapped, "_retry")
    success_result = ToolResult(tool_id=tool_id, status=ToolResultStatus.SUCCESS, output={"x": "ok"})
    wrapped.execute = AsyncMock(return_value=success_result)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = MagicMock(is_valid=True)

    validator = ToolOutputValidator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        event_publisher=None,
        retry_policy=RetryPolicy(max_attempts=2),
    )
    context = _make_context()
    tool_call = ToolCall(tool_id=tool_id, arguments={})

    # 不应抛 AttributeError
    result = await validator.execute(
        tool_id=tool_id,
        tool=tool,
        tool_call=tool_call,
        context=context,
    )

    assert result == success_result


@pytest.mark.asyncio
async def test_retry_exhausted_propagates_tool_result_validation_error_not_engine_error() -> None:
    """P0-B + Round 3 修复:_call_with_retry 抛 ToolExecutionRetryExhaustedError,
    装饰器必须转换为 ToolResultValidationError(AC-3 契约)
    """
    tool_id = uuid.uuid4()
    tool = _make_tool()
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    wrapped._retry = RetryPolicy(max_attempts=2)

    # Engine.execute 抛 ToolExecutionRetryExhaustedError(模拟内层重试耗尽)
    engine_error = ToolExecutionRetryExhaustedError(
        retry_count=2,
        execution_id=None,
        tool_id=str(tool_id),
        cause=RuntimeError("LLM failed"),
    )
    wrapped.execute = AsyncMock(side_effect=engine_error)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = MagicMock(
        is_valid=False,
        violations=(),
    )

    validator = ToolOutputValidator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        event_publisher=None,
        retry_policy=RetryPolicy(max_attempts=2, backoff_strategy="constant", initial_delay_sec=0.001),
    )
    context = _make_context()
    tool_call = ToolCall(tool_id=tool_id, arguments={})

    # Round 3 P0-1:retry_policy_for_validation.retryable_exceptions 现在含
    # ToolExecutionRetryExhaustedError,允许外层重试
    # 当第二次重试仍失败时,装饰器转换为 ToolResultValidationError
    with pytest.raises(ToolResultValidationError):
        await validator.execute(
            tool_id=tool_id,
            tool=tool,
            tool_call=tool_call,
            context=context,
        )
