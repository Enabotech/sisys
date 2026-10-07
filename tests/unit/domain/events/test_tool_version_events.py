"""工具版本管理领域事件单元测试（Story 4-6 Task 2 TDD 红→绿）

3 个事件（聚合根 = ToolVersion，平台级资源无 tenant_id）：
- ToolVersionRegistered：register_version 成功
- ToolVersionPublished：publish/abort 成功（from_status 区分直接全量/转正/调档审计语义）
- ToolRolledBack：rollback 成功（deprecated_versions 记录被降级清单 ≤10）
"""

from __future__ import annotations

import uuid

from src.domain.events.base import DomainEvent
from src.domain.events.tool_version_events import (
    ToolRolledBack,
    ToolVersionPublished,
    ToolVersionRegistered,
)


def _tid() -> uuid.UUID:
    """构造测试 tool_id。"""
    return uuid.uuid4()


class TestToolVersionRegistered:
    """ToolVersionRegistered 事件测试。"""

    def test_event_type_auto_registered(self) -> None:
        """event_type init=False 写法触发 __init_subclass__ 自动注册。"""
        event = ToolVersionRegistered(tool_id=_tid(), tool_version="1.1.0", required_rollout_mode="any")
        assert event.event_type == "ToolVersionRegistered"

    def test_aggregate_type_is_tool_version(self) -> None:
        """聚合类型为 ToolVersion。"""
        event = ToolVersionRegistered(tool_id=_tid(), tool_version="1.1.0", required_rollout_mode="any")
        assert event.aggregate_type == "ToolVersion"
        assert event.aggregate_id == event.tool_id

    def test_payload_fields(self) -> None:
        """payload 字段：tool_id/version/required_rollout_mode/breaking_summary。"""
        summary = [{"path": "/properties/a", "severity": "major"}]
        event = ToolVersionRegistered(
            tool_id=_tid(),
            tool_version="1.1.0",
            required_rollout_mode="canary_only",
            breaking_summary=summary,
        )
        assert event.required_rollout_mode == "canary_only"
        assert event.breaking_summary == summary

    def test_breaking_summary_truncated_to_10(self) -> None:
        """breaking_summary 列表截断 ≤10 条（4-3 P0-H 先例，防撑爆 Redis）。"""
        big = [{"path": f"/p/{i}", "severity": "minor"} for i in range(25)]
        event = ToolVersionRegistered(tool_id=_tid(), tool_version="1.1.0", breaking_summary=big)
        assert len(event.breaking_summary) <= 10

    def test_no_tenant_id(self) -> None:
        """平台级资源事件：payload 不含 tenant_id（Dev Notes 理由声明）。"""
        event = ToolVersionRegistered(tool_id=_tid(), tool_version="1.1.0")
        assert not hasattr(event, "tenant_id")

    def test_to_dict_json_serializable(self) -> None:
        """to_dict 可 JSON 序列化。"""
        import json

        event = ToolVersionRegistered(tool_id=_tid(), tool_version="1.1.0")
        d = event.to_dict()
        json.dumps(d)
        assert d["event_type"] == "ToolVersionRegistered"
        assert d["payload"]["tool_version"] == "1.1.0"


class TestToolVersionPublished:
    """ToolVersionPublished 事件测试。"""

    def test_from_to_status_audit_semantics(self) -> None:
        """from_status 区分审计语义：PENDING=直接全量 / CANARY=转正或调档。"""
        event = ToolVersionPublished(
            tool_id=_tid(),
            tool_version="1.1.0",
            from_status="canary",
            to_status="stable",
            traffic_weight=100,
        )
        assert event.from_status == "canary"
        assert event.to_status == "stable"

    def test_adjustment_semantics_same_status(self) -> None:
        """调档场景：from_status == to_status == canary 且携带新 weight。"""
        event = ToolVersionPublished(
            tool_id=_tid(),
            tool_version="1.1.0",
            from_status="canary",
            to_status="canary",
            traffic_weight=50,
        )
        assert event.from_status == event.to_status == "canary"
        assert event.traffic_weight == 50

    def test_abort_semantics(self) -> None:
        """放弃灰度场景：from=canary → to=deprecated，weight=0。"""
        event = ToolVersionPublished(
            tool_id=_tid(),
            tool_version="1.1.0",
            from_status="canary",
            to_status="deprecated",
            traffic_weight=0,
        )
        assert event.to_status == "deprecated"

    def test_registry_membership(self) -> None:
        """事件进入 DomainEvent 注册表（多态反序列化前提）。"""
        from src.domain.events.base import DomainEvent as Base

        ToolVersionPublished(tool_id=_tid(), tool_version="1.1.0")
        assert Base._registry.get("ToolVersionPublished") is ToolVersionPublished


class TestToolRolledBack:
    """ToolRolledBack 事件测试。"""

    def test_payload_fields(self) -> None:
        """payload：tool_id/from_version/to_version/trigger/deprecated_versions。"""
        event = ToolRolledBack(
            tool_id=_tid(),
            from_version="2.0.0",
            to_version="1.9.0",
            trigger="api",
            deprecated_versions=["2.0.0", "1.1.0"],
        )
        assert event.from_version == "2.0.0"
        assert event.to_version == "1.9.0"
        assert event.trigger == "api"
        assert event.deprecated_versions == ["2.0.0", "1.1.0"]

    def test_deprecated_versions_truncated_to_10(self) -> None:
        """deprecated_versions 截断 ≤10（含被清场 CANARY——下游可重建状态史）。"""
        event = ToolRolledBack(
            tool_id=_tid(),
            from_version="20.0.0",
            to_version="1.0.0",
            deprecated_versions=[f"{i}.0.0" for i in range(30)],
        )
        assert len(event.deprecated_versions) <= 10

    def test_is_domain_event_subclass(self) -> None:
        """继承 DomainEvent（frozen dataclass）。"""
        event = ToolRolledBack(tool_id=_tid(), from_version="2.0.0", to_version="1.9.0")
        assert isinstance(event, DomainEvent)
