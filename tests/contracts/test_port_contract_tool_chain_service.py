"""ToolChainService 端口契约测试（Story 4.2 AC-6）

验证 ToolChainServicePort Protocol 11 维度行为契约：
1. Protocol runtime_checkable 校验
2. async def execute_chain（委托 Orchestrator）
3. async def get_chain_definition（委托 Repository）
4. async def list_chain_definitions（Query Object 模式）
5. 依赖通过端口注入（不导入 infrastructure）
6. ToolNotFoundError 触发
7. execute_chain 委托 Orchestrator 行为
8. get_chain_definition 返回 ToolChainDag 聚合根
9. list_chain_definitions 返回 list[ToolChainDag]
10. 端口协议 3 方法签名完整
11. ToolChainService 实现完整
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from typing import get_type_hints
from unittest.mock import AsyncMock

import pytest

from src.application.ports.tool_chain_orchestrator import ToolChainOrchestratorProtocol
from src.application.ports.tool_chain_service import ToolChainServicePort
from src.application.services.tool_chain_service import ToolChainService
from src.domain.entities.tool_chain import (
    FailureStrategy,
    ToolChainDag,
    ToolChainNode,
)
from src.domain.entities.tool_chain_run import ToolChainRun, ToolChainRunState
from src.domain.exceptions import ToolChainNotFoundError
from src.domain.ports.tool_chain_repository import ToolChainDagQuery
from src.domain.value_objects.tool_execution import ExecutionContext

# ============================================================================
# 工厂函数
# ============================================================================


def _make_dag(chain_id: uuid.UUID | None = None) -> ToolChainDag:
    now = datetime.now(UTC)
    return ToolChainDag(
        chain_id=chain_id or uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="test",
        description="",
        nodes=(ToolChainNode(node_id="n", tool_slug="t"),),
        failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
        max_concurrency=5,
        created_at=now,
        updated_at=now,
    )


def _make_run() -> ToolChainRun:
    started = datetime.now(UTC)
    return ToolChainRun(
        chain_run_id=uuid.uuid4(),
        chain_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        state=ToolChainRunState.COMPLETED,
        started_at=started,
        completed_at=started,
        failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
    )


def _make_context() -> ExecutionContext:
    return ExecutionContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session_id="s",
        trace_id="t",
    )


# ============================================================================
# 1. Protocol runtime_checkable 校验
# ============================================================================


def test_runtime_checkable_protocol_validation() -> None:
    """ToolChainService 必须实现 ToolChainServicePort Protocol"""
    repo = AsyncMock()
    orchestrator = AsyncMock(spec=ToolChainOrchestratorProtocol)
    service = ToolChainService(repository=repo, orchestrator=orchestrator)
    assert isinstance(service, ToolChainServicePort)


def test_protocol_has_runtime_checkable_marker() -> None:
    """Protocol 必须具备 _is_runtime_protocol=True 标记（@runtime_checkable 装饰器自动设置）

    业界参考：tests/contracts/test_port_contract_saga.py:17-18 样板
    """
    assert hasattr(ToolChainServicePort, "_is_runtime_protocol"), "ToolChainServicePort 缺少 _is_runtime_protocol 标记"
    assert ToolChainServicePort._is_runtime_protocol is True, "ToolChainServicePort._is_runtime_protocol 必须为 True"


# ============================================================================
# 2-4. 端口协议 3 方法
# ============================================================================


def test_protocol_has_three_methods() -> None:
    """ToolChainServicePort 必须 3 方法"""
    methods = ["execute_chain", "get_chain_definition", "list_chain_definitions"]
    for m in methods:
        assert hasattr(ToolChainServicePort, m), f"Protocol 缺少方法 {m}"


def test_all_protocol_methods_are_async() -> None:
    """Protocol 3 方法均为 async"""
    for name in ["execute_chain", "get_chain_definition", "list_chain_definitions"]:
        method = getattr(ToolChainServicePort, name)
        assert inspect.iscoroutinefunction(method), f"{name} 必须为 async"


# ============================================================================
# 5. 依赖通过端口注入
# ============================================================================


def test_service_accepts_port_injection() -> None:
    """ToolChainService.__init__ 接受端口实例（不导入 infrastructure）"""
    repo = AsyncMock()
    orchestrator = AsyncMock(spec=ToolChainOrchestratorProtocol)
    service = ToolChainService(repository=repo, orchestrator=orchestrator)
    assert service._repository is repo
    assert service._orchestrator is orchestrator


def test_service_module_does_not_import_infrastructure() -> None:
    """ToolChainService 不导入 infrastructure 具体实现（六边形约束）"""
    import ast
    import pathlib

    source = pathlib.Path("src/application/services/tool_chain_service.py").read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("src.infrastructure"), f"导入禁止模块: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert not node.module.startswith("src.infrastructure"), f"导入禁止模块: {node.module}"


# ============================================================================
# 6. execute_chain 委托行为
# ============================================================================


@pytest.mark.asyncio
async def test_execute_chain_delegates_to_orchestrator() -> None:
    """execute_chain 委托 ToolChainOrchestrator.execute_chain"""
    dag = _make_dag()
    expected_run = _make_run()

    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=dag)
    orchestrator = AsyncMock(spec=ToolChainOrchestratorProtocol)
    orchestrator.execute_chain = AsyncMock(return_value=expected_run)

    service = ToolChainService(repository=repo, orchestrator=orchestrator)
    run = await service.execute_chain(dag.chain_id, {}, _make_context())

    assert run is expected_run
    orchestrator.execute_chain.assert_awaited_once()
    call_args = orchestrator.execute_chain.await_args
    assert call_args.args[0] is dag


# ============================================================================
# 7. get_chain_definition 委托 Repository
# ============================================================================


@pytest.mark.asyncio
async def test_get_chain_definition_returns_dag() -> None:
    """get_chain_definition 返回 Repository 加载的 DAG"""
    dag = _make_dag()

    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=dag)
    orchestrator = AsyncMock(spec=ToolChainOrchestratorProtocol)

    service = ToolChainService(repository=repo, orchestrator=orchestrator)
    fetched = await service.get_chain_definition(dag.chain_id)

    assert fetched is dag
    repo.get_by_id.assert_awaited_once_with(dag.chain_id)


@pytest.mark.asyncio
async def test_get_chain_definition_raises_when_missing() -> None:
    """get_chain_definition 不存在抛 ToolChainNotFoundError（EXCEPTION_394，toolchain 子域）"""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    orchestrator = AsyncMock(spec=ToolChainOrchestratorProtocol)

    service = ToolChainService(repository=repo, orchestrator=orchestrator)
    with pytest.raises(ToolChainNotFoundError):
        await service.get_chain_definition(uuid.uuid4())


# ============================================================================
# 8-9. list_chain_definitions 委托 Repository
# ============================================================================


@pytest.mark.asyncio
async def test_list_chain_definitions_returns_list() -> None:
    """list_chain_definitions 返回 Repository 查询结果列表"""
    dags = [_make_dag(), _make_dag()]

    repo = AsyncMock()
    repo.list_by_query = AsyncMock(return_value=dags)
    orchestrator = AsyncMock(spec=ToolChainOrchestratorProtocol)

    service = ToolChainService(repository=repo, orchestrator=orchestrator)
    query = ToolChainDagQuery(name="test")
    result = await service.list_chain_definitions(query)

    assert result == dags
    repo.list_by_query.assert_awaited_once_with(query)


@pytest.mark.asyncio
async def test_list_chain_definitions_empty() -> None:
    """list_chain_definitions 空结果"""
    repo = AsyncMock()
    repo.list_by_query = AsyncMock(return_value=[])
    orchestrator = AsyncMock(spec=ToolChainOrchestratorProtocol)

    service = ToolChainService(repository=repo, orchestrator=orchestrator)
    result = await service.list_chain_definitions(ToolChainDagQuery())
    assert result == []


# ============================================================================
# 10-11. 协议方法签名 + ToolChainService 实现完整
# ============================================================================


def test_execute_chain_protocol_signature() -> None:
    """execute_chain Protocol 方法签名"""
    hints = get_type_hints(ToolChainServicePort.execute_chain)
    assert "chain_id" in hints
    assert "parameters" in hints
    assert "context" in hints
    assert hints["return"] == ToolChainRun


def test_service_has_all_methods() -> None:
    """ToolChainService 实现 3 方法"""
    for name in ["execute_chain", "get_chain_definition", "list_chain_definitions"]:
        assert hasattr(ToolChainService, name)
        method = getattr(ToolChainService, name)
        assert inspect.iscoroutinefunction(method)
