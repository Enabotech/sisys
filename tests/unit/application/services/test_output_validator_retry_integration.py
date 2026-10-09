"""ToolOutputValidator 81x 放大修复测试(Round 2 P0-1 修复守护)

覆盖范围:
1. 装饰器 execute 期间 effective 引擎策略 max_attempts 封顶 1(R1-F3 ContextVar
   形态——封顶经 per-task 覆盖传递,wrapped._retry 共享属性零写入)
2. 重试成功路径:覆盖退出后 effective 恢复基础策略,wrapped._retry 全程未触碰
3. 重试耗尽异常路径:with 退出自动还原覆盖,无残留
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
from src.application.services.retry_helpers import RetryPolicy, effective_retry_policy
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
    """装饰器 execute 期间,effective 引擎策略 max_attempts 封顶 1(防 81x LLM 放大)

    R1-F3 ContextVar 形态:封顶经 per-task 覆盖传递,wrapped._retry 共享属性
    零写入(并发安全);execute 期间经 effective_retry_policy 读到覆盖值
    """
    tool_id = uuid.uuid4()
    tool = _make_tool()
    original_retry = RetryPolicy(max_attempts=3, backoff_strategy="constant")
    wrapped = AsyncMock(spec=ToolExecutionEnginePort)
    wrapped._retry = original_retry
    success_result = ToolResult(tool_id=tool_id, status=ToolResultStatus.SUCCESS, output={"x": "ok"})
    # 用 side_effect 检查 effective 策略在 execute 期间的状态
    observed_retry_during_exec = []

    async def _capture_execute(**kwargs: Any) -> ToolResult:
        # 在 execute 执行期间观察 effective 策略(引擎 _retry_call 的读取形态)
        observed_retry_during_exec.append(effective_retry_policy(wrapped._retry).max_attempts)
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

    # 装饰器 execute 期间,effective max_attempts 应封顶为 1
    assert all(v == 1 for v in observed_retry_during_exec), "执行期间 effective 应为 1"

    # 装饰器 execute 完成后:覆盖已退出,wrapped._retry 全程未被触碰(R1-F3 零共享写入)
    assert wrapped._retry is original_retry, "wrapped._retry 共享属性全程零写入"
    assert wrapped._retry.max_attempts == 3
    assert effective_retry_policy(wrapped._retry) is original_retry, "覆盖退出后 effective 恢复基础策略"


@pytest.mark.asyncio
async def test_engine_retry_restored_after_exception_path() -> None:
    """重试耗尽抛 ToolResultValidationError 异常后,with 退出自动还原覆盖、
    wrapped._retry 全程未触碰(R1-F3——无残留)"""
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
    """wrapped 无 _retry 属性时(getattr default 为默认 RetryPolicy),不抛 AttributeError"""
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
