"""Task 9 TDD Tests — AsyncOutboxPoller 内部方法文档化 (AC-9)."""

from __future__ import annotations

from unittest import mock

import pytest

from src.infrastructure.messaging.channel_router import ChannelRouter


class TestAsyncOutboxPollerBehavior:
    """AsyncOutboxPoller behavior tests."""

    @pytest.fixture
    def mock_repo(self):
        """Mock outbox repository."""
        repo = mock.AsyncMock()
        repo.get_unpublished = mock.AsyncMock(return_value=[])
        repo.mark_published = mock.AsyncMock()
        repo.mark_failed = mock.AsyncMock()
        return repo

    @pytest.fixture
    def mock_publisher(self):
        """Mock RabbitMQ publisher."""
        pub = mock.AsyncMock()
        pub.async_publish = mock.AsyncMock()
        return pub

    @pytest.fixture
    def mock_router(self):
        """Mock ChannelRouter."""
        router = mock.MagicMock(spec=ChannelRouter)
        router.get_rabbitmq_routing_key.return_value = "sisys.events.reliable.TestEvent"
        return router

    @pytest.fixture
    def poller(self, mock_repo, mock_publisher, mock_router):
        """Provide AsyncOutboxPoller with mocks."""
        from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

        return AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            router=mock_router,
            poll_interval=0.1,
            batch_size=10,
        )

    async def test_poll_once_calls_get_unpublished(self, poller, mock_repo):
        """poll_once should call get_unpublished."""
        await poller.poll_once()
        mock_repo.get_unpublished.assert_called_once()

    async def test_poll_once_handles_empty_queue(self, poller, mock_repo):
        """poll_once should handle empty queue gracefully."""
        mock_repo.get_unpublished.return_value = []
        await poller.poll_once()  # Should not raise

    async def test_poller_stops_cleanly(self, poller):
        """stop() should set _running to False."""
        poller.stop()
        assert poller._running is False
