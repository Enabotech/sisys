"""BlackboardEntry serialization tests."""

from __future__ import annotations

from datetime import UTC, datetime

from src.infrastructure.storage.redis.blackboard_entry import BlackboardEntry


class TestBlackboardEntry:
    """BlackboardEntry 序列化/反序列化测试。"""

    def test_default_values(self) -> None:
        """BlackboardEntry 应有合理的默认值。"""
        entry = BlackboardEntry(
            conversation_id="conv-1",
            agent_id="agent-1",
            content={"key": "value"},
        )
        assert entry.conversation_id == "conv-1"
        assert entry.agent_id == "agent-1"
        assert entry.content == {"key": "value"}
        assert entry.confidence == 1.0
        assert entry.citations == []
        assert entry.version == 1
        assert isinstance(entry.timestamp, datetime)

    def test_to_dict_serialization(self) -> None:
        """to_dict 应正确序列化为字典。"""
        entry = BlackboardEntry(
            conversation_id="conv-1",
            agent_id="agent-1",
            content={"analysis": "result"},
            confidence=0.85,
            citations=["source1", "source2"],
            version=3,
        )
        result = entry.to_dict()
        assert result["conversation_id"] == "conv-1"
        assert result["agent_id"] == "agent-1"
        assert result["content"] == {"analysis": "result"}
        assert result["confidence"] == 0.85
        assert result["citations"] == ["source1", "source2"]
        assert result["version"] == 3
        assert isinstance(result["timestamp"], str)

    def test_from_dict_deserialization(self) -> None:
        """from_dict 应正确从字典反序列化。"""
        data = {
            "conversation_id": "conv-1",
            "agent_id": "agent-1",
            "content": {"result": "value"},
            "confidence": 0.9,
            "citations": ["ref1"],
            "timestamp": "2024-01-01T00:00:00+00:00",
            "version": 5,
        }
        entry = BlackboardEntry.from_dict(data)
        assert entry.conversation_id == "conv-1"
        assert entry.agent_id == "agent-1"
        assert entry.content == {"result": "value"}
        assert entry.confidence == 0.9
        assert entry.citations == ["ref1"]
        assert entry.version == 5

    def test_roundtrip(self) -> None:
        """to_dict -> from_dict 应保持数据不变。"""
        original = BlackboardEntry(
            conversation_id="conv-1",
            agent_id="agent-1",
            content={"nested": {"data": "value"}},
            confidence=0.75,
            citations=["a", "b", "c"],
            version=10,
        )
        restored = BlackboardEntry.from_dict(original.to_dict())
        assert restored.conversation_id == original.conversation_id
        assert restored.agent_id == original.agent_id
        assert restored.content == original.content
        assert restored.confidence == original.confidence
        assert restored.citations == original.citations
        assert restored.version == original.version

    def test_from_dict_with_defaults(self) -> None:
        """from_dict 应使用默认值处理缺失字段。"""
        data = {
            "conversation_id": "conv-1",
            "agent_id": "agent-1",
            "content": {},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }
        entry = BlackboardEntry.from_dict(data)
        assert entry.confidence == 1.0
        assert entry.citations == []
        assert entry.version == 1

    def test_from_dict_with_datetime_object(self) -> None:
        """from_dict 应接受 datetime 对象。"""
        now = datetime.now(UTC)
        data = {
            "conversation_id": "conv-1",
            "agent_id": "agent-1",
            "content": {},
            "timestamp": now,
        }
        entry = BlackboardEntry.from_dict(data)
        assert entry.timestamp == now
