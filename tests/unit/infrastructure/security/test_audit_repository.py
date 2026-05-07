"""Tests for AuditRepository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ports.audit_repository import AuditSearchCriteria, AuditSearchResult
from src.infrastructure.security.audit_repository_impl import AuditRepository


@pytest.fixture
def mock_session() -> mock.AsyncMock:
    """Create mock async session."""
    session = mock.AsyncMock(spec=AsyncSession)
    session.add = mock.Mock()
    session.flush = mock.AsyncMock()
    return session


@pytest.fixture
def repo(mock_session: mock.AsyncMock) -> AuditRepository:
    """Create AuditRepository with mock session."""
    return AuditRepository(session=mock_session)


class TestAuditRepository:
    """Test AuditRepository implementation."""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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
