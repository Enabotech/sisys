"""基础设施层记忆元数据仓储模块

L2 PostgreSQL 持久化实现，使用 SQLAlchemy AsyncSession
支持多用户并行会话级别隔离、UPSERT 版本冲突检测（乐观锁）和软删除
继承 PostgreSQLAdapter[MemoryMetadata, MemoryMetadataModel]

Session 来源：
- Session 通过 ContextVar 由 middleware 或 test fixture 提供
- 无需构造器注入 session 参数

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, select, update

from src.domain.entities.memory_metadata import MemoryMetadata
from src.domain.exceptions.storage_exceptions import MemoryVersionConflictError
from src.domain.ports.memory_repository import L2MetadataRepositoryPort
from src.infrastructure.storage.postgresql.models.memory import MemoryMetadataModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import PostgreSQLAdapter


class PostgreSQLMemoryMetadataRepository(
    PostgreSQLAdapter[MemoryMetadata, MemoryMetadataModel],
    L2MetadataRepositoryPort,
):
    """PostgreSQL 记忆元数据仓储

    继承 PostgreSQLAdapter，覆写 pk_column/soft_delete_column/_do_save
    支持多用户并发的会话级别隔离
    软删除模式：deleted_at 非 NULL 的记录视为已删除
    """

    pk_column = "memory_id"
    soft_delete_column = "deleted_at"

    def __init__(self) -> None:
        super().__init__(MemoryMetadataModel)

    def _to_model(self, entity: MemoryMetadata) -> MemoryMetadataModel:
        """将领域实体转换为数据库模型"""
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
        """将数据库模型转换为领域实体"""
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

    async def save(self, metadata: MemoryMetadata) -> MemoryMetadata:
        """保存或更新记忆元数据（UPSERT with 乐观锁）

        覆写父类 save — 使用自定义 _do_save 实现 UPSERT+版本检查

        Args:
            metadata: 记忆元数据

        Raises:
            MemoryVersionConflictError: 如果版本冲突（并发更新）
        """
        model = self._to_model(metadata)
        await self._do_save(model, metadata)
        return metadata

    async def _do_save(self, model: MemoryMetadataModel, entity: MemoryMetadata) -> None:
        """覆写父类 _do_save — 实现 UPSERT + 乐观锁"""
        # 检查是否已存在（排除已删除的记录）
        result = await self._session.execute(
            select(MemoryMetadataModel).where(
                and_(
                    MemoryMetadataModel.memory_id == entity.memory_id,
                    MemoryMetadataModel.deleted_at.is_(None),
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            # 更新操作：检查版本（乐观锁）
            if entity.version <= existing.version:
                raise MemoryVersionConflictError(entity.memory_id)

            # 执行更新
            await self._session.execute(
                update(MemoryMetadataModel)
                .where(
                    and_(
                        MemoryMetadataModel.memory_id == entity.memory_id,
                        MemoryMetadataModel.deleted_at.is_(None),
                    )
                )
                .values(
                    name=entity.name,
                    description=entity.description,
                    type=entity.type,
                    path=entity.path,
                    version=entity.version,
                    mtime=entity.mtime,
                    owner=entity.owner,
                    group_id=entity.group_id,
                    updated_at=datetime.now(UTC),
                )
            )
        else:
            # 插入操作
            model = self._to_model(entity)
            self._session.add(model)

        await self._session.flush()

    async def get_by_name(self, name: str) -> MemoryMetadata | None:
        """通过名称获取记忆元数据（排除已删除）

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

    async def list_by_user(self, user_id: str) -> list[MemoryMetadata]:
        """列出用户的所有记忆元数据（排除已删除）

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
        """列出指定类型的所有记忆元数据（排除已删除）

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
