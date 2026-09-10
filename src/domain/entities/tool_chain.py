"""领域层工具链实体模块

定义 ToolChainDag 聚合根 + ToolChainNode 实体 + FailureStrategy 枚举，
用于 DAG 工具链编排（Story 4.2）。

设计依据：
- Story 4.2 AC-1：聚合根 9 字段 + 节点实体 7 字段 + 3 值失败策略
- architecture.md §1 六边形架构：领域层零依赖，仅使用 Python 标准库
- 项目惯例：参考 Tool / ToolExecution 聚合根的不变量校验模式

不可变设计：
- @dataclass(frozen=True) 保证聚合根不可变
- nodes: tuple 不可变
- _reverse_adj 预计算（O(V+E)），通过 object.__setattr__ 突破 frozen 限制
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.exceptions import EntityValidationError


class FailureStrategy(str, Enum):
    """工具链失败策略枚举 — 3 值

    Attributes:
        FAIL_FAST: 首个节点失败立即终止整链（最严格）
        CONTINUE_ON_ERROR: 节点失败标记后继续执行后续节点
        SKIP_DOWNSTREAM: 节点失败时跳过所有下游依赖节点（推荐默认）
    """

    FAIL_FAST = "FAIL_FAST"
    CONTINUE_ON_ERROR = "CONTINUE_ON_ERROR"
    SKIP_DOWNSTREAM = "SKIP_DOWNSTREAM"


@dataclass(frozen=True)
class ToolChainNode:
    """工具链节点实体（不可变）

    Attributes:
        node_id: DAG 内唯一标识
        tool_slug: kebab-case 工具标识，引用 Tool.slug
        depends_on: 依赖的上游节点 node_id 列表
        arguments_template: 参数模板，支持 ${upstream_node.output.field} 变量插值
        failure_strategy: 节点级覆盖策略；None 时使用 DAG 级别策略
        skip_on_upstream_failure: 上游失败时是否跳过本节点
    """

    node_id: str
    tool_slug: str
    depends_on: tuple[str, ...] = ()
    arguments_template: dict[str, Any] = field(default_factory=dict)
    failure_strategy: FailureStrategy | None = None
    skip_on_upstream_failure: bool = True

    def __post_init__(self) -> None:
        """构造时强制校验字段不变量"""
        self.validate()

    def validate(self) -> bool:
        """验证字段不变量

        Raises:
            EntityValidationError: 任何不变量违反
        """
        if not isinstance(self.node_id, str) or not self.node_id.strip():
            raise EntityValidationError(
                message="node_id 必须为非空字符串",
                context={"entity": "ToolChainNode", "field": "node_id"},
            )
        if not isinstance(self.tool_slug, str) or not self.tool_slug.strip():
            raise EntityValidationError(
                message="tool_slug 必须为非空字符串",
                context={"entity": "ToolChainNode", "field": "tool_slug"},
            )
        if not isinstance(self.depends_on, tuple):
            raise EntityValidationError(
                message="depends_on 必须为 tuple[str, ...]",
                context={"entity": "ToolChainNode", "field": "depends_on"},
            )
        for dep in self.depends_on:
            if not isinstance(dep, str) or not dep.strip():
                raise EntityValidationError(
                    message="depends_on 内每个元素必须为非空字符串",
                    context={
                        "entity": "ToolChainNode",
                        "field": "depends_on",
                        "invalid_element": dep,
                    },
                )
        if not isinstance(self.arguments_template, dict):
            raise EntityValidationError(
                message="arguments_template 必须为 dict",
                context={"entity": "ToolChainNode", "field": "arguments_template"},
            )
        if self.failure_strategy is not None and not isinstance(self.failure_strategy, FailureStrategy):
            raise EntityValidationError(
                message="failure_strategy 必须为 FailureStrategy 枚举值或 None",
                context={
                    "entity": "ToolChainNode",
                    "field": "failure_strategy",
                    "value": self.failure_strategy,
                },
            )
        return True


@dataclass(frozen=True)
class ToolChainDag:
    """工具链 DAG 聚合根（不可变）

    Attributes:
        chain_id: 聚合根主键
        tenant_id: 多租户隔离
        name: DAG 名称（如 "pestel-to-swot-analysis"）
        description: DAG 业务说明
        nodes: 有序节点列表（不可变 tuple）
        failure_strategy: DAG 级别失败策略
        max_concurrency: 最大并发节点数，默认 5
        created_at: 创建时间
        updated_at: 更新时间
        _reverse_adj: 反向邻接表（O(V+E) 一次性构建），供 SKIP_DOWNSTREAM BFS 使用
    """

    chain_id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str
    nodes: tuple[ToolChainNode, ...]
    failure_strategy: FailureStrategy
    max_concurrency: int
    created_at: datetime
    updated_at: datetime
    # 反向邻接表：node_id → 其下游节点列表（供 SKIP_DOWNSTREAM 失败传播使用）
    _reverse_adj: dict[str, tuple[str, ...]] = field(default_factory=dict, init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        """构造时强制校验 + 预计算 _reverse_adj 反向邻接表"""
        self.validate()
        self._build_reverse_adj()

    def validate(self) -> bool:
        """验证聚合根不变量

        Raises:
            EntityValidationError: 任何不变量违反
        """
        if not isinstance(self.chain_id, uuid.UUID):
            raise EntityValidationError(
                message="chain_id 必须为有效 UUID",
                context={"entity": "ToolChainDag", "field": "chain_id"},
            )
        if not isinstance(self.tenant_id, uuid.UUID):
            raise EntityValidationError(
                message="tenant_id 必须为有效 UUID",
                context={"entity": "ToolChainDag", "field": "tenant_id"},
            )
        if not isinstance(self.name, str) or not self.name.strip():
            raise EntityValidationError(
                message="name 必须为非空字符串",
                context={"entity": "ToolChainDag", "field": "name"},
            )
        if not isinstance(self.description, str):
            raise EntityValidationError(
                message="description 必须为 str",
                context={"entity": "ToolChainDag", "field": "description"},
            )
        if not isinstance(self.nodes, tuple):
            raise EntityValidationError(
                message="nodes 必须为 tuple[ToolChainNode, ...]",
                context={"entity": "ToolChainDag", "field": "nodes"},
            )
        if len(self.nodes) == 0:
            raise EntityValidationError(
                message="nodes 不能为空（DAG 至少包含一个节点）",
                context={"entity": "ToolChainDag", "field": "nodes"},
            )
        for node in self.nodes:
            if not isinstance(node, ToolChainNode):
                raise EntityValidationError(
                    message="nodes 内每个元素必须为 ToolChainNode 实例",
                    context={
                        "entity": "ToolChainDag",
                        "field": "nodes",
                        "invalid_element_type": type(node).__name__,
                    },
                )
        if not isinstance(self.failure_strategy, FailureStrategy):
            raise EntityValidationError(
                message="failure_strategy 必须为 FailureStrategy 枚举值",
                context={
                    "entity": "ToolChainDag",
                    "field": "failure_strategy",
                    "value": self.failure_strategy,
                },
            )
        if not isinstance(self.max_concurrency, int) or self.max_concurrency < 1:
            raise EntityValidationError(
                message="max_concurrency 必须 ≥ 1",
                context={
                    "entity": "ToolChainDag",
                    "field": "max_concurrency",
                    "value": self.max_concurrency,
                },
            )
        if not isinstance(self.created_at, datetime):
            raise EntityValidationError(
                message="created_at 必须为 datetime",
                context={"entity": "ToolChainDag", "field": "created_at"},
            )
        if not isinstance(self.updated_at, datetime):
            raise EntityValidationError(
                message="updated_at 必须为 datetime",
                context={"entity": "ToolChainDag", "field": "updated_at"},
            )
        if self.updated_at < self.created_at:
            raise EntityValidationError(
                message="updated_at 不能早于 created_at",
                context={
                    "entity": "ToolChainDag",
                    "created_at": self.created_at.isoformat(),
                    "updated_at": self.updated_at.isoformat(),
                },
            )
        return True

    def _build_reverse_adj(self) -> None:
        """预计算反向邻接表（O(V+E)），供 SKIP_DOWNSTREAM BFS 使用

        算法：对于每个节点 n，遍历其 depends_on 列表，将 n 加入 reverse_adj[dep]
        使用 object.__setattr__ 突破 @dataclass(frozen=True) 限制
        """
        reverse_adj: dict[str, list[str]] = {n.node_id: [] for n in self.nodes}
        for node in self.nodes:
            for dep in node.depends_on:
                if dep not in reverse_adj:
                    # 依赖节点不在 nodes 列表中（应为前置校验捕获，留防御性）
                    reverse_adj[dep] = []
                reverse_adj[dep].append(node.node_id)
        # 转 tuple 不可变
        final = {k: tuple(v) for k, v in reverse_adj.items()}
        object.__setattr__(self, "_reverse_adj", final)

    def nodes_by_id(self, node_id: str) -> ToolChainNode:
        """通过 node_id 查找节点（O(V)，但 V 通常较小）

        Args:
            node_id: 节点标识

        Returns:
            ToolChainNode 实例

        Raises:
            KeyError: 节点不存在
        """
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        raise KeyError(f"节点 '{node_id}' 不在 DAG '{self.chain_id}' 中")


__all__ = ["FailureStrategy", "ToolChainNode", "ToolChainDag"]
