"""领域层工具执行仓储端口模块

定义 ToolExecutionRepositoryPort（领域层仓储端口），
提供 ToolExecution 聚合根的持久化与查询能力。

设计依据：Story 4.1a AC-1.5
- 继承 L2RdbPort[ToolExecution]（async CRUD 基座）
- 领域扩展方法：list_by_query / count / save_with_state_version
- 查询使用 Query Object 模式（CLAUDE.md §4）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from src.domain.entities.tool_execution import ToolExecution, ToolExecutionState
from src.domain.ports.l2_rdb import L2RdbPort


@dataclass(frozen=True)
class ToolExecutionQuery:
    """ToolExecution 查询值对象（Query Object 模式）

    Attributes:
        tenant_id: 多租户隔离（可选）
        tool_id: 按工具 ID 过滤（可选）
        state: 按状态过滤（可选）
        started_after: 起始时间过滤（可选）
        started_before: 结束时间过滤（可选）
        offset: 分页偏移（默认 0）
        limit: 分页大小（默认 100）
    """

    tenant_id: uuid.UUID | None = None
    tool_id: uuid.UUID | None = None
    state: ToolExecutionState | None = None
    started_after: datetime | None = None
    started_before: datetime | None = None
    offset: int = 0
    limit: int = 100


@runtime_checkable
class ToolExecutionRepositoryPort(L2RdbPort[ToolExecution], Protocol):
    """工具执行仓储端口协议（领域层）

    继承 L2RdbPort[ToolExecution] 泛型 async CRUD 基座：
    - async def get_by_id(id) -> ToolExecution | None
    - async def save(entity) -> ToolExecution
    - async def delete(id) -> None
    - async def list_all() -> list[ToolExecution]

    领域扩展方法：
    - async def list_by_query(query) -> list[ToolExecution]
    - async def count(query) -> int
    - async def save_with_state_version(execution, expected_version) -> ToolExecution
    """

    async def list_by_query(
        self,
        query: ToolExecutionQuery,
    ) -> list[ToolExecution]:
        """通过 Query Object 查询 ToolExecution 列表

        Args:
            query: 查询条件

        Returns:
            符合条件的 ToolExecution 列表
        """
        ...

    async def count(self, query: ToolExecutionQuery) -> int:
        """统计符合条件的 ToolExecution 数量

        Args:
            query: 查询条件

        Returns:
            数量
        """
        ...

    async def save_with_state_version(
        self,
        execution: ToolExecution,
        expected_state_version: int,
    ) -> ToolExecution:
        """乐观锁 CAS 保存（防并发覆盖）

        Args:
            execution: 待保存的 ToolExecution
            expected_state_version: 期望的 state_version

        Returns:
            保存后的实体

        Raises:
            EntityStateTransitionError: state_version 不匹配
        """
        ...
