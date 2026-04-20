"""OutboxProcessor — Transactional outbox processor for audit events.

Processes audit events from the outbox table and publishes them
to the event bus (RabbitMQ) for downstream consumers.

Reference: Story 1.10 SDD规范定义
Reference: architecture.md - ADR-003 Transactional Outbox Pattern
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.audit import AuditConfig, get_audit_config
from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

if TYPE_CHECKING:
    import aio_pika

logger = logging.getLogger(__name__)


class OutboxProcessor:
    """Processes audit events from the outbox table.

    Implements the polling processor pattern:
    1. Poll the outbox table for pending entries
    2. Publish each entry to the event bus (RabbitMQ)
    3. Mark entries as published or failed
    4. Retry failed entries up to max_retries
    """

    def __init__(
        self,
        session: AsyncSession,
        config: AuditConfig | None = None,
        rabbitmq_url: str | None = None,
    ) -> None:
        """Initialize OutboxProcessor.

        Args:
            session: SQLAlchemy async session for database operations.
            config: Audit configuration. If None, loads from environment.
            rabbitmq_url: RabbitMQ connection URL. If None, uses default from env.
        """
        self._session = session
        self._config = config or get_audit_config()
        self._running = False
        self._task: asyncio.Task | None = None
        self._rabbitmq_url = rabbitmq_url or "amqp://guest:guest@localhost:5672/"  # pragma: allowlist secret
        self._rabbitmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._rabbitmq_channel: aio_pika.abc.AbstractChannel | None = None
        self._shutdown_event = asyncio.Event()

    async def process_batch(self, batch_size: int | None = None) -> int:
        """Process a batch of pending outbox entries.

        Args:
            batch_size: Maximum number of entries to process. Defaults to config value.

        Returns:
            int: Number of entries successfully processed.
        """
        if batch_size is None:
            batch_size = self._config.outbox_batch_size

        # Get pending entries
        query = (
            select(AuditOutboxModel)
            .where(AuditOutboxModel.status == "pending")
            .order_by(AuditOutboxModel.created_at)
            .limit(batch_size)
        )
        result = await self._session.execute(query)
        entries = result.scalars().all()

        processed_count = 0

        for entry in entries:
            try:
                # Publish to event bus (RabbitMQ)
                await self._publish_entry(entry)

                # Mark as published
                entry.mark_published()
                processed_count += 1

            except Exception as e:
                logger.error(f"Failed to process outbox entry {entry.id}: {e}")
                entry.mark_failed(str(e))

                # If exceeded max retries, mark as failed permanently
                if not entry.can_retry():
                    logger.warning(
                        f"Outbox entry {entry.id} exceeded max retries " f"({entry.retry_count}/{entry.max_retries})"
                    )

        await self._session.flush()
        return processed_count

    async def _ensure_rabbitmq_connection(self) -> None:
        """Ensure RabbitMQ connection is established."""
        import aio_pika

        if self._rabbitmq_connection is None or self._rabbitmq_connection.is_closed:
            self._rabbitmq_connection = await aio_pika.connect_robust(
                self._rabbitmq_url,
                timeout=10.0,
            )
        if self._rabbitmq_channel is None:
            self._rabbitmq_channel = await self._rabbitmq_connection.channel()

    async def _publish_entry(self, entry: AuditOutboxModel) -> None:
        """Publish an outbox entry to RabbitMQ.

        Args:
            entry: The outbox entry to publish.

        Raises:
            Exception: If publishing fails.
        """
        import aio_pika

        try:
            await self._ensure_rabbitmq_connection()

            if self._rabbitmq_channel is None:
                raise RuntimeError("RabbitMQ channel not initialized")

            message = aio_pika.Message(
                body=json.dumps(entry.payload).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=str(entry.event_id),
            )

            await self._rabbitmq_channel.default_exchange.publish(
                message,
                routing_key=f"audit.{entry.event_type}",
            )

            logger.debug(f"Published audit event to RabbitMQ: " f"event_id={entry.event_id}, " f"event_type={entry.event_type}")

        except Exception as e:
            logger.error(f"Failed to publish audit event {entry.event_id} to RabbitMQ: {e}")
            raise

    async def process_forever(self, poll_interval: int | None = None) -> None:
        """Continuously process outbox entries.

        Args:
            poll_interval: Seconds between polls. Defaults to config value.
        """
        if poll_interval is None:
            poll_interval = self._config.outbox_poll_interval

        self._running = True
        self._shutdown_event.clear()
        logger.info(f"Outbox processor started (poll_interval={poll_interval}s)")

        while not self._shutdown_event.is_set():
            try:
                count = await self.process_batch()
                if count > 0:
                    logger.debug(f"Processed {count} outbox entries")
            except Exception as e:
                logger.error(f"Error in outbox processor loop: {e}")

            await asyncio.sleep(poll_interval)

        logger.info("Outbox processor stopped")

    def start(self) -> None:
        """Start the outbox processor in the background."""
        if self._task is not None and not self._task.done():
            logger.warning("Outbox processor already running")
            return

        self._task = asyncio.create_task(self.process_forever())

    async def stop(self) -> None:
        """Stop the outbox processor."""
        self._running = False
        self._shutdown_event.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def mark_entries_for_retry(self, older_than_minutes: int = 60) -> int:
        """Mark failed entries for retry.

        Resets status to 'pending' for failed entries that have
        been waiting longer than the specified time.

        Args:
            older_than_minutes: Reset entries that failed more than this many minutes ago.

        Returns:
            int: Number of entries reset.
        """
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(minutes=older_than_minutes)

        query = (
            update(AuditOutboxModel)
            .where(
                AuditOutboxModel.status == "failed",
                AuditOutboxModel.error_message.isnot(None),
                AuditOutboxModel.created_at < cutoff,
            )
            .values(status="pending", error_message=None)
        )
        result = await self._session.execute(query)
        await self._session.flush()

        # Get rowcount from result - may be None in async context
        row_count = result.rowcount if hasattr(result, "rowcount") else 0
        return row_count or 0
