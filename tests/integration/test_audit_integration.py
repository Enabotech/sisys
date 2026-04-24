"""Integration tests for Audit Module.

Tests the full audit flow including:
- AuditLogModel creation and persistence
- AuditOutboxModel for transactional outbox pattern
- Checksum verification
- Multi-dimensional query

Requires: PostgreSQL database with audit tables created via migration 002_audit_tables.py

Run with: pytest tests/integration/test_audit_integration.py -v
Parallel execution: Supported via worker-specific schemas
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.config.postgresql import PostgreSQLConfig

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent.parent / ".env")


def is_postgresql_available():
    """Check if PostgreSQL database is available for integration testing."""
    try:
        config = PostgreSQLConfig.from_env()
        return bool(config.host and config.database)
    except Exception:
        return False


# Only run these tests if PostgreSQL is configured
pytestmark = pytest.mark.skipif(
    not is_postgresql_available(), reason="Requires PostgreSQL to be configured via environment variables"
)


@pytest.fixture(scope="module")
def pg_config():
    """Get PostgreSQL configuration from environment."""
    return PostgreSQLConfig.from_env()


def get_schema_name():
    """Get schema name based on worker ID for parallel execution safety."""
    import os

    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"audit_test_{worker_id.replace('-', '_')}"


@pytest.fixture(scope="module")
def sync_engine(pg_config, request):
    """Create synchronous engine for setup/teardown with worker-specific schema."""
    schema = get_schema_name()
    url = f"postgresql://{pg_config.username}:{pg_config.password}@{pg_config.host}:{pg_config.port}/{pg_config.database}"
    engine = create_engine(
        url,
        echo=False,
        connect_args={"options": f"-csearch_path={schema}"},
    )

    # Create schema for this worker
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.commit()

    # Create tables using explicit schema prefix
    with engine.connect() as conn:
        conn.execute(
            text(
                f"""
            CREATE TABLE IF NOT EXISTS {schema}.audit_log (
                id BIGSERIAL PRIMARY KEY,
                log_id UUID NOT NULL UNIQUE,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                actor VARCHAR(255) NOT NULL,
                action_type VARCHAR(100) NOT NULL,
                target_resource VARCHAR(500) NOT NULL,
                old_value JSONB NOT NULL DEFAULT '{{}}',
                new_value JSONB NOT NULL DEFAULT '{{}}',
                correction_level INTEGER CHECK (correction_level IS NULL OR (correction_level >= 0 AND correction_level <= 3)),
                checksum VARCHAR(64) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                archived BOOLEAN NOT NULL DEFAULT FALSE,
                archived_at TIMESTAMP WITH TIME ZONE,
                correlation_id VARCHAR(100)
            )
        """
            )
        )

        conn.execute(
            text(
                f"""
            CREATE TABLE IF NOT EXISTS {schema}.audit_outbox (
                id BIGSERIAL PRIMARY KEY,
                event_id UUID NOT NULL UNIQUE,
                event_type VARCHAR(100) NOT NULL,
                payload JSONB NOT NULL DEFAULT '{{}}',
                status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'published', 'failed')),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                processed_at TIMESTAMP WITH TIME ZONE,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                error_message VARCHAR(1000)
            )
        """
            )
        )
        conn.commit()

    yield engine

    # Cleanup: drop schema
    with engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.commit()
    engine.dispose()


@pytest.fixture(scope="module")
def async_engine(pg_config, request):
    """Create async engine for tests with worker-specific schema."""
    schema = get_schema_name()
    url = (
        f"postgresql+asyncpg://{pg_config.username}:{pg_config.password}@{pg_config.host}:{pg_config.port}/{pg_config.database}"
    )
    engine = create_async_engine(
        url,
        echo=False,
        connect_args={"server_settings": {"search_path": schema}},
    )
    yield engine
    engine.dispose()


@pytest.fixture
async def db_session(pg_config, sync_engine):
    """Create an async session for a test with worker-specific schema.

    Each test gets its own engine to avoid event loop conflicts.
    Schema is already created by sync_engine fixture.
    """
    schema = get_schema_name()
    url = (
        f"postgresql+asyncpg://{pg_config.username}:{pg_config.password}@{pg_config.host}:{pg_config.port}/{pg_config.database}"
    )
    engine = create_async_engine(
        url,
        echo=False,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()

    await engine.dispose()


class TestAuditLogModelIntegration:
    """Integration tests for AuditLogModel persistence."""

    @pytest.mark.asyncio
    async def test_create_audit_log_entry(self, db_session):
        """Can create and persist an audit log entry."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        log_id = uuid.uuid4()
        timestamp = datetime.now(UTC)

        entry = AuditLogModel(
            log_id=log_id,
            timestamp=timestamp,
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={"status": "draft"},
            new_value={"status": "published"},
            correction_level=0,
        )

        db_session.add(entry)
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(select(AuditLogModel).where(AuditLogModel.log_id == log_id))
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.actor == "user-123"
        assert fetched.action_type == "document:upload"

    @pytest.mark.asyncio
    async def test_checksum_persistence(self, db_session):
        """Checksum is correctly computed and persisted."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        log_id = uuid.uuid4()
        timestamp = datetime.now(UTC)

        entry = AuditLogModel(
            log_id=log_id,
            timestamp=timestamp,
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={"status": "draft"},
            new_value={"status": "published"},
        )

        db_session.add(entry)
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(select(AuditLogModel).where(AuditLogModel.log_id == log_id))
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert len(fetched.checksum) == 64
        assert fetched.verify_checksum() is True

    @pytest.mark.asyncio
    async def test_tamper_detection(self, db_session):
        """Tampering with audit log entry is detected via checksum."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        log_id = uuid.uuid4()
        entry = AuditLogModel(
            log_id=log_id,
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={},
            new_value={},
        )

        db_session.add(entry)
        await db_session.commit()

        entry.actor = "tampered-actor"
        assert entry.verify_checksum() is False


