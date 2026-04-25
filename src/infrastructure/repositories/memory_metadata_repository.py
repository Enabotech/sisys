"""InMemoryMemoryMetadataRepository — 记忆元数据仓储（异步内存实现）。

⚠️ 仅用于测试隔离。生产环境使用 PostgreSQLMemoryMetadataRepository。

架构来源: architecture.md §11.2.5
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

from src.domain.entities.memory_metadata import MemoryMetadata
from src.domain.repositories.memory_repository import MemoryMetadataRepositoryProtocol


class MemoryVersionConflictError(Exception):
    """版本冲突异常。"""

    def __init__(self, memory_id: UUID, message: str = "版本冲突"):
        self.memory_id = memory_id
        super().__init__(message)


class InMemoryMemoryMetadataRepository(MemoryMetadataRepositoryProtocol):
    """内存记忆元数据仓储（异步版本）。

    ⚠️ 线程安全说明：
    使用 asyncio.Lock 保护并发访问。
    仅用于测试隔离，生产环境必须使用 PostgreSQL 版本。
    """

    def __init__(self) -> None:
        self._entities: dict[UUID, MemoryMetadata] = {}
        self._lock = asyncio.Lock()

    async def save(self, metadata: MemoryMetadata) -> None:
        """保存或更新记忆元数据（UPSERT）。

        Args:
            metadata: 记忆元数据

        Raises:
            MemoryVersionConflictError: 如果版本冲突
        """
        async with self._lock:
            existing = self._entities.get(metadata.memory_id)
            if existing is not None:
                if metadata.version <= existing.version:
                    raise MemoryVersionConflictError(metadata.memory_id)

            self._entities[metadata.memory_id] = deepcopy(metadata)

    async def get_by_id(self, memory_id: UUID) -> MemoryMetadata | None:
        """通过 ID 获取记忆元数据（排除已删除）。

        Args:
            memory_id: 记忆 ID

        Returns:
            MemoryMetadata 副本如果存在且未删除，否则 None
        """
        async with self._lock:
            entity = self._entities.get(memory_id)
            if entity is None or entity.deleted_at is not None:
                return None
            return deepcopy(entity)

    async def get_by_name(self, name: str) -> MemoryMetadata | None:
        """通过名称获取记忆元数据。

        Args:
            name: 记忆名称

        Returns:
            MemoryMetadata 如果存在，否则 None
        """
        async with self._lock:
            for entity in self._entities.values():
                if entity.name == name:
                    return deepcopy(entity)
            return None

    async def delete(self, memory_id: UUID) -> None:
        """软删除记忆元数据。

        Args:
            memory_id: 记忆 ID
        """
        async with self._lock:
            if memory_id in self._entities:
                # 软删除：设置 deleted 标记
                self._entities[memory_id].deleted_at = datetime.now(UTC)

    async def list_by_user(self, user_id: str) -> list[MemoryMetadata]:
        """列出用户的所有记忆元数据。

        Args:
            user_id: 用户 ID

        Returns:
            记忆元数据列表
        """
        async with self._lock:
            return [deepcopy(m) for m in self._entities.values() if m.user_id == user_id]

    async def list_by_type(self, memory_type: str) -> list[MemoryMetadata]:
        """列出指定类型的所有记忆元数据。

        Args:
            memory_type: 记忆类型

        Returns:
            记忆元数据列表
        """
        async with self._lock:
            return [deepcopy(m) for m in self._entities.values() if m.type == memory_type]

    async def list_all(self) -> list[MemoryMetadata]:
        """列出所有记忆元数据。

        Returns:
            所有记忆元数据列表
        """
        async with self._lock:
            return [deepcopy(m) for m in self._entities.values()]


# 别名：MemoryMetadataRepository
MemoryMetadataRepository = InMemoryMemoryMetadataRepository
