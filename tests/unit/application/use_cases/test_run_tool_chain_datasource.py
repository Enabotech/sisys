"""Story 4.1c Task 1 [B]: RunToolChainUseCase 生产链路接线单元测试

验证工具链用例入口将 L2 `load_sop` 解析出的 ToolMetadata（含 data_sources 白名单）
注入 `context.extensions["tool_metadata"]` 后委托 `execute_chain`（AC-2，
Round 1 D2 评审新增的第二入口；链路共享单 ToolMetadata，节点级切换属 Story 4.2）。

3 场景（Story AC-2 验证标准）：
1. 多节点并发 load_sop + 任一节点 metadata 注入 —— execute_chain 收到的 context
   extensions 含 tool_metadata
2. 全部 load_sop 失败容错 —— 不阻断执行，extensions 不含 tool_metadata 键
3. 无 tool_slug 节点零行为变化 —— context 原样透传（extensions 不变）

遵循项目标准单元测试模式（Mock 端口，禁止真实服务）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.application.ports.skill_loader import SkillDocument, SkillLoaderPort, ToolMetadata
from src.application.ports.tool_chain_service import ToolChainServicePort
from src.application.use_cases.run_tool_chain import RunToolChainUseCase
from src.domain.entities.tool_chain import (
    FailureStrategy,
    ToolChainDag,
    ToolChainNode,
)
from src.domain.entities.tool_chain_run import ToolChainRun, ToolChainRunState
from src.domain.exceptions import SkillNotFoundError
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.tool_chain_repository import ToolChainRepositoryPort
from src.domain.value_objects.data_source import DataSourceApiType, DataSourceRef
from src.domain.value_objects.tool_execution import ExecutionContext

# =============================================================================
# 测试工厂
# =============================================================================


def _make_dag(name: str = "test-chain") -> ToolChainDag:
    """工厂函数：创建双节点 ToolChainDag（范本 test_run_tool_chain_usecase.py）"""
    now = datetime.now(UTC)
    return ToolChainDag(
        chain_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name=name,
        description="",
        nodes=(
            ToolChainNode(node_id="a", tool_slug="pestel-analysis"),
            ToolChainNode(node_id="b", tool_slug="porters", depends_on=("a",)),
        ),
        failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
        max_concurrency=5,
        created_at=now,
        updated_at=now,
    )


def _make_run() -> ToolChainRun:
    """工厂函数：创建 COMPLETED 状态 ToolChainRun"""
    now = datetime.now(UTC)
    return ToolChainRun(
        chain_run_id=uuid.uuid4(),
        chain_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        state=ToolChainRunState.COMPLETED,
        started_at=now,
        completed_at=now,
        failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
        cost_audit={},
    )


def _make_metadata(slug: str, *source_names: str) -> ToolMetadata:
    """工厂函数：创建声明指定数据源白名单的 ToolMetadata"""
    return ToolMetadata(
        tool_name=slug,
        slug=slug,
        category="environment_analysis",
        input_schema={},
        output_schema={},
        data_sources=tuple(
            DataSourceRef(
                name=name,
                url=f"https://fake.local/{name}",
                ttl_seconds=3600,
                api_type=DataSourceApiType.REST_JSON,
            )
            for name in source_names
        ),
    )


def _make_skill_document(metadata: ToolMetadata) -> SkillDocument:
    """工厂函数：创建 load_sop 返回的 SkillDocument"""
    return SkillDocument(
        tool_name=metadata.tool_name,
        slug=metadata.slug,
        content="# SOP",
        token_count=10,
        frontmatter=metadata,
        body="# SOP",
    )


def _make_use_case(
    dag: ToolChainDag | None,
    skill_loader: AsyncMock,
) -> tuple[RunToolChainUseCase, AsyncMock, AsyncMock]:
    """工厂函数：创建用例 + (service mock, publisher mock)"""
    repo = AsyncMock(spec=ToolChainRepositoryPort)
    repo.list_by_query = AsyncMock(return_value=[dag] if dag else [])

    service = AsyncMock(spec=ToolChainServicePort)
    service.execute_chain = AsyncMock(return_value=_make_run())

    publisher = AsyncMock(spec=EventPublisher)
    publisher.publish = AsyncMock()

    use_case = RunToolChainUseCase(
        repository=repo,
        service=service,
        skill_loader=skill_loader,
        event_publisher=publisher,
    )
    return use_case, service, publisher


def _make_context(tenant_id: uuid.UUID) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        session_id="s",
        trace_id="t",
    )


# =============================================================================
# 测试类
# =============================================================================


class TestRunToolChainDataSourceWiring:
    """RunToolChainUseCase 接线测试（load_sop + extensions["tool_metadata"] 注入）"""

    @pytest.mark.asyncio
    async def test_node_metadata_injected_into_extensions(self) -> None:
        """场景 1：多节点并发 load_sop，当前节点 ToolMetadata 注入 extensions"""
        dag = _make_dag("pestel-porter")
        metadata = _make_metadata("pestel-analysis", "world-bank", "imf")

        skill_loader = AsyncMock(spec=SkillLoaderPort)
        skill_loader.load_sop = AsyncMock(return_value=_make_skill_document(metadata))

        use_case, service, _ = _make_use_case(dag, skill_loader)
        context = _make_context(dag.tenant_id)

        run = await use_case.execute("pestel-porter", {}, context)

        assert run is not None
        # 每个 tool_slug 节点均并发调用 load_sop
        assert skill_loader.load_sop.await_count == 2
        # execute_chain 收到的 context 注入了 tool_metadata（链路共享单 ToolMetadata）
        delegated_context = service.execute_chain.call_args[1]["context"]
        assert delegated_context.extensions.get("tool_metadata") is not None
        injected: ToolMetadata = delegated_context.extensions["tool_metadata"]
        assert tuple(ref.name for ref in injected.data_sources) == ("world-bank", "imf")

    @pytest.mark.asyncio
    async def test_load_sop_failure_tolerated_extensions_empty(self) -> None:
        """场景 2：全部 load_sop 失败容错不阻断，extensions 不含 tool_metadata 键"""
        dag = _make_dag("pestel-porter")

        skill_loader = AsyncMock(spec=SkillLoaderPort)
        skill_loader.load_sop = AsyncMock(side_effect=SkillNotFoundError(tool_name="pestel-analysis"))

        use_case, service, _ = _make_use_case(dag, skill_loader)
        context = _make_context(dag.tenant_id)

        run = await use_case.execute("pestel-porter", {}, context)

        assert run is not None
        delegated_context = service.execute_chain.call_args[1]["context"]
        assert "tool_metadata" not in delegated_context.extensions

    @pytest.mark.asyncio
    async def test_empty_whitelist_metadata_zero_behavior_change(self) -> None:
        """场景 3：未成熟化 Skill（metadata.data_sources 空 tuple）链路零行为变化

        领域约束下 ToolChainNode.tool_slug 必非空、DAG 至少 1 节点，
        "无节点零行为变化"落地为：节点 metadata 无数据源声明时正常委托执行
        （无标记时 Engine 行为不变，对齐 AC-2 回归语义）。
        """
        dag = _make_dag("no-datasource-chain")
        metadata = _make_metadata("pestel-analysis")  # data_sources 空 tuple

        skill_loader = AsyncMock(spec=SkillLoaderPort)
        skill_loader.load_sop = AsyncMock(return_value=_make_skill_document(metadata))

        use_case, service, _ = _make_use_case(dag, skill_loader)
        context = _make_context(dag.tenant_id)

        run = await use_case.execute("no-datasource-chain", {}, context)

        assert run is not None
        delegated_context = service.execute_chain.call_args[1]["context"]
        injected: ToolMetadata = delegated_context.extensions["tool_metadata"]
        assert injected.data_sources == ()
