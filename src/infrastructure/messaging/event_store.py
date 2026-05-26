"""基础设施层事件溯源存储模块

基于 PostgreSQL 实现事件溯源存储，支持事件追加（带乐观锁版本检查）、
按聚合 ID 查询事件、按事件类型和时间范围查询

Session 通过 ContextVar 由 middleware 或 test fixture 提供，
无需构造器注入 session 参数
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events.base import DomainEvent
from src.domain.exceptions.event_exceptions import VersionError
from src.infrastructure.storage.postgresql.session_context import get_session

logger = logging.getLogger(__name__)

EVENT_STORE_TABLE = "event_store"


class EventStoreModel:
    """事件存储记录数据类（非 SQLAlchemy 模型）

    使用原始 SQL 进行事件存储操作，实际表结构通过 create_table_sql() 管理

    Attributes:
        id: 自增主键
        event_id: 事件唯一标识
        aggregate_id: 聚合根唯一标识
        aggregate_type: 聚合根类型名称
        version: 事件版本号
        event_type: 事件类型名称
        payload: 事件负载（JSONB）
        timestamp: 事件时间戳
        metadata: 事件元数据（可选）
    """

    __tablename__ = EVENT_STORE_TABLE

    def __init__(
        self,
        event_id: str,
        aggregate_id: str,
        aggregate_type: str,
        version: int,
        event_type: str,
        payload: dict,
        timestamp: datetime,
        metadata: dict | None = None,
        id: int | None = None,
    ):
        self.id = id
        self.event_id = event_id
        self.aggregate_id = aggregate_id
        self.aggregate_type = aggregate_type
        self.version = version
        self.event_type = event_type
        self.payload = payload
        self.timestamp = timestamp
        self.metadata = metadata

    @classmethod
    def create_table_sql(cls) -> str:
        """返回创建事件存储表的 SQL 语句

        Returns:
            CREATE TABLE IF NOT EXISTS 的 SQL 语句
        """
        return f"""
        CREATE TABLE IF NOT EXISTS {cls.__tablename__} (
            id SERIAL PRIMARY KEY,
            event_id VARCHAR(36) NOT NULL,
            aggregate_id VARCHAR(36) NOT NULL,
            aggregate_type VARCHAR(255) NOT NULL,
            version INTEGER NOT NULL,
            event_type VARCHAR(255) NOT NULL,
            payload JSONB NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            metadata JSONB,
            UNIQUE (aggregate_id, version)
        )
        CREATE INDEX IF NOT EXISTS idx_event_store_aggregate_id ON {cls.__tablename__} (aggregate_id)
        CREATE INDEX IF NOT EXISTS idx_event_store_event_type ON {cls.__tablename__} (event_type)
        CREATE INDEX IF NOT EXISTS idx_event_store_timestamp ON {cls.__tablename__} (timestamp)
        """


class PostgreSQLEventStore:
    """PostgreSQL EventStore 实现

    使用原始 SQL 实现事件存储：
    - append() 追加事件（带乐观锁版本检查）
    - get_events() 获取聚合的所有事件
    - get_events_by_type() 按事件类型和时间范围查询
    """

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    async def append(self, event: DomainEvent) -> None:
        """追加事件到存储（带乐观锁版本检查）

        Args:
            event: 领域事件

        Raises:
            VersionError: 版本冲突（已存在相同 aggregate_id 和 version 的事件）
        """
        # 先检查是否已存在版本冲突
        check_stmt = text(
            """
            SELECT id FROM event_store
            WHERE aggregate_id = :aggregate_id AND version = :version
            LIMIT 1
            """
        )
        result = await self._session.execute(
            check_stmt,
            {"aggregate_id": str(event.aggregate_id), "version": event.version},
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            raise VersionError(f"Version conflict for aggregate {event.aggregate_id}, version {event.version}")

        # 插入新事件
        insert_stmt = text(
            """
            INSERT INTO event_store
            (event_id, aggregate_id, aggregate_type, version, event_type, payload, timestamp, metadata)
            VALUES (:event_id, :aggregate_id, :aggregate_type, :version, :event_type, :payload, :timestamp, :metadata)
            """
        )
        await self._session.execute(
            insert_stmt,
            {
                "event_id": str(event.event_id),
                "aggregate_id": str(event.aggregate_id),
                "aggregate_type": event.aggregate_type,
                "version": event.version,
                "event_type": event.event_type,
                "payload": json.dumps(event.payload),
                "timestamp": event.timestamp,
                "metadata": json.dumps(event.metadata) if event.metadata else None,
            },
        )

    async def get_events(self, aggregate_id: UUID) -> list[DomainEvent]:
        """获取指定聚合的所有事件

        Args:
            aggregate_id: 聚合 ID

        Returns:
            事件列表（按 version 排序）
        """
        stmt = text(
            """
            SELECT event_id, aggregate_id, aggregate_type, version, event_type, payload, timestamp, metadata
            FROM event_store
            WHERE aggregate_id = :aggregate_id
            ORDER BY version
            """
        )
        result = await self._session.execute(stmt, {"aggregate_id": str(aggregate_id)})
        rows = result.fetchall()

        events = []
        for row in rows:
            metadata_val = json.loads(row.metadata) if row.metadata and isinstance(row.metadata, str) else (row.metadata or {})
            event_data = {
                "event_id": row.event_id,
                "event_type": row.event_type,
                "timestamp": row.timestamp.isoformat() if hasattr(row.timestamp, "isoformat") else str(row.timestamp),
                "payload": json.loads(row.payload) if isinstance(row.payload, str) else row.payload,
                "aggregate_id": row.aggregate_id,
                "aggregate_type": row.aggregate_type,
                "version": row.version,
                "metadata": metadata_val,
            }
            events.append(DomainEvent.from_dict(event_data))

        return events

    async def get_events_by_type(
        self,
        event_type: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[DomainEvent]:
        """按事件类型和时间范围查询事件

        Args:
            event_type: 事件类型
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            匹配的事件列表
        """
        stmt = text(
            """
            SELECT event_id, aggregate_id, aggregate_type, version, event_type, payload, timestamp, metadata
            FROM event_store
            WHERE event_type = :event_type
            AND timestamp >= :start_time
            AND timestamp <= :end_time
            ORDER BY timestamp
            """
        )
        result = await self._session.execute(
            stmt,
            {
                "event_type": event_type,
                "start_time": start_time,
                "end_time": end_time,
            },
        )
        rows = result.fetchall()

        events = []
        for row in rows:
            metadata_val = json.loads(row.metadata) if row.metadata and isinstance(row.metadata, str) else (row.metadata or {})
            event_data = {
                "event_id": row.event_id,
                "event_type": row.event_type,
                "timestamp": row.timestamp.isoformat() if hasattr(row.timestamp, "isoformat") else str(row.timestamp),
                "payload": json.loads(row.payload) if isinstance(row.payload, str) else row.payload,
                "aggregate_id": row.aggregate_id,
                "aggregate_type": row.aggregate_type,
                "version": row.version,
                "metadata": metadata_val,
            }
            events.append(DomainEvent.from_dict(event_data))

        return events
