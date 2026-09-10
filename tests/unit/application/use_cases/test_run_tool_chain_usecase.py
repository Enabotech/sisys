"""RunToolChainUseCase 单元测试（Story 4.2 AC-7）

测试覆盖：
1. 用例编排流程（chain 查询 → Skill 加载 → execute_chain → 事件发布）
2. chain_name 查询通过 Repository.list_by_query
3. Skill 加载（节点级，asyncio.gather 并发）
4. execute_chain 委托 ToolChainService
5. ToolChainExecuted 事件发布（含 chain_run_id / chain_id / failure_strategy）
6. 异常链路：chain_name 不存在 → ToolNotFoundError
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.application.ports.skill_loader import SkillLoaderPort, ToolMetadata
from src.application.ports.tool_chain_service import ToolChainServicePort
from src.application.use_cases.run_tool_chain import RunToolChainUseCase
from src.domain.entities.tool_chain import (
    FailureStrategy,
    ToolChainDag,
    ToolChainNode,
)
from src.domain.entities.tool_chain_run import ToolChainRun, ToolChainRunState
from src.domain.exceptions import ToolChainNotFoundError
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.tool_chain_repository import ToolChainRepositoryPort
from src.domain.value_objects.tool_execution import ExecutionContext


def _make_dag(name: str = "test-chain") -> ToolChainDag:
    now = datetime.now(UTC)
    return ToolChainDag(
        chain_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name=name,
        description="",
        nodes=(
            ToolChainNode(node_id="a", tool_slug="pestel"),
            ToolChainNode(node_id="b", tool_slug="porter", depends_on=("a",)),
        ),
        failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
        max_concurrency=5,
        created_at=now,
        updated_at=now,
    )


def _make_run(state: ToolChainRunState = ToolChainRunState.COMPLETED) -> ToolChainRun:
    started = datetime.now(UTC)
    return ToolChainRun(
        chain_run_id=uuid.uuid4(),
        chain_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        state=state,
        started_at=started,
        completed_at=started,
        failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
        cost_audit={"llm_total_tokens": 100, "parallel_speedup_ratio": 1.5},
    )


def _make_context(tenant_id: uuid.UUID | None = None) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=tenant_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        session_id="s",
        trace_id="t",
    )


# ============================================================================
# 1. 用例编排流程
# ============================================================================


@pytest.mark.asyncio
async def test_execute_full_flow() -> None:
    """完整流程：chain 查询 → Skill 加载 → execute_chain → 事件发布"""
    dag = _make_dag("pestel-porter")
    expected_run = _make_run()

    repo = AsyncMock(spec=ToolChainRepositoryPort)
    repo.list_by_query = AsyncMock(return_value=[dag])

    service = AsyncMock(spec=ToolChainServicePort)
    service.execute_chain = AsyncMock(return_value=expected_run)

    skill_loader = AsyncMock(spec=SkillLoaderPort)
    skill_loader.load_metadata = AsyncMock(
        return_value=ToolMetadata(
            tool_name="PESTEL",
            slug="pestel",
            category="analysis",
            input_schema={},
            output_schema={},
        )
    )

    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish = AsyncMock()

    use_case = RunToolChainUseCase(
        repository=repo,
        service=service,
        skill_loader=skill_loader,
        event_publisher=publisher,
    )

    context = _make_context(tenant_id=dag.tenant_id)
    run = await use_case.execute("pestel-porter", {}, context)

    assert run is expected_run


# ============================================================================
# 2. chain_name 查询
# ============================================================================


@pytest.mark.asyncio
async def test_find_dag_by_name_uses_list_by_query() -> None:
    """chain_name 查询通过 Repository.list_by_query 过滤 name + tenant_id"""
    dag = _make_dag("alpha")
    repo = AsyncMock(spec=ToolChainRepositoryPort)
    repo.list_by_query = AsyncMock(return_value=[dag])

    service = AsyncMock(spec=ToolChainServicePort)
    service.execute_chain = AsyncMock(return_value=_make_run())

    skill_loader = AsyncMock(spec=SkillLoaderPort)
    skill_loader.load_metadata = AsyncMock(
        return_value=ToolMetadata(tool_name="t", slug="t", category="t", input_schema={}, output_schema={})
    )
    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish = AsyncMock()

    use_case = RunToolChainUseCase(
        repository=repo,
        service=service,
        skill_loader=skill_loader,
        event_publisher=publisher,
    )

    context = _make_context(tenant_id=dag.tenant_id)
    await use_case.execute("alpha", {}, context)

    # 验证查询参数
    call_args = repo.list_by_query.await_args
    assert call_args is not None
    query = call_args.args[0]
    assert query.name == "alpha"
    assert query.tenant_id == dag.tenant_id


@pytest.mark.asyncio
async def test_chain_not_found_raises_tool_chain_not_found() -> None:
    """chain_name 不存在抛 ToolChainNotFoundError（EXCEPTION_394，toolchain 子域）"""
    repo = AsyncMock(spec=ToolChainRepositoryPort)
    repo.list_by_query = AsyncMock(return_value=[])

    service = AsyncMock(spec=ToolChainServicePort)
    skill_loader = AsyncMock(spec=SkillLoaderPort)
    publisher = AsyncMock(spec=EventPublisher)

    use_case = RunToolChainUseCase(
        repository=repo,
        service=service,
        skill_loader=skill_loader,
        event_publisher=publisher,
    )

    with pytest.raises(ToolChainNotFoundError):
        await use_case.execute("nonexistent", {}, _make_context())


# ============================================================================
# 3. Skill 加载
# ============================================================================


@pytest.mark.asyncio
async def test_skill_loading_uses_concurrent_gather() -> None:
    """Skill 加载：asyncio.gather 并发预加载节点 metadata"""
    dag = _make_dag("chain")  # 2 个节点
    repo = AsyncMock(spec=ToolChainRepositoryPort)
    repo.list_by_query = AsyncMock(return_value=[dag])

    service = AsyncMock(spec=ToolChainServicePort)
    service.execute_chain = AsyncMock(return_value=_make_run())

    skill_loader = AsyncMock(spec=SkillLoaderPort)
    skill_loader.load_metadata = AsyncMock(
        side_effect=lambda slug: ToolMetadata(
            tool_name=slug,
            slug=slug,
            category="x",
            input_schema={},
            output_schema={},
        )
    )

    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish = AsyncMock()

    use_case = RunToolChainUseCase(
        repository=repo,
        service=service,
        skill_loader=skill_loader,
        event_publisher=publisher,
    )

    context = _make_context(tenant_id=dag.tenant_id)
    await use_case.execute("chain", {}, context)

    # 验证 load_metadata 被调用 2 次（每个节点 tool_slug）
    assert skill_loader.load_metadata.await_count == 2
    call_args_list = skill_loader.load_metadata.await_args_list
    slugs_called = [c.args[0] for c in call_args_list]
    assert "pestel" in slugs_called
    assert "porter" in slugs_called


@pytest.mark.asyncio
async def test_skill_load_failure_logged_but_not_fatal() -> None:
    """Skill 加载失败仅记录日志，不阻塞业务执行"""
    dag = _make_dag("chain")
    repo = AsyncMock(spec=ToolChainRepositoryPort)
    repo.list_by_query = AsyncMock(return_value=[dag])

    service = AsyncMock(spec=ToolChainServicePort)
    service.execute_chain = AsyncMock(return_value=_make_run())

    skill_loader = AsyncMock(spec=SkillLoaderPort)
    skill_loader.load_metadata = AsyncMock(side_effect=RuntimeError("load failed"))

    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish = AsyncMock()

    use_case = RunToolChainUseCase(
        repository=repo,
        service=service,
        skill_loader=skill_loader,
        event_publisher=publisher,
    )

    context = _make_context(tenant_id=dag.tenant_id)
    # 不应抛出异常
    run = await use_case.execute("chain", {}, context)
    assert run is not None


# ============================================================================
# 4. execute_chain 委托
# ============================================================================


@pytest.mark.asyncio
async def test_execute_chain_delegates_to_service() -> None:
    """execute_chain 委托 ToolChainService.execute_chain"""
    dag = _make_dag("chain")
    expected_run = _make_run()

    repo = AsyncMock(spec=ToolChainRepositoryPort)
    repo.list_by_query = AsyncMock(return_value=[dag])

    service = AsyncMock(spec=ToolChainServicePort)
    service.execute_chain = AsyncMock(return_value=expected_run)

    skill_loader = AsyncMock(spec=SkillLoaderPort)
    skill_loader.load_metadata = AsyncMock(
        return_value=ToolMetadata(
            tool_name="t",
            slug="t",
            category="t",
            input_schema={},
            output_schema={},
        )
    )

    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish = AsyncMock()

    use_case = RunToolChainUseCase(
        repository=repo,
        service=service,
        skill_loader=skill_loader,
        event_publisher=publisher,
    )

    context = _make_context(tenant_id=dag.tenant_id)
    await use_case.execute("chain", {"x": 1}, context)

    call_args = service.execute_chain.await_args
    # 使用 kwargs（兼容位置参数）
    if call_args.kwargs:
        assert call_args.kwargs["chain_id"] == dag.chain_id
        assert call_args.kwargs["parameters"] == {"x": 1}
        assert call_args.kwargs["context"] is context
    else:
        assert call_args.args[0] == dag.chain_id
        assert call_args.args[1] == {"x": 1}
        assert call_args.args[2] is context


# ============================================================================
# 5. ToolChainExecuted 事件发布
# ============================================================================


@pytest.mark.asyncio
async def test_publish_tool_chain_executed_event() -> None:
    """ToolChainExecuted 事件发布（含 chain_run_id / chain_id / failure_strategy）"""
    dag = _make_dag("chain")
    run = _make_run(ToolChainRunState.COMPLETED_WITH_ERRORS)

    repo = AsyncMock(spec=ToolChainRepositoryPort)
    repo.list_by_query = AsyncMock(return_value=[dag])

    service = AsyncMock(spec=ToolChainServicePort)
    service.execute_chain = AsyncMock(return_value=run)

    skill_loader = AsyncMock(spec=SkillLoaderPort)
    skill_loader.load_metadata = AsyncMock(
        return_value=ToolMetadata(
            tool_name="t",
            slug="t",
            category="t",
            input_schema={},
            output_schema={},
        )
    )

    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish = AsyncMock()

    use_case = RunToolChainUseCase(
        repository=repo,
        service=service,
        skill_loader=skill_loader,
        event_publisher=publisher,
    )

    context = _make_context(tenant_id=dag.tenant_id)
    await use_case.execute("chain", {}, context)

    # 验证事件已发布
    publisher.publish.assert_awaited_once()
    event = publisher.publish.await_args.args[0]
    assert event.event_type == "ToolChainExecuted"
    assert event.chain_run_id == run.chain_run_id
    assert event.chain_id == run.chain_id
    assert event.tenant_id == run.tenant_id
    assert event.failure_strategy == "SKIP_DOWNSTREAM"
    assert "parallel_speedup_ratio" in event.cost_audit


@pytest.mark.asyncio
async def test_event_publish_failure_does_not_break_flow() -> None:
    """事件发布失败不阻塞业务结果"""
    dag = _make_dag("chain")
    expected_run = _make_run()

    repo = AsyncMock(spec=ToolChainRepositoryPort)
    repo.list_by_query = AsyncMock(return_value=[dag])

    service = AsyncMock(spec=ToolChainServicePort)
    service.execute_chain = AsyncMock(return_value=expected_run)

    skill_loader = AsyncMock(spec=SkillLoaderPort)
    skill_loader.load_metadata = AsyncMock(
        return_value=ToolMetadata(
            tool_name="t",
            slug="t",
            category="t",
            input_schema={},
            output_schema={},
        )
    )

    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish = AsyncMock(side_effect=RuntimeError("publish failed"))

    use_case = RunToolChainUseCase(
        repository=repo,
        service=service,
        skill_loader=skill_loader,
        event_publisher=publisher,
    )

    context = _make_context(tenant_id=dag.tenant_id)
    # 不应抛出异常
    run = await use_case.execute("chain", {}, context)
    assert run is expected_run


# ============================================================================
# 6. 端口注入（六边形约束）
# ============================================================================


def test_use_case_only_uses_port_injection() -> None:
    """RunToolChainUseCase 仅通过端口注入依赖（不导入具体实现）"""
    import ast
    import pathlib

    source = pathlib.Path("src/application/use_cases/run_tool_chain.py").read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                assert not node.module.startswith("src.infrastructure"), f"导入禁止模块: {node.module}"
