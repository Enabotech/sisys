"""Story 4.1a: ToolExecutionEngine 单元测试

TDD 测试覆盖：
- 五阶段端口映射（Think/Code/Execute/Observe/Validate）
- RetryPolicy 重试机制
- 沙箱 Session 生命周期
- 证据包组装
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.services.tool_execution_engine import (
    RetryPolicy,
    ToolExecutionEngine,
)
from src.domain.entities.tool import Tool, ToolCategory
from src.domain.exceptions import (
    LLMAPIError,
    ToolExecutionRetryExhaustedError,
)
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResultStatus,
)


def _make_tool(**kwargs) -> Tool:
    defaults = {
        "tool_id": uuid.uuid4(),
        "name": "Test Tool",
        "category": ToolCategory.ANALYSIS,
        "rule_version": "BLM-v3.2",
        "reliability_score": 0.85,
        "version": "1.0.0",
    }
    defaults.update(kwargs)
    return Tool(**defaults)


def _make_context(**kwargs) -> ExecutionContext:
    defaults = {
        "tenant_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "session_id": "sess-1",
        "trace_id": "trace-1",
        "timeout_sec": 60.0,
    }
    defaults.update(kwargs)
    return ExecutionContext(**defaults)


def _make_llm_mock() -> AsyncMock:
    """构造 LLMClientPort mock"""
    mock = AsyncMock()
    mock.structured_generate = AsyncMock(return_value="mock_response")
    return mock


def _make_sandbox_mock() -> AsyncMock:
    """构造 SandboxExecutor mock"""
    mock = AsyncMock()
    mock.start_container = AsyncMock()
    mock.execute_code = AsyncMock(return_value={"status": "ok", "output": "result_data"})
    mock.stop_container = AsyncMock()
    return mock


class TestToolExecutionEngineFiveStage:
    """五阶段端口映射测试"""

    @pytest.mark.asyncio
    async def test_think_stage_invokes_llm(self) -> None:
        """Think 阶段调用 LLM.structured_generate"""
        llm = _make_llm_mock()
        sandbox = _make_sandbox_mock()
        engine = ToolExecutionEngine(llm, sandbox)

        tool = _make_tool()
        tool_call = ToolCall(tool_id=tool.tool_id, arguments={"x": 1})
        context = _make_context()

        await engine.execute(tool.tool_id, tool, tool_call, context)

        # 验证 LLM.structured_generate 被调用（Think/Code/Validate 三阶段）
        assert llm.structured_generate.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_and_observe_stage_invoke_sandbox(self) -> None:
        """Execute + Observe 阶段调用 sandbox.execute_code"""
        llm = _make_llm_mock()
        sandbox = _make_sandbox_mock()
        engine = ToolExecutionEngine(llm, sandbox)

        tool = _make_tool()
        tool_call = ToolCall(tool_id=tool.tool_id, arguments={})
        context = _make_context()

        await engine.execute(tool.tool_id, tool, tool_call, context)

        # execute_code 被调用 2 次（Execute + Observe）
        assert sandbox.execute_code.call_count == 2
        # start_container + stop_container 各 1 次
        assert sandbox.start_container.call_count == 1
        assert sandbox.stop_container.call_count == 1

    @pytest.mark.asyncio
    async def test_successful_execution_returns_tool_result(self) -> None:
        """成功执行返回 ToolResult.status=success"""
        llm = _make_llm_mock()
        sandbox = _make_sandbox_mock()
        engine = ToolExecutionEngine(llm, sandbox)

        tool = _make_tool()
        tool_call = ToolCall(tool_id=tool.tool_id, arguments={})
        context = _make_context()

        result = await engine.execute(tool.tool_id, tool, tool_call, context)

        assert result.status == ToolResultStatus.SUCCESS
        assert result.tool_id == tool.tool_id
        assert result.evidence_package is not None

    @pytest.mark.asyncio
    async def test_sandbox_cleanup_on_completion(self) -> None:
        """执行完成后清理沙箱 session"""
        llm = _make_llm_mock()
        sandbox = _make_sandbox_mock()
        engine = ToolExecutionEngine(llm, sandbox)

        tool = _make_tool()
        tool_call = ToolCall(tool_id=tool.tool_id, arguments={})
        context = _make_context(session_id="sess-cleanup-test")

        await engine.execute(tool.tool_id, tool, tool_call, context)

        # stop_container 被调用清理
        sandbox.stop_container.assert_called_with("sess-cleanup-test")


class TestRetryPolicy:
    """RetryPolicy 重试测试"""

    @pytest.mark.asyncio
    async def test_retry_on_llm_api_error(self) -> None:
        """LLM 错误触发重试"""
        llm = _make_llm_mock()
        # 第一次调用失败，后续调用成功
        call_count = {"n": 0}

        async def mock_generate(*args: Any, **kwargs: Any) -> Any:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise LLMAPIError("api error")
            return "success_response"

        llm.structured_generate = mock_generate
        sandbox = _make_sandbox_mock()
        engine = ToolExecutionEngine(
            llm,
            sandbox,
            retry_policy=RetryPolicy(
                max_attempts=3,
                initial_delay_sec=0.01,  # 加速测试
            ),
        )

        tool = _make_tool()
        tool_call = ToolCall(tool_id=tool.tool_id, arguments={})
        context = _make_context()

        result = await engine.execute(tool.tool_id, tool, tool_call, context)
        assert result.status == ToolResultStatus.SUCCESS
        # LLM 被调用 ≥ 2 次（第一次失败 + 重试成功）
        assert call_count["n"] >= 2

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_error(self) -> None:
        """重试耗尽抛 ToolExecutionRetryExhaustedError"""
        llm = _make_llm_mock()
        llm.structured_generate = AsyncMock(side_effect=LLMAPIError("persistent error"))
        sandbox = _make_sandbox_mock()
        engine = ToolExecutionEngine(
            llm,
            sandbox,
            retry_policy=RetryPolicy(
                max_attempts=2,
                initial_delay_sec=0.01,
            ),
        )

        tool = _make_tool()
        tool_call = ToolCall(tool_id=tool.tool_id, arguments={})
        context = _make_context()

        with pytest.raises(ToolExecutionRetryExhaustedError):
            await engine.execute(tool.tool_id, tool, tool_call, context)


class TestEvidencePackageAssembly:
    """证据包组装测试"""

    @pytest.mark.asyncio
    async def test_evidence_package_has_nine_fields(self) -> None:
        """证据包 9 字段完整"""
        llm = _make_llm_mock()
        sandbox = _make_sandbox_mock()
        engine = ToolExecutionEngine(llm, sandbox)

        tool = _make_tool()
        tool_call = ToolCall(tool_id=tool.tool_id, arguments={"x": 1})
        context = _make_context()

        result = await engine.execute(tool.tool_id, tool, tool_call, context)
        ep = result.evidence_package
        assert ep is not None
        # 9 字段全部存在
        assert ep.input_hash != ""
        assert ep.rule_version != ""
        assert ep.plan != ""
        assert ep.code != ""
        assert ep.result != ""
        assert ep.observation != ""
        assert ep.validation != ""

    @pytest.mark.asyncio
    async def test_evidence_package_uses_tool_reliability_score(self) -> None:
        """confidence 来自 Tool.reliability_score"""
        llm = _make_llm_mock()
        sandbox = _make_sandbox_mock()
        engine = ToolExecutionEngine(llm, sandbox)

        tool = _make_tool(reliability_score=0.92)
        tool_call = ToolCall(tool_id=tool.tool_id, arguments={})
        context = _make_context()

        result = await engine.execute(tool.tool_id, tool, tool_call, context)
        assert result.evidence_package is not None
        assert result.evidence_package.confidence == 0.92
