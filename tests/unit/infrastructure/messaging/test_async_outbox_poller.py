"""Task 9 TDD Tests — AsyncOutboxPoller 内部方法文档化 (AC-9)."""

from __future__ import annotations

from unittest import mock

import pytest


class TestAsyncOutboxPollerBehavior:
    """AsyncOutboxPoller behavior tests."""

    @pytest.fixture
    def mock_repo(self):
        """Mock outbox repository."""
        repo = mock.AsyncMock()
        repo._get_unpublished_entities = mock.AsyncMock(return_value=[])
        repo._mark_published_entity = mock.AsyncMock()
        repo._mark_failed_entity = mock.AsyncMock()
        return repo

    @pytest.fixture
    def mock_publisher(self):
        """Mock RabbitMQ publisher."""
        pub = mock.AsyncMock()
        pub.async_publish = mock.AsyncMock()
        return pub

    @pytest.fixture
    def poller(self, mock_repo, mock_publisher):
        """Provide AsyncOutboxPoller with mocks."""
        from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

        return AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            poll_interval=0.1,
            batch_size=10,
        )

    @pytest.mark.asyncio
    async def test_poll_once_calls_get_unpublished_entities(self, poller, mock_repo):
        """poll_once should call _get_unpublished_entities."""
        await poller.poll_once()
        mock_repo._get_unpublished_entities.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_once_handles_empty_queue(self, poller, mock_repo):
        """poll_once should handle empty queue gracefully."""
        mock_repo._get_unpublished_entities.return_value = []
        await poller.poll_once()  # Should not raise

    @pytest.mark.asyncio
    async def test_poller_stops_cleanly(self, poller):
        """stop() should set _running to False."""
        poller.stop()
        assert poller._running is False


class TestOutboxRepositoryInternalMethods:
    """Test internal methods documentation."""

    def test_internal_methods_have_poller_only_comment(self):
        """Internal methods should have @poller_only comment."""
        from src.infrastructure.messaging.outbox.outbox_repository import (
            PostgreSQLOutboxRepository,
        )

        # Check that internal methods exist and have docstrings
        assert hasattr(PostgreSQLOutboxRepository, "_get_unpublished_entities")
        assert hasattr(PostgreSQLOutboxRepository, "_mark_published_entity")
        assert hasattr(PostgreSQLOutboxRepository, "_mark_failed_entity")

        # Check docstrings mention @poller_only
        assert (
            "@poller_only" in PostgreSQLOutboxRepository._get_unpublished_entities.__doc__
            or "内部方法" in PostgreSQLOutboxRepository._get_unpublished_entities.__doc__
        )
        assert (
            "@poller_only" in PostgreSQLOutboxRepository._mark_published_entity.__doc__
            or "内部方法" in PostgreSQLOutboxRepository._mark_published_entity.__doc__
        )
        assert (
            "@poller_only" in PostgreSQLOutboxRepository._mark_failed_entity.__doc__
            or "内部方法" in PostgreSQLOutboxRepository._mark_failed_entity.__doc__
        )
