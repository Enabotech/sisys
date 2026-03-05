"""
sisys - Domain Entity Base Class.

领域实体基类 - 所有领域实体的抽象基类。
"""

from abc import ABC
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


class BaseEntity(ABC):
    """
    领域实体基类。

    所有领域实体都应继承此类，以获得通用的实体行为。

    领域实体特征：
    1. 有唯一标识（ID）
    2. 有创建时间和更新时间
    3. 支持领域事件
    4. 支持审计追踪

    使用示例：
        class StrategicPlan(BaseEntity):
            def __init__(self, id: UUID, plan_type: str, ...):
                super().__init__(id)
                self._plan_type = plan_type
                ...
    """

    def __init__(self, id: UUID | None = None):
        """
        初始化领域实体。

        Args:
            id: 实体 ID（可选，不提供则自动生成）
        """
        self._id = id or uuid4()
        self._created_at = datetime.now(UTC)
        self._updated_at = datetime.now(UTC)

    @property
    def id(self) -> UUID:
        """获取实体 ID。"""
        return self._id

    @property
    def created_at(self) -> datetime:
        """获取创建时间。"""
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        """获取更新时间。"""
        return self._updated_at

    def _update_timestamp(self):
        """更新时间戳。"""
        self._updated_at = datetime.now(UTC)

    def __eq__(self, other: Any) -> bool:
        """
        基于 ID 比较实体相等性。

        Args:
            other: 另一个对象

        Returns:
            如果 ID 相同则返回 True，否则返回 False
        """
        if not isinstance(other, BaseEntity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """返回 ID 的哈希值。"""
        return hash(self.id)

    def __repr__(self) -> str:
        """返回实体的字符串表示。"""
        return f"{self.__class__.__name__}(id={self.id})"


class AggregateRoot(BaseEntity):
    """
    聚合根基类。

    聚合根是领域驱动设计中最重要的概念之一：
    1. 聚合根是聚合的入口点
    2. 外部对象只能引用聚合根
    3. 聚合根负责维护聚合内的一致性
    4. 聚合根发布领域事件

    使用示例：
        class StrategicPlan(AggregateRoot):
            def __init__(self, id: UUID, ...):
                super().__init__(id)
                self._checkpoints = []
                self._domain_events = []

            def add_checkpoint(self, stage: str, status: str):
                self._checkpoints.append({...})
                self._domain_events.append(CheckpointAdded(...))
    """

    def __init__(self, id: UUID | None = None):
        """初始化聚合根。"""
        super().__init__(id)
        self._domain_events: list[Any] = []

    @property
    def domain_events(self) -> list[Any]:
        """获取领域事件列表。"""
        return self._domain_events

    def clear_events(self):
        """清空领域事件（通常在持久化后调用）。"""
        self._domain_events.clear()

    def add_event(self, event: Any):
        """
        添加领域事件。

        Args:
            event: 领域事件实例
        """
        self._domain_events.append(event)


class ValueObject(ABC):
    """
    值对象基类。

    值对象特征：
    1. 没有唯一标识
    2. 通过属性值比较
    3. 不可变（创建后不能修改）
    4. 可以替换为另一个值对象

    使用示例：
        class Money(ValueObject):
            def __init__(self, amount: float, currency: str):
                self._amount = amount
                self._currency = currency

            def __eq__(self, other):
                if not isinstance(other, Money):
                    return False
                return self.amount == other.amount and self.currency == other.currency

            def __hash__(self):
                return hash((self.amount, self.currency))
    """

    def __init__(self):
        """初始化值对象。"""
        pass

    def __eq__(self, other: Any) -> bool:
        """
        基于所有属性值比较。

        Args:
            other: 另一个对象

        Returns:
            如果所有属性值相同则返回 True
        """
        if not isinstance(other, ValueObject):
            return False
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        """基于所有属性值计算哈希。"""
        return hash(tuple(sorted(self.__dict__.items())))
