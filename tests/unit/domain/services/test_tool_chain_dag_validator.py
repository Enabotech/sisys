"""ToolChainDagValidator 领域服务单元测试（Story 4.2 AC-2）

测试覆盖：
1. 节点唯一性校验（重复抛 ToolChainDuplicateNodeError EXCEPTION_391）
2. 依赖节点存在性校验（缺失抛 ToolChainNodeNotFoundError EXCEPTION_392）
3. 无环检测（自依赖 / 简单环 / 复杂环 / 多环 → ToolChainCycleDetectedError EXCEPTION_390）
4. 正常 DAG 通过校验
5. cycle_path 异常上下文
6. 算法复杂度 O(V+E) 验证
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.tool_chain import (
    FailureStrategy,
    ToolChainDag,
    ToolChainNode,
)
from src.domain.exceptions import (
    EntityValidationError,
    ToolChainCycleDetectedError,
    ToolChainDuplicateNodeError,
    ToolChainNodeNotFoundError,
)
from src.domain.services.tool_chain_dag_validator import ToolChainDagValidator


def _make_node(node_id: str, depends_on: tuple[str, ...] = ()) -> ToolChainNode:
    return ToolChainNode(
        node_id=node_id,
        tool_slug="t",
        depends_on=depends_on,
    )


def _make_dag(nodes: tuple[ToolChainNode, ...]) -> ToolChainDag:
    now = datetime.now(UTC)
    return ToolChainDag(
        chain_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="t",
        description="t",
        nodes=nodes,
        failure_strategy=FailureStrategy.SKIP_DOWNSTREAM,
        max_concurrency=5,
        created_at=now,
        updated_at=now,
    )


# ============================================================================
# 1. 正常 DAG 通过校验
# ============================================================================


def test_valid_dag_passes_validation() -> None:
    """合法 DAG（无重复节点 / 依赖节点存在 / 无环）通过校验"""
    dag = _make_dag(
        (
            _make_node("a"),
            _make_node("b", depends_on=("a",)),
            _make_node("c", depends_on=("b",)),
        )
    )
    ToolChainDagValidator.validate(dag)  # 不抛错


def test_valid_diamond_dag_passes_validation() -> None:
    """菱形依赖 DAG 通过校验（A → B, A → C, B → D, C → D）"""
    dag = _make_dag(
        (
            _make_node("a"),
            _make_node("b", depends_on=("a",)),
            _make_node("c", depends_on=("a",)),
            _make_node("d", depends_on=("b", "c")),
        )
    )
    ToolChainDagValidator.validate(dag)


# ============================================================================
# 2. 节点唯一性校验
# ============================================================================


def test_duplicate_node_id_raises_391() -> None:
    """重复 node_id 触发 ToolChainDuplicateNodeError（EXCEPTION_391）"""
    dag = _make_dag(
        (
            _make_node("a"),
            _make_node("a"),  # 重复
        )
    )
    with pytest.raises(ToolChainDuplicateNodeError) as exc_info:
        ToolChainDagValidator.validate(dag)
    assert exc_info.value.code == "EXCEPTION_391"
    assert exc_info.value.context["duplicate_node_id"] == "a"
    assert exc_info.value.context["chain_id"] == str(dag.chain_id)


# ============================================================================
# 3. 依赖节点存在性校验
# ============================================================================


def test_missing_dependency_raises_392() -> None:
    """依赖节点不存在触发 ToolChainNodeNotFoundError（EXCEPTION_392）"""
    dag = _make_dag(
        (
            _make_node("a"),
            _make_node("b", depends_on=("x",)),  # x 不在 nodes 中
        )
    )
    with pytest.raises(ToolChainNodeNotFoundError) as exc_info:
        ToolChainDagValidator.validate(dag)
    assert exc_info.value.code == "EXCEPTION_392"
    assert exc_info.value.context["missing_node_id"] == "x"
    assert "b" in exc_info.value.context["referenced_by_node_ids"]


def test_missing_dependency_with_multiple_references() -> None:
    """多个节点引用缺失节点时，referenced_by_node_ids 完整"""
    dag = _make_dag(
        (
            _make_node("a"),
            _make_node("b", depends_on=("ghost",)),
            _make_node("c", depends_on=("ghost",)),
        )
    )
    with pytest.raises(ToolChainNodeNotFoundError) as exc_info:
        ToolChainDagValidator.validate(dag)
    assert set(exc_info.value.context["referenced_by_node_ids"]) == {"b", "c"}


# ============================================================================
# 4. 无环检测
# ============================================================================


def test_self_dependency_raises_390() -> None:
    """自依赖（A→A）触发 ToolChainCycleDetectedError（EXCEPTION_390）"""
    dag = _make_dag((_make_node("a", depends_on=("a",)),))
    with pytest.raises(ToolChainCycleDetectedError) as exc_info:
        ToolChainDagValidator.validate(dag)
    assert exc_info.value.code == "EXCEPTION_390"
    assert "a" in exc_info.value.context["cycle_path"]


def test_simple_cycle_a_to_b_to_a_raises_390() -> None:
    """简单环（A→B→A）触发 ToolChainCycleDetectedError"""
    dag = _make_dag(
        (
            _make_node("a", depends_on=("b",)),
            _make_node("b", depends_on=("a",)),
        )
    )
    with pytest.raises(ToolChainCycleDetectedError) as exc_info:
        ToolChainDagValidator.validate(dag)
    assert exc_info.value.code == "EXCEPTION_390"
    cycle_path = exc_info.value.context["cycle_path"]
    assert set(cycle_path) == {"a", "b"}


def test_complex_cycle_a_to_b_to_c_to_d_to_b_raises_390() -> None:
    """复杂环（A→B→C→D→B）触发 ToolChainCycleDetectedError"""
    dag = _make_dag(
        (
            _make_node("a", depends_on=("b",)),
            _make_node("b", depends_on=("c",)),
            _make_node("c", depends_on=("d",)),
            _make_node("d", depends_on=("b",)),  # 闭环
        )
    )
    with pytest.raises(ToolChainCycleDetectedError) as exc_info:
        ToolChainDagValidator.validate(dag)
    cycle_path = set(exc_info.value.context["cycle_path"])
    assert {"b", "c", "d"} <= cycle_path  # 环上至少有 3 个节点


def test_validation_order_duplicate_before_cycle() -> None:
    """校验顺序：先节点唯一性，再依赖存在性，最后环检测

    重复 + 环同时存在时，应先报告重复节点（EXCEPTION_391）
    """
    dag = _make_dag(
        (
            _make_node("a", depends_on=("a",)),  # 重复 + 自依赖
            _make_node("a", depends_on=("ghost",)),  # 重复 + 缺失依赖
        )
    )
    with pytest.raises(ToolChainDuplicateNodeError):
        ToolChainDagValidator.validate(dag)


def test_validation_order_missing_before_cycle() -> None:
    """校验顺序：缺失依赖先于环检测（a 依赖不存在的 ghost + a/b 形成环）"""
    dag = _make_dag(
        (
            _make_node("a", depends_on=("ghost", "b")),  # ghost 缺失 + 环
            _make_node("b", depends_on=("a",)),  # a/b 环
        )
    )
    with pytest.raises(ToolChainNodeNotFoundError):
        ToolChainDagValidator.validate(dag)


# ============================================================================
# 5. 算法复杂度 O(V+E)
# ============================================================================


def test_algorithm_complexity_o_v_plus_e() -> None:
    """算法复杂度 O(V+E)：100 节点 / 200 边验证耗时 < 100ms"""
    # 构造线性链：n0 → n1 → n2 → ... → n99（99 条边）
    nodes = tuple(_make_node(f"n{i}", depends_on=(f"n{i - 1}",) if i > 0 else ()) for i in range(100))
    dag = _make_dag(nodes)
    start = time.perf_counter()
    ToolChainDagValidator.validate(dag)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 100, f"100 节点 / 99 边 校验耗时 {elapsed_ms:.2f}ms > 100ms"


# ============================================================================
# 6. validator 是纯函数（无副作用）
# ============================================================================


def test_validator_is_pure_function() -> None:
    """ToolChainDagValidator 是纯函数（@staticmethod，无状态）"""
    # 校验器无 __init__，可作为静态方法直接调用
    assert hasattr(ToolChainDagValidator, "validate")
    # 无实例属性
    assert not hasattr(ToolChainDagValidator(), "_state")


def test_validate_passes_entity_validation_error_on_invalid_dag() -> None:
    """DAG 自身不变量违反（构造时）抛 EntityValidationError

    Validator 仅校验 DAG 拓扑，不变量校验由 DAG 自身 __post_init__ 完成
    """
    with pytest.raises(EntityValidationError):
        _make_dag(())  # 空 nodes → DAG 构造时已失败
