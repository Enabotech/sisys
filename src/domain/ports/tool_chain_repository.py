"""领域层工具链仓储端口模块

定义 ToolChainRepositoryPort（领域层仓储端口），提供 ToolChainDag 聚合根的
持久化与查询能力。

设计依据：Story 4.2 AC-3
- 继承 L2RdbPort[ToolChainDag]（async CRUD 基座）
- 领域扩展方法：list_by_query / count
- 查询使用 Query Object 模式（CLAUDE.md §4）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.domain.entities.tool_chain import FailureStrategy, ToolChainDag
from src.domain.ports.l2_rdb import L2RdbPort


@dataclass(frozen=True)
class ToolChainDagQuery:
    """ToolChainDag 查询值对象（Query Object 模式）

    Attributes:
        tenant_id: 多租户隔离（可选）
        name: 按名称精确过滤（可选）
        failure_strategy: 按失败策略过滤（可选）
        min_nodes: 至少包含 N 个节点（可选）
        max_nodes: 最多包含 N 个节点（可选）
        offset: 分页偏移（默认）
        limit: 分页大小（默认 100）
    """

    tenant_id: uuid.UUID | None = None
    name: str | None = None
    failure_strategy: FailureStrategy | None = None
    min_nodes: int | None = None
    max_nodes: int | None = None
    offset: int = 0
    limit: int = 100


@runtime_checkable
class ToolChainRepositoryPort(L2RdbPort[ToolChainDag], Protocol):
    """工具链仓储端口协议（领域层）

    继承 L2RdbPort[ToolChainDag] 泛型 async CRUD 基座：
    - async def get_by_id(id) -> ToolChainDag | None
    - async def save(entity) -> ToolChainDag
    - async def delete(id) -> None
    - async def list_all() -> list[ToolChainDag]

    领域扩展方法：
    - async def list_by_query(query) -> list[ToolChainDag]
    - async def count(query) -> int
    """

    async def list_by_query(
        self,
        query: ToolChainDagQuery,
    ) -> list[ToolChainDag]:
        """通过 Query Object 查询 ToolChainDag 列表

        Args:
            query: 查询条件

        Returns:
            符合条件的 ToolChainDag 列表
        """
        ...

    async def count(self, query: ToolChainDagQuery) -> int:
        """统计符合条件的 ToolChainDag 数量

        Args:
            query: 查询条件

        Returns:
            数量
        """
        ...


__all__ = ["ToolChainDagQuery", "ToolChainRepositoryPort"]
