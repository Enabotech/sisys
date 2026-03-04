"""
领域事件基类测试 - 测试 DomainEvent 基类的功能。
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.base import DomainEvent


class TestDomainEvent:
    """领域事件基类测试"""

    def test_create_event_with_auto_id_and_time(self):
        """Given 不指定 ID 和时间，When 创建事件，Then 自动生成"""
        # Arrange & Act
        event = DomainEvent()

        # Assert
        assert event.event_id is not None
        assert event.occurred_on is not None
        assert isinstance(event.occurred_on, datetime)

    def test_create_event_with_custom_id_and_time(self):
        """Given 自定义 ID 和时间，When 创建事件，Then 使用提供的值"""
        # Arrange
        custom_id = uuid4()
        custom_time = datetime.now(timezone.utc)

        # Act
        event = DomainEvent(event_id=custom_id, occurred_on=custom_time)

        # Assert
        assert event.event_id == custom_id
        assert event.occurred_on == custom_time

    def test_event_type_default_implementation(self):
        """Given 子类事件，When 获取 event_type，Then 返回蛇形命名的类名"""
        # Arrange
        class TestEvent(DomainEvent):
            pass

        event = TestEvent()

        # Act
        result = event.event_type

        # Assert
        assert result == "test.event"

    def test_event_payload_default_implementation(self):
        """Given 基类事件，When 获取 payload，Then 返回空字典"""
        # Arrange
        event = DomainEvent()

        # Act
        result = event.payload

        # Assert
        assert result == {}

    def test_event_aggregate_id(self):
        """Given 带 aggregate_id 的事件，When 访问属性，Then 返回正确的值"""
        # Arrange
        agg_id = uuid4()
        event = DomainEvent(aggregate_id=agg_id)

        # Act & Assert
        assert event.aggregate_id == agg_id

    def test_event_aggregate_id_none(self):
        """Given 不带 aggregate_id 的事件，When 访问属性，Then 返回 None"""
        # Arrange
        event = DomainEvent()

        # Act & Assert
        assert event.aggregate_id is None

    def test_event_repr(self):
        """Given 事件实例，When 调用 repr，Then 返回格式化的字符串"""
        # Arrange
        event = DomainEvent()

        # Act
        result = repr(event)

        # Assert
        assert "DomainEvent" in result
        assert str(event.event_id) in result

    def test_event_eq_same_object(self):
        """Given 同一对象，When 比较，Then 相等"""
        # Arrange
        event = DomainEvent()

        # Act & Assert
        assert event == event

    def test_event_eq_different_objects_same_id(self):
        """Given 不同对象但相同 ID，When 比较，Then 相等"""
        # Arrange
        event_id = uuid4()
        event1 = DomainEvent(event_id=event_id)
        event2 = DomainEvent(event_id=event_id)

        # Act & Assert
        assert event1 == event2

    def test_event_eq_different_objects_different_id(self):
        """Given 不同对象且不同 ID，When 比较，Then 不相等"""
        # Arrange
        event1 = DomainEvent()
        event2 = DomainEvent()

        # Act & Assert
        assert event1 != event2

    def test_event_eq_different_type(self):
        """Given 不同类型对象，When 比较，Then 不相等"""
        # Arrange
        event = DomainEvent()

        # Act & Assert
        assert event != "not an event"
        assert event != 123
        assert event != {"event_id": event.event_id}

    def test_event_hash(self):
        """Given 事件实例，When 调用 hash，Then 返回 ID 的哈希值"""
        # Arrange
        event = DomainEvent()

        # Act
        result = hash(event)

        # Assert
        assert result == hash(event.event_id)


class TestDomainEventSubclass:
    """测试 DomainEvent 子类的自定义实现"""

    def test_custom_event_type(self):
        """Given 自定义 event_type，When 创建子类事件，Then 返回自定义类型"""

        # Arrange
        class PlanCreated(DomainEvent):
            @property
            def event_type(self) -> str:
                return "plan.created"

        # Act
        event = PlanCreated()

        # Assert
        assert event.event_type == "plan.created"

    def test_custom_event_payload(self):
        """Given 自定义 payload，When 创建子类事件，Then 返回自定义数据"""

        # Arrange
        class PlanCreated(DomainEvent):
            def __init__(self, plan_id, creator_id, **kwargs):
                super().__init__(**kwargs)
                self._plan_id = plan_id
                self._creator_id = creator_id

            @property
            def payload(self):
                return {
                    "plan_id": self._plan_id,
                    "creator_id": self._creator_id,
                }

        plan_id = uuid4()
        creator_id = "agent_ceo"

        # Act
        event = PlanCreated(plan_id=plan_id, creator_id=creator_id)

        # Assert
        payload = event.payload
        assert payload["plan_id"] == plan_id  # 直接比较 UUID 对象
        assert payload["creator_id"] == creator_id
