"""Story 4.7: ValidationFeedbackDecorator 装饰链最外层单元测试.

覆盖触发判定对齐九行矩阵（R9-1 口径：389 委托 / 382-EXECUTION-cause∈族委托 /
cause∉族直传 / SANDBOX_START 透传 / 其他异常透传 / INFEASIBLE 结果转换不抛）。

TDD 红→绿：本文件先于 src/application/services/validation_feedback_decorator.py
实现（Subtask 6.1）。
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import (
    ExecutionError,
    LLMAPIError,
    LLMConfigError,
    ToolExecutionFailedError,
    ToolResultValidationError,
    ToolSchemaMissingError,
)
from src.domain.value_objects.tool_execution import ToolResult, ToolResultStatus

_TOOL = uuid.uuid4()
_TENANT = uuid.uuid4()


def _make_vfd(wrapped: AsyncMock, service: AsyncMock) -> Any:
    """构造被测装饰器."""
    from src.application.services.validation_feedback_decorator import ValidationFeedbackDecorator
    from src.application.services.validation_feedback_service import ValidationFeedbackService

    # 谓词挂真实实现（CR-R1-27 端口化后 VFD 经端口调用——AsyncMock 任意属性
    # 调用返回协程恒真，直传行判定需真谓词承载）
    service.should_enter_feedback_loop = ValidationFeedbackService.should_enter_feedback_loop
    return ValidationFeedbackDecorator(wrapped=wrapped, feedback_service=service)


def _make_ctx() -> Any:
    """构造执行上下文."""
    from src.domain.value_objects.tool_execution import ExecutionContext

    return ExecutionContext(tenant_id=_TENANT)


class TestDecoratorTriggerMatrix:
    """装饰器层触发判定（九行矩阵——R9-1 口径补齐）."""

    @pytest.mark.asyncio
    async def test_389_delegates_to_service(self) -> None:
        """389 → 委托 service.recover."""
        trigger = ToolResultValidationError(
            message="exhausted", tool_id=str(_TOOL), execution_id=str(uuid.uuid4()), reason="schema"
        )
        wrapped = AsyncMock()
        wrapped.execute = AsyncMock(side_effect=trigger)
        service = AsyncMock()
        service.recover = AsyncMock(return_value=ToolResult(tool_id=_TOOL, status=ToolResultStatus.SUCCESS, output={}))
        vfd = _make_vfd(wrapped, service)
        result = await vfd.execute(_TOOL, AsyncMock(), AsyncMock(), _make_ctx())
        assert result is not None
        assert service.recover.await_count == 1
        assert service.recover.await_args.kwargs["trigger_error"] is trigger

    @pytest.mark.asyncio
    async def test_382_execution_cause_in_family_delegates(self) -> None:
        """382-EXECUTION 且 cause∈ExecutionError 族 → 委托."""
        trigger = ToolExecutionFailedError(
            execution_id=str(uuid.uuid4()),
            tool_id=str(_TOOL),
            stage="EXECUTION",
            cause=ExecutionError("exec fail", stderr="err", exit_code=1),
        )
        wrapped = AsyncMock()
        wrapped.execute = AsyncMock(side_effect=trigger)
        service = AsyncMock()
        service.recover = AsyncMock(return_value=ToolResult(tool_id=_TOOL, status=ToolResultStatus.INFEASIBLE, output={}))
        vfd = _make_vfd(wrapped, service)
        result = await vfd.execute(_TOOL, AsyncMock(), AsyncMock(), _make_ctx())
        assert result is not None
        assert result.status == ToolResultStatus.INFEASIBLE
        assert service.recover.await_count == 1

    @pytest.mark.asyncio
    async def test_382_execution_cause_not_in_family_reraises(self) -> None:
        """382-EXECUTION 且 cause∉族（332——R8-4 核心新增行为）→ 直传不委托."""
        trigger = ToolExecutionFailedError(
            execution_id=str(uuid.uuid4()),
            tool_id=str(_TOOL),
            stage="EXECUTION",
            cause=LLMConfigError("missing api key"),
        )
        wrapped = AsyncMock()
        wrapped.execute = AsyncMock(side_effect=trigger)
        service = AsyncMock()
        vfd = _make_vfd(wrapped, service)
        with pytest.raises(ToolExecutionFailedError):
            await vfd.execute(_TOOL, AsyncMock(), AsyncMock(), _make_ctx())
        assert service.recover.await_count == 0

    @pytest.mark.asyncio
    async def test_382_sandbox_start_reraises(self) -> None:
        """382-SANDBOX_START → 透传."""
        trigger = ToolExecutionFailedError(
            execution_id=str(uuid.uuid4()),
            tool_id=str(_TOOL),
            stage="SANDBOX_START",
            cause=RuntimeError("pull denied"),
        )
        wrapped = AsyncMock()
        wrapped.execute = AsyncMock(side_effect=trigger)
        vfd = _make_vfd(wrapped, AsyncMock())
        with pytest.raises(ToolExecutionFailedError):
            await vfd.execute(_TOOL, AsyncMock(), AsyncMock(), _make_ctx())

    @pytest.mark.asyncio
    async def test_other_exceptions_propagate(self) -> None:
        """385/207/201/410-413/398 等其他异常自然上浮（不捕获）."""
        wrapped = AsyncMock()
        wrapped.execute = AsyncMock(side_effect=ToolSchemaMissingError(message="required_schema 缺失"))
        vfd = _make_vfd(wrapped, AsyncMock())
        with pytest.raises(ToolSchemaMissingError):
            await vfd.execute(_TOOL, AsyncMock(), AsyncMock(), _make_ctx())

    @pytest.mark.asyncio
    async def test_success_passthrough(self) -> None:
        """成功结果原样透传（零行为变化）。"""
        ok = ToolResult(tool_id=_TOOL, status=ToolResultStatus.SUCCESS, output={"r": "OK_x"})
        wrapped = AsyncMock()
        wrapped.execute = AsyncMock(return_value=ok)
        service = AsyncMock()
        vfd = _make_vfd(wrapped, service)
        result = await vfd.execute(_TOOL, AsyncMock(), AsyncMock(), _make_ctx())
        assert result is ok
        assert service.recover.await_count == 0

    @pytest.mark.asyncio
    async def test_llm_transient_recovered_via_389(self) -> None:
        """389-LLM 瞬时子路径（cause 链 383）同样委托."""
        from src.domain.exceptions import ToolExecutionRetryExhaustedError

        retry_exc = ToolExecutionRetryExhaustedError(
            message="exhausted", execution_id="e", tool_id="t", cause=LLMAPIError("503")
        )
        trigger = ToolResultValidationError(
            message="exhausted", tool_id=str(_TOOL), execution_id=str(uuid.uuid4()), reason="llm", schema_violations=[]
        )
        chained: ToolResultValidationError
        try:
            raise trigger from retry_exc
        except ToolResultValidationError as exc:
            chained = exc
        wrapped = AsyncMock()
        wrapped.execute = AsyncMock(side_effect=chained)
        service = AsyncMock()
        service.recover = AsyncMock(return_value=ToolResult(tool_id=_TOOL, status=ToolResultStatus.SUCCESS, output={}))
        vfd = _make_vfd(wrapped, service)
        result = await vfd.execute(_TOOL, AsyncMock(), AsyncMock(), _make_ctx())
        assert result is not None
        assert service.recover.await_count == 1
