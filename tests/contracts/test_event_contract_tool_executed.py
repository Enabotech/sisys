"""Story 4.1a: ToolExecuted 事件契约测试

验证 ToolExecuted 事件的字段完整性、序列化、双通道配置。

遵循项目标准事件契约测试模式。
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.events.tool_events import ToolExecuted


class TestToolExecutedEventSchema:
    """ToolExecuted 事件 Schema 完整性测试。"""

    def _make_event(self) -> ToolExecuted:
        """创建标准 ToolExecuted 事件实例。"""
        return ToolExecuted(
            execution_id=uuid.uuid4(),
            tool_id=uuid.uuid4(),
            tool_version="v1.0.0",
            execution_result={"status": "success", "output": {}},
            cost_audit={"llm_tokens": 100, "sandbox_duration_sec": 2.5},
        )

    def test_event_type_is_tool_executed(self) -> None:
        """事件类型固定为 ToolExecuted。"""
        event = self._make_event()
        assert event.event_type == "ToolExecuted"

    def test_aggregate_id_set_to_execution_id(self) -> None:
        """aggregate_id 应为 execution_id（不是 tool_id）。"""
        event = self._make_event()
        assert event.aggregate_id == event.execution_id

    def test_aggregate_type_set_to_tool_execution(self) -> None:
        """aggregate_type 应为 ToolExecution（不是 Tool）。"""
        event = self._make_event()
        assert event.aggregate_type == "ToolExecution"

    def test_event_inherits_domain_event_fields(self) -> None:
        """事件应继承 DomainEvent 所有核心字段。"""
        from src.domain.events.base import DomainEvent

        event = self._make_event()
        assert isinstance(event, DomainEvent)
        assert hasattr(event, "event_id")
        assert hasattr(event, "timestamp")
        assert hasattr(event, "source")
        assert hasattr(event, "schema_version")

    def test_event_has_all_subclass_fields(self) -> None:
        """事件应包含所有子类特有字段。"""
        event = self._make_event()
        assert hasattr(event, "execution_id")
        assert hasattr(event, "tool_id")
        assert hasattr(event, "tool_version")
        assert hasattr(event, "execution_result")
        assert hasattr(event, "cost_audit")


class TestToolExecutedEventSerialization:
    """ToolExecuted 事件序列化 roundtrip 测试。"""

    def _make_event(self) -> ToolExecuted:
        """创建标准 ToolExecuted 事件实例。"""
        return ToolExecuted(
            execution_id=uuid.uuid4(),
            tool_id=uuid.uuid4(),
            tool_version="v1.0.0",
            execution_result={"status": "success", "output": {"result": "done"}},
            cost_audit={"llm_tokens": 150, "sandbox_duration_sec": 3.2},
        )

    def test_to_dict_includes_execution_id(self) -> None:
        """to_dict 应包含 execution_id。"""
        event = self._make_event()
        data = event.to_dict()
        assert "execution_id" in data

    def test_to_dict_includes_tool_id(self) -> None:
        """to_dict 应包含 tool_id。"""
        event = self._make_event()
        data = event.to_dict()
        assert "tool_id" in data

    def test_to_dict_includes_execution_result(self) -> None:
        """to_dict 应包含 execution_result。"""
        event = self._make_event()
        data = event.to_dict()
        assert "execution_result" in data

    def test_to_dict_includes_cost_audit(self) -> None:
        """to_dict 应包含 cost_audit。"""
        event = self._make_event()
        data = event.to_dict()
        assert "cost_audit" in data

    def test_from_dict_roundtrip(self) -> None:
        """to_dict -> from_dict -> to_dict 应等值。"""
        event = self._make_event()
        data = event.to_dict()
        restored = ToolExecuted.from_dict(data)
        assert restored.execution_id == event.execution_id
        assert restored.tool_id == event.tool_id
        assert restored.execution_result == event.execution_result
        assert restored.cost_audit == event.cost_audit


class TestToolExecutedEventInvariants:
    """ToolExecuted 事件不变量测试。"""

    def test_event_is_frozen(self) -> None:
        """frozen dataclass 应不可变。"""
        event = ToolExecuted(
            execution_id=uuid.uuid4(),
            tool_id=uuid.uuid4(),
            tool_version="v1.0.0",
            execution_result={},
            cost_audit={},
        )
        with pytest.raises(AttributeError):
            event.execution_id = uuid.uuid4()  # type: ignore[misc]

    def test_event_is_domain_event_subclass(self) -> None:
        """事件应为 DomainEvent 子类。"""
        from src.domain.events.base import DomainEvent

        event = ToolExecuted(
            execution_id=uuid.uuid4(),
            tool_id=uuid.uuid4(),
            tool_version="v1.0.0",
            execution_result={},
            cost_audit={},
        )
        assert isinstance(event, DomainEvent)
