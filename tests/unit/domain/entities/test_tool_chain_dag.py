"""ToolChainDag 聚合根单元测试（Story 4.2 AC-1）

测试覆盖：
1. ToolChainDag 9 字段完整构造 + factory 函数
2. ToolChainNode 7 字段完整构造 + factory 函数
3. FailureStrategy 枚举 3 值
4. __post_init__ 不变量校验（chain_id 非空 UUID、name 非空、nodes 非空、max_concurrency ≥ 1）
5. failure_strategy 枚举值校验
6. nodes tuple 不可变设计
7. _reverse_adj 反向邻接表预计算正确
8. domain 层零依赖验证（grep 自查辅助）
"""

from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime

import pytest

from src.domain.entities.tool_chain import (
    FailureStrategy,
    ToolChainDag,
    ToolChainNode,
)
from src.domain.exceptions import EntityValidationError

# ============================================================================
# 工厂函数
# ============================================================================


def _make_node(
    node_id: str = "node_a",
    tool_slug: str = "pestel",
    depends_on: tuple[str, ...] = (),
    arguments_template: dict | None = None,
    failure_strategy: FailureStrategy | None = None,
    skip_on_upstream_failure: bool = True,
) -> ToolChainNode:
    """构造 ToolChainNode 测试实例"""
    return ToolChainNode(
        node_id=node_id,
        tool_slug=tool_slug,
        depends_on=depends_on,
        arguments_template=arguments_template if arguments_template is not None else {},
        failure_strategy=failure_strategy,
        skip_on_upstream_failure=skip_on_upstream_failure,
    )


def _make_dag(
    nodes: tuple[ToolChainNode, ...] | None = None,
    name: str = "test-dag",
    description: str = "测试用 DAG",
    failure_strategy: FailureStrategy = FailureStrategy.SKIP_DOWNSTREAM,
    max_concurrency: int = 5,
    chain_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
) -> ToolChainDag:
    """构造 ToolChainDag 测试实例"""
    if nodes is None:
        nodes = (_make_node(),)
    now = datetime.now(UTC)
    return ToolChainDag(
        chain_id=chain_id or uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        name=name,
        description=description,
        nodes=nodes,
        failure_strategy=failure_strategy,
        max_concurrency=max_concurrency,
        created_at=now,
        updated_at=now,
    )


# ============================================================================
# 1. FailureStrategy 枚举 3 值
# ============================================================================


def test_failure_strategy_has_three_values() -> None:
    """FailureStrategy 枚举必须 3 值（FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM）"""
    assert len(FailureStrategy) == 3
    assert FailureStrategy.FAIL_FAST.value == "FAIL_FAST"
    assert FailureStrategy.CONTINUE_ON_ERROR.value == "CONTINUE_ON_ERROR"
    assert FailureStrategy.SKIP_DOWNSTREAM.value == "SKIP_DOWNSTREAM"


def test_failure_strategy_is_str_enum() -> None:
    """FailureStrategy 是 str 子类（与项目惯例对齐）"""
    assert FailureStrategy.FAIL_FAST == "FAIL_FAST"
    assert FailureStrategy("FAIL_FAST") is FailureStrategy.FAIL_FAST


# ============================================================================
# 2. ToolChainNode 7 字段
# ============================================================================


def test_tool_chain_node_has_six_fields() -> None:
    """ToolChainNode 实体必须 6 init 字段（Round 2 移除 retry_override）"""
    field_names = {f.name for f in fields(ToolChainNode) if f.init}
    expected = {
        "node_id",
        "tool_slug",
        "depends_on",
        "arguments_template",
        "failure_strategy",
        "skip_on_upstream_failure",
    }
    assert field_names == expected


def test_tool_chain_node_default_values() -> None:
    """ToolChainNode 默认值正确"""
    node = _make_node()
    assert node.node_id == "node_a"
    assert node.tool_slug == "pestel"
    assert node.depends_on == ()
    assert node.arguments_template == {}
    assert node.failure_strategy is None
    assert node.skip_on_upstream_failure is True


def test_tool_chain_node_frozen() -> None:
    """ToolChainNode frozen 不可变"""
    node = _make_node()
    with pytest.raises(FrozenInstanceError):
        node.node_id = "other"  # type: ignore[misc]


def test_tool_chain_node_empty_node_id_raises() -> None:
    """node_id 为空字符串触发不变量违反（EntityValidationError）"""
    with pytest.raises(EntityValidationError) as exc_info:
        _make_node(node_id="")
    assert exc_info.value.context["field"] == "node_id"


def test_tool_chain_node_empty_tool_slug_raises() -> None:
    """tool_slug 为空字符串触发不变量违反"""
    with pytest.raises(EntityValidationError) as exc_info:
        _make_node(tool_slug="")
    assert exc_info.value.context["field"] == "tool_slug"


def test_tool_chain_node_invalid_failure_strategy_raises() -> None:
    """failure_strategy 非法值（非枚举）触发不变量违反"""
    with pytest.raises(EntityValidationError):
        _make_node(failure_strategy="INVALID")  # type: ignore[arg-type]


# ============================================================================
# 3. ToolChainDag 9 字段
# ============================================================================


def test_tool_chain_dag_has_nine_fields() -> None:
    """ToolChainDag 聚合根必须 9 init 字段（_reverse_adj 为派生字段 init=False）"""
    field_names = {f.name for f in fields(ToolChainDag) if f.init}
    expected = {
        "chain_id",
        "tenant_id",
        "name",
        "description",
        "nodes",
        "failure_strategy",
        "max_concurrency",
        "created_at",
        "updated_at",
    }
    assert field_names == expected


