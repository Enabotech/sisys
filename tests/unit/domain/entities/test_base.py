"""
领域实体基类测试 - 测试 BaseEntity、AggregateRoot、ValueObject。

领域层测试特点：
- 快速执行（无外部依赖）
- 100% 内存执行
- 验证业务规则
- 验证领域不变量
"""

from datetime import datetime
from uuid import uuid4

from src.domain.entities.base import AggregateRoot, BaseEntity, ValueObject


class TestBaseEntity:
    """BaseEntity 基类测试"""

    def test_create_entity_with_auto_id(self):
        """Given 不提供 ID，When 创建实体，Then 自动生成 UUID"""
        # Arrange & Act
        entity = DummyEntity()

        # Assert
        assert entity.id is not None
        assert isinstance(entity.id, uuid4().__class__)

    def test_create_entity_with_custom_id(self):
        """Given 提供自定义 ID，When 创建实体，Then 使用自定义 ID"""
        # Arrange
        custom_id = uuid4()

        # Act
        entity = DummyEntity(id=custom_id)

        # Assert
        assert entity.id == custom_id

    def test_entity_created_at_is_auto_set(self):
        """Given 创建实体，When 访问 created_at，Then 自动设置为当前时间"""
        # Arrange & Act
        entity = DummyEntity()

        # Assert
        assert entity.created_at is not None
        assert isinstance(entity.created_at, datetime)
        assert entity.created_at.tzinfo is not None

    def test_entity_updated_at_is_auto_set(self):
        """Given 创建实体，When 访问 updated_at，Then 自动设置为当前时间"""
        # Arrange & Act
        entity = DummyEntity()

        # Assert
        assert entity.updated_at is not None
        assert isinstance(entity.updated_at, datetime)
        assert entity.updated_at.tzinfo is not None

    def test_entity_eq_same_object(self):
        """Given 同一对象，When 比较，Then 相等"""
        # Arrange
        entity = DummyEntity()

        # Act & Assert
        assert entity == entity

    def test_entity_eq_different_objects_same_id(self):
        """Given 不同对象但相同 ID，When 比较，Then 相等"""
        # Arrange
        entity1 = DummyEntity(id=uuid4())
        entity2 = DummyEntity(id=entity1.id)

        # Act & Assert
        assert entity1 == entity2

    def test_entity_eq_different_objects_different_id(self):
        """Given 不同对象且不同 ID，When 比较，Then 不相等"""
        # Arrange
        entity1 = DummyEntity()
        entity2 = DummyEntity()

        # Act & Assert
        assert entity1 != entity2

    def test_entity_eq_different_type(self):
        """Given 不同类型对象，When 比较，Then 不相等"""
        # Arrange
        entity = DummyEntity()

        # Act & Assert
        assert entity != "not an entity"
        assert entity != 123
        assert entity != {"id": entity.id}

    def test_entity_hash(self):
        """Given 实体，When 调用 hash，Then 返回 ID 的哈希值"""
        # Arrange
        entity = DummyEntity()

        # Act
        result = hash(entity)

        # Assert
        assert result == hash(entity.id)

    def test_entity_repr(self):
        """Given 实体，When 调用 repr，Then 返回格式化的字符串表示"""
        # Arrange
        entity = DummyEntity()

        # Act
        result = repr(entity)

        # Assert
        assert "DummyEntity" in result
        assert str(entity.id) in result


class TestAggregateRoot:
    """AggregateRoot 聚合根测试"""

    def test_create_aggregate_root_with_events(self):
        """Given 创建聚合根，When 访问 domain_events，Then 返回空列表"""
        # Arrange & Act
        aggregate = DummyAggregateRoot()

        # Assert
        assert aggregate.domain_events == []
        assert isinstance(aggregate.domain_events, list)

    def test_aggregate_root_add_event(self):
        """Given 聚合根，When 添加事件，Then 事件添加到列表"""
        # Arrange
        aggregate = DummyAggregateRoot()
        test_event = {"event_type": "test.event", "data": "test_data"}

        # Act
        aggregate.add_event(test_event)

        # Assert
        assert len(aggregate.domain_events) == 1
        assert aggregate.domain_events[0] == test_event

    def test_aggregate_root_clear_events(self):
        """Given 有事件的聚合根，When 清空事件，Then 事件列表为空"""
        # Arrange
        aggregate = DummyAggregateRoot()
        aggregate.add_event({"event_type": "test.event1"})
        aggregate.add_event({"event_type": "test.event2"})
        assert len(aggregate.domain_events) == 2

        # Act
        aggregate.clear_events()

        # Assert
        assert len(aggregate.domain_events) == 0

    def test_aggregate_root_inherits_from_base_entity(self):
        """Given 聚合根，When 检查继承关系，Then 继承自 BaseEntity"""
        # Arrange & Act
        aggregate = DummyAggregateRoot()

        # Assert
        assert isinstance(aggregate, BaseEntity)
        assert hasattr(aggregate, "id")
        assert hasattr(aggregate, "created_at")
        assert hasattr(aggregate, "updated_at")


class TestValueObject:
    """ValueObject 值对象测试"""

    def test_value_object_eq_same_values(self):
        """Given 相同值的值对象，When 比较，Then 相等"""
        # Arrange
        vo1 = DummyValueObject({"key": "value"})
        vo2 = DummyValueObject({"key": "value"})

        # Act & Assert
        assert vo1 == vo2

    def test_value_object_eq_different_values(self):
        """Given 不同值的值对象，When 比较，Then 不相等"""
        # Arrange
        vo1 = DummyValueObject({"key": "value1"})
        vo2 = DummyValueObject({"key": "value2"})

        # Act & Assert
        assert vo1 != vo2

    def test_value_object_eq_different_type(self):
        """Given 不同类型对象，When 比较，Then 不相等"""
        # Arrange
        vo = DummyValueObject({"key": "value"})

        # Act & Assert
        assert vo != "not a value object"
        assert vo != 123
        assert vo != {"key": "value"}

    def test_value_object_hash_same_values(self):
        """Given 相同值的值对象，When 调用 hash，Then 返回相同哈希值"""
        # Arrange
        vo1 = DummyValueObject({"key": "value"})
        vo2 = DummyValueObject({"key": "value"})

        # Act
        hash1 = hash(vo1)
        hash2 = hash(vo2)

        # Assert
        assert hash1 == hash2

    def test_value_object_hash_different_values(self):
        """Given 不同值的值对象，When 调用 hash，Then 返回不同哈希值"""
        # Arrange
        vo1 = DummyValueObject({"key": "value1"})
        vo2 = DummyValueObject({"key": "value2"})

        # Act
        hash1 = hash(vo1)
        hash2 = hash(vo2)

        # Assert
        assert hash1 != hash2


# ========== 测试辅助类 ==========


class DummyEntity(BaseEntity):
    """测试用实体"""

    def __init__(self, id=None):
        super().__init__(id)


class DummyAggregateRoot(AggregateRoot):
    """测试用聚合根"""

    def __init__(self, id=None):
        super().__init__(id)


class DummyValueObject(ValueObject):
    """测试用值对象"""

    def __init__(self, data):
        super().__init__()
        self._data = data

    def __eq__(self, other):
        if not isinstance(other, DummyValueObject):
            return False
        return self._data == other._data

    def __hash__(self):
        return hash(tuple(sorted(self._data.items())))
