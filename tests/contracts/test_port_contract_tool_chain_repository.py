"""ToolChainRepository 端口契约测试（Story 4.2 AC-3）

验证 ToolChainRepositoryPort Protocol 11 维度行为契约：
1. Protocol runtime_checkable 校验
2. async def get_by_id
3. async def save (insert + update)
4. async def delete
5. async def list_all
6. async def list_by_query（Query Object 模式）
7. async def count
8. asyncio.Lock 类变量并发安全
9. Query Object frozen dataclass 验证
10. ToolChainDagQuery 5 过滤字段
11. InMemoryToolChainRepository 实现完整
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import get_type_hints

import pytest

from src.domain.entities.tool_chain import (
    FailureStrategy,
    ToolChainDag,
    ToolChainNode,
)
from src.domain.ports.l2_rdb import L2RdbPort
from src.domain.ports.tool_chain_repository import (
    ToolChainDagQuery,
    ToolChainRepositoryPort,
)
from src.infrastructure.storage.inmemory.tool_chain_repository import (
    InMemoryToolChainRepository,
)

# ============================================================================
# 工厂函数
# ============================================================================


def _make_node(node_id: str = "n", depends_on: tuple[str, ...] = ()) -> ToolChainNode:
    return ToolChainNode(node_id=node_id, tool_slug="pestel", depends_on=depends_on)


def _make_dag(
    name: str = "test-dag",
    tenant_id: uuid.UUID | None = None,
    nodes_count: int = 1,
) -> ToolChainDag:
    now = datetime.now(UTC)
    return ToolChainDag(
        chain_id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        name=name,
        description="test",
        nodes=tuple(_make_node(f"n{i}") for i in range(nodes_count)),
        failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
        max_concurrency=5,
        created_at=now,
        updated_at=now,
    )


# ============================================================================
# 1. Protocol runtime_checkable 校验
# ============================================================================


def test_runtime_checkable_protocol_validation() -> None:
    """InMemoryToolChainRepository 必须实现 ToolChainRepositoryPort Protocol"""
    repo = InMemoryToolChainRepository()
    assert isinstance(repo, ToolChainRepositoryPort)


def test_protocol_inherits_l2_rdb_port() -> None:
    """ToolChainRepositoryPort 必须继承 L2RdbPort[T] 基座"""
    assert issubclass(ToolChainRepositoryPort, L2RdbPort)


# ============================================================================
# 2-5. L2RdbPort 继承方法
# ============================================================================


@pytest.mark.asyncio
async def test_save_then_get_by_id() -> None:
    """save + get_by_id 正常路径"""
    repo = InMemoryToolChainRepository()
    dag = _make_dag()
    saved = await repo.save(dag)
    assert saved.chain_id == dag.chain_id
    fetched = await repo.get_by_id(dag.chain_id)
    assert fetched is not None
    assert fetched.name == dag.name


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_missing() -> None:
    """get_by_id 不存在时返回 None（不抛错）"""
    repo = InMemoryToolChainRepository()
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_delete_removes_entity() -> None:
    """delete 移除实体（缺失不抛错）"""
    repo = InMemoryToolChainRepository()
    dag = _make_dag()
    await repo.save(dag)
    await repo.delete(dag.chain_id)
    assert await repo.get_by_id(dag.chain_id) is None
    # 重复删除不抛错
    await repo.delete(dag.chain_id)


@pytest.mark.asyncio
async def test_list_all_returns_all_entities() -> None:
    """list_all 列出所有实体"""
    repo = InMemoryToolChainRepository()
    dags = [_make_dag(f"d{i}") for i in range(3)]
    for d in dags:
        await repo.save(d)
    all_dags = await repo.list_all()
    assert len(all_dags) == 3


# ============================================================================
# 6-7. Query Object 模式
# ============================================================================


@pytest.mark.asyncio
async def test_list_by_query_filter_by_tenant() -> None:
    """list_by_query 按 tenant_id 过滤"""
    repo = InMemoryToolChainRepository()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await repo.save(_make_dag("a1", tenant_id=tenant_a))
    await repo.save(_make_dag("a2", tenant_id=tenant_a))
    await repo.save(_make_dag("b1", tenant_id=tenant_b))
    results = await repo.list_by_query(ToolChainDagQuery(tenant_id=tenant_a))
    assert len(results) == 2
    assert all(d.tenant_id == tenant_a for d in results)


@pytest.mark.asyncio
async def test_list_by_query_filter_by_name() -> None:
    """list_by_query 按 name 精确匹配"""
    repo = InMemoryToolChainRepository()
    await repo.save(_make_dag("alpha"))
    await repo.save(_make_dag("beta"))
    results = await repo.list_by_query(ToolChainDagQuery(name="alpha"))
    assert len(results) == 1
    assert results[0].name == "alpha"


@pytest.mark.asyncio
async def test_list_by_query_filter_by_failure_strategy() -> None:
    """list_by_query 按 failure_strategy 过滤"""
    repo = InMemoryToolChainRepository()
    # 直接用 builder 构造 3 个不同策略的 DAG
    now = datetime.now(UTC)
    tenant = uuid.uuid4()
    for strat in [
        FailureStrategy.FAIL_FAST,
        FailureStrategy.CONTINUE_ON_ERROR,
        FailureStrategy.SKIP_DOWNSTREAM,
    ]:
        await repo.save(
            ToolChainDag(
                chain_id=uuid.uuid4(),
                tenant_id=tenant,
                name=f"d-{strat.value}",
                description="",
                nodes=(_make_node(),),
                failure_strategy=strat,
                max_concurrency=5,
                created_at=now,
                updated_at=now,
            )
        )
    results = await repo.list_by_query(ToolChainDagQuery(failure_strategy=FailureStrategy.FAIL_FAST))
    assert len(results) == 1
    assert results[0].failure_strategy == FailureStrategy.FAIL_FAST


@pytest.mark.asyncio
async def test_list_by_query_filter_by_node_count() -> None:
    """list_by_query 按 min_nodes / max_nodes 过滤"""
    repo = InMemoryToolChainRepository()
    await repo.save(_make_dag("d1", nodes_count=1))
    await repo.save(_make_dag("d3", nodes_count=3))
    await repo.save(_make_dag("d5", nodes_count=5))
    results = await repo.list_by_query(ToolChainDagQuery(min_nodes=3, max_nodes=4))
    assert len(results) == 1
    assert len(results[0].nodes) == 3


@pytest.mark.asyncio
async def test_list_by_query_pagination() -> None:
    """list_by_query offset/limit 分页"""
    repo = InMemoryToolChainRepository()
    for i in range(10):
        await repo.save(_make_dag(f"d{i:02d}"))
    page1 = await repo.list_by_query(ToolChainDagQuery(offset=0, limit=3))
    page2 = await repo.list_by_query(ToolChainDagQuery(offset=3, limit=3))
    assert len(page1) == 3
    assert len(page2) == 3
    assert set(d.chain_id for d in page1).isdisjoint(set(d.chain_id for d in page2))


@pytest.mark.asyncio
async def test_count_by_query() -> None:
    """count 统计符合条件的实体数量"""
    repo = InMemoryToolChainRepository()
    tenant = uuid.uuid4()
    for i in range(3):
        await repo.save(_make_dag(f"d{i}", tenant_id=tenant))
    await repo.save(_make_dag("other", tenant_id=uuid.uuid4()))
    count = await repo.count(ToolChainDagQuery(tenant_id=tenant))
    assert count == 3


# ============================================================================
# 8. asyncio.Lock 类变量并发安全
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_save_safety_with_class_lock() -> None:
    """asyncio.Lock 类变量：并发 save 不丢失"""
    repo = InMemoryToolChainRepository()

    async def save_dag(i: int) -> None:
        await repo.save(_make_dag(f"d{i:02d}"))

    await asyncio.gather(*[save_dag(i) for i in range(20)])
    all_dags = await repo.list_all()
    assert len(all_dags) == 20


def test_asyncio_lock_is_class_variable() -> None:
    """asyncio.Lock 声明为类变量（非实例变量）"""
    assert "_lock" in InMemoryToolChainRepository.__dict__
    # 类变量被所有实例共享
    repo1 = InMemoryToolChainRepository()
    repo2 = InMemoryToolChainRepository()
    assert repo1._lock is repo2._lock


# ============================================================================
# 9-10. Query Object frozen dataclass 验证
# ============================================================================


def test_query_object_is_frozen() -> None:
    """ToolChainDagQuery 是 frozen dataclass"""
    from dataclasses import FrozenInstanceError

    query = ToolChainDagQuery()
    with pytest.raises(FrozenInstanceError):
        query.limit = 200  # type: ignore[misc]


def test_query_object_has_six_init_fields() -> None:
    """ToolChainDagQuery 6 init 字段"""
    from dataclasses import fields

    field_names = {f.name for f in fields(ToolChainDagQuery) if f.init}
    expected = {
        "tenant_id",
        "name",
        "failure_strategy",
        "min_nodes",
        "max_nodes",
        "offset",
        "limit",
    }
    assert field_names == expected


def test_query_object_defaults() -> None:
    """ToolChainDagQuery 默认值"""
    q = ToolChainDagQuery()
    assert q.offset == 0
    assert q.limit == 100
    assert q.tenant_id is None


# ============================================================================
# 11. InMemoryToolChainRepository 实现完整性
# ============================================================================


def test_repository_implements_all_protocol_methods() -> None:
    """InMemoryToolChainRepository 必须实现 Protocol 全部方法"""
    required_methods = [
        "get_by_id",
        "save",
        "delete",
        "list_all",
        "list_by_query",
        "count",
    ]
    for name in required_methods:
        assert hasattr(InMemoryToolChainRepository, name), f"缺少方法 {name}"


def test_all_methods_are_async() -> None:
    """所有方法必须 async def（继承 L2RdbPort async 基座）"""
    import inspect

    method_names = ["get_by_id", "save", "delete", "list_all", "list_by_query", "count"]
    for name in method_names:
        method = getattr(InMemoryToolChainRepository, name)
        assert inspect.iscoroutinefunction(method), f"{name} 必须为 async def"


def test_protocol_type_hints() -> None:
    """Protocol 方法签名 + 返回类型"""
    hints = get_type_hints(ToolChainRepositoryPort.list_by_query)
    # 简单验证 Protocol 有此方法签名
    assert "query" in hints
    assert hints["return"] == list[ToolChainDag]