def test_tool_chain_dag_default_construction() -> None:
    """ToolChainDag 默认构造成功"""
    dag = _make_dag()
    assert isinstance(dag.chain_id, uuid.UUID)
    assert isinstance(dag.tenant_id, uuid.UUID)
    assert dag.name == "test-dag"
    assert dag.failure_strategy == FailureStrategy.SKIP_DOWNSTREAM
    assert dag.max_concurrency == 5
    assert len(dag.nodes) == 1


def test_tool_chain_dag_frozen() -> None:
    """ToolChainDag frozen 不可变（nodes 是 tuple 也保护不可变）"""
    dag = _make_dag()
    with pytest.raises(FrozenInstanceError):
        dag.name = "new"  # type: ignore[misc]


def test_tool_chain_dag_nodes_is_tuple() -> None:
    """nodes 字段为 tuple（不可变设计）"""
    dag = _make_dag()
    assert isinstance(dag.nodes, tuple)


def test_tool_chain_dag_empty_name_raises() -> None:
    """name 为空字符串触发 EntityValidationError"""
    with pytest.raises(EntityValidationError) as exc_info:
        _make_dag(name="")
    assert exc_info.value.context["field"] == "name"


def test_tool_chain_dag_empty_nodes_raises() -> None:
    """nodes 为空 tuple 触发 EntityValidationError"""
    with pytest.raises(EntityValidationError) as exc_info:
        _make_dag(nodes=())
    assert exc_info.value.context["field"] == "nodes"


def test_tool_chain_dag_invalid_max_concurrency_raises() -> None:
    """max_concurrency < 1 触发 EntityValidationError"""
    with pytest.raises(EntityValidationError) as exc_info:
        _make_dag(max_concurrency=0)
    assert exc_info.value.context["field"] == "max_concurrency"


def test_tool_chain_dag_invalid_chain_id_raises() -> None:
    """chain_id 非 UUID 触发 EntityValidationError"""
    with pytest.raises(EntityValidationError) as exc_info:
        _make_dag(chain_id="not-a-uuid")  # type: ignore[arg-type]
    assert exc_info.value.context["field"] == "chain_id"


def test_tool_chain_dag_invalid_failure_strategy_raises() -> None:
    """failure_strategy 非法值触发 EntityValidationError"""
    with pytest.raises(EntityValidationError):
        _make_dag(failure_strategy="INVALID")  # type: ignore[arg-type]


# ============================================================================
# 4. _reverse_adj 反向邻接表预计算
# ============================================================================


def test_reverse_adj_computed_for_dependencies() -> None:
    """_reverse_adj 正确反映节点的依赖关系（O(V+E) 一次性构建）"""
    node_a = _make_node(node_id="a")
    node_b = _make_node(node_id="b", depends_on=("a",))
    node_c = _make_node(node_id="c", depends_on=("a", "b"))
    dag = _make_dag(nodes=(node_a, node_b, node_c))

    # a 是 b 和 c 的上游 → reverse_adj[a] = ("b", "c")
    assert set(dag._reverse_adj["a"]) == {"b", "c"}
    # b 是 c 的上游 → reverse_adj[b] = ("c",)
    assert set(dag._reverse_adj["b"]) == {"c"}
    # c 无下游
    assert dag._reverse_adj["c"] == ()


def test_reverse_adj_for_diamond_dependency() -> None:
    """_reverse_adj 在菱形依赖下正确（A 是 B/C 的上游，B/C 是 D 的上游）"""
    node_a = _make_node(node_id="a")
    node_b = _make_node(node_id="b", depends_on=("a",))
    node_c = _make_node(node_id="c", depends_on=("a",))
    node_d = _make_node(node_id="d", depends_on=("b", "c"))
    dag = _make_dag(nodes=(node_a, node_b, node_c, node_d))

    assert set(dag._reverse_adj["a"]) == {"b", "c"}
    assert set(dag._reverse_adj["b"]) == {"d"}
    assert set(dag._reverse_adj["c"]) == {"d"}
    assert dag._reverse_adj["d"] == ()


def test_reverse_adj_empty_for_no_dependencies() -> None:
    """无依赖节点的 reverse_adj 为空 tuple"""
    node = _make_node(node_id="solo")
    dag = _make_dag(nodes=(node,))
    assert dag._reverse_adj == {"solo": ()}


# ============================================================================
# 5. Domain 层零依赖（辅助验证）
# ============================================================================


def test_domain_entities_tool_chain_only_uses_stdlib() -> None:
    """ToolChainDag 仅使用标准库（domain 层零依赖）

    验证 src/domain/entities/tool_chain.py 不导入任何第三方库
    """
    import ast
    import pathlib

    source = pathlib.Path("src/domain/entities/tool_chain.py").read_text()
    tree = ast.parse(source)

    forbidden_modules = {
        "pydantic",
        "sqlalchemy",
        "redis",
        "qdrant_client",
        "minio",
        "neo4j",
        "fastapi",
        "langgraph",
        "prefect",
        "typer",
        "litellm",
        "instructor",
        "aio_pika",
        "src.application",
        "src.infrastructure",
        "src.interfaces",
    }

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])

    violations = imported & forbidden_modules
    assert not violations, f"domain/entities/tool_chain.py 引入了禁止模块: {violations}"
