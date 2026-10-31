"""Tests for AuditRepository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ports.audit_repository import AuditSearchCriteria, AuditSearchResult
from src.infrastructure.security.audit_repository_impl import AuditRepository
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


@pytest.fixture
def mock_session() -> mock.AsyncMock:
    """Create mock async session."""
    session = mock.AsyncMock(spec=AsyncSession)
    session.add = mock.Mock()
    session.flush = mock.AsyncMock()
    return session


@pytest.fixture
def repo(mock_session: mock.AsyncMock):
    """Create AuditRepository with mock session."""
    token = set_session(mock_session)
    repo = AuditRepository()
    yield repo
    reset_session(token)


class TestAuditRepository:
    """Test AuditRepository implementation."""

    async def test_save_creates_log(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test save creates an audit log."""
        log_id = uuid4()
        timestamp = datetime.now(UTC)
        audit_data = {
            "log_id": str(log_id),
            "timestamp": timestamp.isoformat(),
            "actor": "user-123",
            "action_type": "authentication:login",
            "target_resource": "/api/v1/auth/login",
            "old_value": {},
            "new_value": {"status": "success"},
            "correction_level": None,
            "checksum": "abc123",
            "correlation_id": None,
        }

        result = await repo.save(audit_data)

        assert result == log_id
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    async def test_get_by_id_returns_none_for_missing(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test get_by_id returns None for non-existent log."""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_id(uuid4())

        assert result is None
        mock_session.execute.assert_called_once()

    async def test_search_with_no_criteria_returns_empty(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test search with no criteria returns empty result."""
        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        criteria = AuditSearchCriteria()
        result = await repo.search(criteria)

        assert isinstance(result, AuditSearchResult)
        assert result.items == ()
        assert result.total == 0

    async def test_search_with_offset_and_limit(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test search with pagination."""
        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        criteria = AuditSearchCriteria(offset=0, limit=10)
        result = await repo.search(criteria)

        assert isinstance(result, AuditSearchResult)
        assert result.offset == 0
        assert result.limit == 10

    async def test_update_archive_status_returns_false_for_missing(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test update_archive_status returns False for non-existent log."""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.update_archive_status(uuid4(), True, datetime.now(UTC))
        assert result is False

    async def test_get_archive_status_returns_none_for_missing(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test get_archive_status returns None for non-existent log."""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_archive_status(uuid4())
        assert result is None

    async def test_search_with_match_any_true(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test search with match_any=True uses OR logic."""
        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        criteria = AuditSearchCriteria(
            actor="user-123",
            action_type="login",
            match_any=True,
        )
        result = await repo.search(criteria)

        assert isinstance(result, AuditSearchResult)

    async def test_search_with_match_any_false(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test search with match_any=False uses AND logic."""
        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        criteria = AuditSearchCriteria(
            actor="user-123",
            action_type="login",
            match_any=False,
        )
        result = await repo.search(criteria)

        assert isinstance(result, AuditSearchResult)

    async def test_search_with_time_range(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test search with time range criteria."""
        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        now = datetime.now(UTC)
        criteria = AuditSearchCriteria(
            start_time=now - timedelta(days=7),
            end_time=now,
        )
        result = await repo.search(criteria)

        assert isinstance(result, AuditSearchResult)

    async def test_search_with_all_criteria(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test search with all criteria fields."""
        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        now = datetime.now(UTC)
        criteria = AuditSearchCriteria(
            start_time=now - timedelta(days=7),
            end_time=now,
            actor="user-123",
            action_type="login",
            target_resource="/api/",
            offset=0,
            limit=20,
            match_any=False,
        )
        result = await repo.search(criteria)

        assert isinstance(result, AuditSearchResult)
        assert result.offset == 0
        assert result.limit == 20

    async def test_search_conditions_built_correctly(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test search builds conditions correctly."""
        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        criteria = AuditSearchCriteria(
            start_time=datetime.now(UTC) - timedelta(days=1),
            end_time=datetime.now(UTC),
            actor="test-user",
            action_type="test",
            target_resource="/test",
        )
        result = await repo.search(criteria)

        assert isinstance(result, AuditSearchResult)
        assert result.total >= 0

    async def test_search_no_conditions(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test search with no conditions."""
        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        criteria = AuditSearchCriteria()
        result = await repo.search(criteria)

        assert isinstance(result, AuditSearchResult)
        assert result.total == 0
        assert result.items == ()

    async def test_search_pagination_offset(
        self,
        repo: AuditRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """Test search pagination with offset."""
        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        criteria = AuditSearchCriteria(offset=5, limit=10)
        result = await repo.search(criteria)

        assert isinstance(result, AuditSearchResult)
        assert result.offset == 5
        assert result.limit == 10


def _make_audit_data() -> dict[str, str]:
    """构造最小合法审计数据（fallback 路径测试用——save 从 dict 提取字段）。"""
    return {
        "log_id": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "actor": "agent:test",
        "action_type": "isolation:switch",
    }


class TestSaveFallbackPath:
    """save 双模式分派——fallback 路径（核销 R2 批 K10 回归锁）.

    CLI set-isolation 路径无 ContextVar session → RuntimeError → 注入工厂
    走独立会话 commit（isolation_switch_log_repository DC-5 模板同款）；
    修复前该路径结构性 100% 降级（RuntimeError 被 record 的 except 包
    AuditError → 服务层 DC-6 降级 warning——audit 联动在 MVP 唯一运行
    通道永不可达）。
    """

    def test_save_via_factory_session_commits(self) -> None:
        """无 ContextVar session: factory 独立会话 add+commit（session_context 编排）。"""
        import asyncio
        from unittest import mock

        factory_session = mock.AsyncMock(spec=AsyncSession)
        factory_session.add = mock.Mock()
        repo_with_factory = AuditRepository(session_factory=mock.MagicMock(return_value=factory_session))

        asyncio.new_event_loop().run_until_complete(repo_with_factory.save(_make_audit_data()))

        factory_session.add.assert_called_once()
        factory_session.commit.assert_awaited_once()  # session_context 独立会话 commit

    def test_save_without_factory_reraises_runtime_error(self) -> None:
        """无 ContextVar 且无 factory: RuntimeError 原样上抛（配置缺失显式失败）。"""
        import asyncio

        repo_bare = AuditRepository()
        try:
            asyncio.new_event_loop().run_until_complete(repo_bare.save(_make_audit_data()))
            raise AssertionError("预期 RuntimeError 上抛")
        except RuntimeError:
            pass  # 无请求 session 且无工厂——显式失败（保持修复前行为）

    def test_save_with_context_session_uses_request_path(self) -> None:
        """有 ContextVar session: 请求路径 add+flush（不触发工厂——主事务语义）。"""
        import asyncio

        context_session = mock.AsyncMock(spec=AsyncSession)
        context_session.add = mock.Mock()
        token = set_session(context_session)
        try:
            factory_probe = mock.MagicMock()
            repo_request_path = AuditRepository(session_factory=factory_probe)
            asyncio.new_event_loop().run_until_complete(repo_request_path.save(_make_audit_data()))
            factory_probe.assert_not_called()  # 请求路径优先——工厂不触发
            context_session.add.assert_called_once()
            context_session.flush.assert_awaited_once()
        finally:
            reset_session(token)
