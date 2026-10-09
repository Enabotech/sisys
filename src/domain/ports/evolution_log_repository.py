"""领域层演进日志仓储端口模块（Story 4.7 AC-4）

定义 EvolutionLogRepositoryPort——反馈闭环终态记录的持久化端口。

- save 按 execution_id 幂等 upsert（同 execution 重复写入不产生重复行）
- 查询使用 Query Object 模式（CLAUDE.md §4 多字段+分页决策规则——
  ToolExecutionQuery 先例同款）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.domain.entities.evolution_log_entry import EvolutionLogEntry
from src.domain.ports.l2_rdb import L2RdbPort

__all__ = ["EvolutionLogQuery", "EvolutionLogRepositoryPort"]


@dataclass(frozen=True)
class EvolutionLogQuery:
    """演进日志查询值对象（Query Object 模式——多字段组合 + 分页）

    Attributes:
        tool_id: 按工具 ID 过滤（「按工具查询反馈历史」主查询面，可选）
        tenant_id: 按租户过滤（可选——缺省跨租户聚合运维视图）
        execution_id: 按执行 ID 精确过滤（可选）
        offset: 分页偏移（默认 0）
        limit: 分页大小（默认 100）
    """

    tool_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None
    execution_id: uuid.UUID | None = None
    offset: int = 0
    limit: int = 100


@runtime_checkable
class EvolutionLogRepositoryPort(L2RdbPort[EvolutionLogEntry], Protocol):
    """演进日志仓储端口（execution_id 幂等 + 失败历史双查询面）"""

    async def save(self, entity: EvolutionLogEntry) -> EvolutionLogEntry:
        """保存日志（execution_id upsert 幂等——同 execution 重复写入覆盖为最新次）.

        Args:
            entity: 演进日志条目

        Returns:
            保存后的实体
        """
        ...

    async def list_by_query(self, query: EvolutionLogQuery) -> tuple[EvolutionLogEntry, ...]:
        """按查询条件列出演进日志（created_at 降序——最近反馈在前）.

        Args:
            query: 查询值对象（多字段过滤 + 分页）

        Returns:
            日志元组（按 created_at 降序）
        """
        ...

    async def get_by_execution(
        self,
        execution_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> EvolutionLogEntry | None:
        """按 execution_id 精确定位单次记录（幂等短路判定的读取面）.

        Args:
            execution_id: 触发执行的 execution id
            tenant_id: 租户 ID（隔离）

        Returns:
            命中日志；未命中返回 None
        """
        ...
