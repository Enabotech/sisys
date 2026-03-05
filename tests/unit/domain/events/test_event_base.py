"""
领域事件基类测试 - 测试 DomainEvent。

领域层测试特点：
- 快速执行（无外部依赖）
- 100% 内存执行
- 验证业务规则
- 验证领域不变量
"""

from datetime import UTC, datetime
from uuid import uuid4

from src.domain.events.base import DomainEvent


class TestDomainEvent:
    """DomainEvent 基类测试"""

    def test_create_event_with_auto_id_and_time(self):
        """Given 不提供 ID 和时间，When 创建事件，Then 自动生成"""
        # Arrange & Act
        event = DomainEvent(aggregate_id=uuid4())

        # Assert
        assert event.event_id is not None
        assert isinstance(event.event_id, uuid4().__class__)
        assert event.occurred_on is not None
        assert isinstance(event.occurred_on, datetime)
        assert event.occurred_on.tzinfo is not None

    def test_create_event_with_custom_id_and_time(self):
        """Given 提供自定义 ID 和时间，When 创建事件，Then 使用自定义值"""
        # Arrange
        custom_id = uuid4()
        custom_time = datetime(2026, 3, 4, 10, 0, 0, tzinfo=UTC)

        # Act
        event = DomainEvent(
            event_id=custom_id,
            occurred_on=custom_time,
            aggregate_id=uuid4(),
        )

        # Assert
        assert event.event_id == custom_id
        assert event.occurred_on == custom_time

    def test_event_aggregate_id(self):
        """Given 创建事件，When 访问 aggregate_id，Then 返回关联的聚合根 ID"""
        # Arrange
        aggregate_id = uuid4()

        # Act
        event = DomainEvent(aggregate_id=aggregate_id)

        # Assert
        assert event.aggregate_id == aggregate_id

    def test_event_type_default_implementation(self):
        """Given DomainEvent 基类，When 访问 event_type，Then 返回默认值"""
        # Arrange & Act
        event = DomainEvent(aggregate_id=uuid4())

        # Assert
        assert event.event_type == "domain.event"

    def test_event_payload_default_implementation(self):
        """Given DomainEvent 基类，When 访问 payload，Then 返回空字典"""
        # Arrange & Act
        event = DomainEvent(aggregate_id=uuid4())

        # Assert
        assert event.payload == {}

    def test_event_schema_version_default(self):
        """Given DomainEvent 基类，When 访问 schema_version，Then 返回默认版本号"""
        # Arrange & Act
        event = DomainEvent(aggregate_id=uuid4())

        # Assert
        assert event.schema_version == "1.0"

    def test_event_eq_same_object(self):
        """Given 同一对象，When 比较，Then 相等"""
        # Arrange
        event = DomainEvent(aggregate_id=uuid4())

        # Act & Assert
        assert event == event

    def test_event_eq_different_objects_same_id(self):
        """Given 不同对象但相同 ID，When 比较，Then 相等"""
        # Arrange
        event_id = uuid4()
        event1 = DomainEvent(event_id=event_id, aggregate_id=uuid4())
        event2 = DomainEvent(event_id=event_id, aggregate_id=uuid4())

        # Act & Assert
        assert event1 == event2

    def test_event_eq_different_objects_different_id(self):
        """Given 不同对象且不同 ID，When 比较，Then 不相等"""
        # Arrange
        event1 = DomainEvent(aggregate_id=uuid4())
        event2 = DomainEvent(aggregate_id=uuid4())

        # Act & Assert
        assert event1 != event2

    def test_event_eq_different_type(self):
        """Given 不同类型对象，When 比较，Then 不相等"""
        # Arrange
        event = DomainEvent(aggregate_id=uuid4())

        # Act & Assert
        assert event != "not an event"
        assert event != 123
        assert event != {"event_id": event.event_id}

    def test_event_hash(self):
        """Given 事件，When 调用 hash，Then 返回 ID 的哈希值"""
        # Arrange
        event = DomainEvent(aggregate_id=uuid4())

        # Act
        result = hash(event)

        # Assert
        assert result == hash(event.event_id)

    def test_event_repr(self):
        """Given 事件，When 调用 repr，Then 返回格式化的字符串表示"""
        # Arrange
        event = DomainEvent(aggregate_id=uuid4())

        # Act
        result = repr(event)

        # Assert
        assert "DomainEvent" in result
        assert str(event.event_id) in result
        assert event.event_type in result


class TestDomainEventSubclass:
    """DomainEvent 子类测试"""

    def test_custom_event_type(self):
        """Given 自定义事件，When 创建事件，Then 使用自定义事件类型"""
        # Arrange & Act
        event = CustomEvent(aggregate_id=uuid4())

        # Assert
        assert event.event_type == "custom.event"

    def test_custom_event_payload(self):
        """Given 自定义事件，When 创建事件，Then 包含自定义载荷"""
        # Arrange
        payload = {"key": "value", "number": 42}

        # Act
        event = CustomEvent(aggregate_id=uuid4(), payload=payload)

        # Assert
        assert event.payload == payload
        assert event.payload["key"] == "value"
        assert event.payload["number"] == 42


# ========== 测试辅助类 ==========


class CustomEvent(DomainEvent):
    """自定义事件用于测试"""

    def __init__(self, aggregate_id, payload=None):
        super().__init__(aggregate_id=aggregate_id, payload=payload)

    @property
    def event_type(self) -> str:
        return "custom.event"

    @property
    def payload(self) -> dict:
        return self._payload
