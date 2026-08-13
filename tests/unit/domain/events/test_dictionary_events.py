"""DictionaryUpdated 领域事件单元测试

测试事件构造、序列化、自动注册、aggregate_type 设置。
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.events import DictionaryUpdated, DomainEvent


class TestDictionaryUpdatedSchema:
    """DictionaryUpdated 事件 Schema 验证"""

    def test_inherits_domain_event(self):
        """继承 DomainEvent 基类"""
        assert issubclass(DictionaryUpdated, DomainEvent)

    def test_event_type_default(self):
        """event_type 默认为 DictionaryUpdated"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api")
        assert event.event_type == "DictionaryUpdated"

    def test_required_fields(self):
        """必需字段存在"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api")
        assert event.term == "BLM"
        assert event.action == "add"
        assert event.trigger == "api"

    def test_dictionary_version_default(self):
        """dictionary_version 默认为 0"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api")
        assert event.dictionary_version == 0

    def test_dictionary_version_custom(self):
        """dictionary_version 可自定义"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api", dictionary_version=5)
        assert event.dictionary_version == 5

    def test_action_validation(self):
        """action 接受有效值"""
        for action in ("add", "update", "delete", "rollback"):
            event = DictionaryUpdated(term="BLM", action=action, trigger="api")
            assert event.action == action

    def test_trigger_validation(self):
        """trigger 接受有效值"""
        for trigger in ("api", "ingest", "manual"):
            event = DictionaryUpdated(term="BLM", action="add", trigger=trigger)
            assert event.trigger == trigger

    def test_aggregate_type_default(self):
        """aggregate_type 默认为 Dictionary"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api")
        assert event.aggregate_type == "Dictionary"

    def test_frozen_dataclass(self):
        """frozen dataclass 不可变"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api")
        with pytest.raises(AttributeError):
            event.term = "SWOT"

    def test_auto_registered(self):
        """事件自动注册到 _registry"""
        # 确保注册表中包含 DictionaryUpdated
        assert "DictionaryUpdated" in DomainEvent._registry
        assert DomainEvent._registry["DictionaryUpdated"] is DictionaryUpdated


class TestDictionaryUpdatedSerialization:
    """DictionaryUpdated 序列化测试"""

    def test_to_dict_contains_event_type(self):
        """to_dict() 包含 event_type"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api")
        data = event.to_dict()
        assert data["event_type"] == "DictionaryUpdated"

    def test_to_dict_contains_event_id(self):
        """to_dict() 包含 event_id"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api")
        data = event.to_dict()
        assert uuid.UUID(data["event_id"])

    def test_to_dict_contains_payload_fields(self):
        """to_dict() 的 payload 包含 term/action/trigger/dictionary_version"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api", dictionary_version=3)
        data = event.to_dict()
        payload = data["payload"]
        assert payload["term"] == "BLM"
        assert payload["action"] == "add"
        assert payload["trigger"] == "api"
        assert payload["dictionary_version"] == 3

    def test_to_dict_contains_aggregate_type(self):
        """to_dict() 包含 aggregate_type"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api")
        data = event.to_dict()
        assert data.get("aggregate_type") == "Dictionary"

    def test_to_dict_contains_aggregate_id(self):
        """to_dict() 包含 aggregate_id"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api")
        data = event.to_dict()
        assert uuid.UUID(data["aggregate_id"])

    def test_roundtrip(self):
        """to_dict() -> from_dict() 往返一致"""
        event = DictionaryUpdated(
            term="BLM",
            action="add",
            trigger="api",
            dictionary_version=3,
            source="test",
        )
        data = event.to_dict()
        restored = DomainEvent.from_dict(data)
        assert isinstance(restored, DictionaryUpdated)
        assert restored.term == "BLM"
        assert restored.action == "add"
        assert restored.trigger == "api"
        assert restored.dictionary_version == 3
        assert restored.event_type == "DictionaryUpdated"

    def test_roundtrip_with_payload_context(self):
        """payload 中的额外上下文在往返中保留"""
        event = DictionaryUpdated(
            term="BLM",
            action="add",
            trigger="api",
            payload={"extra": "info"},
        )
        data = event.to_dict()
        restored = DomainEvent.from_dict(data)
        assert isinstance(restored, DictionaryUpdated)
        assert restored.term == "BLM"
        assert restored.action == "add"
        assert restored.trigger == "api"
        # 合并后的 payload 包含 extra
        assert "extra" in data["payload"]

    def test_serialization_idempotent(self):
        """两次序列化结果一致（event_id 不变）"""
        event = DictionaryUpdated(term="BLM", action="add", trigger="api")
        data1 = event.to_dict()
        data2 = event.to_dict()
        assert data1["event_id"] == data2["event_id"]
