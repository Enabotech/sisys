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
    ToolExecutionFailedError,
    ToolExecutionRetryExhaustedError,
    ToolExecutionTimeoutError,
)
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResultStatus,
)


def _make_tool(**kwargs) -> Tool:
    defaults: dict = {
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
    defaults: dict = {
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


class TestFailurePathPersistence:
    """失败路径持久化（R3-3 H1v2：原 6 处失败路径迁移 FAILED 后均不落库——
    list_by_query(state=FAILED) 永远空集，失败可观测性为零）"""

    @staticmethod
    def _make_repo() -> AsyncMock:
        """构造 ToolExecutionRepositoryPort mock（记录 save 调用）"""
        from src.domain.ports.tool_execution_repository import ToolExecutionRepositoryPort

        repo = AsyncMock(spec=ToolExecutionRepositoryPort)
        repo.save = AsyncMock(return_value=None)
        return repo

    @pytest.mark.asyncio
    async def test_sandbox_start_failure_persists_failed_execution(self) -> None:
        """沙箱启动失败 → ToolExecutionFailedError + FAILED 态落库（原死分支：
        IDLE→FAILED 非法迁移抛 243 掩盖预期异常；修复后 PLANNING 前置 + completed_at）"""
        from src.domain.entities.tool_execution import ToolExecutionState

        llm = _make_llm_mock()
        sandbox = _make_sandbox_mock()
        sandbox.start_container = AsyncMock(side_effect=RuntimeError("docker down"))
        repo = self._make_repo()
        engine = ToolExecutionEngine(llm, sandbox, tool_execution_repository=repo)

        with pytest.raises(ToolExecutionFailedError):
            await engine.execute(uuid.uuid4(), _make_tool(), ToolCall(tool_id=uuid.uuid4(), arguments={}), _make_context())

        repo.save.assert_awaited_once()
        saved = repo.save.await_args.args[0]
        assert saved.state == ToolExecutionState.FAILED
        assert saved.completed_at is not None
        assert "sandbox_start_failed" in saved.failure_reason

    @pytest.mark.asyncio
    async def test_retry_exhausted_persists_failed_execution(self) -> None:
        """LLM 持续失败重试耗尽 → FAILED 态 + failure_reason 落库"""
        from src.domain.entities.tool_execution import ToolExecutionState

        llm = _make_llm_mock()
        llm.structured_generate = AsyncMock(side_effect=LLMAPIError("persistent error"))
        sandbox = _make_sandbox_mock()
        repo = self._make_repo()
        engine = ToolExecutionEngine(
            llm, sandbox, retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0.01), tool_execution_repository=repo
        )

        with pytest.raises(ToolExecutionRetryExhaustedError):
            await engine.execute(uuid.uuid4(), _make_tool(), ToolCall(tool_id=uuid.uuid4(), arguments={}), _make_context())

        saved = repo.save.await_args.args[0]
        assert saved.state == ToolExecutionState.FAILED
        assert saved.failure_reason is not None and saved.failure_reason != ""

    @pytest.mark.asyncio
    async def test_completed_timeout_persists_completed_with_reason(self) -> None:
        """COMPLETED 后超预算 → COMPLETED 态 + failure_reason 落库（原该路径
        执行记录完全丢失——save 仅在未超时分支前调用）"""
        from src.domain.entities.tool_execution import ToolExecutionState

        llm = _make_llm_mock()
        sandbox = _make_sandbox_mock()
        repo = self._make_repo()
        # max_total_duration_sec=0：elapsed > 0 恒真，确定性触发超时分支
        engine = ToolExecutionEngine(
            llm, sandbox, retry_policy=RetryPolicy(max_attempts=1, max_total_duration_sec=0), tool_execution_repository=repo
        )

        with pytest.raises(ToolExecutionTimeoutError):
            await engine.execute(uuid.uuid4(), _make_tool(), ToolCall(tool_id=uuid.uuid4(), arguments={}), _make_context())

        saved = repo.save.await_args.args[0]
        assert saved.state == ToolExecutionState.COMPLETED  # 完成但超预算，不回退 FAILED
        assert "timeout" in saved.failure_reason.lower()  # 「完成但超预算」原因已记录

    @pytest.mark.asyncio
    async def test_persist_failure_does_not_mask_original_error(self) -> None:
        """save 自身异常被 best-effort 吞噬——原始 ToolExecutionFailedError 照常传播"""
        from src.domain.ports.tool_execution_repository import ToolExecutionRepositoryPort

        llm = _make_llm_mock()
        sandbox = _make_sandbox_mock()
        sandbox.start_container = AsyncMock(side_effect=RuntimeError("docker down"))
        repo = AsyncMock(spec=ToolExecutionRepositoryPort)
        repo.save = AsyncMock(side_effect=RuntimeError("db down"))
        engine = ToolExecutionEngine(llm, sandbox, tool_execution_repository=repo)

        with pytest.raises(ToolExecutionFailedError):  # 不被 save 的 db down 顶替
            await engine.execute(uuid.uuid4(), _make_tool(), ToolCall(tool_id=uuid.uuid4(), arguments={}), _make_context())
