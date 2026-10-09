"""Story 4.7: 编排器 INFEASIBLE 语义修复单元测试（Task 6 循环 E——决策 #14）.

三断言（R6 业界对标定稿——K8s JobFailed condition reason 同型）：
① node state 三值：INFEASIBLE 结果的节点 state=="INFEASIBLE"（非 "FAILED"
   二值折叠——类型元数据在传播链不可抹除，Temporal re-wrap 反模式）
② FAIL_FAST 中断异常 context 含 error_signature 与 enhanced_retry_count
   （从 completed_node_results 的 output 取——cause=None 下的可观测性补全）
③ SKIP_DOWNSTREAM 下游 SKIPPED + 独立分支正常执行（既有行为回归位）

TDD 红→绿：本文件先于编排器三文件修改（Subtask 6.13）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from src.application.services.tool_chain_orchestrator import ToolChainOrchestrator
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.entities.tool_chain import FailureStrategy, ToolChainDag, ToolChainNode
from src.domain.exceptions import ToolChainExecutionFailedError
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolResult,
    ToolResultStatus,
)

_TENANT = uuid.uuid4()


def _make_tool(slug: str) -> Tool:
    """构造测试工具."""
    now = datetime.now(UTC)
    return Tool(
        tool_id=uuid.uuid4(),
        name=slug,
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema={},
        output_schema={},
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        slug=slug,
        created_at=now,
        updated_at=now,
    )


def _infeasible_result(tool_id: uuid.UUID) -> ToolResult:
    """构造 INFEASIBLE 结果（output 携带失败摘要——AC-3 契约形态）."""
    return ToolResult(
        tool_id=tool_id,
        status=ToolResultStatus.INFEASIBLE,
        output={
            "error_signature": "c" * 64,
            "stderr_excerpt": "Traceback ... KeyError: 'data'",
            "enhanced_retry_count": 3,
        },
        retry_count=3,
    )


def _ok_result(tool_id: uuid.UUID) -> ToolResult:
    """构造成功结果."""
    return ToolResult(tool_id=tool_id, status=ToolResultStatus.SUCCESS, output={"result": "OK_x"})


class _StubRegistry:
    """注册表替身（list_all_tools 同步契约——编排器 asyncio.to_thread 调用）."""

    def __init__(self, tools: list[Tool]) -> None:
        self._tools = tools
        self._by_id = {t.tool_id: t for t in tools}

    def list_all_tools(self) -> list[Tool]:
        """全量工具列表."""
        return self._tools

    def get_tool(self, tool_id: uuid.UUID) -> Tool:
        """按 id 查工具."""
        tool = self._by_id.get(tool_id)
        if tool is None:
            from src.domain.exceptions import ToolNotFoundError

            raise ToolNotFoundError(slug=str(tool_id))
        return tool


class _ScriptedExecutionService:
    """执行服务替身（按 slug 分派可编程结果——VFD 结果面模拟）."""

    def __init__(self, results_by_slug: dict[str, ToolResult]) -> None:
        self._results = results_by_slug
        self._tools: dict[uuid.UUID, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册工具（slug→tool_id 映射）."""
        self._tools[tool.tool_id] = tool

    async def execute(self, tool_id: uuid.UUID, tool_call: Any, context: Any) -> ToolResult:
        """按工具分派预置结果."""
        tool = self._tools[tool_id]
        slug: str = tool.slug or ""
        return self._results[slug]


def _make_dag(strategy: str) -> ToolChainDag:
    """构造三节点 DAG：broken → downstream；independent 独立."""
    now = datetime.now(UTC)
    return ToolChainDag(
        chain_id=uuid.uuid4(),
        tenant_id=_TENANT,
        name="infeasible-dag",
        description="4-7 循环 E",
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


class TestNodeStateThreeValued:
    """①node state 三值判定（类型不抹除——决策 #14①）."""

    @pytest.mark.asyncio
    async def test_infeasible_node_state_not_failed(self) -> None:
        """INFEASIBLE 结果的节点 state=="INFEASIBLE"（SKIP_DOWNSTREAM 链不中断可观测）."""
        broken = _make_tool("broken-tool")
        ok = _make_tool("ok-tool")
        registry = _StubRegistry([broken, ok])
        service = _ScriptedExecutionService(
            {"broken-tool": _infeasible_result(broken.tool_id), "ok-tool": _ok_result(ok.tool_id)}
        )
        service.register(broken)
        service.register(ok)
        orchestrator = _orchestrator(service, registry)
        run = await orchestrator.execute_chain(_make_dag("SKIP_DOWNSTREAM"), {}, ExecutionContext(tenant_id=_TENANT))
        assert run.node_runs["broken"].state == "INFEASIBLE"


class TestFailFastContextEnriched:
    """②FAIL_FAST 中断异常 context 含 error_signature 与尝试次数（决策 #14②）."""

    @pytest.mark.asyncio
    async def test_fail_fast_exception_carries_signature_and_count(self) -> None:
        """INFEASIBLE 触发 FAIL_FAST 中断时异常 context 可观测性补全."""
        broken = _make_tool("broken-tool")
        ok = _make_tool("ok-tool")
        registry = _StubRegistry([broken, ok])
        service = _ScriptedExecutionService(
            {"broken-tool": _infeasible_result(broken.tool_id), "ok-tool": _ok_result(ok.tool_id)}
        )
        service.register(broken)
        service.register(ok)
        orchestrator = _orchestrator(service, registry)
        with pytest.raises(ToolChainExecutionFailedError) as exc_info:
            await orchestrator.execute_chain(_make_dag("FAIL_FAST"), {}, ExecutionContext(tenant_id=_TENANT))
        assert "error_signature" in exc_info.value.context
        assert "enhanced_retry_count" in exc_info.value.context
        assert exc_info.value.context["error_signature"] == "c" * 64
        assert exc_info.value.context["enhanced_retry_count"] == 3


class TestSkipDownstreamCompat:
    """③SKIP_DOWNSTREAM 兼容（既有行为回归位——不预期红）."""

    @pytest.mark.asyncio
    async def test_downstream_skipped_independent_completes(self) -> None:
        """下游 SKIPPED + 独立分支 COMPLETED."""
        broken = _make_tool("broken-tool")
        ok = _make_tool("ok-tool")
        registry = _StubRegistry([broken, ok])
        service = _ScriptedExecutionService(
            {"broken-tool": _infeasible_result(broken.tool_id), "ok-tool": _ok_result(ok.tool_id)}
        )
        service.register(broken)
        service.register(ok)
        orchestrator = _orchestrator(service, registry)
        run = await orchestrator.execute_chain(_make_dag("SKIP_DOWNSTREAM"), {}, ExecutionContext(tenant_id=_TENANT))
        assert run.node_runs["downstream"].state == "SKIPPED"
        assert run.node_runs["independent"].state == "COMPLETED"


def _orchestrator(service: Any, registry: Any) -> ToolChainOrchestrator:
    """构造编排器（替身经 cast 注入——Protocol 结构兼容形态）."""
    from typing import cast

    from src.application.ports.tool_execution_service import ToolExecutionServicePort
    from src.application.ports.tool_registry_service import ToolRegistryServicePort

    return ToolChainOrchestrator(
        tool_execution_service=cast(ToolExecutionServicePort, service),
        tool_registry_service=cast(ToolRegistryServicePort, registry),
    )
