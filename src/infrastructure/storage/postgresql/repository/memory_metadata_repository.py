"""PostgreSQLMemoryMetadataRepository — L2 PostgreSQL 持久化实现。

使用 SQLAlchemy AsyncSession，支持：
- 多用户并行：会话级别隔离
- 线程安全：异步操作，依赖数据库事务
- UPSERT：版本冲突检测（乐观锁）
- 软删除：deleted_at 标记

架构来源: architecture.md §11.2.5
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.memory_metadata import MemoryMetadata
from src.domain.ports.l2_rdb import L2MetadataRepositoryProtocol
from src.infrastructure.storage.postgresql.models.memory import MemoryMetadataModel


class MemoryVersionConflictError(Exception):
    """版本冲突异常。"""

    def __init__(self, memory_id: UUID):
        self.memory_id = memory_id
        self.message = f"版本冲突: memory_id={memory_id}"
        super().__init__(self.message)


class PostgreSQLMemoryMetadataRepository(L2MetadataRepositoryProtocol):
    """PostgreSQL 记忆元数据仓储。

    使用 AsyncSession 提供异步、线程安全的数据库操作。
    支持多用户并发的会话级别隔离。
    软删除模式：deleted_at 非 NULL 的记录视为已删除。
    """

    def __init__(self, session: AsyncSession):
        """初始化 PostgreSQLMemoryMetadataRepository。

        Args:
            session: SQLAlchemy 异步会话（非线程共享，会话绑定到特定连接）
        """
        self._session = session

    def _to_model(self, entity: MemoryMetadata) -> MemoryMetadataModel:
        """将领域实体转换为数据库模型。"""
        return MemoryMetadataModel(
            memory_id=entity.memory_id,
            user_id=entity.user_id,
            name=entity.name,
            description=entity.description,
            type=entity.type,
            path=entity.path,
            version=entity.version,
            mtime=entity.mtime,
            owner=entity.owner,
            group_id=entity.group_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _to_entity(self, model: MemoryMetadataModel) -> MemoryMetadata:
        """将数据库模型转换为领域实体。"""
        return MemoryMetadata(
            memory_id=model.memory_id,
            user_id=model.user_id,
            name=model.name,
            description=model.description or "",
            type=model.type,
            path=model.path,
            version=model.version,
            mtime=model.mtime,
            owner=model.owner or "",
            group_id=model.group_id or "",
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, metadata: MemoryMetadata) -> None:
        """保存或更新记忆元数据（UPSERT with 乐观锁）。

        Args:
            metadata: 记忆元数据

        Raises:
            MemoryVersionConflictError: 如果版本冲突（并发更新）
        """
        # 检查是否已存在（排除已删除的记录）
        result = await self._session.execute(
            select(MemoryMetadataModel).where(
                and_(
                    MemoryMetadataModel.memory_id == metadata.memory_id,
                    MemoryMetadataModel.deleted_at.is_(None),
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            # 更新操作：检查版本（乐观锁）
            if metadata.version <= existing.version:
                raise MemoryVersionConflictError(metadata.memory_id)

            # 执行更新
            await self._session.execute(
                update(MemoryMetadataModel)
                .where(
                    and_(
                        MemoryMetadataModel.memory_id == metadata.memory_id,
                        MemoryMetadataModel.deleted_at.is_(None),
                    )
                )
                .values(
                    name=metadata.name,
                    description=metadata.description,
                    type=metadata.type,
                    path=metadata.path,
                    version=metadata.version,
                    mtime=metadata.mtime,
                    owner=metadata.owner,
                    group_id=metadata.group_id,
                    updated_at=datetime.now(UTC),
                )
            )
        else:
            # 插入操作
            model = self._to_model(metadata)
            self._session.add(model)

        await self._session.flush()

    async def get_by_id(self, memory_id: UUID) -> MemoryMetadata | None:
        """通过 ID 获取记忆元数据（排除已删除）。

        Args:
            memory_id: 记忆 ID

        Returns:
            MemoryMetadata 如果存在且未删除，否则 None
        """
        result = await self._session.execute(
            select(MemoryMetadataModel).where(
                and_(
                    MemoryMetadataModel.memory_id == memory_id,
                    MemoryMetadataModel.deleted_at.is_(None),
                )
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def get_by_name(self, name: str) -> MemoryMetadata | None:
        """通过名称获取记忆元数据（排除已删除）。

        Args:
            name: 记忆名称

        Returns:
            MemoryMetadata 如果存在且未删除，否则 None
        """
        result = await self._session.execute(
            select(MemoryMetadataModel).where(
                and_(
                    MemoryMetadataModel.name == name,
                    MemoryMetadataModel.deleted_at.is_(None),
                )
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def delete(self, memory_id: UUID) -> None:
        """软删除记忆元数据。

        Args:
            memory_id: 记忆 ID
        """
        await self._session.execute(
            update(MemoryMetadataModel)
            .where(
                and_(
                    MemoryMetadataModel.memory_id == memory_id,
                    MemoryMetadataModel.deleted_at.is_(None),
                )
            )
            .values(deleted_at=datetime.now(UTC))
        )
        await self._session.flush()

    async def list_by_user(self, user_id: str) -> list[MemoryMetadata]:
        """列出用户的所有记忆元数据（排除已删除）。

        Args:
            user_id: 用户 ID

        Returns:
            记忆元数据列表
        """
        result = await self._session.execute(
            select(MemoryMetadataModel)
            .where(
                and_(
                    MemoryMetadataModel.user_id == user_id,
                    MemoryMetadataModel.deleted_at.is_(None),
                )
            )
            .order_by(MemoryMetadataModel.updated_at.desc())
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def list_by_type(self, memory_type: str) -> list[MemoryMetadata]:
        """列出指定类型的所有记忆元数据（排除已删除）。

        Args:
            memory_type: 记忆类型

        Returns:
            记忆元数据列表
        """
        result = await self._session.execute(
            select(MemoryMetadataModel)
            .where(
                and_(
                    MemoryMetadataModel.type == memory_type,
                    MemoryMetadataModel.deleted_at.is_(None),
                )
            )
            .order_by(MemoryMetadataModel.updated_at.desc())
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def list_all(self) -> list[MemoryMetadata]:
        """列出所有记忆元数据（排除已删除）。

        Returns:
            所有记忆元数据列表
        """
        result = await self._session.execute(
            select(MemoryMetadataModel)
            .where(MemoryMetadataModel.deleted_at.is_(None))
            .order_by(MemoryMetadataModel.updated_at.desc())
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]
