"""领域层沙箱会话仓储端口模块

Story 4.4 — Docker 沙箱执行。

关键设计决策:
- SandboxSessionRepositoryPort **不继承 L2RdbPort**
  原因:L2RdbPort 的 get_by_id/save/delete 强制使用 UUID 主键,
  而 SandboxSession 主键为字符串 session_id(业务标识符),
  类型冲突且与项目惯例(其他 InMemory 仓储主键均为 UUID)不符。
  本端口独立定义,通过 SandboxSessionQuery 查询值对象支持多字段组合。

参考: CLAUDE.md §4 端口查询参数决策规则
- 多字段组合 + 分页 → frozen dataclass Query VO
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from src.domain.entities.sandbox_session import SandboxSession

SandboxSessionState = Literal["RUNNING", "TERMINATED", "FAILED"]


@dataclass(frozen=True)
class SandboxSessionQuery:
    """沙箱会话查询值对象(CLAUDE.md §4 多字段组合查询模式)

    Attributes:
        tenant_id: 按租户过滤(None 表示不过滤)
        state: 按状态过滤(None 表示不过滤)
        idle_threshold: 过滤 last_activity_at < threshold 的空闲会话(None 表示不过滤)
        offset: 分页偏移
        limit: 分页上限
    """

    tenant_id: uuid.UUID | None = None
    state: SandboxSessionState | None = None
    idle_threshold: datetime | None = None
    offset: int = 0
    limit: int = 100


@runtime_checkable
class SandboxSessionRepositoryPort(Protocol):
    """沙箱会话仓储端口（领域层,Story 4.4 新增）

    设计决策: **不继承 L2RdbPort**（主键类型冲突,详见模块顶部说明）。

    基础 CRUD（按字符串 session_id 索引）:
    - async def get_by_session_id(session_id) -> SandboxSession | None
    - async def save(session) -> SandboxSession（使用 state_version 乐观锁）
    - async def delete_by_session_id(session_id) -> None
    - async def list_all() -> list[SandboxSession]

    领域扩展方法:
    - async def find_by_query(query) -> list[SandboxSession]
    - async def list_idle_sessions(threshold) -> list[SandboxSession]
    - async def count_active(tenant_id=None) -> int
    """

    async def get_by_session_id(self, session_id: str) -> SandboxSession | None:
        """按 session_id 查询会话（主键查找）

        Args:
            session_id: 业务会话标识符

        Returns:
            SandboxSession 实例,不存在则返回 None
        """
        ...

    async def save(self, session: SandboxSession) -> SandboxSession:
        """保存会话（insert or update,使用 state_version 乐观锁）

        Args:
            session: 待保存的 SandboxSession 实例

        Returns:
            保存后的 SandboxSession 实例（含递增的 state_version）
        """
        ...

    async def delete_by_session_id(self, session_id: str) -> None:
        """按 session_id 删除会话

        Args:
            session_id: 业务会话标识符
        """
        ...

    async def list_all(self) -> list[SandboxSession]:
        """列出所有会话

        Returns:
            所有 SandboxSession 实例列表
        """
        ...

    async def find_by_query(self, query: SandboxSessionQuery) -> list[SandboxSession]:
        """通过 SandboxSessionQuery 查询值对象查找会话

        Args:
            query: SandboxSessionQuery 实例

        Returns:
            匹配的 SandboxSession 实例列表
        """
        ...

    async def list_idle_sessions(self, threshold: datetime) -> list[SandboxSession]:
        """列出空闲会话（last_activity_at < threshold 且 state == RUNNING）

        Args:
            threshold: 空闲判定阈值时间点

        Returns:
            空闲 SandboxSession 实例列表
        """
        ...

    async def count_active(self, tenant_id: uuid.UUID | None = None) -> int:
        """统计活跃会话数（state == RUNNING）

        Args:
            tenant_id: 可选租户过滤

        Returns:
            活跃会话数
        """
        ...


__all__ = [
    "SandboxSessionQuery",
    "SandboxSessionRepositoryPort",
    "SandboxSessionState",
]
