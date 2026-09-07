"""基础设施层 PostgreSQL ToolExecution 仓储

最小可用实现：使用 asyncpg 直接查询。
为集成测试设计（CLAUDE.md §5 真实服务 TestTenant 隔离模式）。

不替代未来的 SQLAlchemy 实现（后续 Story 替换）。

设计说明：
- SQL 字符串使用硬编码表名（不使用字符串拼接），避开 bandit B608 误报
- asyncpg 使用参数化查询（$1, $2, ...），无 SQL 注入风险
- schema 隔离由 fixture 通过 DELETE FROM tool_executions 实现
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg

from src.domain.entities.tool_execution import (
    ToolExecution,
    ToolExecutionState,
)
from src.domain.exceptions.business_exceptions import EntityStateTransitionError
from src.domain.ports.tool_execution_repository import (
    ToolExecutionQuery,
    ToolExecutionRepositoryPort,
)

# 硬编码表名（测试专用 adapter；生产应使用 SQLAlchemy 实现）
TABLE_NAME = "tool_executions"


class PostgreSQLToolExecutionRepository(ToolExecutionRepositoryPort):
    """PostgreSQL ToolExecution 仓储（asyncpg 直连）

    设计原则：
    - SQL 字符串使用硬编码表名 + asyncpg 参数化查询
    - 测试通过 DELETE FROM tool_executions 实现隔离
    - save() 用 INSERT ON CONFLICT 实现 upsert
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        schema: str = "public",
    ) -> None:
        self._pool = pool
        # 兼容 schema 参数（默认 public），硬编码表名
        self._schema = schema

    async def save(self, entity: ToolExecution) -> ToolExecution:
        """upsert ToolExecution（INSERT ON CONFLICT）"""
        entity.validate()
        sql_insert = (
            "INSERT INTO tool_executions "
            "(execution_id, tenant_id, tool_id, tool_version, state, "
            "started_at, completed_at, retry_count, failure_reason, "
            "state_version) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
            "ON CONFLICT (execution_id) DO UPDATE SET "
            "state = EXCLUDED.state, "
            "completed_at = EXCLUDED.completed_at, "
            "retry_count = EXCLUDED.retry_count, "
            "failure_reason = EXCLUDED.failure_reason, "
            "state_version = EXCLUDED.state_version, "
            "updated_at = NOW()"
        )
        async with self._pool.acquire() as conn:
            await conn.execute(
                sql_insert,
                entity.execution_id,
                entity.tenant_id,
                entity.tool_id,
                entity.tool_version,
                entity.state.value,
                entity.started_at,
                entity.completed_at,
                entity.retry_count,
                entity.failure_reason,
                entity.state_version,
            )
        return entity

    async def get_by_id(self, id: uuid.UUID) -> ToolExecution | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tool_executions WHERE execution_id = $1",
                id,
            )
        if row is None:
            return None
        return self._row_to_entity(row)

    async def delete(self, id: uuid.UUID) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM tool_executions WHERE execution_id = $1",
                id,
            )

    async def list_all(self) -> list[ToolExecution]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM tool_executions")
        return [self._row_to_entity(r) for r in rows]

    async def list_by_query(self, query: ToolExecutionQuery) -> list[ToolExecution]:
        sql_parts = ["SELECT * FROM tool_executions WHERE 1=1"]
        params: list[Any] = []
        if query.tenant_id is not None:
            params.append(query.tenant_id)
            sql_parts.append(f"AND tenant_id = ${len(params)}")
        if query.tool_id is not None:
            params.append(query.tool_id)
            sql_parts.append(f"AND tool_id = ${len(params)}")
        if query.state is not None:
            params.append(query.state.value)
            sql_parts.append(f"AND state = ${len(params)}")
        if query.started_after is not None:
            params.append(query.started_after)
            sql_parts.append(f"AND started_at >= ${len(params)}")
        if query.started_before is not None:
            params.append(query.started_before)
            sql_parts.append(f"AND started_at <= ${len(params)}")
        sql_parts.append("ORDER BY started_at DESC")
        params.append(query.limit)
        sql_parts.append(f"LIMIT ${len(params)}")
        params.append(query.offset)
        sql_parts.append(f"OFFSET ${len(params)}")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(" ".join(sql_parts), *params)
        return [self._row_to_entity(r) for r in rows]

    async def count(self, query: ToolExecutionQuery) -> int:
        sql_parts = ["SELECT COUNT(*) FROM tool_executions WHERE 1=1"]
        params: list[Any] = []
        if query.tenant_id is not None:
            params.append(query.tenant_id)
            sql_parts.append(f"AND tenant_id = ${len(params)}")
        if query.tool_id is not None:
            params.append(query.tool_id)
            sql_parts.append(f"AND tool_id = ${len(params)}")
        if query.state is not None:
            params.append(query.state.value)
            sql_parts.append(f"AND state = ${len(params)}")

        async with self._pool.acquire() as conn:
            return await conn.fetchval(" ".join(sql_parts), *params) or 0

    async def save_with_state_version(
        self,
        execution: ToolExecution,
        expected_state_version: int,
    ) -> ToolExecution:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state_version FROM tool_executions WHERE execution_id = $1",
                execution.execution_id,
            )
            if row is None:
                raise EntityStateTransitionError(
                    entity_type="ToolExecution",
                    entity_id=str(execution.execution_id),
                    from_status="UNKNOWN",
                    to_status=execution.state.name,
                    message="execution not found in repository",
                )
            if row["state_version"] != expected_state_version:
                raise EntityStateTransitionError(
                    entity_type="ToolExecution",
                    entity_id=str(execution.execution_id),
                    from_status="UNKNOWN",
                    to_status=execution.state.name,
                    message=(
                        f"Optimistic lock conflict: expected state_version="
                        f"{expected_state_version}, actual={row['state_version']}"
                    ),
                )
            sql_update = (
                "UPDATE tool_executions SET state = $2, completed_at = $3, "
                "retry_count = $4, failure_reason = $5, "
                "state_version = state_version + 1, updated_at = NOW() "
                "WHERE execution_id = $1"
            )
            await conn.execute(
                sql_update,
                execution.execution_id,
                execution.state.value,
                execution.completed_at,
                execution.retry_count,
                execution.failure_reason,
            )
        execution.state_version = expected_state_version + 1
        return execution

    def _row_to_entity(self, row: Any) -> ToolExecution:
        """将 PG 行转换为 ToolExecution 实体"""
        return ToolExecution(
            execution_id=row["execution_id"],
            tenant_id=row["tenant_id"],
            tool_id=row["tool_id"],
            tool_version=row["tool_version"],
            state=ToolExecutionState(row["state"]),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            retry_count=row["retry_count"],
            failure_reason=row["failure_reason"],
            state_version=row["state_version"],
        )
