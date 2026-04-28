"""SessionState serialization tests."""

from __future__ import annotations

from datetime import UTC, datetime

from src.infrastructure.storage.redis.session_state import SessionState


class TestSessionState:
    """SessionState 序列化/反序列化测试。"""

    def test_default_values(self) -> None:
        """SessionState 应有合理的默认值。"""
        state = SessionState(session_id="sess-1", agent_id="agent-1")
        assert state.session_id == "sess-1"
        assert state.agent_id == "agent-1"
        assert state.state == {}
        assert state.ttl == 86400
        assert isinstance(state.created_at, datetime)
        assert isinstance(state.updated_at, datetime)

    def test_to_dict_serialization(self) -> None:
        """to_dict 应正确序列化为字典。"""
        state = SessionState(
            session_id="sess-1",
            agent_id="agent-1",
            state={"key": "value"},
            ttl=3600,
        )
        result = state.to_dict()
        assert result["session_id"] == "sess-1"
        assert result["agent_id"] == "agent-1"
        assert result["state"] == {"key": "value"}
        assert result["ttl"] == 3600
        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)

    def test_from_dict_deserialization(self) -> None:
        """from_dict 应正确从字典反序列化。"""
        data = {
            "session_id": "sess-1",
            "agent_id": "agent-1",
            "state": {"key": "value"},
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
            "ttl": 7200,
        }
        state = SessionState.from_dict(data)
        assert state.session_id == "sess-1"
        assert state.agent_id == "agent-1"
        assert state.state == {"key": "value"}
        assert state.ttl == 7200

    def test_roundtrip(self) -> None:
        """to_dict -> from_dict 应保持数据不变。"""
        original = SessionState(
            session_id="sess-1",
            agent_id="agent-1",
            state={"counter": 42, "items": ["a", "b"]},
            ttl=3600,
        )
        restored = SessionState.from_dict(original.to_dict())
        assert restored.session_id == original.session_id
        assert restored.agent_id == original.agent_id
        assert restored.state == original.state
        assert restored.ttl == original.ttl

    def test_from_dict_with_defaults(self) -> None:
        """from_dict 应使用默认值处理缺失字段。"""
        data = {
            "session_id": "sess-1",
            "agent_id": "agent-1",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }
        state = SessionState.from_dict(data)
        assert state.state == {}
        assert state.ttl == 86400

    def test_from_dict_with_datetime_objects(self) -> None:
        """from_dict 应接受 datetime 对象而非字符串。"""
        now = datetime.now(UTC)
        data = {
            "session_id": "sess-1",
            "agent_id": "agent-1",
            "state": {},
            "created_at": now,
            "updated_at": now,
        }
        state = SessionState.from_dict(data)
        assert state.created_at == now
        assert state.updated_at == now
