"""Story 4.5 — InMemoryDebateSessionRepository 单元测试

验证 roundtrip / 未知名 None / 50 并发 save 零丢失 / 先 validate 再幂等覆盖。

约束：
- asyncio.Lock 类变量（CLAUDE.md §6 Gotcha）
- save 先 validate() 再幂等覆盖（按 debate_id，无版本冲突检测——V1 CAS 预留）
- save 返回实体（对齐既有 5 个 InMemory 仓储先例）
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.debate_session import DebateSession, DebateSessionState
from src.domain.exceptions import EntityValidationError
from src.domain.ports.debate_session_repository import DebateSessionRepositoryPort
from src.infrastructure.storage.inmemory.debate_session_repository import InMemoryDebateSessionRepository


def _make_session(
    debate_id: uuid.UUID | None = None,
    title: str = "仓储测试议题",
    **kwargs,
) -> DebateSession:
    """构造 DebateSession（测试工厂，默认全合法 IDLE）"""
    return DebateSession(
        debate_id=debate_id if debate_id is not None else uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        title=title,
        **kwargs,
    )


def _make_completed_session(debate_id: uuid.UUID | None = None) -> DebateSession:
    """构造 COMPLETED 终态会话（save 前置 validate 用）"""
    from src.domain.value_objects.debate import ConsensusArea, DisagreementArea, RiskView

    risk_view = RiskView(
        consensus_areas=(ConsensusArea(area="主题", description="内容", confidence=0.9),),
        disagreement_areas=(DisagreementArea(area="主题", red_position="红", blue_position="蓝", risk_note="风险"),),
        overall_risk_level="LOW",
        overlap_rate=0.4,
    )
    return _make_session(
        debate_id=debate_id,
        state=DebateSessionState.COMPLETED,
        risk_view=risk_view,
        completed_at=datetime.now(UTC),
    )


# ===================================================================
# 端口契约
# ===================================================================


class TestPortContract:
    def test_inmemory_repo_satisfies_port(self) -> None:
        """InMemory 实现满足 runtime_checkable 端口协议"""
        repository = InMemoryDebateSessionRepository()
        assert isinstance(repository, DebateSessionRepositoryPort)

    def test_lock_is_class_variable(self) -> None:
        """asyncio.Lock 必须为类变量（CLAUDE.md §6，跨协程共享）"""
        repo_a = InMemoryDebateSessionRepository()
        repo_b = InMemoryDebateSessionRepository()
        assert InMemoryDebateSessionRepository._lock is repo_a._lock
        assert repo_a._lock is repo_b._lock


# ===================================================================
# roundtrip
# ===================================================================


class TestRoundtrip:
    async def test_save_then_get_by_id(self) -> None:
        """save → get_by_id roundtrip 字段一致"""
        repository = InMemoryDebateSessionRepository()
        session = _make_session(title="roundtrip 议题")
        saved = await repository.save(session)
        assert saved is session or saved.debate_id == session.debate_id

        loaded = await repository.get_by_id(session.debate_id)
        assert loaded is not None
        assert loaded.debate_id == session.debate_id
        assert loaded.title == "roundtrip 议题"
        assert loaded.state is DebateSessionState.IDLE
        assert loaded.state_version == 0

    async def test_get_by_id_unknown_returns_none(self) -> None:
        """未知名返回 None（不抛错）"""
        repository = InMemoryDebateSessionRepository()
        assert await repository.get_by_id(uuid.uuid4()) is None

    async def test_save_idempotent_overwrite(self) -> None:
        """同 debate_id 幂等覆盖（迁移后 save 纪律依赖）"""
        repository = InMemoryDebateSessionRepository()
        debate_id = uuid.uuid4()
        session = _make_session(debate_id=debate_id)
        await repository.save(session)

        session.transition_to(DebateSessionState.GENERATING)
        await repository.save(session)
        loaded = await repository.get_by_id(debate_id)
        assert loaded is not None
        assert loaded.state is DebateSessionState.GENERATING
        assert loaded.state_version == 1

    async def test_save_validates_before_persist(self) -> None:
        """save 先 validate：构造后绕过状态机注入非法终态（COMPLETED 缺 risk_view）在 save 抛 242"""
        repository = InMemoryDebateSessionRepository()
        session = _make_session()
        # 直接属性赋值绕过构造校验与状态机（实体为非 frozen 聚合根）
        session.state = DebateSessionState.COMPLETED
        session.completed_at = datetime.now(UTC)
        with pytest.raises(EntityValidationError) as exc_info:
            await repository.save(session)
        assert exc_info.value.code == "EXCEPTION_242"
        assert await repository.get_by_id(session.debate_id) is None

    async def test_completed_session_roundtrip(self) -> None:
        """COMPLETED 终态会话（含 risk_view/completed_at）roundtrip"""
        repository = InMemoryDebateSessionRepository()
        session = _make_completed_session()
        await repository.save(session)
        loaded = await repository.get_by_id(session.debate_id)
        assert loaded is not None
        assert loaded.state is DebateSessionState.COMPLETED
        assert loaded.risk_view is not None


# ===================================================================
# 并发安全
# ===================================================================


class TestConcurrency:
    async def test_50_concurrent_saves_no_loss(self) -> None:
        """asyncio.gather 50 并发 save 无丢失（test_sandbox_session_repository 同款场景）"""
        repository = InMemoryDebateSessionRepository()
        sessions = [_make_session(title=f"并发议题{i}") for i in range(50)]

        results = await asyncio.gather(*(repository.save(session) for session in sessions))
        assert len(results) == 50

        loaded_sessions = await asyncio.gather(*(repository.get_by_id(session.debate_id) for session in sessions))
        assert all(loaded is not None for loaded in loaded_sessions), "并发保存出现丢失"

    async def test_concurrent_save_and_read(self) -> None:
        """并发读写混合安全（锁保护下无脏读异常）"""
        repository = InMemoryDebateSessionRepository()
        sessions = [_make_session(title=f"混合议题{i}") for i in range(20)]

        async def _save_and_read(session: DebateSession) -> DebateSession | None:
            await repository.save(session)
            return await repository.get_by_id(session.debate_id)

        results = await asyncio.gather(*(_save_and_read(session) for session in sessions))
        assert all(result is not None for result in results)
