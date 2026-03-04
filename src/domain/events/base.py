"""
sisys - Domain Event Base.

领域事件基类 - 所有领域事件的抽象。
"""

from abc import ABC
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


class DomainEvent(ABC):
    """
    领域事件基类。

    领域事件表示领域中发生的重要事情，用于触发后续操作或通知其他组件。
    """

    def __init__(
        self,
        event_id: UUID | None = None,
        occurred_on: datetime | None = None,
        aggregate_id: UUID | None = None,
    ):
        """
        初始化领域事件。

        Args:
            event_id: 事件 ID，不提供则自动生成
            occurred_on: 事件发生时间，不提供则使用当前时间
            aggregate_id: 关联的聚合根 ID
        """
        self._event_id = event_id or uuid4()
        self._occurred_on = occurred_on or datetime.now(UTC)
        self._aggregate_id = aggregate_id

    @property
    def event_id(self) -> UUID:
        """返回事件 ID。"""
        return self._event_id

    @property
    def occurred_on(self) -> datetime:
        """返回事件发生时间。"""
        return self._occurred_on

    @property
    def aggregate_id(self) -> UUID | None:
        """返回关联的聚合根 ID。"""
        return self._aggregate_id

    @property
    def event_type(self) -> str:
        """
        返回事件类型。

        默认实现返回类名的蛇形命名（如 PlanCreated -> plan.created）。
        子类可以重写此属性以自定义事件类型。
        """
        class_name = self.__class__.__name__
        # 将驼峰命名转换为点分命名
        result = ""
        for i, char in enumerate(class_name):
            if char.isupper() and i > 0:
                result += "."
            result += char.lower()
        return result

    @property
    def payload(self) -> dict[str, Any]:
        """
        返回事件负载。

        子类应重写此属性以提供事件的具体数据。
        """
        return {}

    def __repr__(self) -> str:
        """返回事件的字符串表示。"""
        return f"{self.__class__.__name__}(id={self.event_id}, type={self.event_type})"

    def __eq__(self, other: object) -> bool:
        """比较两个事件是否相等。"""
        if not isinstance(other, DomainEvent):
            return False
        return self.event_id == other.event_id

    def __hash__(self) -> int:
        """返回事件的哈希值。"""
        return hash(self.event_id)
