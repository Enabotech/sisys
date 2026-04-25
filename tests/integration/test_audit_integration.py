"""Integration tests for Audit Module.

Tests the full audit flow including:
- AuditLogModel creation and persistence
- AuditOutboxModel for transactional outbox pattern
- Checksum verification
- Multi-dimensional query

Requires: PostgreSQL database with audit tables created via migration 002_audit_tables.py

Run with: pytest tests/integration/test_audit_integration.py -v
Parallel execution: Supported via worker-specific schemas

Test isolation strategy:
- Each test uses worker-specific schema (pytest-xdist worker ID)
- Schema auto-created in fixture before tables
- Transaction rollback after each test
- UUID-based test data isolation
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.models.audit import AuditLogModel
from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

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


def get_schema_name():
    """Get schema name based on worker ID for parallel execution safety."""
    import os

    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"audit_test_{worker_id.replace('-', '_')}"


def get_unique_id():
    """Generate a unique ID for test isolation."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
async def db_engine(pg_config, setup_schema):
    """Create an async engine with worker-specific schema using schema_translate_map.

    Depends on setup_schema to ensure schema and tables exist before engine creation.
    Uses schema_translate_map on engine level (more reliable than server_settings).
    """
    schema = get_schema_name()
    url = (
        f"postgresql+asyncpg://{pg_config.username}:{pg_config.password}@{pg_config.host}:{pg_config.port}/{pg_config.database}"
    )

    engine = create_async_engine(
        url,
        echo=False,
        execution_options={"schema_translate_map": {None: schema}},
    )

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Create an async session with transaction rollback isolation.

    Each test gets a clean transaction that is rolled back after the test,
    ensuring no data pollution between tests.
    """
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="module")
def pg_config():
    """Get PostgreSQL configuration from environment."""
    return PostgreSQLConfig.from_env()


@pytest.fixture(scope="module", autouse=True)
async def setup_schema(pg_config):
    """Create schema and tables once per worker module.

    Uses sync connection for DDL to avoid asyncpg issues.
    Drop schema first to ensure clean state (handles failed previous runs).
    """
    schema = get_schema_name()
    sync_url = f"postgresql://{pg_config.username}:{pg_config.password}@{pg_config.host}:{pg_config.port}/{pg_config.database}"

    from sqlalchemy import create_engine

    engine = create_engine(
        sync_url,
        echo=False,
        connect_args={"options": f"-csearch_path={schema}"},
    )

    # Drop schema first to ensure clean state (handles failed previous runs)
    with engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.commit()

    # Create schema
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
        conn.commit()

    # Create tables
    with engine.connect() as conn:
        conn.execute(
            text(
                f"""
            CREATE TABLE {schema}.audit_log (
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
            CREATE TABLE {schema}.audit_outbox (
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

    engine.dispose()

    yield

    # Cleanup after all tests in module
    from sqlalchemy import create_engine

    cleanup_engine = create_engine(
        sync_url,
        echo=False,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    with cleanup_engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.commit()
    cleanup_engine.dispose()


class TestAuditLogModelIntegration:
    """Integration tests for AuditLogModel persistence."""

    @pytest.mark.asyncio
    async def test_create_audit_log_entry(self, db_session):
        """Can create and persist an audit log entry with all required fields."""
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
        assert fetched.log_id == log_id
        assert fetched.actor == "user-123"
        assert fetched.action_type == "document:upload"
        assert fetched.target_resource == "document/doc-456"
        assert fetched.old_value == {"status": "draft"}
        assert fetched.new_value == {"status": "published"}
        assert fetched.correction_level == 0

    @pytest.mark.asyncio
    async def test_checksum_auto_computed(self, db_session):
        """Checksum is automatically computed on model creation."""
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
        assert len(fetched.checksum) == 64  # SHA256 hex length

    @pytest.mark.asyncio
    async def test_verify_checksum_valid(self, db_session):
        """verify_checksum returns True when data has not been tampered."""
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

        assert entry.verify_checksum() is True

    @pytest.mark.asyncio
    async def test_verify_checksum_detects_tamper(self, db_session):
        """verify_checksum returns False when audit log has been tampered."""
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

        # Tamper with the data
        entry.actor = "tampered-actor"

        assert entry.verify_checksum() is False


class TestAuditOutboxModelIntegration:
    """Integration tests for AuditOutboxModel."""

    @pytest.mark.asyncio
    async def test_create_outbox_entry(self, db_session):
        """Can create and persist an outbox entry with pending status."""
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
        assert fetched.event_type == "AuditEvent"

    @pytest.mark.asyncio
    async def test_mark_published(self, db_session):
        """mark_published updates status and sets processed_at."""
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

        assert fetched is not None
        assert fetched.status == "published"
        assert fetched.processed_at is not None

    @pytest.mark.asyncio
    async def test_mark_failed_increments_retry(self, db_session):
        """mark_failed updates status, increments retry_count, and sets error_message."""
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

        assert fetched is not None
        assert fetched.status == "failed"
        assert fetched.retry_count == 1
        assert fetched.error_message == "Connection timeout"

    @pytest.mark.asyncio
    async def test_can_retry(self, db_session):
        """can_retry returns True when retry_count < max_retries."""
        event_id = uuid.uuid4()
        entry = AuditOutboxModel(
            event_id=event_id,
            payload={"action": "test"},
            retry_count=0,
            max_retries=3,
        )

        db_session.add(entry)
        await db_session.commit()

        assert entry.can_retry() is True

        # Exhaust retries
        entry.retry_count = 3
        assert entry.can_retry() is False


class TestAuditQueryIntegration:
    """Integration tests for audit log multi-dimensional query."""

    @pytest.mark.asyncio
    async def test_query_by_time_range(self, db_session):
        """Can query audit logs by timestamp range."""
        now = datetime.now(UTC)
        older = now - timedelta(days=7)

        entry1 = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=older,
            actor=f"user-time-{get_unique_id()}",
            action_type="document:upload",
            target_resource="doc-time-1",
            old_value={},
            new_value={},
        )
        entry2 = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=now,
            actor=f"user-time-{get_unique_id()}",
            action_type="document:download",
            target_resource="doc-time-2",
            old_value={},
            new_value={},
        )

        db_session.add_all([entry1, entry2])
        await db_session.commit()

        # Force expire to ensure fresh data from database
        db_session.expire_all()

        from sqlalchemy import select

        # Only query entries with actor starting with "user-time-" to isolate this test
        result = await db_session.execute(
            select(AuditLogModel).where(
                AuditLogModel.timestamp >= older, AuditLogModel.timestamp <= now, AuditLogModel.actor.like("user-time-%")
            )
        )
        results = result.scalars().all()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_by_actor(self, db_session):
        """Can query audit logs by actor field."""
        unique_actor = f"specific-user-{get_unique_id()}"

        entry = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor=unique_actor,
            action_type="document:upload",
            target_resource="doc-1",
            old_value={},
            new_value={},
        )

        db_session.add(entry)
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(select(AuditLogModel).where(AuditLogModel.actor == unique_actor))
        results = result.scalars().all()

        assert len(results) == 1
        assert results[0].actor == unique_actor

    @pytest.mark.asyncio
    async def test_query_by_action_type(self, db_session):
        """Can query audit logs by action_type field."""
        unique_action = f"custom:action-{get_unique_id()}"

        entry = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type=unique_action,
            target_resource="doc-1",
            old_value={},
            new_value={},
        )

        db_session.add(entry)
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(select(AuditLogModel).where(AuditLogModel.action_type == unique_action))
        results = result.scalars().all()

        assert len(results) == 1
        assert results[0].action_type == unique_action

    @pytest.mark.asyncio
    async def test_query_by_correction_level(self, db_session):
        """Can query audit logs by correction_level (FR-SC-04)."""
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

    @pytest.mark.asyncio
    async def test_query_by_target_resource(self, db_session):
        """Can query audit logs by target_resource field."""
        unique_resource = f"document/custom-doc-{get_unique_id()}"

        entry = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:upload",
            target_resource=unique_resource,
            old_value={},
            new_value={},
        )

        db_session.add(entry)
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(select(AuditLogModel).where(AuditLogModel.target_resource == unique_resource))
        results = result.scalars().all()

        assert len(results) == 1
        assert results[0].target_resource == unique_resource