class TestAuditOutboxIntegration:
    """Integration tests for AuditOutboxModel."""

    @pytest.mark.asyncio
    async def test_create_outbox_entry(self, db_session):
        """Can create and persist outbox entry."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        event_id = uuid.uuid4()
        entry = AuditOutboxModel(
            event_id=event_id,
            payload={"log_id": str(uuid.uuid4()), "action": "test"},
        )

        db_session.add(entry)
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(select(AuditOutboxModel).where(AuditOutboxModel.event_id == event_id))
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.status == "pending"
        assert fetched.retry_count == 0

    @pytest.mark.asyncio
    async def test_mark_published(self, db_session):
        """Can mark outbox entry as published."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        event_id = uuid.uuid4()
        entry = AuditOutboxModel(
            event_id=event_id,
            payload={"action": "test"},
        )

        db_session.add(entry)
        await db_session.commit()

        entry.mark_published()
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(select(AuditOutboxModel).where(AuditOutboxModel.event_id == event_id))
        fetched = result.scalar_one_or_none()
        assert fetched.status == "published"
        assert fetched.processed_at is not None

    @pytest.mark.asyncio
    async def test_mark_failed_increments_retry(self, db_session):
        """Mark failed increments retry_count."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        event_id = uuid.uuid4()
        entry = AuditOutboxModel(
            event_id=event_id,
            payload={"action": "test"},
        )

        db_session.add(entry)
        await db_session.commit()

        entry.mark_failed("Connection timeout")
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(select(AuditOutboxModel).where(AuditOutboxModel.event_id == event_id))
        fetched = result.scalar_one_or_none()
        assert fetched.status == "failed"
        assert fetched.retry_count == 1
        assert fetched.error_message == "Connection timeout"


class TestAuditQueryIntegration:
    """Integration tests for audit log queries."""

    @pytest.mark.asyncio
    async def test_query_by_time_range(self, db_session):
        """Can query audit logs by time range."""
        # Clear existing data first
        from sqlalchemy import delete

        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        await db_session.execute(delete(AuditLogModel))
        await db_session.commit()

        now = datetime.now(UTC)
        older = now - timedelta(days=7)

        entry1 = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=older,
            actor="user-123",
            action_type="document:upload",
            target_resource="doc-1",
            old_value={},
            new_value={},
        )
        entry2 = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=now,
            actor="user-123",
            action_type="document:download",
            target_resource="doc-2",
            old_value={},
            new_value={},
        )

        db_session.add_all([entry1, entry2])
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(
            select(AuditLogModel).where(AuditLogModel.timestamp >= older).where(AuditLogModel.timestamp <= now)
        )
        results = result.scalars().all()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_by_actor(self, db_session):
        """Can query audit logs by actor."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        entry = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="specific-user",
            action_type="document:upload",
            target_resource="doc-1",
            old_value={},
            new_value={},
        )

        db_session.add(entry)
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(select(AuditLogModel).where(AuditLogModel.actor == "specific-user"))
        results = result.scalars().all()
        assert len(results) == 1
        assert results[0].actor == "specific-user"

    @pytest.mark.asyncio
    async def test_query_by_correction_level(self, db_session):
        """Can query audit logs by correction_level (FR-SC-04)."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        entries = [
            AuditLogModel(
                log_id=uuid.uuid4(),
                timestamp=datetime.now(UTC),
                actor="user-1",
                action_type="correction:apply",
                target_resource="doc-1",
                old_value={},
                new_value={},
                correction_level=1,
            ),
            AuditLogModel(
                log_id=uuid.uuid4(),
                timestamp=datetime.now(UTC),
                actor="user-2",
                action_type="correction:apply",
                target_resource="doc-2",
                old_value={},
                new_value={},
                correction_level=2,
            ),
        ]

        db_session.add_all(entries)
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(select(AuditLogModel).where(AuditLogModel.correction_level == 2))
        results = result.scalars().all()
        assert len(results) == 1
        assert results[0].correction_level == 2
