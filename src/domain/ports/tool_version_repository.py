"""领域层工具版本仓储端口模块（Story 4-6）

定义 ToolVersionRepositoryPort（领域层仓储端口），提供 ToolVersion
聚合根的持久化与查询能力。

设计依据：Story 4-6 SDD 端口契约清单
- 继承 L2RdbPort[ToolVersion]（async CRUD 基座——ToolExecutionRepositoryPort 先例形态）
- 领域扩展方法：get_by_tool_and_version / list_by_query / count / list_active / delete
- 查询使用 Query Object 模式（CLAUDE.md §4 多字段+分页决策规则）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus
from src.domain.ports.l2_rdb import L2RdbPort


@dataclass(frozen=True)
class ToolVersionQuery:
    """ToolVersion 查询值对象（Query Object 模式）。

    Attributes:
        tool_id: 按工具 ID 过滤（可选）
        status: 按发布状态过滤（可选）
        version: 按版本号精确过滤（可选）
        created_after: 注册时间下界（可选，含）
        created_before: 注册时间上界（可选，不含）
        offset: 分页偏移（默认 0）
        limit: 分页大小（默认 100）
    """

    tool_id: uuid.UUID | None = None
    status: ToolVersionStatus | None = None
    version: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    offset: int = 0
    limit: int = 100


@runtime_checkable
class ToolVersionRepositoryPort(L2RdbPort[ToolVersion], Protocol):
    """工具版本仓储端口协议（领域层）。

    继承 L2RdbPort[ToolVersion] 泛型 async CRUD 基座：
    - async def get_by_id(id) -> ToolVersion | None
    - async def save(entity) -> ToolVersion
    - async def delete(id) -> None
    - async def list_all() -> list[ToolVersion]

    领域扩展方法：
    - async def get_by_tool_and_version(tool_id, version) -> ToolVersion | None
    - async def list_by_query(query) -> list[ToolVersion]
    - async def count(query) -> int
    - async def list_active(tool_id) -> list[ToolVersion]（CANARY+STABLE）

    并发不变量守护（实现契约）：
    - (tool_id, version) 唯一——重复 save 新记录抛 431
    - 单 STABLE / 单活跃 CANARY——PG 实现以 partial unique index 硬守护，
      InMemory 实现在 save 时软校验（432 并存冲突族）
    """

    async def get_by_tool_and_version(
        self,
        tool_id: uuid.UUID,
        version: str,
    ) -> ToolVersion | None:
        """按 (tool_id, version) 精确查找。

        Args:
            tool_id: 工具 ID
            version: 版本号

        Returns:
            版本实体，不存在返回 None
        """
        ...

    async def list_by_query(self, query: ToolVersionQuery) -> list[ToolVersion]:
        """通过 Query Object 多字段过滤查询。

        Args:
            query: 查询条件

        Returns:
            按注册时间升序的结果列表（含 offset/limit 分页）
        """
        ...

    async def count(self, query: ToolVersionQuery) -> int:
        """统计符合条件的版本数量。

        Args:
            query: 查询条件

        Returns:
            数量
        """
        ...

    async def list_active(self, tool_id: uuid.UUID) -> list[ToolVersion]:
        """查询工具的活跃版本（CANARY + STABLE）。

        Args:
            tool_id: 工具 ID

        Returns:
            活跃版本列表
        """
        ...


__all__ = [
    "ToolVersionQuery",
    "ToolVersionRepositoryPort",
]
