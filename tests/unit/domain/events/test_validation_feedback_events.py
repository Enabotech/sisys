"""Story 4.7: Validation Feedback 领域事件单元测试.

覆盖两事件字段/序列化 str 化（4-5 R1-F01）/aggregate 关联（execution_id 主 id——
R2-11）/自有字段数边界（8/7）/event_type 自动注册。

TDD 红→绿：本文件先于 src/domain/events/validation_feedback_events.py 实现（Subtask 2.1）。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.validation_feedback_events import (
    ToolExecutionMarkedInfeasible,
    ToolExecutionRecovered,
)

_TENANT = uuid.uuid4()
_EXEC = uuid.uuid4()
_TOOL = uuid.uuid4()
_SIG = "c" * 64


def _make_infeasible(**overrides: object) -> ToolExecutionMarkedInfeasible:
    """构造不可行标记事件（基准形态）."""
    kwargs: dict = {
        "execution_id": _EXEC,
        "tool_id": _TOOL,
        "tenant_id": _TENANT,
        "tool_version": "1.0.0",
        "error_signature": _SIG,
        "enhanced_retry_count": 3,
        "failure_summary": "3 次增强尝试均失败",
        "occurred_at": datetime.now(UTC),
    }
    kwargs.update(overrides)
    return ToolExecutionMarkedInfeasible(**kwargs)


def _make_recovered(**overrides: object) -> ToolExecutionRecovered:
    """构造恢复事件（基准形态）."""
    kwargs: dict = {
        "execution_id": _EXEC,
        "tool_id": _TOOL,
        "tenant_id": _TENANT,
        "tool_version": "1.0.0",
        "error_signature": _SIG,
        "enhanced_retry_count": 2,
        "occurred_at": datetime.now(UTC),
    }
    kwargs.update(overrides)
    return ToolExecutionRecovered(**kwargs)


class TestMarkedInfeasibleEvent:
    """ToolExecutionMarkedInfeasible 事件."""

    def test_event_type_fixed(self) -> None:
        """event_type 固定为类名."""
        assert _make_infeasible().event_type == "ToolExecutionMarkedInfeasible"

    def test_aggregate_association(self) -> None:
        """aggregate_type=ToolExecution / aggregate_id=execution_id（主 id 定稿 R2-11）."""
        event = _make_infeasible()
        assert event.aggregate_type == "ToolExecution"
        assert event.aggregate_id == _EXEC

    def test_own_fields_are_8(self) -> None:
        """自有字段 8 个（SSOT 定稿：MarkedInfeasible 8 / Recovered 7）."""
        import dataclasses

        from src.domain.events.base import _CORE_FIELD_NAMES

        own = [f.name for f in dataclasses.fields(ToolExecutionMarkedInfeasible) if f.name not in _CORE_FIELD_NAMES]
        assert len(own) == 8
        assert set(own) == {
            "execution_id",
            "tool_id",
            "tenant_id",
            "tool_version",
            "error_signature",
            "enhanced_retry_count",
            "failure_summary",
            "occurred_at",
        }

    def test_metadata_tenant_id_str_form(self) -> None:
        """tenant_id 以 str 形态透传 metadata（UUID 对象击穿 json.dumps——R1-F01）."""
        event = _make_infeasible()
        assert event.metadata["tenant_id"] == str(_TENANT)

    def test_to_dict_json_serializable(self) -> None:
        """to_dict 全量可 json 序列化（reliable 通道绊线）."""
        json.dumps(_make_infeasible().to_dict())

    def test_to_dict_payload_str_typed(self) -> None:
        """payload 自有字段 str 化（UUID → str / datetime → isoformat）."""
        payload = _make_infeasible().to_dict()["payload"]
        assert payload["execution_id"] == str(_EXEC)
        assert payload["tool_id"] == str(_TOOL)
        assert isinstance(payload["occurred_at"], str)

    def test_frozen(self) -> None:
        """frozen dataclass."""
        event = _make_infeasible()
        with pytest.raises(AttributeError):
            setattr(event, "error_signature", "x" * 64)

    def test_registry_auto_registration(self) -> None:
        """__init_subclass__ 自动注册（from_dict 多态支撑）."""
        assert DomainEvent._registry.get("ToolExecutionMarkedInfeasible") is ToolExecutionMarkedInfeasible


class TestRecoveredEvent:
    """ToolExecutionRecovered 事件."""

    def test_event_type_fixed(self) -> None:
        """event_type 固定为类名."""
        assert _make_recovered().event_type == "ToolExecutionRecovered"

    def test_aggregate_association(self) -> None:
        """aggregate_type=ToolExecution / aggregate_id=execution_id."""
        event = _make_recovered()
        assert event.aggregate_type == "ToolExecution"
        assert event.aggregate_id == _EXEC

    def test_own_fields_are_7(self) -> None:
        """自有字段 7 个."""
        import dataclasses

        from src.domain.events.base import _CORE_FIELD_NAMES

        own = [f.name for f in dataclasses.fields(ToolExecutionRecovered) if f.name not in _CORE_FIELD_NAMES]
        assert len(own) == 7

    def test_metadata_tenant_id_str_form(self) -> None:
        """tenant_id str 化透传 metadata."""
        assert _make_recovered().metadata["tenant_id"] == str(_TENANT)

    def test_to_dict_json_serializable(self) -> None:
        """to_dict 全量可 json 序列化."""
        json.dumps(_make_recovered().to_dict())

    def test_registry_auto_registration(self) -> None:
        """自动注册."""
        assert DomainEvent._registry.get("ToolExecutionRecovered") is ToolExecutionRecovered
