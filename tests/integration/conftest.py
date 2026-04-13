"""Shared pytest fixtures for integration tests.

Provides Mock services, test data factories, and test isolation fixtures.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import fakeredis
import pytest

# Ensure all domain events are imported so EventRegistry is populated.
# This MUST happen before any test that uses EventOutboxAdapter.
from src.domain.events import (  # noqa: F401, E402
    AgentDecided,
    CheckpointReached,
    CheckpointRecovered,
    CorrectionApproved,
    DocumentProcessed,
    HeartbeatTriggered,
    IsolationLevelSwitched,
    RoutingDecided,
    StrategicDeviationWarning,
    ToolExecuted,
)
from src.domain.events.base import DomainEvent
from src.infrastructure.events.in_memory_store import InMemoryEventStore
from src.infrastructure.idempotency.checker import IdempotencyChecker
from src.infrastructure.idempotency.retry_policy import RetryPolicy
from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

# ===================================================================
# Mock Fixtures (AC-1)
# ===================================================================


@pytest.fixture
def mock_redis() -> fakeredis.FakeRedis:
    """Provide a fakeredis instance mimicking real Redis behavior."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_postgresql_repo() -> AsyncMock:
    """Mock PostgreSQL repository interface."""
    return AsyncMock()


@pytest.fixture
def mock_rabbitmq_publisher() -> AsyncMock:
    """Mock RabbitMQ async publisher."""
    mock = AsyncMock()
    mock.async_publish.return_value = None
    return mock


# ===================================================================
# Test Data Factory (AC-1, AC-2)
# ===================================================================


@pytest.fixture
def event_id() -> UUID:
    """Provide a unique event ID for tests."""
    return uuid4()


@pytest.fixture
def sample_event(event_id: UUID) -> DomainEvent:
    """Provide a sample DomainEvent for testing."""
    return DomainEvent(
        event_id=event_id,
        event_type="DocumentProcessed",
        source="test",
        aggregate_id=uuid4(),
        aggregate_type="Document",
        version=1,
        payload={"document_id": "test-doc-1"},
    )


@pytest.fixture
def event_list(event_id: UUID) -> list[DomainEvent]:
    """Provide a list of sample events for testing."""
    return [
        DomainEvent(
            event_id=uuid4(),
            event_type=f"EventType{i}",
            source="test",
            aggregate_id=uuid4(),
            aggregate_type="TestAggregate",
            version=i,
            payload={"index": i},
        )
        for i in range(3)
    ]


# ===================================================================
# Test Isolation Fixtures (AC-1, AC-3)
# ===================================================================


@pytest.fixture
def outbox_repo() -> InMemoryOutboxRepository:
    """Provide a fresh InMemoryOutboxRepository instance per test.

    Each test gets its own isolated repo instance.
    No need for explicit clear() — fresh instance = clean state.
    """
    return InMemoryOutboxRepository()


@pytest.fixture
def event_store() -> Generator[InMemoryEventStore, None, None]:
    """Provide a fresh InMemoryEventStore instance per test."""
    store = InMemoryEventStore()
    yield store
    store.clear()  # cleanup (defensive)


@pytest.fixture
def idempotency_checker(mock_redis: fakeredis.FakeRedis) -> IdempotencyChecker:
    """Provide IdempotencyChecker backed by fakeredis."""
    return IdempotencyChecker(redis_client=mock_redis)


@pytest.fixture
def retry_policy() -> RetryPolicy:
    """Provide a RetryPolicy with fast delays for testing."""
    return RetryPolicy(base_delay=0.01, max_delay=0.1, max_retries=3)
