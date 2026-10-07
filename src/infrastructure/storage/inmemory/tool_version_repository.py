"""基础设施层工具版本 InMemory 仓储模块（Story 4-6）

实现 InMemoryToolVersionRepository：
- 继承 L2RdbPort[ToolVersion]（InMemorySchemaValidationRecordRepository 先例形态）
- asyncio.Lock 类变量（CLAUDE.md §6 Gotchas）
- (tool_id, version) 唯一性 + 单 STABLE/单 CANARY 不变量软校验
  （与 PG partial unique index 硬守护双层对齐——单活跃不变量测试直连构造）

用于集成测试与本地开发；生产环境为 PostgreSQL 实现（migration 016）。
"""

from __future__ import annotations

import asyncio
import copy
import uuid

from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus
from src.domain.exceptions.tool_version_exceptions import (
    ToolVersionAlreadyExistsError,
    ToolVersionTrafficWeightError,
)
from src.domain.ports.tool_version_repository import (
    ToolVersionQuery,
    ToolVersionRepositoryPort,
)

# 单活跃不变量状态集（软校验范围——与 migration 016 partial unique index 对齐）
_SINGLETON_STATES = (ToolVersionStatus.STABLE, ToolVersionStatus.CANARY)


def _detached(tv: ToolVersion) -> ToolVersion:
    """返回与仓储内部存储完全隔离的副本。

    双端副本纪律：save 存副本、读路径返回副本——调用方在校验失败等异常
    路径上对实体的就地改写不会污染仓储持有的共享引用（ToolVersion 字段
    全部为 deepcopy 安全类型：UUID/datetime/dict/Enum/str/int）。
    """
    return copy.deepcopy(tv)


class InMemoryToolVersionRepository(ToolVersionRepositoryPort):
    """内存工具版本仓储。

    关键设计（CLAUDE.md §6）：
    - asyncio.Lock 声明为**类变量**（多协程共享），_versions 为实例变量
    - 保存顺序契约：多行状态变更由服务层保证"先降级/清场、后提升"
      （save 只对逐条记录做不变量校验，与 PG partial index 逐语句语义一致）
    """

    # CLAUDE.md §6：asyncio.Lock 必须声明为类变量
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """初始化内存仓储（主存储 + 复合键索引双结构）。"""
        self._versions: dict[uuid.UUID, ToolVersion] = {}
        self._by_tool_version: dict[tuple[uuid.UUID, str], ToolVersion] = {}

    # ---- L2RdbPort 继承方法（async） ----

    async def get_by_id(self, id: uuid.UUID) -> ToolVersion | None:
        """通过 ID 获取版本（返回隔离副本）。"""
        async with self._lock:
            tv = self._versions.get(id)
            return _detached(tv) if tv is not None else None

    async def save(self, entity: ToolVersion) -> ToolVersion:
        """保存版本（新记录做唯一性与单活跃校验；同 ID 为原地更新）。

        Args:
            entity: 版本实体

        Returns:
            保存后的实体

        Raises:
            ToolVersionAlreadyExistsError: (tool_id, version) 已存在（新记录）
            ToolVersionTrafficWeightError: 单 STABLE/单 CANARY 不变量破坏
        """
        entity.validate()
        async with self._lock:
            key = (entity.tool_id, entity.version)
            existing = self._by_tool_version.get(key)
            if existing is not None and existing.version_id != entity.version_id:
                raise ToolVersionAlreadyExistsError(tool_id=str(entity.tool_id), version=entity.version)
            is_new = entity.version_id not in self._versions
            if entity.status in _SINGLETON_STATES:
                conflict = any(
                    other.version_id != entity.version_id and other.tool_id == entity.tool_id and other.status == entity.status
                    for other in self._versions.values()
                )
                if conflict:
                    raise ToolVersionTrafficWeightError(
                        tool_id=str(entity.tool_id),
                        version=entity.version,
                        conflict_reason=f"单 {entity.status.value} 不变量破坏（并存冲突族）",
                    )
            self._versions[entity.version_id] = _detached(entity)
            self._by_tool_version[key] = self._versions[entity.version_id]
            if not is_new and existing is None:
                # 同 ID 但复合键索引缺失的防御（正常流程不可达）
                for other_key, other in list(self._by_tool_version.items()):
                    if other.version_id == entity.version_id and other_key != key:
                        del self._by_tool_version[other_key]
            return entity

    async def delete(self, id: uuid.UUID) -> None:
        """通过 ID 删除版本（双索引同步）。"""
        async with self._lock:
            entity = self._versions.pop(id, None)
            if entity is not None:
                self._by_tool_version.pop((entity.tool_id, entity.version), None)

    async def list_all(self) -> list[ToolVersion]:
        """列出全部版本（返回隔离副本）。"""
        async with self._lock:
            return [_detached(tv) for tv in self._versions.values()]

    # ---- 领域扩展方法 ----

    async def get_by_tool_and_version(
        self,
        tool_id: uuid.UUID,
        version: str,
    ) -> ToolVersion | None:
        """按 (tool_id, version) 精确查找（返回隔离副本）。"""
        async with self._lock:
            tv = self._by_tool_version.get((tool_id, version))
            return _detached(tv) if tv is not None else None

    async def list_by_query(self, query: ToolVersionQuery) -> list[ToolVersion]:
        """Query Object 多字段过滤（按注册时间升序 + 分页，返回隔离副本）。"""
        async with self._lock:
            snapshot = [_detached(tv) for tv in self._versions.values()]
        results = snapshot
        if query.tool_id is not None:
            results = [tv for tv in results if tv.tool_id == query.tool_id]
        if query.status is not None:
            results = [tv for tv in results if tv.status == query.status]
        if query.version is not None:
            results = [tv for tv in results if tv.version == query.version]
        if query.created_after is not None:
            results = [tv for tv in results if tv.created_at >= query.created_after]
        if query.created_before is not None:
            results = [tv for tv in results if tv.created_at < query.created_before]
        results.sort(key=lambda tv: tv.created_at)
        return results[query.offset : query.offset + query.limit]

    async def count(self, query: ToolVersionQuery) -> int:
        """统计符合条件的版本数量。"""
        results = await self.list_by_query(
            ToolVersionQuery(
                tool_id=query.tool_id,
                status=query.status,
                version=query.version,
                created_after=query.created_after,
                created_before=query.created_before,
                offset=0,
                limit=10**9,
            )
        )
        return len(results)

    async def list_active(self, tool_id: uuid.UUID) -> list[ToolVersion]:
        """查询工具的活跃版本（CANARY + STABLE，返回隔离副本）。"""
        async with self._lock:
            return [
                _detached(tv)
                for tv in self._versions.values()
                if tv.tool_id == tool_id and tv.status in (ToolVersionStatus.CANARY, ToolVersionStatus.STABLE)
            ]


__all__ = ["InMemoryToolVersionRepository"]
