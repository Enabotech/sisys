"""领域层沙箱会话仓储端口模块（Story 4.4 R3 新建）

定义 SandboxSessionRepositoryPort Protocol + SandboxSessionQuery Query 值对象。

设计决策（关键 P0 修正）:
- 不继承 L2RdbPort（主键类型冲突）
  - L2RdbPort 基类主键为 UUID（src/domain/ports/l2_rdb.py:26 get_by_id(id: UUID)）
  - SandboxSession 业务主键为字符串 session_id（匹配 ^[A-Za-z0-9_-]{1,64}$）
  - 若强行继承会导致 mypy 类型不兼容 + 违反 Liskov 替换原则
- 通过独立 Protocol + SandboxSessionQuery Query 值对象实现多字段组合查询
- CLAUDE.md §4 决策规则:多字段组合 + 分页 → frozen dataclass Query VO

基础 CRUD（按字符串 session_id 索引）:
- get_by_session_id(session_id) -> SandboxSession | None
- save(session) -> SandboxSession  # 使用 state_version 乐观锁
- delete_by_session_id(session_id) -> None
- list_all() -> list[SandboxSession]

领域扩展:
- find_by_query(query) -> list[SandboxSession]
- list_idle_sessions(threshold) -> list[SandboxSession]
- count_active(tenant_id) -> int
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.entities.sandbox_session import (
    SandboxSession,
    SandboxSessionState,
)

__all__ = [
    "SandboxSessionRepositoryPort",
    "SandboxSessionQuery",
]


@dataclass(frozen=True)
class SandboxSessionQuery:
    """SandboxSession 多字段查询值对象（frozen dataclass）

    Attributes:
        tenant_id: 多租户过滤
        state: 状态过滤("RUNNING"/"TERMINATED"/"FAILED")
        idle_threshold: 空闲阈值(last_activity_at < threshold)
        offset: 分页起始位置
        limit: 分页大小（默认 100,上限 1000）
    """

    tenant_id: UUID | None = None
    state: SandboxSessionState | None = None
    idle_threshold: datetime | None = None
    offset: int = 0
    limit: int = 100


@runtime_checkable
class SandboxSessionRepositoryPort(Protocol):
    """沙箱会话仓储端口（Story 4.4 R3,领域层,独立 Protocol 不继承 L2RdbPort）

    业务主键为字符串 session_id,与 L2RdbPort UUID 主键约束不兼容,
    故独立定义 Protocol + 通过 SandboxSessionQuery Query VO 实现多字段查询。
    """

    async def get_by_session_id(self, session_id: str) -> SandboxSession | None:
        """按 session_id 查询单个会话。

        Args:
            session_id: 业务标识符（字符串,匹配 ^[A-Za-z0-9_-]{1,64}$）

        Returns:
            找到的 SandboxSession,否则 None
        """
        ...

    async def save(self, session: SandboxSession) -> SandboxSession:
        """保存会话（使用 state_version 乐观锁)。

        Args:
            session: 要保存的会话实例

        Returns:
            保存后的实例（含更新后的 state_version）

        Raises:
            EntityBusinessRuleError: state_version 冲突
        """
        ...

    async def delete_by_session_id(self, session_id: str) -> None:
        """按 session_id 删除会话。

        Args:
            session_id: 业务标识符
        """
        ...

    async def list_all(self) -> list[SandboxSession]:
        """列出全部会话（仅用于管理/调试,生产环境慎用）。"""
        ...

    async def find_by_query(self, query: SandboxSessionQuery) -> list[SandboxSession]:
        """按多字段组合查询会话。

        Args:
            query: SandboxSessionQuery 查询值对象

        Returns:
            匹配的 SandboxSession 列表（按 started_at 升序）
        """
        ...

    async def list_idle_sessions(self, threshold: datetime) -> list[SandboxSession]:
        """列出空闲会话（last_activity_at < threshold 且 state=RUNNING）。

        用于 30 分钟空闲清理（SandboxSessionReaper）。

        Args:
            threshold: 空闲阈值（last_activity_at < threshold 即视为空闲）

        Returns:
            空闲会话列表
        """
        ...

    async def count_active(self, tenant_id: UUID | None = None) -> int:
        """统计活跃会话数（state=RUNNING）。

        用于配额控制（MAX_CONCURRENT_CONTAINERS）。

        Args:
            tenant_id: 可选,按租户过滤

        Returns:
            活跃会话数量
        """
        ...
