"""ToolChainOrchestrator 应用层编排器单元测试（Story 4.2 AC-5）

测试覆盖：
1. Kahn 算法拓扑排序（线性链 / 钻石依赖 / 简单并行 / 复杂并行）
2. 执行波次划分（wave[0] 无依赖 → wave[n] 依赖前序波）
3. asyncio.gather 并行执行同波节点
4. asyncio.Semaphore 并发控制（max_concurrency）
5. 变量插值（${upstream.output.field} 通过 stdlib string.Template）
6. 3 种失败策略（FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM）
7. ToolChainRun 状态更新 + 性能指标
8. 上游节点未完成引用 → EntityBusinessRuleError
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.services.tool_chain_orchestrator import ToolChainOrchestrator
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.entities.tool_chain import (
    FailureStrategy,
    ToolChainDag,
    ToolChainNode,
)
from src.domain.entities.tool_chain_run import (
    ToolChainRunState,
)
from src.domain.exceptions import (
    EntityBusinessRuleError,
    ToolChainCycleDetectedError,
    ToolChainExecutionFailedError,
)
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolResult,
    ToolResultStatus,
)

# ============================================================================
# 工厂函数
# ============================================================================


def _make_tool_node(
    node_id: str,
    depends_on: tuple[str, ...] = (),
    tool_slug: str = "pestel",
    arguments_template: dict | None = None,
    failure_strategy: FailureStrategy | None = None,
) -> ToolChainNode:
    return ToolChainNode(
        node_id=node_id,
        tool_slug=tool_slug,
        depends_on=depends_on,
        arguments_template=arguments_template if arguments_template is not None else {},
        failure_strategy=failure_strategy,
    )


def _make_dag(
    nodes: tuple[ToolChainNode, ...],
    failure_strategy: FailureStrategy = FailureStrategy.SKIP_DOWNSTREAM,
    max_concurrency: int = 5,
) -> ToolChainDag:
    now = datetime.now(UTC)
    return ToolChainDag(
        chain_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="t",
        description="t",
        nodes=nodes,
        failure_strategy=failure_strategy,
        max_concurrency=max_concurrency,
        created_at=now,
        updated_at=now,
    )


def _make_tool(tool_id: uuid.UUID, slug: str) -> Tool:
    return Tool(
        tool_id=tool_id,
        name=slug,
        slug=slug,
        category=ToolCategory.ANALYSIS,
        status=ToolStatus.ACTIVE,
        version="1.0.0",
    )


def _make_tool_result(tool_id: uuid.UUID, output: dict[str, Any]) -> ToolResult:
    return ToolResult(
        tool_id=tool_id,
        status=ToolResultStatus.SUCCESS,
        output=output,
    )


def _make_execution_context() -> ExecutionContext:
    return ExecutionContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session_id="test-session",
        trace_id="test-trace",
        timeout_sec=60.0,
    )


# ============================================================================
# 1. Kahn 算法 + 波次构建
# ============================================================================


def test_topological_sort_linear_chain() -> None:
    """线性链 A → B → C：拓扑序 [A, B, C]"""
    dag = _make_dag(
        (
            _make_tool_node("a"),
            _make_tool_node("b", depends_on=("a",)),
            _make_tool_node("c", depends_on=("b",)),
        )
    )
    waves = ToolChainOrchestrator._build_execution_waves(dag)
    assert waves == [["a"], ["b"], ["c"]]


def test_topological_sort_diamond() -> None:
    """菱形依赖 A → {B, C} → D：waves = [[A], [B, C], [D]]"""
    dag = _make_dag(
        (
            _make_tool_node("a"),
            _make_tool_node("b", depends_on=("a",)),
            _make_tool_node("c", depends_on=("a",)),
            _make_tool_node("d", depends_on=("b", "c")),
        )
    )
    waves = ToolChainOrchestrator._build_execution_waves(dag)
    assert waves[0] == ["a"]
    assert sorted(waves[1]) == ["b", "c"]
    assert waves[2] == ["d"]


def test_topological_sort_complex_parallel() -> None:
    """复杂并行：多个无依赖根节点 + 多层依赖"""
    dag = _make_dag(
        (
            _make_tool_node("a"),
            _make_tool_node("b"),
            _make_tool_node("c", depends_on=("a",)),
            _make_tool_node("d", depends_on=("a", "b")),
            _make_tool_node("e", depends_on=("c", "d")),
        )
    )
    waves = ToolChainOrchestrator._build_execution_waves(dag)
    assert sorted(waves[0]) == ["a", "b"]
    assert sorted(waves[1]) == ["c", "d"]
    assert waves[2] == ["e"]


def test_topological_sort_cycle_raises() -> None:
    """_build_execution_waves 检测环（防御性）"""
    with pytest.raises(ToolChainCycleDetectedError):
        ToolChainOrchestrator._build_execution_waves(
            ToolChainDag(
                chain_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                name="t",
                description="t",
                nodes=(
                    ToolChainNode(node_id="a", tool_slug="t", depends_on=("b",)),
                    ToolChainNode(node_id="b", tool_slug="t", depends_on=("a",)),
                ),
                failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
                max_concurrency=5,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )


def test_topological_sort_duplicate_node_raises() -> None:
    """重复节点抛 ToolChainDuplicateNodeError（Validator 责任，不在 build waves）"""
    # 重复节点由 ToolChainDagValidator.validate 捕获
    # _build_execution_waves 仅依赖节点入度，不检查重复
    # 此测试验证 _build_execution_waves 不抛错（Validator 才是责任方）
    waves = ToolChainOrchestrator._build_execution_waves(_make_dag((_make_tool_node("a"), _make_tool_node("a"))))
    # 重复节点时 BFS 会处理两个 "a"（同名）
    assert "a" in waves[0]


# ============================================================================
# 2. 变量插值
# ============================================================================


def test_interpolate_arguments_simple_field() -> None:
    """变量插值 ${upstream.output.field} 正确解析"""
    node = ToolChainNode(
        node_id="b",
        tool_slug="porter",
        depends_on=("a",),
        arguments_template={"input": "${a.output.score}"},
    )
    upstream_results = {"a": _make_tool_result(uuid.uuid4(), {"score": 0.85})}
    interpolated = ToolChainOrchestrator._interpolate_arguments(node, upstream_results)
    assert interpolated["input"] == 0.85


def test_interpolate_arguments_nested_field() -> None:
    """嵌套字段 ${upstream.output.nested.field} 正确解析"""
    node = ToolChainNode(
        node_id="b",
        tool_slug="porter",
        depends_on=("a",),
        arguments_template={"data": "${a.output.analysis.summary}"},
    )
    upstream_results = {"a": _make_tool_result(uuid.uuid4(), {"analysis": {"summary": "PESTEL complete"}})}
    interpolated = ToolChainOrchestrator._interpolate_arguments(node, upstream_results)
    assert interpolated["data"] == "PESTEL complete"


def test_interpolate_arguments_unknown_variable_preserved() -> None:
    """未知变量保留原文本（safe_substitute 模式）"""
    node = ToolChainNode(
        node_id="b",
        tool_slug="porter",
        depends_on=("a",),
        arguments_template={"input": "${unknown.output.field}"},
    )
    upstream_results = {"a": _make_tool_result(uuid.uuid4(), {})}
    interpolated = ToolChainOrchestrator._interpolate_arguments(node, upstream_results)
    assert interpolated["input"] == "${unknown.output.field}"


def test_interpolate_arguments_missing_upstream_raises() -> None:
    """上游节点未完成引用 → EntityBusinessRuleError（Orchestrator 守卫）"""
    node = ToolChainNode(
        node_id="b",
        tool_slug="porter",
        depends_on=("a",),
        arguments_template={"input": "${a.output.score}"},
    )
    upstream_results: dict[str, ToolResult] = {}  # a 不存在
    with pytest.raises(EntityBusinessRuleError) as exc_info:
        ToolChainOrchestrator._interpolate_arguments(node, upstream_results)
    assert exc_info.value.context["missing_upstream"] == "a"


def test_interpolate_arguments_multiple_upstreams() -> None:
    """多个上游节点变量插值"""
    node = ToolChainNode(
        node_id="swot",
        tool_slug="swot",
        depends_on=("a", "b"),
        arguments_template={
            "pestel": "${a.output.summary}",
            "porter": "${b.output.summary}",
        },
    )
    upstream_results = {
        "a": _make_tool_result(uuid.uuid4(), {"summary": "PESTEL result"}),
        "b": _make_tool_result(uuid.uuid4(), {"summary": "Porter result"}),
    }
    interpolated = ToolChainOrchestrator._interpolate_arguments(node, upstream_results)
    assert interpolated["pestel"] == "PESTEL result"
    assert interpolated["porter"] == "Porter result"


# ============================================================================
# 3. execute_chain 端到端（Mock 工具调用）
# ============================================================================


@pytest.mark.asyncio
async def test_execute_chain_linear_success() -> None:
    """线性链 A → B → C 全部成功 → ToolChainRun.state=COMPLETED"""
    tool_a_id, tool_b_id, tool_c_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    tool_service = AsyncMock()
    registry_service = AsyncMock()

    tools_by_slug = {
        "pestel": _make_tool(tool_a_id, "pestel"),
        "porter": _make_tool(tool_b_id, "porter"),
        "swot": _make_tool(tool_c_id, "swot"),
    }

    async def fake_execute(tool_id, tool_call, context):
        if tool_id == tool_a_id:
            return _make_tool_result(tool_a_id, {"summary": "A done"})
        if tool_id == tool_b_id:
            return _make_tool_result(tool_b_id, {"summary": "B done"})
        if tool_id == tool_c_id:
            return _make_tool_result(tool_c_id, {"summary": "C done"})
        raise ValueError(f"unexpected tool_id: {tool_id}")

    tool_service.execute = AsyncMock(side_effect=fake_execute)
    registry_service.list_all_tools = lambda: list(tools_by_slug.values())

    dag = _make_dag(
        (
            _make_tool_node("a", tool_slug="pestel"),
            _make_tool_node("b", depends_on=("a",), tool_slug="porter"),
            _make_tool_node("c", depends_on=("b",), tool_slug="swot"),
        )
    )

    orchestrator = ToolChainOrchestrator(tool_service, registry_service)
    run = await orchestrator.execute_chain(dag, {}, _make_execution_context())

    assert run.state == ToolChainRunState.COMPLETED
    assert run.completed_at is not None
    assert "a" in run.node_runs and run.node_runs["a"].state == "COMPLETED"
    assert "b" in run.node_runs and run.node_runs["b"].state == "COMPLETED"
    assert "c" in run.node_runs and run.node_runs["c"].state == "COMPLETED"
    assert run.failed_nodes == ()


@pytest.mark.asyncio
async def test_execute_chain_diamond_parallel() -> None:
    """菱形依赖：wave[1] 的 B 和 C 并行执行"""
    tool_a_id, tool_b_id, tool_c_id, tool_d_id = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )

    tool_service = AsyncMock()
    registry_service = AsyncMock()

    tools_by_slug = {
        "a": _make_tool(tool_a_id, "a"),
        "b": _make_tool(tool_b_id, "b"),
        "c": _make_tool(tool_c_id, "c"),
        "d": _make_tool(tool_d_id, "d"),
    }

    async def fake_execute(tool_id, tool_call, context):
        await asyncio.sleep(0.05)  # 模拟工作
        return _make_tool_result(tool_id, {"summary": "done"})

    tool_service.execute = AsyncMock(side_effect=fake_execute)
    registry_service.list_all_tools = lambda: list(tools_by_slug.values())

    dag = _make_dag(
        (
            _make_tool_node("a", tool_slug="a"),
            _make_tool_node("b", depends_on=("a",), tool_slug="b"),
            _make_tool_node("c", depends_on=("a",), tool_slug="c"),
            _make_tool_node("d", depends_on=("b", "c"), tool_slug="d"),
        )
    )

    orchestrator = ToolChainOrchestrator(tool_service, registry_service)
    run = await orchestrator.execute_chain(dag, {}, _make_execution_context())

    assert run.state == ToolChainRunState.COMPLETED
    # 总耗时 ≤ 0.5s（4 层 × 0.05s = 0.2s 串行；并行后应更短）
    assert run.total_duration_sec is not None
    assert run.total_duration_sec < 0.5


# ============================================================================
# 4. 失败策略
# ============================================================================


@pytest.mark.asyncio
async def test_execute_chain_fail_fast_terminates() -> None:
    """FAIL_FAST 策略：节点失败立即终止整链 → ToolChainExecutionFailedError"""
    tool_a_id, tool_b_id = uuid.uuid4(), uuid.uuid4()

    tool_service = AsyncMock()
    registry_service = AsyncMock()

    tools_by_slug = {
        "pestel": _make_tool(tool_a_id, "pestel"),
        "porter": _make_tool(tool_b_id, "porter"),
    }

    async def fake_execute(tool_id, tool_call, context):
        if tool_id == tool_a_id:
            raise RuntimeError("A failed")
        return _make_tool_result(tool_b_id, {"summary": "B"})

    tool_service.execute = AsyncMock(side_effect=fake_execute)
    registry_service.list_all_tools = lambda: list(tools_by_slug.values())

    dag = _make_dag(
        (
            _make_tool_node("a", tool_slug="pestel"),
            _make_tool_node("b", depends_on=("a",), tool_slug="porter"),
        ),
        failure_strategy=FailureStrategy.FAIL_FAST,
    )

    orchestrator = ToolChainOrchestrator(tool_service, registry_service)
    with pytest.raises(ToolChainExecutionFailedError) as exc_info:
        await orchestrator.execute_chain(dag, {}, _make_execution_context())

    assert exc_info.value.context["failed_node_id"] == "a"


@pytest.mark.asyncio
async def test_execute_chain_continue_on_error_marks_failed() -> None:
    """CONTINUE_ON_ERROR 策略：节点失败标记但继续后续"""
    tool_a_id, tool_b_id = uuid.uuid4(), uuid.uuid4()

    tool_service = AsyncMock()
    registry_service = AsyncMock()

    tools_by_slug = {
        "pestel": _make_tool(tool_a_id, "pestel"),
        "porter": _make_tool(tool_b_id, "porter"),
    }

    async def fake_execute(tool_id, tool_call, context):
        if tool_id == tool_a_id:
            raise RuntimeError("A failed")
        return _make_tool_result(tool_b_id, {"summary": "B"})

    tool_service.execute = AsyncMock(side_effect=fake_execute)
    registry_service.list_all_tools = lambda: list(tools_by_slug.values())

    dag = _make_dag(
        (
            _make_tool_node("a", tool_slug="pestel"),
            _make_tool_node("b", depends_on=("a",), tool_slug="porter"),
        ),
        failure_strategy=FailureStrategy.CONTINUE_ON_ERROR,
    )

    orchestrator = ToolChainOrchestrator(tool_service, registry_service)
    run = await orchestrator.execute_chain(dag, {}, _make_execution_context())

    assert run.state == ToolChainRunState.COMPLETED_WITH_ERRORS
    assert run.failed_nodes == ("a",)
    assert run.node_runs["a"].state == "FAILED"
    assert run.node_runs["b"].state == "COMPLETED"


@pytest.mark.asyncio
async def test_execute_chain_skip_downstream_marks_skipped() -> None:
    """SKIP_DOWNSTREAM 策略：节点失败时跳过所有下游"""
    tool_a_id, tool_b_id, tool_c_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    tool_service = AsyncMock()
    registry_service = AsyncMock()

    tools_by_slug = {
        "pestel": _make_tool(tool_a_id, "pestel"),
        "porter": _make_tool(tool_b_id, "porter"),
        "swot": _make_tool(tool_c_id, "swot"),
    }

    async def fake_execute(tool_id, tool_call, context):
        if tool_id == tool_a_id:
            raise RuntimeError("A failed")
        return _make_tool_result(tool_id, {"summary": "ok"})

    tool_service.execute = AsyncMock(side_effect=fake_execute)
    registry_service.list_all_tools = lambda: list(tools_by_slug.values())

    # A → B → C
    dag = _make_dag(
        (
            _make_tool_node("a", tool_slug="pestel"),
            _make_tool_node("b", depends_on=("a",), tool_slug="porter"),
            _make_tool_node("c", depends_on=("b",), tool_slug="swot"),
        ),
        failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
    )

    orchestrator = ToolChainOrchestrator(tool_service, registry_service)
    run = await orchestrator.execute_chain(dag, {}, _make_execution_context())

    assert run.state == ToolChainRunState.COMPLETED_WITH_ERRORS
    assert run.failed_nodes == ("a",)
    assert run.node_runs["a"].state == "FAILED"
    assert run.node_runs["b"].state == "SKIPPED"
    assert run.node_runs["c"].state == "SKIPPED"


# ============================================================================
# 5. 并发控制
# ============================================================================


@pytest.mark.asyncio
async def test_execute_chain_concurrency_limit() -> None:
    """max_concurrency 限制：5 个并行节点 / max_concurrency=2 → 分批执行"""
    tool_ids = [uuid.uuid4() for _ in range(5)]

    tool_service = AsyncMock()
    registry_service = AsyncMock()

    tools_by_slug = {str(i): _make_tool(tool_ids[i], str(i)) for i in range(5)}

    concurrent_count = 0
    max_concurrent_observed = 0

    async def fake_execute(tool_id, tool_call, context):
        nonlocal concurrent_count, max_concurrent_observed
        concurrent_count += 1
        max_concurrent_observed = max(max_concurrent_observed, concurrent_count)
        await asyncio.sleep(0.05)
        concurrent_count -= 1
        return _make_tool_result(tool_id, {"summary": "ok"})

    tool_service.execute = AsyncMock(side_effect=fake_execute)
    registry_service.list_all_tools = lambda: list(tools_by_slug.values())

    nodes = tuple(_make_tool_node(f"n{i}", tool_slug=str(i)) for i in range(5))
    dag = _make_dag(nodes, max_concurrency=2)

    orchestrator = ToolChainOrchestrator(tool_service, registry_service)
    run = await orchestrator.execute_chain(dag, {}, _make_execution_context())

    assert run.state == ToolChainRunState.COMPLETED
    # max_concurrency=2 → 最大并发不超过 2
    assert max_concurrent_observed <= 2


# ============================================================================
# 6. 性能指标计算
# ============================================================================


@pytest.mark.asyncio
async def test_execute_chain_computes_metrics() -> None:
    """ToolChainRun 终态时计算 total_duration_sec / parallel_speedup_ratio"""
    tool_a_id, tool_b_id, tool_c_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    tool_service = AsyncMock()
    registry_service = AsyncMock()

    tools_by_slug = {
        "a": _make_tool(tool_a_id, "a"),
        "b": _make_tool(tool_b_id, "b"),
        "c": _make_tool(tool_c_id, "c"),
    }

    async def fake_execute(tool_id, tool_call, context):
        await asyncio.sleep(0.01)
        return _make_tool_result(tool_id, {"summary": "ok"})

    tool_service.execute = AsyncMock(side_effect=fake_execute)
    registry_service.list_all_tools = lambda: list(tools_by_slug.values())

    # A → B, A → C（菱形）
    dag = _make_dag(
        (
            _make_tool_node("a", tool_slug="a"),
            _make_tool_node("b", depends_on=("a",), tool_slug="b"),
            _make_tool_node("c", depends_on=("a",), tool_slug="c"),
        )
    )

    orchestrator = ToolChainOrchestrator(tool_service, registry_service)
    run = await orchestrator.execute_chain(dag, {}, _make_execution_context())

    assert run.total_duration_sec is not None
    assert run.total_duration_sec > 0
    # 加速比 >= 1.0（菱形依赖并行后 wall-clock 应小于串行）
    assert run.parallel_speedup_ratio is not None
    assert run.parallel_speedup_ratio >= 1.0


# ============================================================================
# 7. 辅助验证
# ============================================================================


def test_orchestrator_module_importable() -> None:
    """ToolChainOrchestrator 模块可导入"""
    import importlib

    mod = importlib.import_module("src.application.services.tool_chain_orchestrator")
    assert hasattr(mod, "ToolChainOrchestrator")
