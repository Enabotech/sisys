"""Story 4.4: InMemorySandboxSessionRepository 单元测试

验证内存仓储的 CRUD + 查询 + 乐观锁 + asyncio.Lock 类变量。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities.sandbox_session import SandboxSession
from src.domain.exceptions import EntityStateTransitionError
from src.domain.ports.sandbox_session_repository import SandboxSessionQuery
from src.infrastructure.storage.inmemory.sandbox_session_repository import (
    InMemorySandboxSessionRepository,
)


@pytest.fixture
def repo() -> InMemorySandboxSessionRepository:
    """每个测试使用新的仓储实例"""
    return InMemorySandboxSessionRepository()


def _make_session(**overrides: object) -> SandboxSession:
    defaults: dict[str, object] = {
        "session_id": f"sess-{uuid.uuid4().hex[:12]}",
        "tenant_id": uuid.uuid4(),
        "image_digest": "python:3.11-slim@sha256:abc",
    }
    defaults.update(overrides)
    return SandboxSession(**defaults)  # type: ignore[arg-type]


class TestInMemorySandboxSessionRepositoryLock:
    """asyncio.Lock 类变量测试（CLAUDE.md §6 红线）"""

    def test_lock_is_class_variable(self) -> None:
        """asyncio.Lock 必须声明为类变量（非实例变量）"""
        # 直接访问类（不创建实例）即可拿到 _lock
        lock_on_class = InMemorySandboxSessionRepository.__dict__.get("_lock")
        assert lock_on_class is not None
        assert isinstance(lock_on_class, asyncio.Lock)

    def test_multiple_instances_share_same_lock_class_var(self) -> None:
        """多个实例共享同一类变量锁"""
        repo1 = InMemorySandboxSessionRepository()
        repo2 = InMemorySandboxSessionRepository()
        # 通过类读取（确保是类变量）
        assert InMemorySandboxSessionRepository.__dict__["_lock"] is InMemorySandboxSessionRepository.__dict__["_lock"]
        # 实例访问应返回类变量
        assert repo1._lock is repo2._lock


class TestInMemorySandboxSessionRepositoryCRUD:
    """基础 CRUD 测试"""

    async def test_save_and_get_by_session_id(self, repo: InMemorySandboxSessionRepository) -> None:
        """save 后 get_by_session_id 应返回相同会话"""
        session = _make_session()
        await repo.save(session)
        fetched = await repo.get_by_session_id(session.session_id)
        assert fetched is session

    async def test_get_by_session_id_not_found(self, repo: InMemorySandboxSessionRepository) -> None:
        """get_by_session_id 找不到返回 None"""
        result = await repo.get_by_session_id("nonexistent")
        assert result is None

    async def test_save_with_matching_state_version_ok(self, repo: InMemorySandboxSessionRepository) -> None:
        """save 时 state_version 匹配应直接覆盖"""
        session = _make_session()
        await repo.save(session)
        # 重新保存相同版本号
        await repo.save(session)
        fetched = await repo.get_by_session_id(session.session_id)
        assert fetched is session

    async def test_save_with_state_version_regression_raises(self, repo: InMemorySandboxSessionRepository) -> None:
        """save 时新版本低于已存版本(版本回退)抛 EntityStateTransitionError"""
        session_v1 = _make_session()
        await repo.save(session_v1)
        # 创建 state_version 回退的副本(试图用 v0 覆盖已存的 v1)
        regression_session = SandboxSession(
            session_id=session_v1.session_id,
            tenant_id=session_v1.tenant_id,
            container_id=session_v1.container_id,
            image_digest=session_v1.image_digest,
            started_at=session_v1.started_at,
            last_activity_at=session_v1.last_activity_at,
            terminated_at=session_v1.terminated_at,
            resource_limits=session_v1.resource_limits,
            state=session_v1.state,
            state_version=session_v1.state_version - 1,  # v-1 回退
        )
        with pytest.raises(EntityStateTransitionError):
            await repo.save(regression_session)

    async def test_save_with_incrementing_version_ok(self, repo: InMemorySandboxSessionRepository) -> None:
        """save 时新版本高于已存版本(内部递增)应成功"""
        session = _make_session()
        await repo.save(session)
        # 模拟 adapter 内部 with_activity_updated() 产生的 v1
        updated_session = session.with_activity_updated()
        await repo.save(updated_session)
        fetched = await repo.get_by_session_id(session.session_id)
        assert fetched is not None
        assert fetched.state_version == 1

    async def test_delete_by_session_id(self, repo: InMemorySandboxSessionRepository) -> None:
        """delete_by_session_id 应移除会话"""
        session = _make_session()
        await repo.save(session)
        await repo.delete_by_session_id(session.session_id)
        assert await repo.get_by_session_id(session.session_id) is None

    async def test_delete_nonexistent_session_no_error(self, repo: InMemorySandboxSessionRepository) -> None:
        """delete 不存在的 session_id 不抛错"""
        await repo.delete_by_session_id("nonexistent")

    async def test_list_all(self, repo: InMemorySandboxSessionRepository) -> None:
        """list_all 应返回所有会话"""
        s1 = _make_session()
        s2 = _make_session()
        await repo.save(s1)
        await repo.save(s2)
        all_sessions = await repo.list_all()
        assert len(all_sessions) == 2
        assert s1 in all_sessions
        assert s2 in all_sessions


class TestInMemorySandboxSessionRepositoryFindByQuery:
    """find_by_query 多字段查询测试"""

    async def test_find_by_query_filter_by_tenant(self, repo: InMemorySandboxSessionRepository) -> None:
        """按 tenant_id 过滤"""
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        s_a = _make_session(tenant_id=tenant_a)
        s_b = _make_session(tenant_id=tenant_b)
        await repo.save(s_a)
        await repo.save(s_b)

        query = SandboxSessionQuery(tenant_id=tenant_a)
        results = await repo.find_by_query(query)
        assert len(results) == 1
        assert results[0] is s_a

    async def test_find_by_query_filter_by_state(self, repo: InMemorySandboxSessionRepository) -> None:
        """按 state 过滤"""
        now = datetime.now(UTC)
        s_running = _make_session()
        s_terminated = _make_session(state="TERMINATED", terminated_at=now)
        await repo.save(s_running)
        await repo.save(s_terminated)

        query = SandboxSessionQuery(state="TERMINATED")
        results = await repo.find_by_query(query)
        assert len(results) == 1
        assert results[0] is s_terminated

    async def test_find_by_query_pagination(self, repo: InMemorySandboxSessionRepository) -> None:
        """分页 offset + limit"""
        for _ in range(5):
            await repo.save(_make_session())

        query = SandboxSessionQuery(offset=0, limit=3)
        results = await repo.find_by_query(query)
        assert len(results) == 3

        query = SandboxSessionQuery(offset=3, limit=3)
        results = await repo.find_by_query(query)
        assert len(results) == 2


class TestInMemorySandboxSessionRepositoryListIdle:
    """list_idle_sessions 测试"""

    async def test_list_idle_sessions_threshold(self, repo: InMemorySandboxSessionRepository) -> None:
        """list_idle_sessions 应过滤 last_activity_at < threshold 且 state == RUNNING"""
        old_activity = datetime.now(UTC) - timedelta(hours=2)
        recent_activity = datetime.now(UTC)

        s_old = _make_session(last_activity_at=old_activity)
        s_recent = _make_session(last_activity_at=recent_activity)
        await repo.save(s_old)
        await repo.save(s_recent)

        threshold = datetime.now(UTC) - timedelta(hours=1)
        idle = await repo.list_idle_sessions(threshold)
        assert len(idle) == 1
        assert idle[0] is s_old

    async def test_list_idle_sessions_excludes_terminated(self, repo: InMemorySandboxSessionRepository) -> None:
        """list_idle_sessions 应排除非 RUNNING 状态"""
        now = datetime.now(UTC)
        old = now - timedelta(hours=2)
        s_terminated = _make_session(state="TERMINATED", last_activity_at=old, terminated_at=now)
        await repo.save(s_terminated)

        threshold = now - timedelta(hours=1)
        idle = await repo.list_idle_sessions(threshold)
        assert len(idle) == 0


class TestInMemorySandboxSessionRepositoryCountActive:
    """count_active 测试"""

    async def test_count_active_all_tenants(self, repo: InMemorySandboxSessionRepository) -> None:
        """count_active(None) 应统计所有 RUNNING 会话"""
        now = datetime.now(UTC)
        s1 = _make_session()
        s2 = _make_session()
        s_terminated = _make_session(state="TERMINATED", terminated_at=now)
        await repo.save(s1)
        await repo.save(s2)
        await repo.save(s_terminated)

        count = await repo.count_active()
        assert count == 2

    async def test_count_active_filter_by_tenant(self, repo: InMemorySandboxSessionRepository) -> None:
        """count_active(tenant_id) 应按租户过滤"""
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        s_a = _make_session(tenant_id=tenant_a)
        s_b = _make_session(tenant_id=tenant_b)
        await repo.save(s_a)
        await repo.save(s_b)

        count = await repo.count_active(tenant_id=tenant_a)
        assert count == 1
