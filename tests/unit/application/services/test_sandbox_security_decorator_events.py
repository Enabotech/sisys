"""Story 4.7: SandboxSecurityDecorator 事件填充与 cause 链 STDERR 提取单元测试.

覆盖（AC-1 循环 B）：
- SandboxExecutionFailed 事件 execution_id（取自外层 382 异常 context）与
  stderr（取自内层 313 context）填充——:132-137 预留字段清偿
- 直连路径（execute_code_with_protection）execution_id 空串分支
- cause 链 stderr 提取 helper（extract_stderr_from_cause_chain）双分支：
  主分支 = 382 自定义 cause 属性单跳到 313；次分支 = 389 __cause__ 链

TDD 红→绿：本文件先于 decorator 填充实现（Subtask 3.4）。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.sandbox_security_decorator import (
    SandboxSecurityDecorator,
    extract_stderr_from_cause_chain,
)
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.events.sandbox_events import SandboxExecutionFailed
from src.domain.exceptions import (
    ExecutionError,
    LLMAPIError,
    ToolExecutionFailedError,
    ToolExecutionRetryExhaustedError,
    ToolResultValidationError,
)


class _RecordingPublisher:
    """记录式事件发布器（EventPublisher Protocol 兼容形态——publish 返回 PublishResult）."""

    def __init__(self) -> None:
        self.published: list = []

    async def publish(self, event) -> "PublishResult":
        """记录事件并返回成功结果."""
        self.published.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


def _make_313(stderr: str = "Traceback ... ValueError: bad", exit_code: int = 1) -> ExecutionError:
    """构造内层执行失败异常（Task 3 增强形态）."""
    return ExecutionError("execution failed", stderr=stderr, exit_code=exit_code)


def _make_382(inner: ExecutionError, execution_id: str | None = None) -> ToolExecutionFailedError:
    """构造外层 382（引擎兜底包装形态——自定义 cause 属性）."""
    return ToolExecutionFailedError(
        execution_id=execution_id or str(uuid.uuid4()),
        tool_id=str(uuid.uuid4()),
        stage="EXECUTION",
        cause=inner,
    )


def _make_decorator(publisher: _RecordingPublisher) -> SandboxSecurityDecorator:
    """构造仅持有 publisher 的装饰器实例（事件发布路径直测）."""
    ssd = object.__new__(SandboxSecurityDecorator)
    ssd._event_publisher = publisher
    return ssd


class TestEventFieldPopulation:
    """SandboxExecutionFailed 事件 execution_id/stderr 填充（:132-137 清偿）."""

    @pytest.mark.asyncio
    async def test_event_filled_from_outer_and_inner_context(self) -> None:
        """execution_id 取外层 382 context；stderr 取内层 313 context."""
        publisher = _RecordingPublisher()
        ssd = _make_decorator(publisher)
        inner = _make_313()
        outer = _make_382(inner, execution_id=str(uuid.uuid4()))

        await ssd._publish_execution_failed("sess-1", inner, outer_exc=outer)

        assert len(publisher.published) == 1
        event = publisher.published[0]
        assert isinstance(event, SandboxExecutionFailed)
        assert event.execution_id == outer.context["execution_id"]
        assert "ValueError: bad" in event.stderr

    @pytest.mark.asyncio
    async def test_direct_protection_path_execution_id_empty(self) -> None:
        """直连路径（execute_code_with_protection）无聚合根——execution_id 保持空串."""
        publisher = _RecordingPublisher()
        ssd = _make_decorator(publisher)
        inner = _make_313()

        # 直连路径无外层异常（outer_exc 缺省 None）
        await ssd._publish_execution_failed("sess-2", inner)

        event = publisher.published[0]
        assert event.execution_id == ""
        assert "ValueError: bad" in event.stderr

    @pytest.mark.asyncio
    async def test_stderr_missing_inner_falls_back_to_empty(self) -> None:
        """内层 313 无 stderr（旧形态异常）——事件 stderr 空串不炸."""
        publisher = _RecordingPublisher()
        ssd = _make_decorator(publisher)
        inner = ExecutionError("legacy failure without stderr")

        await ssd._publish_execution_failed("sess-3", inner, outer_exc=None)

        event = publisher.published[0]
        assert event.stderr == ""

    @pytest.mark.asyncio
    async def test_execute_path_publishes_with_outer_context(self) -> None:
        """execute() 主路径：except 块传外层异常——事件经真实路径填充."""
        publisher = _RecordingPublisher()
        inner = _make_313(stderr="Traceback ... KeyError: 'k'")
        outer = _make_382(inner)

        wrapped = MagicMock()
        wrapped.execute = AsyncMock(side_effect=outer)
        ssd = SandboxSecurityDecorator(
            wrapped=wrapped,
            sandbox=AsyncMock(),
            event_publisher=publisher,
        )
        context = MagicMock()
        context.extensions = {}

        from datetime import UTC, datetime

        from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
        from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall

        now = datetime.now(UTC)
        tool = Tool(
            tool_id=uuid.uuid4(),
            name="t",
            description="d",
            category=ToolCategory.ANALYSIS,
            input_schema={},
            output_schema={},
            status=ToolStatus.ACTIVE,
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )
        ctx = ExecutionContext(tenant_id=uuid.uuid4())
        tool_call = ToolCall(tool_id=tool.tool_id, arguments={}, tenant_id=ctx.tenant_id)

        with pytest.raises(ToolExecutionFailedError):
            await ssd.execute(tool.tool_id, tool, tool_call, ctx)

        events = [e for e in publisher.published if isinstance(e, SandboxExecutionFailed)]
        assert events, "主路径应发布 SandboxExecutionFailed"
        assert "KeyError: 'k'" in events[-1].stderr
        assert events[-1].execution_id == outer.context["execution_id"]


class TestExtractStderrFromCauseChain:
    """cause 链 stderr 提取 helper（双分支——Dev Notes 浮现路径）."""

    def test_main_path_custom_cause_attribute(self) -> None:
        """主分支：382 自定义 cause 属性单跳到 313——提取 stderr."""
        inner = _make_313(stderr="Traceback ... ZeroDivisionError: division by zero")
        outer = _make_382(inner)
        assert "ZeroDivisionError" in extract_stderr_from_cause_chain(outer)

    def test_secondary_path_dunder_cause_chain(self) -> None:
        """次分支：389 __cause__ 链经 383 到 LLM 错误——无 stderr 返回空串."""
        llm_err = LLMAPIError("connection reset")
        retry_exc = ToolExecutionRetryExhaustedError(message="exhausted", execution_id="e", tool_id="t", cause=llm_err)
        outer = ToolResultValidationError(
            message="exhausted",
            tool_id="t",
            execution_id=str(uuid.uuid4()),
            reason="llm transient",
            schema_violations=[],
        )
        try:
            raise outer from retry_exc
        except ToolResultValidationError as chained:
            assert extract_stderr_from_cause_chain(chained) == ""

    def test_dunder_chain_reaching_execution_error(self) -> None:
        """__cause__ 链到达 ExecutionError（raise from 形态）也能提取."""
        inner = _make_313(stderr="Traceback ... IndexError: list index out of range")
        wrapper = RuntimeError("wrapper")
        try:
            raise wrapper from inner
        except RuntimeError as chained:
            assert "IndexError" in extract_stderr_from_cause_chain(chained)

    def test_direct_execution_error(self) -> None:
        """直接传入 ExecutionError（自身即链头）也能提取."""
        inner = _make_313()
        assert "ValueError: bad" in extract_stderr_from_cause_chain(inner)

    def test_no_execution_error_returns_empty(self) -> None:
        """链上无 ExecutionError 族——返回空串."""
        assert extract_stderr_from_cause_chain(LLMAPIError("x")) == ""

    def test_cycle_safe(self) -> None:
        """环状 cause 链不死循环（seen 防护——_unwrap_sandbox_error 同款）."""
        a = RuntimeError("a")
        b = RuntimeError("b")
        a.__cause__ = b
        b.__cause__ = a
        assert extract_stderr_from_cause_chain(a) == ""
