"""通用仓储基类。

所有具体仓储类继承此基类，复用 CRUD 操作。
支持异步操作（async/await）。
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.models import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """通用仓储基类。

    泛型类型参数 T 必须是 SQLAlchemy 模型（继承自 Base）。
    """

    def __init__(self, model_class: type[T], session: AsyncSession):
        """初始化 BaseRepository。

        Args:
            model_class: SQLAlchemy 模型类
            session: 异步数据库会话
        """
        self._model_class: type[T] = model_class
        self._session = session

    async def get_by_id(self, id: str) -> T | None:
        """根据 ID 获取实体。

        Args:
            id: 实体 UUID（字符串格式）

        Returns:
            实体实例，如果不存在则返回 None
        """
        result = await self._session.execute(select(self._model_class).where(cast(Any, self._model_class).id == id))
        return result.scalar_one_or_none()

    async def save(self, entity: T) -> T:
        """保存实体（插入或更新）。

        Args:
            entity: 实体实例

        Returns:
            保存后的实体实例
        """
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, id: str) -> None:
        """删除实体。

        Args:
            id: 实体 UUID（字符串格式）
        """
        entity = await self.get_by_id(id)
        if entity:
            await self._session.delete(entity)
            await self._session.flush()

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        """获取实体列表。

        Args:
            skip: 跳过数量
            limit: 返回数量上限

        Returns:
            实体列表
        """
        result = await self._session.execute(select(self._model_class).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def count(self) -> int:
        """获取实体总数。

        Returns:
            实体总数
        """
        result = await self._session.execute(select(func.count()).select_from(self._model_class))
        return int(result.scalar() or 0)
