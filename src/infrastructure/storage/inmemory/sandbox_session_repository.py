"""基础设施层 内存沙箱会话仓储实现模块

Story 4.4 — Docker 沙箱执行。
InMemorySandboxSessionRepository 实现 SandboxSessionRepositoryPort。

CLAUDE.md §6 Gotcha: asyncio.Lock 必须声明为**类变量**而非实例变量,
否则在协程间不共享。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List

from src.domain.entities.sandbox_session import SandboxSession
from src.domain.ports.sandbox_session_repository import (
    SandboxSessionQuery,
    SandboxSessionRepositoryPort,
)


class InMemorySandboxSessionRepository(SandboxSessionRepositoryPort):
    """内存沙箱会话仓储（按字符串 session_id 索引）

    关键设计:
    - 继承 SandboxSessionRepositoryPort 获得 async CRUD 接口
    - asyncio.Lock 类变量（CLAUDE.md §6 红线）
    - 乐观锁 CAS（save 使用 state_version）
    - 按字符串 session_id 索引（**非 UUID**）
    """

    # CLAUDE.md §6: asyncio.Lock 必须声明为类变量
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """初始化内存仓储（数据字典,不创建新 lock）"""
        self._sessions: Dict[str, SandboxSession] = {}

    async def get_by_session_id(self, session_id: str) -> SandboxSession | None:
        """按 session_id 获取实体（返回 None 而非抛错）"""
        async with self._lock:
            return self._sessions.get(session_id)

    async def save(self, session: SandboxSession) -> SandboxSession:
        """保存实体(insert or update,乐观锁 CAS)

        若已存在相同 session_id 且 state_version 不匹配,抛 EntityStateTransitionError。
        state_version 自增方法 with_activity_updated/with_terminated 内部已递增版本号,
        故同一调用流中 v0 → v1 是合法状态变更(进入仓储时已 +1)。
        """
        async with self._lock:
            existing = self._sessions.get(session.session_id)
            if existing is not None and existing.state_version > session.state_version:
                # 现有版本 > 待保存版本 = 外部并发修改覆盖(不允许回退)
                from src.domain.exceptions import EntityStateTransitionError

                raise EntityStateTransitionError(
                    from_status=f"v{existing.state_version}",
                    to_status=f"v{session.state_version}",
                    message=f"state_version regression for session {session.session_id}",
                    entity_type="SandboxSession",
                    entity_id=session.session_id,
                )
            self._sessions[session.session_id] = session
            return session

    async def delete_by_session_id(self, session_id: str) -> None:
        """按 session_id 删除实体"""
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def list_all(self) -> List[SandboxSession]:
        """列出所有实体"""
        async with self._lock:
            return list(self._sessions.values())

    async def find_by_query(self, query: SandboxSessionQuery) -> List[SandboxSession]:
        """通过 SandboxSessionQuery 查询"""
        async with self._lock:
            results: list[SandboxSession] = []
            for session in self._sessions.values():
                if query.tenant_id is not None and session.tenant_id != query.tenant_id:
                    continue
                if query.state is not None and session.state != query.state:
                    continue
                if query.idle_threshold is not None:
                    if session.state != "RUNNING":
                        continue
                    if session.last_activity_at >= query.idle_threshold:
                        continue
                results.append(session)
            # 默认排序: started_at 降序（最新优先）
            results.sort(key=lambda s: s.started_at, reverse=True)
            return results[query.offset : query.offset + query.limit]

    async def list_idle_sessions(self, threshold: datetime) -> List[SandboxSession]:
        """列出空闲会话（last_activity_at < threshold 且 state == RUNNING）"""
        async with self._lock:
            return [
                session
                for session in self._sessions.values()
                if session.state == "RUNNING" and session.last_activity_at < threshold
            ]

    async def count_active(self, tenant_id: uuid.UUID | None = None) -> int:
        """统计活跃会话数（state == RUNNING）"""
        async with self._lock:
            count = 0
            for session in self._sessions.values():
                if session.state != "RUNNING":
                    continue
                if tenant_id is not None and session.tenant_id != tenant_id:
                    continue
                count += 1
            return count


__all__ = ["InMemorySandboxSessionRepository"]
