"""Story 4.4: PostgreSQL SandboxSession 仓储单元测试

Mock AsyncSession + SQLAlchemy result 验证 SQL 生成逻辑。
不连接真实 Postgres(集成测试由 tests/integration 覆盖)。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.domain.entities.sandbox_session import SandboxSession
from src.domain.exceptions import EntityStateTransitionError
from src.domain.ports.sandbox_session_repository import SandboxSessionQuery
from src.infrastructure.storage.postgresql.repository.sandbox_session_repository import (
    PostgreSQLSandboxSessionRepository,
)


def _make_session(**overrides: object) -> SandboxSession:
    defaults: dict[str, object] = {
        "session_id": f"sess-{uuid.uuid4().hex[:12]}",
        "tenant_id": uuid.uuid4(),
        "image_digest": "python:3.11-slim@sha256:abc",
    }
    defaults.update(overrides)
    return SandboxSession(**defaults)  # type: ignore[arg-type]


def _make_model_from_entity(session: SandboxSession) -> MagicMock:
    """Mock SandboxSessionModel from entity"""
    model = MagicMock()
    model.session_id = session.session_id
    model.tenant_id = session.tenant_id
    model.container_id = session.container_id
    model.image_digest = session.image_digest
    model.started_at = session.started_at
    model.last_activity_at = session.last_activity_at
    model.terminated_at = session.terminated_at
    model.resource_limits = dict(session.resource_limits)
    model.state = session.state
    model.state_version = session.state_version
    return model


@pytest.fixture
def repo() -> PostgreSQLSandboxSessionRepository:
    return PostgreSQLSandboxSessionRepository()


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.merge = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


def _patch_session(repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock):
    """Patch repo._session property to return mock_session"""
    return patch.object(
        type(repo),
        "_session",
        new_callable=PropertyMock,
        return_value=mock_session,
    )


class TestGetBySessionId:
    """get_by_session_id 测试"""

    async def test_get_existing_session(self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock) -> None:
        """查询存在的会话返回 SandboxSession"""
        session = _make_session()
        mock_model = _make_model_from_entity(session)

        # Mock execute 返回 scalar_one_or_none
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=mock_model)
        mock_session.execute.return_value = result

        with _patch_session(repo, mock_session):
            fetched = await repo.get_by_session_id(session.session_id)

        assert fetched is not None
        assert fetched.session_id == session.session_id
        assert fetched.tenant_id == session.tenant_id

    async def test_get_nonexistent_returns_none(
        self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock
    ) -> None:
        """查询不存在的会话返回 None"""
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = result

        with _patch_session(repo, mock_session):
            fetched = await repo.get_by_session_id("sess-nonexistent")

        assert fetched is None

    async def test_invalid_state_in_db_defaults_to_running(
        self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock
    ) -> None:
        """DB 中 state 字段非法值时回退到 RUNNING（防 DB 漂移）"""
        session = _make_session()
        mock_model = _make_model_from_entity(session)
        mock_model.state = "INVALID_STATE"

        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=mock_model)
        mock_session.execute.return_value = result

        with _patch_session(repo, mock_session):
            fetched = await repo.get_by_session_id(session.session_id)

        assert fetched is not None
        assert fetched.state == "RUNNING"


class TestSave:
    """save 测试"""

    async def test_save_new_session(self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock) -> None:
        """save 新会话:不触发 state_version 回退校验"""
        session = _make_session()

        # 模拟 get_by_session_id 返回 None（不存在）
        result_get = MagicMock()
        result_get.scalar_one_or_none = MagicMock(return_value=None)
        # merge 返回带默认值的模型
        merged_model = _make_model_from_entity(session)
        mock_session.merge.return_value = merged_model
        mock_session.execute.return_value = result_get

        with _patch_session(repo, mock_session):
            saved = await repo.save(session)

        assert saved.session_id == session.session_id
        assert mock_session.merge.await_count == 1
        assert mock_session.flush.await_count == 1

    async def test_save_with_state_version_regression_raises(
        self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock
    ) -> None:
        """save 时 state_version 回退(新 < 旧)抛 EntityStateTransitionError"""
        existing_session = _make_session(state_version=5)
        new_session = _make_session(
            session_id=existing_session.session_id,
            tenant_id=existing_session.tenant_id,
            state_version=2,  # 回退
        )
        mock_model = _make_model_from_entity(existing_session)

        result_get = MagicMock()
        result_get.scalar_one_or_none = MagicMock(return_value=mock_model)
        mock_session.execute.return_value = result_get

        with _patch_session(repo, mock_session):
            with pytest.raises(EntityStateTransitionError):
                await repo.save(new_session)


class TestDeleteBySessionId:
    """delete_by_session_id 测试"""

    async def test_delete_existing_session(self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock) -> None:
        """删除存在的会话"""
        session = _make_session()
        mock_model = _make_model_from_entity(session)

        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=mock_model)
        mock_session.execute.return_value = result

        with _patch_session(repo, mock_session):
            await repo.delete_by_session_id(session.session_id)

        assert mock_session.delete.await_count == 1

    async def test_delete_nonexistent_no_error(self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock) -> None:
        """删除不存在的会话不抛错"""
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = result

        with _patch_session(repo, mock_session):
            await repo.delete_by_session_id("sess-nonexistent")

        assert mock_session.delete.await_count == 0


class TestListAll:
    """list_all 测试"""

    async def test_list_all_returns_sessions(self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock) -> None:
        """list_all 返回所有会话列表"""
        sessions = [_make_session() for _ in range(3)]
        models = [_make_model_from_entity(s) for s in sessions]

        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=models)
        result.scalars = MagicMock(return_value=scalars)
        mock_session.execute.return_value = result

        with _patch_session(repo, mock_session):
            all_sessions = await repo.list_all()

        assert len(all_sessions) == 3


class TestFindByQuery:
    """find_by_query 多字段查询测试"""

    async def test_find_by_query_filter_by_tenant(
        self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock
    ) -> None:
        """按 tenant_id 过滤"""
        session = _make_session()
        mock_model = _make_model_from_entity(session)

        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[mock_model])
        result.scalars = MagicMock(return_value=scalars)
        mock_session.execute.return_value = result

        query = SandboxSessionQuery(tenant_id=session.tenant_id)
        with _patch_session(repo, mock_session):
            results = await repo.find_by_query(query)

        assert len(results) == 1
        assert results[0].tenant_id == session.tenant_id

    async def test_find_by_query_with_idle_threshold(
        self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock
    ) -> None:
        """含 idle_threshold 时附加 last_activity_at < threshold 过滤"""
        session = _make_session()
        mock_model = _make_model_from_entity(session)

        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[mock_model])
        result.scalars = MagicMock(return_value=scalars)
        mock_session.execute.return_value = result

        query = SandboxSessionQuery(idle_threshold=datetime.now(UTC) - timedelta(minutes=30))
        with _patch_session(repo, mock_session):
            await repo.find_by_query(query)

        # 验证 execute 被调用（SQL 由 SQLAlchemy 生成）
        assert mock_session.execute.await_count == 1


class TestListIdleSessions:
    """list_idle_sessions 测试"""

    async def test_list_idle_sessions(self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock) -> None:
        """list_idle_sessions 过滤 RUNNING + last_activity_at < threshold"""
        sessions = [_make_session() for _ in range(2)]
        models = [_make_model_from_entity(s) for s in sessions]

        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=models)
        result.scalars = MagicMock(return_value=scalars)
        mock_session.execute.return_value = result

        threshold = datetime.now(UTC) - timedelta(minutes=30)
        with _patch_session(repo, mock_session):
            idle = await repo.list_idle_sessions(threshold)

        assert len(idle) == 2


class TestCountActive:
    """count_active 测试"""

    async def test_count_active_all(self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock) -> None:
        """count_active(None) 返回全部 RUNNING 数"""
        result = MagicMock()
        result.scalar = MagicMock(return_value=42)
        mock_session.execute.return_value = result

        with _patch_session(repo, mock_session):
            count = await repo.count_active()

        assert count == 42

    async def test_count_active_by_tenant(self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock) -> None:
        """count_active(tenant_id) 按租户过滤"""
        result = MagicMock()
        result.scalar = MagicMock(return_value=5)
        mock_session.execute.return_value = result

        with _patch_session(repo, mock_session):
            count = await repo.count_active(tenant_id=uuid.uuid4())

        assert count == 5

    async def test_count_active_handles_null(self, repo: PostgreSQLSandboxSessionRepository, mock_session: MagicMock) -> None:
        """count_active 处理 scalar 返回 None 的边界情况"""
        result = MagicMock()
        result.scalar = MagicMock(return_value=None)
        mock_session.execute.return_value = result

        with _patch_session(repo, mock_session):
            count = await repo.count_active()

        assert count == 0


class TestRequiresActiveSession:
    """ContextVar session 未设置时错误处理"""

    async def test_get_without_session_raises(self, repo: PostgreSQLSandboxSessionRepository) -> None:
        """未设置 AsyncSession ContextVar 时抛 InvalidStateError"""
        # 不通过 patch 设置 _session,触发 get_session() RuntimeError
        from src.infrastructure.storage.postgresql.session_context import _session_ctx

        # 重置 ContextVar
        token = _session_ctx.set(None)
        try:
            with pytest.raises(Exception):  # InvalidStateError 包装 RuntimeError
                await repo.get_by_session_id("sess-001")
        finally:
            _session_ctx.reset(token)
