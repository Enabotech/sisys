"""Story 4-6: 工具版本管理领域事件契约测试

验证 3 事件的事件类型注册 / aggregate_type 契约 / to_dict payload 契约。
"""

from __future__ import annotations

import json
import uuid

from src.domain.events.base import DomainEvent
from src.domain.events.tool_version_events import (
    ToolRolledBack,
    ToolVersionPublished,
    ToolVersionRegistered,
)

EVENTS = {
    "ToolVersionRegistered": ToolVersionRegistered,
    "ToolVersionPublished": ToolVersionPublished,
    "ToolRolledBack": ToolRolledBack,
}


class TestToolVersionEventContract:
    """3 事件的注册与序列化契约。"""

    def test_all_events_registered_in_domain_registry(self) -> None:
        """三事件均进入 DomainEvent._registry（event_type init=False 写法）。"""
        for event_type, event_cls in EVENTS.items():
            assert DomainEvent._registry.get(event_type) is event_cls, (
                f"{event_type} 未自动注册——检查 event_type field(init=False) 写法"
            )

    def test_aggregate_type_is_tool_version(self) -> None:
        """聚合类型统一为 ToolVersion。"""
        tid = uuid.uuid4()
        samples = [
            ToolVersionRegistered(tool_id=tid, tool_version="1.0.0"),
            ToolVersionPublished(tool_id=tid, tool_version="1.0.0", from_status="pending", to_status="stable"),
            ToolRolledBack(tool_id=tid, from_version="2.0.0", to_version="1.0.0"),
        ]
        for event in samples:
            assert event.aggregate_type == "ToolVersion"

    def test_to_dict_payload_contract(self) -> None:
        """to_dict 的 payload 包含事件特定字段。"""
        event = ToolVersionPublished(
            tool_id=uuid.uuid4(),
            tool_version="1.1.0",
            from_status="canary",
            to_status="stable",
            traffic_weight=100,
        )
        payload = event.to_dict()["payload"]
        for key in ("tool_version", "from_status", "to_status", "traffic_weight"):
            assert key in payload, f"payload 缺少 {key}"

    def test_to_dict_round_trip_json(self) -> None:
        """全部事件 to_dict 可 JSON 序列化（Redis pub/sub 投递前提）。"""
        tid = uuid.uuid4()
        samples = [
            ToolVersionRegistered(tool_id=tid, tool_version="1.0.0", breaking_summary=[{"s": "major"}]),
            ToolVersionPublished(tool_id=tid, tool_version="1.1.0", from_status="pending", to_status="canary"),
            ToolRolledBack(tool_id=tid, from_version="2.0.0", to_version="1.0.0", deprecated_versions=["2.0.0"]),
        ]
        for event in samples:
            json.dumps(event.to_dict())
