"""内存演进日志仓储实现（Story 4.7 AC-4）

InMemoryEvolutionLogRepository——单测/验收装配用内存实现（生产为 PostgreSQL 实现）。

- execution_id 幂等 upsert（同 execution 重复写入覆盖为最新次）
- list_by_query 多字段过滤 + created_at 降序 + 分页
- 双端深拷贝隔离（4-6 CR1-2）
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime

from src.domain.entities.evolution_log_entry import EvolutionLogEntry
from src.domain.ports.evolution_log_repository import (
    EvolutionLogQuery,
    EvolutionLogRepositoryPort,
)

__all__ = ["InMemoryEvolutionLogRepository"]

# 排序兜底纪元（created_at 类型注解含 None——构造后必非 None，类型系统不知）
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _detached(entry: EvolutionLogEntry) -> EvolutionLogEntry:
    """返回与仓储内部存储完全隔离的副本（双端副本纪律）."""
    return copy.deepcopy(entry)


class InMemoryEvolutionLogRepository(EvolutionLogRepositoryPort):
    """内存演进日志仓储（execution_id 索引 + 幂等 upsert）"""

    def __init__(self) -> None:
        """初始化索引结构."""
        self._entries: dict[uuid.UUID, EvolutionLogEntry] = {}

    async def save(self, entity: EvolutionLogEntry) -> EvolutionLogEntry:
        """保存日志（execution_id upsert 幂等——重复写入覆盖）."""
        stored = _detached(entity)
        self._entries[stored.execution_id] = stored
        return _detached(stored)

    async def list_by_query(self, query: EvolutionLogQuery) -> tuple[EvolutionLogEntry, ...]:
        """按查询条件列出（created_at 降序 + 分页）."""
        matched = [
            entry
            for entry in self._entries.values()
            if (query.tool_id is None or entry.tool_id == query.tool_id)
            and (query.tenant_id is None or entry.tenant_id == query.tenant_id)
            and (query.execution_id is None or entry.execution_id == query.execution_id)
        ]
        matched.sort(key=lambda e: e.created_at or _EPOCH, reverse=True)
        return tuple(_detached(e) for e in matched[query.offset : query.offset + query.limit])

    async def get_by_execution(
        self,
        execution_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> EvolutionLogEntry | None:
        """按 execution_id 精确定位（租户隔离）."""
        entry = self._entries.get(execution_id)
        if entry is None or entry.tenant_id != tenant_id:
            return None
        return _detached(entry)

    # ---- L2RdbPort 基座方法（端口契约完整性——PG 版经 PostgreSQLAdapter 获得）----

    async def get_by_id(self, id: uuid.UUID) -> EvolutionLogEntry | None:
        """按主键获取（L2RdbPort 基座）."""
        entry = self._entries.get(id)
        return _detached(entry) if entry is not None else None

    async def delete(self, id: uuid.UUID) -> None:
        """按主键删除（L2RdbPort 基座）."""
        self._entries.pop(id, None)

    async def list_all(self) -> list[EvolutionLogEntry]:
        """列出全部（L2RdbPort 基座——created_at 降序）."""
        entries = sorted(self._entries.values(), key=lambda e: e.created_at or _EPOCH, reverse=True)
        return [_detached(e) for e in entries]
