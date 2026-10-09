"""Story 4.7: 引擎 validation_feedback_hints prompt 读取单元测试.

覆盖 `validation_feedback_hints` 扩展键读取并拼入 Think/Code prompt
（Subtask 0.12 per-stage 消费映射：Code stage 必消费 suggested_fix +
prior_attempts + stderr_excerpt + 禁止重复指令；Think stage 消费 case_summaries
（含负样本提示）+ stderr 摘要；schema_violations → Code/Validate 两 stage）、
无 hints 零行为变化、`__init__` 签名不变（4.4 AC-7.4 保护）。

TDD 红→绿：本文件先于引擎 prompt 构建扩展实现（Subtask 6.1）。
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall

_TENANT = uuid.uuid4()
_TOOL_ID = uuid.uuid4()

_HINTS = {
    "stderr_excerpt": "Traceback ... KeyError: 'data'",
    "schema_violations": [{"path": "result", "expected": "^OK_", "message": "mismatch"}],
    "case_summaries": ["历史配方：改前缀为 OK_"],
    "prior_attempts": [{"attempt_no": 1, "detail": "retry_failed", "stderr_excerpt": "err", "suggested_fix_excerpt": "方案A"}],
    "suggested_fix": "方案B：重构输出结构",
}


def _make_tool() -> Tool:
    """构造测试工具（宽松 schema）."""
    now = datetime.now(UTC)
    return Tool(
        tool_id=_TOOL_ID,
        name="swot-analysis",
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema={},
        output_schema={"type": "object"},
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


def _make_engine(llm: AsyncMock, sandbox: AsyncMock) -> ToolExecutionEngine:
    """构造真实引擎（白名单 + 零退避）。"""
    from src.application.services.retry_helpers import RetryPolicy
    from src.domain.exceptions import LLMAPIError, LLMResponseError, TimeoutError

    return ToolExecutionEngine(
        llm_client=llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(
            retryable_exceptions=(LLMAPIError, LLMResponseError, TimeoutError),
            initial_delay_sec=0,
            max_delay_sec=0,
        ),
    )


def _make_llm() -> AsyncMock:
    """录制式 LLM（记录全部 structured_generate prompt）."""
    llm = AsyncMock()
    prompts: list[str] = []

    async def _structured(prompt: str, **kwargs: Any) -> str:
        prompts.append(prompt)
        if prompt.startswith("为工具"):
            return "plan-1"
        if prompt.startswith("基于以下计划"):
            return "print('result')"
        return "validation-ok"

    llm.structured_generate = AsyncMock(side_effect=_structured)
    llm.prompts = prompts
    return llm


def _make_sandbox() -> AsyncMock:
    """成功沙箱."""
    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock()
    sandbox.stop_container = AsyncMock()

    async def _execute(session_id: str, code: str, timeout_sec: float | None = None) -> dict:
        if code.startswith("# Observe"):
            return {"status": "ok", "output": "observed"}
        return {"status": "ok", "output": "OK_result"}

    sandbox.execute_code = AsyncMock(side_effect=_execute)
    return sandbox


async def _run_engine(engine: ToolExecutionEngine, extensions: dict[str, Any] | None = None) -> Any:
    """执行引擎五阶段（全成功链）。"""
    ctx = ExecutionContext(tenant_id=_TENANT, extensions=extensions or {})
    tool_call = ToolCall(tool_id=_TOOL_ID, arguments={"topic": "t"}, tenant_id=_TENANT)
    return await engine.execute(_TOOL_ID, _make_tool(), tool_call, ctx)


class TestEngineInitSignatureUnchanged:
    """4.4 AC-7.4 保护：__init__ 签名不变."""

    def test_init_signature_stable(self) -> None:
        """构造器仍为 4 参（llm_client/sandbox/retry_policy/tool_execution_repository）."""
        sig = inspect.signature(ToolExecutionEngine.__init__)
        params = list(sig.parameters)
        assert params == ["self", "llm_client", "sandbox", "retry_policy", "tool_execution_repository"]


class TestEngineHintsConsumption:
    """hints per-stage 消费（Subtask 0.12 定稿映射——按各 stage 键集断言）."""

    @pytest.mark.asyncio
    async def test_code_stage_consumes_fix_keys(self) -> None:
        """Code stage 必消费 suggested_fix + prior_attempts（含方案摘要）+
        stderr_excerpt + 禁止重复指令（Reflexion 反馈在作者层不断链）."""
        llm = _make_llm()
        engine = _make_engine(llm, _make_sandbox())
        await _run_engine(engine, {"validation_feedback_hints": _HINTS})
        code_prompts = [p for p in llm.prompts if p.startswith("基于以下计划")]
        assert code_prompts, "应有 Code prompt"
        code_prompt = code_prompts[-1]
        assert "方案B：重构输出结构" in code_prompt, "Code 须消费 suggested_fix"
        assert "方案A" in code_prompt, "Code 须消费 prior_attempts 方案摘要（R8-1）"
        assert "KeyError" in code_prompt, "Code 须消费 stderr_excerpt"
        assert "禁止重复" in code_prompt, "Code 须含禁止重复指令"

    @pytest.mark.asyncio
    async def test_think_stage_consumes_case_summaries_and_stderr(self) -> None:
        """Think stage 消费 case_summaries（含负样本提示）+ stderr 摘要."""
        llm = _make_llm()
        engine = _make_engine(llm, _make_sandbox())
        await _run_engine(engine, {"validation_feedback_hints": _HINTS})
        think_prompts = [p for p in llm.prompts if p.startswith("为工具")]
        assert think_prompts
        think_prompt = think_prompts[-1]
        assert "历史配方" in think_prompt, "Think 须消费 case_summaries"
        assert "KeyError" in think_prompt, "Think 须消费 stderr 摘要"

    @pytest.mark.asyncio
    async def test_code_stage_consumes_negative_hint(self) -> None:
        """负样本提示（case_summaries 携带）经 Think/Code 可感知."""
        hints = {**_HINTS, "case_summaries": ["注意：此签名已观测到 2 次不可行"]}
        llm = _make_llm()
        engine = _make_engine(llm, _make_sandbox())
        await _run_engine(engine, {"validation_feedback_hints": hints})
        think_prompt = [p for p in llm.prompts if p.startswith("为工具")][-1]
        assert "不可行" in think_prompt

    @pytest.mark.asyncio
    async def test_no_hints_zero_behavior_change(self) -> None:
        """无 hints 时 prompt 与 4.4 既有形态一致（零行为变化）."""
        llm = _make_llm()
        engine = _make_engine(llm, _make_sandbox())
        await _run_engine(engine)
        think_prompt = [p for p in llm.prompts if p.startswith("为工具")][-1]
        code_prompt = [p for p in llm.prompts if p.startswith("基于以下计划")][-1]
        assert "历史配方" not in think_prompt
        assert "禁止重复" not in code_prompt
        assert think_prompt.startswith("为工具 swot-analysis 规划执行步骤")
        assert code_prompt.startswith("基于以下计划生成代码: ")
