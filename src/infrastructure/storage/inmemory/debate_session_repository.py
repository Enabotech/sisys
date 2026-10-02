"""基础设施层辩论会话 InMemory 仓储模块

Story 4.5 — 红蓝辩论机制基础：DebateSessionRepositoryPort 的内存实现。

MVP 定位：无 PG 持久化需求（历史辩论查询随 Epic 10 审计落地新增 migration），
InMemory 仓储支撑编排可观测与测试断言；重启丢失会话可接受。

实现要点：
- asyncio.Lock 必须声明为**类变量**（CLAUDE.md §6 Gotcha：实例变量在协程间不共享）
- save 先 entity.validate() 再幂等覆盖（按 debate_id，无版本冲突检测——V1 CAS 预留）
- save 返回实体（对齐既有 5 个 InMemory 仓储先例）
"""

from __future__ import annotations

import asyncio
import uuid

from src.domain.entities.debate_session import DebateSession
from src.domain.ports.debate_session_repository import DebateSessionRepositoryPort


class InMemoryDebateSessionRepository(DebateSessionRepositoryPort):
    """辩论会话内存仓储（线程/协程安全，幂等覆盖）"""

    # CLAUDE.md §6: asyncio.Lock 必须声明为类变量（协程间共享）
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """初始化内存仓储（数据字典，不创建新 lock）"""
        self._sessions: dict[uuid.UUID, DebateSession] = {}

    async def save(self, session: DebateSession) -> DebateSession:
        """保存辩论会话（先 validate 再幂等覆盖）

        Args:
            session: 辩论会话聚合根实例

        Returns:
            保存后的实体

        Raises:
            EntityValidationError: 实体不变量违反（COMPLETED 缺 risk_view 等终态守卫）
        """
        session.validate()
        async with self._lock:
            self._sessions[session.debate_id] = session
            return session

    async def get_by_id(self, debate_id: uuid.UUID) -> DebateSession | None:
        """按辩论会话 ID 查询（主键查找）

        Args:
            debate_id: 辩论会话 ID

        Returns:
            DebateSession 实例，不存在则返回 None
        """
        async with self._lock:
            return self._sessions.get(debate_id)


__all__ = ["InMemoryDebateSessionRepository"]
