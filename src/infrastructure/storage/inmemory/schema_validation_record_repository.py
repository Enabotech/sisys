"""基础设施层 Schema 验证记录 InMemory 仓储模块

实现 InMemorySchemaValidationRecordRepository(Story 4.3 AC-5):
- 继承 L2RdbPort[SchemaValidationRecord]
- asyncio.Lock 类变量(CLAUDE.md §6 硬约束)
- list_by_query / count 领域扩展方法
- 租户隔离 + 时间倒序 + 分页

用于集成测试与本地开发,生产环境替换为 PostgreSQL 实现(migration 013)。
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Dict, List

from src.domain.entities.schema_validation_record import (
    SchemaValidationRecord,
    SchemaValidationRecordQuery,
)
from src.domain.ports.l2_rdb import L2RdbPort


class InMemorySchemaValidationRecordRepository(L2RdbPort[SchemaValidationRecord]):
    """内存 Schema 验证记录仓储

    关键设计（CLAUDE.md §6）：
    - asyncio.Lock 必须声明为**类变量**(非实例变量),保证多协程间共享锁
    - _records 是**实例变量**(每个实例独立存储),与 _lock 类变量对比清晰
    """

    # CLAUDE.md §6:asyncio.Lock 必须声明为类变量
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """初始化内存仓储"""
        self._records: Dict[uuid.UUID, SchemaValidationRecord] = {}

    # ---- L2RdbPort 继承方法（async） ----

    async def get_by_id(self, id: uuid.UUID) -> SchemaValidationRecord | None:
        """通过 ID 获取记录"""
        async with self._lock:
            return self._records.get(id)

    async def save(self, entity: SchemaValidationRecord) -> SchemaValidationRecord:
        """保存记录（insert or update）"""
        entity.validate()
        async with self._lock:
            self._records[entity.record_id] = entity
            return entity

    async def delete(self, id: uuid.UUID) -> None:
        """通过 ID 删除记录"""
        async with self._lock:
            self._records.pop(id, None)

    async def list_all(self) -> List[SchemaValidationRecord]:
        """列出所有记录"""
        async with self._lock:
            return list(self._records.values())

    # ---- 领域扩展方法 ----

    async def list_by_query(
        self,
        query: SchemaValidationRecordQuery,
    ) -> List[SchemaValidationRecord]:
        """通过 Query Object 多字段过滤查询

        Args:
            query: 查询条件

        Returns:
            符合条件记录列表（按 validated_at DESC 排序 + offset/limit 分页）
        """
        results = list(self._records.values())
        if query.tenant_id is not None:
            results = [r for r in results if r.tenant_id == query.tenant_id]
        if query.tool_id is not None:
            results = [r for r in results if r.tool_id == query.tool_id]
        if query.execution_id is not None:
            results = [r for r in results if r.execution_id == query.execution_id]
        if query.validation_phase is not None:
            results = [r for r in results if r.validation_phase == query.validation_phase]
        if query.is_valid is not None:
            results = [r for r in results if r.is_valid == query.is_valid]
        results.sort(key=lambda r: r.validated_at, reverse=True)
        return results[query.offset : query.offset + query.limit]

    async def count(self, query: SchemaValidationRecordQuery) -> int:
        """统计符合条件记录数量

        Args:
            query: 查询条件

        Returns:
            记录总数
        """
        all_results = await self.list_by_query(
            SchemaValidationRecordQuery(
                tenant_id=query.tenant_id,
                tool_id=query.tool_id,
                execution_id=query.execution_id,
                validation_phase=query.validation_phase,
                is_valid=query.is_valid,
                offset=0,
                limit=10**9,
            )
        )
        return len(all_results)


__all__ = ["InMemorySchemaValidationRecordRepository"]
