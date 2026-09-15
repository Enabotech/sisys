"""基础设施层 InMemory 沙箱会话仓储实现（Story 4.4 Task 2)

实现 SandboxSessionRepositoryPort 协议,内存字典存储,用于单进程测试与开发环境。

设计依据:
- asyncio.Lock 必须声明为类变量（CLAUDE.md §6 Gotcha)
- 按 session_id 字符串索引（非 UUID),与 L2RdbPort UUID 主键约束不兼容
- 乐观锁 state_version CAS（与 InMemoryToolExecutionRepository.save_with_state_version 一致）
- 集成测试自包含:每个测试创建新实例,无跨测试共享状态
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from src.domain.entities.sandbox_session import SandboxSession
from src.domain.exceptions import EntityBusinessRuleError
from src.domain.ports.sandbox_session_repository import (
    SandboxSessionQuery,
    SandboxSessionRepositoryPort,
)

__all__ = ["InMemorySandboxSessionRepository"]


class InMemorySandboxSessionRepository(SandboxSessionRepositoryPort):
    """内存版沙箱会话仓储（CLAUDE.md §5 Mock/Fake/Real 三层策略 - Fake 层)

    Attributes:
        _sessions: 按 session_id 索引的会话字典（实例变量,每个实例独立)
        _lock: asyncio.Lock 类变量（CLAUDE.md §6 强制)
    """

    # CLAUDE.md §6:asyncio.Lock 必须声明为类变量,协程间共享
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """初始化仓储实例。"""
        self._sessions: dict[str, SandboxSession] = {}

    async def get_by_session_id(self, session_id: str) -> SandboxSession | None:
        """按 session_id 查询单个会话。"""
        async with self._lock:
            return self._sessions.get(session_id)

    async def save(self, session: SandboxSession) -> SandboxSession:
        """保存会话(允许递增版本号的乐观锁 CAS)。

        Args:
            session: 要保存的会话实例

        Returns:
            保存后的实例

        Raises:
            EntityBusinessRuleError: state_version 回退(传入版本 < 现有版本)

        设计依据:save 语义为"持久化最新状态",允许客户端从仓储读出后再写回
        (版本号自然递增)。仅在版本回退(小于现有版本号)时报错,防止外部
        直接覆盖更新导致状态丢失。
        """
        async with self._lock:
            existing = self._sessions.get(session.session_id)
            if existing is not None and session.state_version < existing.state_version:
                # 版本回退 → 异常(防止外部覆盖)
                raise EntityBusinessRuleError(
                    message=(
                        f"state_version regression for session {session.session_id}: "
                        f"existing {existing.state_version} > new {session.state_version}"
                    ),
                    context={
                        "entity": "SandboxSession",
                        "session_id": session.session_id,
                        "existing_version": existing.state_version,
                        "new_version": session.state_version,
                    },
                )
            self._sessions[session.session_id] = session
            return session

    async def delete_by_session_id(self, session_id: str) -> None:
        """按 session_id 删除会话。"""
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def list_all(self) -> list[SandboxSession]:
        """列出全部会话（仅用于管理/调试,生产环境慎用）。"""
        async with self._lock:
            return list(self._sessions.values())

    async def find_by_query(self, query: SandboxSessionQuery) -> list[SandboxSession]:
        """按多字段组合查询会话。

        Args:
            query: SandboxSessionQuery 查询值对象

        Returns:
            匹配的 SandboxSession 列表（按 started_at 升序,带分页）
        """
        async with self._lock:
            sessions: Iterable[SandboxSession] = self._sessions.values()

            if query.tenant_id is not None:
                sessions = [s for s in sessions if s.tenant_id == query.tenant_id]
            if query.state is not None:
                sessions = [s for s in sessions if s.state == query.state]
            if query.idle_threshold is not None:
                sessions = [s for s in sessions if s.state == "RUNNING" and s.last_activity_at < query.idle_threshold]

            ordered = sorted(sessions, key=lambda s: s.started_at)
            return list(ordered[query.offset : query.offset + query.limit])

    async def list_idle_sessions(self, threshold: datetime) -> list[SandboxSession]:
        """列出空闲会话（last_activity_at < threshold 且 state=RUNNING）。"""
        async with self._lock:
            return [s for s in self._sessions.values() if s.state == "RUNNING" and s.last_activity_at < threshold]

    async def count_active(self, tenant_id: UUID | None = None) -> int:
        """统计活跃会话数（state=RUNNING）。"""
        async with self._lock:
            sessions = self._sessions.values()
            if tenant_id is not None:
                return sum(1 for s in sessions if s.tenant_id == tenant_id and s.state == "RUNNING")
            return sum(1 for s in sessions if s.state == "RUNNING")
