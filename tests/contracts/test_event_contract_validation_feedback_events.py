"""Story 4.7: 事件契约测试 — Validation Feedback 领域事件 ×2

验证 ToolExecutionMarkedInfeasible / ToolExecutionRecovered 两事件的自有字段数
（8/7）、DomainEvent 基类 12 核心字段对齐、to_dict 序列化 str 化（4-5 R1-F01）、
aggregate 关联与 __init_subclass__ 自动注册。

遵循项目事件契约测试模式（与 test_debate_events.py 样板对齐）。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from src.domain.events.base import _CORE_FIELD_NAMES, DomainEvent
from src.domain.events.validation_feedback_events import (
    ToolExecutionMarkedInfeasible,
    ToolExecutionRecovered,
)

_TENANT = uuid.uuid4()
_EXEC = uuid.uuid4()
_TOOL = uuid.uuid4()


def _make_infeasible() -> ToolExecutionMarkedInfeasible:
    """构造不可行标记事件。"""
    return ToolExecutionMarkedInfeasible(
        execution_id=_EXEC,
        tool_id=_TOOL,
        tenant_id=_TENANT,
        tool_version="1.0.0",
        error_signature="a" * 64,
        enhanced_retry_count=3,
        failure_summary="3 次增强尝试均失败",
        occurred_at=datetime.now(UTC),
    )


def _make_recovered() -> ToolExecutionRecovered:
    """构造恢复事件。"""
    return ToolExecutionRecovered(
        execution_id=_EXEC,
        tool_id=_TOOL,
        tenant_id=_TENANT,
        tool_version="1.0.0",
        error_signature="a" * 64,
        enhanced_retry_count=2,
        occurred_at=datetime.now(UTC),
    )


class TestMarkedInfeasibleContract:
    """ToolExecutionMarkedInfeasible 事件契约."""

    def test_event_type_is_fixed(self) -> None:
        """event_type 固定为类名（__init_subclass__ 自动注册键）."""
        event = _make_infeasible()
        assert event.event_type == "ToolExecutionMarkedInfeasible"

    def test_own_field_count_is_8(self) -> None:
        """自有字段 8 个（SSOT 定稿）."""
        import dataclasses

        core = set(_CORE_FIELD_NAMES)
        own = [f.name for f in dataclasses.fields(ToolExecutionMarkedInfeasible) if f.name not in core]
        assert len(own) == 8

    def test_aggregate_type_is_tool_execution(self) -> None:
        """aggregate_type 固定为 ToolExecution."""
        event = _make_infeasible()
        assert event.aggregate_type == "ToolExecution"

    def test_aggregate_id_follows_execution_id(self) -> None:
        """aggregate_id 关联 execution_id（聚合根主键）."""
        event = _make_infeasible()
        assert event.aggregate_id == _EXEC

    def test_metadata_tenant_id_is_str(self) -> None:
        """tenant_id 以 str 形态进 metadata（4-5 R1-F01：UUID 对象击穿 json.dumps）."""
        event = _make_infeasible()
        assert event.metadata.get("tenant_id") == str(_TENANT)

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict 全量可 json 序列化（reliable 通道绊线）."""
        event = _make_infeasible()
        data = event.to_dict()
        json.dumps(data)

    def test_payload_contains_own_fields_as_str(self) -> None:
        """自有字段 str 化进 payload."""
        event = _make_infeasible()
        payload = event.to_dict()["payload"]
        assert payload["execution_id"] == str(_EXEC)
        assert payload["tool_id"] == str(_TOOL)
        assert payload["enhanced_retry_count"] == 3
        assert payload["error_signature"] == "a" * 64

    def test_is_frozen(self) -> None:
        """frozen dataclass（不可变事件）——setattr 运行时验证（静态直赋对 frozen 属性非法）."""
        event = _make_infeasible()
        with pytest.raises(AttributeError):
            setattr(event, "tool_id", uuid.uuid4())

    def test_auto_registered_in_registry(self) -> None:
        """__init_subclass__ 自动注册（from_dict 多态反序列化支撑）."""
        assert DomainEvent._registry.get("ToolExecutionMarkedInfeasible") is ToolExecutionMarkedInfeasible


class TestRecoveredContract:
    """ToolExecutionRecovered 事件契约."""

    def test_event_type_is_fixed(self) -> None:
        """event_type 固定为类名."""
        event = _make_recovered()
        assert event.event_type == "ToolExecutionRecovered"

    def test_own_field_count_is_7(self) -> None:
        """自有字段 7 个（SSOT 定稿）."""
        import dataclasses

        core = set(_CORE_FIELD_NAMES)
        own = [f.name for f in dataclasses.fields(ToolExecutionRecovered) if f.name not in core]
        assert len(own) == 7

    def test_aggregate_type_is_tool_execution(self) -> None:
        """aggregate_type 固定为 ToolExecution."""
        event = _make_recovered()
        assert event.aggregate_type == "ToolExecution"

    def test_aggregate_id_follows_execution_id(self) -> None:
        """aggregate_id 关联 execution_id."""
        event = _make_recovered()
        assert event.aggregate_id == _EXEC

    def test_metadata_tenant_id_is_str(self) -> None:
        """tenant_id str 化进 metadata."""
        event = _make_recovered()
        assert event.metadata.get("tenant_id") == str(_TENANT)

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict 全量可 json 序列化."""
        event = _make_recovered()
        json.dumps(event.to_dict())

    def test_auto_registered_in_registry(self) -> None:
        """__init_subclass__ 自动注册."""
        assert DomainEvent._registry.get("ToolExecutionRecovered") is ToolExecutionRecovered
