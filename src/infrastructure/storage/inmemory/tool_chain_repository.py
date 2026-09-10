"""内存工具链仓储实现模块

实现 InMemoryToolChainRepository，遵循 ToolChainRepositoryPort 接口。
继承 L2RdbPort[ToolChainDag] async CRUD 基座，所有方法 async。

CLAUDE.md §6 Gotchas：asyncio.Lock 必须声明为类变量而非实例变量。
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Dict, List

from src.domain.entities.tool_chain import ToolChainDag
from src.domain.ports.l2_rdb import L2RdbPort
from src.domain.ports.tool_chain_repository import ToolChainDagQuery


class InMemoryToolChainRepository(L2RdbPort[ToolChainDag]):
    """内存工具链仓储

    关键设计：
    - 继承 L2RdbPort[ToolChainDag] 获得 async CRUD 接口
    - asyncio.Lock 类变量（CLAUDE.md §6）
    """

    # CLAUDE.md §6：asyncio.Lock 必须声明为类变量
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """初始化内存仓储"""
        self._dags: Dict[uuid.UUID, ToolChainDag] = {}

    # ---- L2RdbPort 继承方法（async） ----

    async def get_by_id(self, id: uuid.UUID) -> ToolChainDag | None:
        """通过 ID 获取实体（返回 None 而非抛错）"""
        async with self._lock:
            return self._dags.get(id)

    async def save(self, entity: ToolChainDag) -> ToolChainDag:
        """保存实体（insert or update）"""
        entity.validate()
        async with self._lock:
            self._dags[entity.chain_id] = entity
            return entity

    async def delete(self, id: uuid.UUID) -> None:
        """通过 ID 删除实体"""
        async with self._lock:
            self._dags.pop(id, None)

    async def list_all(self) -> List[ToolChainDag]:
        """列出所有实体"""
        async with self._lock:
            return list(self._dags.values())

    # ---- 领域扩展方法 ----

    async def list_by_query(self, query: ToolChainDagQuery) -> List[ToolChainDag]:
        """通过 Query Object 查询"""
        results = list(self._dags.values())
        if query.tenant_id is not None:
            results = [d for d in results if d.tenant_id == query.tenant_id]
        if query.name is not None:
            results = [d for d in results if d.name == query.name]
        if query.failure_strategy is not None:
            results = [d for d in results if d.failure_strategy == query.failure_strategy]
        if query.min_nodes is not None:
            results = [d for d in results if len(d.nodes) >= query.min_nodes]
        if query.max_nodes is not None:
            results = [d for d in results if len(d.nodes) <= query.max_nodes]
        results.sort(key=lambda d: d.created_at, reverse=True)
        return results[query.offset : query.offset + query.limit]

    async def count(self, query: ToolChainDagQuery) -> int:
        """统计符合条件的实体数量"""
        all_results = await self.list_by_query(
            ToolChainDagQuery(
                tenant_id=query.tenant_id,
                name=query.name,
                failure_strategy=query.failure_strategy,
                min_nodes=query.min_nodes,
                max_nodes=query.max_nodes,
                offset=0,
                limit=10**9,
            )
        )
        return len(all_results)


__all__ = ["InMemoryToolChainRepository"]
