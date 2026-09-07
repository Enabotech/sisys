"""内存工具执行仓储实现模块

实现 InMemoryToolExecutionRepository，遵循 ToolExecutionRepositoryPort 接口。
继承 L2RdbPort[ToolExecution] async CRUD 基座，所有方法 async。

CLAUDE.md §6 Gotchas：asyncio.Lock 必须声明为类变量而非实例变量。
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Dict, List

from src.domain.entities.tool_execution import ToolExecution
from src.domain.exceptions import EntityStateTransitionError
from src.domain.ports.l2_rdb import L2RdbPort
from src.domain.ports.tool_execution_repository import ToolExecutionQuery


class InMemoryToolExecutionRepository(L2RdbPort[ToolExecution]):
    """内存工具执行仓储

    关键设计：
    - 继承 L2RdbPort[ToolExecution] 获得 async CRUD 接口
    - asyncio.Lock 类变量（CLAUDE.md §6）
    - 乐观锁 CAS（save_with_state_version）
    """

    # CLAUDE.md §6：asyncio.Lock 必须声明为类变量
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """初始化内存仓储"""
        self._executions: Dict[uuid.UUID, ToolExecution] = {}

    # ---- L2RdbPort 继承方法（async） ----

    async def get_by_id(self, id: uuid.UUID) -> ToolExecution | None:
        """通过 ID 获取实体（返回 None 而非抛错）"""
        async with self._lock:
            return self._executions.get(id)

    async def save(self, entity: ToolExecution) -> ToolExecution:
        """保存实体（insert or update）"""
        entity.validate()
        async with self._lock:
            self._executions[entity.execution_id] = entity
            return entity

    async def delete(self, id: uuid.UUID) -> None:
        """通过 ID 删除实体"""
        async with self._lock:
            self._executions.pop(id, None)

    async def list_all(self) -> List[ToolExecution]:
        """列出所有实体"""
        async with self._lock:
            return list(self._executions.values())

    # ---- 领域扩展方法 ----

    async def list_by_query(self, query: ToolExecutionQuery) -> List[ToolExecution]:
        """通过 Query Object 查询"""
        results = list(self._executions.values())
        if query.tenant_id is not None:
            results = [e for e in results if e.tenant_id == query.tenant_id]
        if query.tool_id is not None:
            results = [e for e in results if e.tool_id == query.tool_id]
        if query.state is not None:
            results = [e for e in results if e.state == query.state]
        if query.started_after is not None:
            results = [e for e in results if e.started_at >= query.started_after]
        if query.started_before is not None:
            results = [e for e in results if e.started_at <= query.started_before]
        results.sort(key=lambda e: e.started_at, reverse=True)
        return results[query.offset : query.offset + query.limit]

    async def count(self, query: ToolExecutionQuery) -> int:
        """统计符合条件的实体数量"""
        all_results = await self.list_by_query(
            ToolExecutionQuery(
                tenant_id=query.tenant_id,
                tool_id=query.tool_id,
                state=query.state,
                started_after=query.started_after,
                started_before=query.started_before,
                offset=0,
                limit=10**9,
            )
        )
        return len(all_results)

    async def save_with_state_version(
        self,
        execution: ToolExecution,
        expected_state_version: int,
    ) -> ToolExecution:
        """乐观锁 CAS（防并发覆盖）

        Raises:
            EntityStateTransitionError: state_version 不匹配
        """
        async with self._lock:
            current = self._executions.get(execution.execution_id)
            if current is None:
                raise EntityStateTransitionError(
                    entity_type="ToolExecution",
                    entity_id=str(execution.execution_id),
                    from_status="UNKNOWN",
                    to_status=execution.state.name,
                    message="execution not found in repository",
                )
            if current.state_version != expected_state_version:
                raise EntityStateTransitionError(
                    entity_type="ToolExecution",
                    entity_id=str(execution.execution_id),
                    from_status=current.state.name,
                    to_status=execution.state.name,
                    message=(
                        f"Optimistic lock conflict: expected state_version="
                        f"{expected_state_version}, actual={current.state_version}"
                    ),
                )
            execution.validate()
            self._executions[execution.execution_id] = execution
            return execution


__all__ = ["InMemoryToolExecutionRepository"]
