"""基础设施层 Saga 仓储模块

基于 PostgreSQL 持久化 Saga 实例状态

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ports.saga import SagaRepositoryProtocol
from src.domain.ports.saga_context import SagaContext
from src.infrastructure.saga.saga_context import SagaContext as ConcreteSagaContext
from src.infrastructure.saga.saga_status import SagaStatus
from src.infrastructure.storage.postgresql.session_context import get_session


class SagaModel:
    """Saga 实例 ORM 模型（简化版，使用 raw SQL/JSON 字段）

    实际生产可替换为完整 SQLAlchemy 声明式模型
    """

    def __init__(
        self,
        saga_id: UUID,
        saga_type: str,
        status: str,
        context_data: str,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        self.saga_id = saga_id
        self.saga_type = saga_type
        self.status = status
        self.context_data = context_data
        self.created_at = created_at
        self.updated_at = updated_at


class PostgreSQLSagaRepository(SagaRepositoryProtocol):
    """PostgreSQL Saga 仓储实现

    通过 ContextVar 获取 session，无需构造器注入
    """

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    async def save(self, context: SagaContext) -> None:
        """保存 Saga 上下文（UPSERT）

        Args:
            context: Saga 执行上下文
        """
        data = context.to_dict()

        await self._session.execute(
            text(
                "INSERT INTO saga_instance (saga_id, saga_type, status, context_data, created_at, updated_at) "
                "VALUES (:saga_id, :saga_type, :status, :context_data, :created_at, :updated_at) "
                "ON CONFLICT (saga_id) DO UPDATE SET "
                "status = EXCLUDED.status, "
                "context_data = EXCLUDED.context_data, "
                "updated_at = EXCLUDED.updated_at"
            ),
            {
                "saga_id": str(context.saga_id),
                "saga_type": context.saga_type,
                "status": context.status.value,
                "context_data": json.dumps(data),
                "created_at": context.created_at,
                "updated_at": datetime.now(UTC),
            },
        )
        await self._session.flush()

    async def load(self, saga_id: str) -> SagaContext | None:
        """加载 Saga 上下文

        Args:
            saga_id: Saga 实例唯一标识

        Returns:
            SagaContext 或 None
        """
        result = await self._session.execute(
            text("SELECT context_data FROM saga_instance WHERE saga_id = :saga_id"),
            {"saga_id": str(saga_id)},
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ConcreteSagaContext.from_dict(json.loads(row))

    async def update_status(self, saga_id: str, status: SagaStatus) -> None:
        """更新 Saga 状态

        Args:
            saga_id: Saga 实例唯一标识
            status: 新状态

        Raises:
            ValueError: 未找到对应 Saga 实例时抛出
        """
        existing = await self._session.execute(
            text("SELECT 1 FROM saga_instance WHERE saga_id = :saga_id"),
            {"saga_id": str(saga_id)},
        )
        if existing.scalar_one_or_none() is None:
            raise ValueError(f"update_status 未找到 saga_id={saga_id} 的 Saga 实例")

        await self._session.execute(
            text("UPDATE saga_instance SET status = :status, updated_at = :updated_at WHERE saga_id = :saga_id"),
            {
                "saga_id": str(saga_id),
                "status": status.value,
                "updated_at": datetime.now(UTC),
            },
        )
