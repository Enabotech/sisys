"""
sisys - Domain Repository Base.

仓储基类 - 所有仓储接口的抽象。
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from src.domain.entities.base import AggregateRoot
from src.domain.exceptions import NotFoundError

T = TypeVar("T", bound=AggregateRoot)


class BaseRepository(ABC, Generic[T]):
    """
    仓储基类（协议接口）。

    仓储模式的核心概念：
    1. 仓储提供集合的抽象，隐藏数据存储细节
    2. 仓储操作聚合根，不操作实体或值对象
    3. 仓储接口在领域层定义，实现在基础设施层
    4. 仓储方法应该使用领域术语，而非数据库术语

    使用示例：
        class PlanRepository(BaseRepository[StrategicPlan]):
            async def get_by_id(self, id: UUID) -> StrategicPlan | None:
                # 实现从数据库获取

            async def add(self, plan: StrategicPlan) -> StrategicPlan:
                # 实现保存到数据库
    """

    @abstractmethod
    async def get_by_id(self, id: str | T) -> T | None:
        """
        根据 ID 获取聚合根。

        Args:
            id: 聚合根 ID

        Returns:
            聚合根实例，不存在则返回 None
        """
        pass

    @abstractmethod
    async def get_by_id_or_raise(self, id: str | T) -> T:
        """
        根据 ID 获取聚合根，不存在则抛出异常。

        Args:
            id: 聚合根 ID

        Returns:
            聚合根实例

        Raises:
            NotFoundError: 当聚合根不存在时
        """
        entity = await self.get_by_id(id)
        if entity is None:
            # 将 id 转换为字符串
            entity_id = str(id) if not isinstance(id, str) else id
            # 使用自定义消息风格
            raise NotFoundError(message=f"{self._entity_name()} with id {entity_id} not found")
        return entity

    @abstractmethod
    async def add(self, entity: T) -> T:
        """
        添加新的聚合根。

        Args:
            entity: 要添加的聚合根

        Returns:
            已保存的聚合根
        """
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """
        更新现有的聚合根。

        Args:
            entity: 要更新的聚合根

        Returns:
            已更新的聚合根
        """
        pass

    @abstractmethod
    async def delete(self, id: str | T) -> bool:
        """
        删除聚合根。

        Args:
            id: 聚合根 ID

        Returns:
            True 如果删除成功，False 如果不存在
        """
        pass

    @abstractmethod
    async def find_all(self) -> list[T]:
        """
        获取所有聚合根。

        Returns:
            聚合根列表
        """
        pass

    def _entity_name(self) -> str:
        """获取实体名称（用于错误消息）。"""
        return self.__class__.__name__.replace("Repository", "")


class UnitOfWork(ABC):
    """
    工作单元接口。

    工作单元模式的核心概念：
    1. 维护业务操作期间改变的对象列表
    2. 协调事务的提交
    3. 处理并发问题

    使用示例：
        class SqlAlchemyUnitOfWork(UnitOfWork):
            async def __aenter__(self):
                # 开始事务
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                # 提交或回滚事务
                pass
    """

    @abstractmethod
    async def commit(self):
        """提交工作单元中的所有变更。"""
        pass

    @abstractmethod
    async def rollback(self):
        """回滚工作单元中的所有变更。"""
        pass

    @abstractmethod
    async def close(self):
        """关闭工作单元，释放资源。"""
        pass
