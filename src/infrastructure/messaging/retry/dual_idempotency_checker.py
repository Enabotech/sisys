"""DualIdempotencyChecker — 双写幂等性检查器

Redis（高性能）+ PostgreSQL（持久化）双写：
- Redis SET NX 原子操作提供高性能检查
- PostgreSQL 记录提供持久化保证
- Redis 故障时降级至 PostgreSQL

Session 来源：
- Session 通过 ContextVar 由 middleware 或 test fixture 提供
- 无需构造器注入 session 参数
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.session_context import get_session

logger = logging.getLogger(__name__)

# Default TTL for Redis: 7 days
DEFAULT_TTL = 7 * 24 * 3600

# PostgreSQL table name for idempotency records
IDEMPOTENCY_TABLE = "idempotency_records"


class IdempotencyRecordModel:
    """SQLAlchemy model for idempotency records in PostgreSQL."""

    __tablename__ = IDEMPOTENCY_TABLE

    event_id: str
    processed_at: str

    @classmethod
    def create_table_sql(cls) -> str:
        """Return SQL to create the idempotency table."""
        return f"""
        CREATE TABLE IF NOT EXISTS {cls.__tablename__} (
            event_id VARCHAR(36) PRIMARY KEY,
            processed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
        """


class DualIdempotencyChecker:
    """双写幂等性检查器

    同时使用 Redis（高性能）和 PostgreSQL（持久化）进行幂等性检查
    - Redis SET NX 提供高性能检查
    - PostgreSQL 记录提供持久化保证
    - Redis 故障时降级至 PostgreSQL

    与现有 IdempotencyChecker 并存，RabbitMQEventListener 使用此实现
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        ttl: int = DEFAULT_TTL,
    ):
        """初始化 DualIdempotencyChecker

        Args:
            redis_client: Async Redis client
            ttl: Redis TTL in seconds, default 7 days
        """
        self._redis = redis_client
        self._ttl = ttl

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    async def try_acquire(self, event_id: UUID) -> bool:
        """原子性尝试获取事件处理权（双写模式）

        1. 先尝试 Redis SET NX（高性能）
        2. 成功后异步写入 PostgreSQL（持久化）
        3. Redis 故障时降级至 PostgreSQL

        Args:
            event_id: 事件唯一标识

        Returns:
            True: 首次处理（获取成功）
            False: 已处理（获取失败）
        """
        key = f"idempotency:{event_id}"

        # Step 1: Try Redis SET NX
        try:
            result = await self._redis.set(key, "1", nx=True, ex=self._ttl)
            if result:
                # Success on Redis, async write to PostgreSQL
                await self._write_to_postgresql(event_id)
                logger.debug("Acquired processing lock for event %s (Redis)", event_id)
                return True
            # Already in Redis
            logger.debug("Event %s already processed (Redis)", event_id)
            return False
        except aioredis.RedisError as e:
            logger.warning("Redis error during idempotency check: %s, falling back to PostgreSQL", e)
            # Fall back to PostgreSQL
            return await self._try_acquire_postgresql(event_id)

    async def _write_to_postgresql(self, event_id: UUID) -> None:
        """异步写入 PostgreSQL 记录"""
        try:
            stmt = text(
                """
                INSERT INTO idempotency_records (event_id, processed_at)
                VALUES (:event_id, :processed_at)
                ON CONFLICT (event_id) DO NOTHING
                """
            )
            await self._session.execute(stmt, {"event_id": str(event_id), "processed_at": datetime.now(UTC)})
        except Exception as e:
            # PostgreSQL 写入失败不影响主流程（Redis 已成功）
            logger.warning("Failed to write idempotency record to PostgreSQL: %s", e)

    async def _try_acquire_postgresql(self, event_id: UUID) -> bool:
        """PostgreSQL 降级模式：尝试获取处理权

        Args:
            event_id: 事件唯一标识

        Returns:
            True: 首次处理（获取成功）
            False: 已处理（获取失败）
        """
        try:
            stmt = text(
                """
                INSERT INTO idempotency_records (event_id, processed_at)
                VALUES (:event_id, :processed_at)
                ON CONFLICT (event_id) DO NOTHING
                """
            )
            result = await self._session.execute(stmt, {"event_id": str(event_id), "processed_at": datetime.now(UTC)})
            # Check if row was inserted (rowcount not always available, use fetched row count)
            rows = result.fetchone()
            return rows is not None
        except Exception as e:
            logger.error("PostgreSQL error during idempotency check: %s", e)
            # Both failed - fail open to allow processing
            return True

    async def is_processed(self, event_id: UUID) -> bool:
        """检查事件是否已处理（双写模式）

        先查 Redis，Redis 不可用时查 PostgreSQL

        Args:
            event_id: 事件唯一标识

        Returns:
            True: 已处理
            False: 未处理
        """
        key = f"idempotency:{event_id}"

        # Try Redis first
        try:
            exists = await self._redis.exists(key)
            if exists:
                return True
        except aioredis.RedisError:
            pass

        # Fall back to PostgreSQL
        return await self._is_processed_postgresql(event_id)

    async def _is_processed_postgresql(self, event_id: UUID) -> bool:
        """PostgreSQL 模式：检查事件是否已处理"""
        try:
            stmt = text("SELECT 1 FROM idempotency_records WHERE event_id = :event_id LIMIT 1")
            result = await self._session.execute(stmt, {"event_id": str(event_id)})
            row = result.scalar_one_or_none()
            return row is not None
        except Exception as e:
            logger.error("PostgreSQL error checking idempotency: %s", e)
            return False
