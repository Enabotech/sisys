"""Tests for MemoryChanged domain event.

RED PHASE: 验证 MemoryChanged 事件 Schema 定义正确性
"""

from __future__ import annotations

import uuid
from dataclasses import fields

from src.domain.events.memory_events import MemoryChanged


class TestMemoryChangedSchema:
    """MemoryChanged 事件 Schema 验证"""

    def test_memory_changed_has_required_fields(self):
        """验证必需字段存在"""
        event_fields = {f.name for f in fields(MemoryChanged)}
        required = {
            "memory_id",
            "user_id",
            "name",
            "change_type",
            "is_automatic",
            "old_value",
            "new_value",
        }
        assert required.issubset(event_fields), f"Missing fields: {required - event_fields}"

    def test_memory_changed_event_type_default(self):
        """验证 event_type 默认值为 'MemoryChanged'"""
        event = MemoryChanged(
            memory_id=str(uuid.uuid4()),
            user_id="user123",
            name="test-memory",
            change_type="create",
        )
        assert event.event_type == "MemoryChanged"

    def test_memory_changed_aggregate_id_from_memory_id(self):
        """验证 aggregate_id 自动设置为 UUID"""
        memory_id = str(uuid.uuid4())
        event = MemoryChanged(
            memory_id=memory_id,
            user_id="user123",
            name="test-memory",
            change_type="create",
        )
        # aggregate_id 是独立生成的 UUID，与 memory_id 无关
        assert isinstance(event.aggregate_id, uuid.UUID)
        assert str(event.aggregate_id) != memory_id

    def test_memory_changed_aggregate_type(self):
        """验证 aggregate_type 设置为 'Memory'"""
        event = MemoryChanged(
            memory_id=str(uuid.uuid4()),
            user_id="user123",
            name="test-memory",
            change_type="create",
        )
        assert event.aggregate_type == "Memory"

    def test_memory_changed_change_type_values(self):
        """验证 change_type 支持 create/update/delete"""
        for change_type in ("create", "update", "delete"):
            event = MemoryChanged(
                memory_id=str(uuid.uuid4()),
                user_id="user123",
                name="test-memory",
                change_type=change_type,
            )
            assert event.change_type == change_type

    def test_memory_changed_is_automatic_false_by_default(self):
        """验证 is_automatic 默认为 False（用户主动操作）"""
        event = MemoryChanged(
            memory_id=str(uuid.uuid4()),
            user_id="user123",
            name="test-memory",
            change_type="create",
        )
        assert event.is_automatic is False

    def test_memory_changed_old_new_value(self):
        """验证 old_value 和 new_value 字段"""
        old_val = {"name": "old-name", "content": "old content"}
        new_val = {"name": "new-name", "content": "new content"}
        event = MemoryChanged(
            memory_id=str(uuid.uuid4()),
            user_id="user123",
            name="test-memory",
            change_type="update",
            old_value=old_val,
            new_value=new_val,
        )
        assert event.old_value == old_val
        assert event.new_value == new_val


class TestMemoryChangedSerialization:
    """MemoryChanged 序列化验证"""

    def test_to_dict(self):
        """验证 to_dict() 序列化"""
        memory_id = str(uuid.uuid4())
        event = MemoryChanged(
            memory_id=memory_id,
            user_id="user123",
            name="test-memory",
            change_type="create",
            is_automatic=False,
        )
        data = event.to_dict()
        assert data["event_type"] == "MemoryChanged"
        assert data["payload"]["memory_id"] == memory_id
        assert data["payload"]["user_id"] == "user123"
        assert data["payload"]["change_type"] == "create"

    def test_from_dict(self):
        """验证 from_dict() 反序列化"""
        memory_id = str(uuid.uuid4())
        original = MemoryChanged(
            memory_id=memory_id,
            user_id="user123",
            name="test-memory",
            change_type="create",
            is_automatic=False,
        )
        data = original.to_dict()
        restored = MemoryChanged.from_dict(data)
        assert restored.event_type == "MemoryChanged"
        assert restored.memory_id == memory_id
        assert restored.user_id == "user123"

    def test_roundtrip(self):
        """验证序列化往返一致性"""
        event = MemoryChanged(
            memory_id=str(uuid.uuid4()),
            user_id="user123",
            name="test-memory",
            change_type="update",
            is_automatic=True,
            old_value={"name": "old"},
            new_value={"name": "new"},
        )
        restored = MemoryChanged.from_dict(event.to_dict())
        assert restored.memory_id == event.memory_id
        assert restored.change_type == event.change_type
        assert restored.is_automatic == event.is_automatic
