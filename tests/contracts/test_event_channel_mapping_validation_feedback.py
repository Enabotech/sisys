"""Story 4.7: 事件通道映射契约测试 — Validation Feedback 两新事件 + reliable 升级

验证 ToolExecutionMarkedInfeasible / ToolExecutionRecovered 双通道两处
（configs/event_channels.yaml 与 ChannelRouter.DEFAULT_MAPPINGS）逐字段一致，
以及 ToolSchemaValidationFailed 由 realtime-only 升级 reliable（4.3 预留债清偿）。

遵循项目通道映射契约测试模式（与 test_event_channel_mapping_tool_version.py 样板对齐）。
「双通道」语义：配置面双登记（redis_channel + rabbitmq_routing_key + delivery_mode:
reliable）；运行时 DualChannelEventBus 对 reliable 事件仅走 outbox 路径不发布 Redis。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

ROOT = Path(__file__).resolve().parents[2]

EVENT_TYPES = (
    "ToolExecutionMarkedInfeasible",
    "ToolExecutionRecovered",
)

EXPECTED_CHANNELS = {
    "ToolExecutionMarkedInfeasible": {
        "redis_channel": "sisys:rt:tool_execution_marked_infeasible",
        "rabbitmq_routing_key": "sisys.events.reliable.tool_execution_marked_infeasible",
    },
    "ToolExecutionRecovered": {
        "redis_channel": "sisys:rt:tool_execution_recovered",
        "rabbitmq_routing_key": "sisys.events.reliable.tool_execution_recovered",
    },
}


def _yaml_channels() -> dict[str, Any]:
    """读取 YAML 顶层 event_channels 配置。"""
    yaml_path = ROOT / "configs" / "event_channels.yaml"
    config: dict[str, Any] = yaml.safe_load(yaml_path.read_text())
    channels: dict[str, Any] = config["event_channels"]
    return channels


class TestNewEventChannelMapping:
    """两新事件双通道两处一致."""

    def test_all_registered_in_default_mappings(self) -> None:
        """DEFAULT_MAPPINGS 登记两事件."""
        for event_type in EVENT_TYPES:
            assert ChannelRouter.DEFAULT_MAPPINGS.get(event_type) is not None, f"{event_type} 未登记"

    def test_all_registered_in_yaml(self) -> None:
        """YAML 登记两事件."""
        yaml_channels = _yaml_channels()
        for event_type in EVENT_TYPES:
            assert yaml_channels.get(event_type) is not None, f"{event_type} 未登记"

    def test_redis_channel_consistent(self) -> None:
        """redis_channel 三重一致（YAML / DEFAULT_MAPPINGS / 期望值）."""
        yaml_channels = _yaml_channels()
        for event_type in EVENT_TYPES:
            expected = EXPECTED_CHANNELS[event_type]["redis_channel"]
            yaml_cfg = yaml_channels[event_type]
            mapping = ChannelRouter.DEFAULT_MAPPINGS[event_type]
            assert yaml_cfg["redis_channel"] == expected
            assert mapping.redis_channel == expected

    def test_rabbitmq_routing_key_consistent(self) -> None:
        """rabbitmq_routing_key 三重一致."""
        yaml_channels = _yaml_channels()
        for event_type in EVENT_TYPES:
            expected = EXPECTED_CHANNELS[event_type]["rabbitmq_routing_key"]
            yaml_cfg = yaml_channels[event_type]
            mapping = ChannelRouter.DEFAULT_MAPPINGS[event_type]
            assert yaml_cfg["rabbitmq_routing_key"] == expected
            assert mapping.rabbitmq_routing_key == expected

    def test_delivery_mode_reliable_in_both(self) -> None:
        """delivery_mode 双侧均为 reliable（YAML 字符串 / 枚举）."""
        yaml_channels = _yaml_channels()
        for event_type in EVENT_TYPES:
            assert yaml_channels[event_type]["delivery_mode"] == "reliable"
            mapping = ChannelRouter.DEFAULT_MAPPINGS[event_type]
            assert mapping.delivery_mode is DeliveryMode.RELIABLE

    def test_description_non_empty(self) -> None:
        """description 非空（可运维性）."""
        yaml_channels = _yaml_channels()
        for event_type in EVENT_TYPES:
            assert yaml_channels[event_type].get("description")
            assert ChannelRouter.DEFAULT_MAPPINGS[event_type].description

    def test_router_delivery_mode_lookup(self) -> None:
        """ChannelRouter.from_default_config 实际查询路径可用."""
        router = ChannelRouter.from_default_config()
        for event_type in EVENT_TYPES:
            assert router.get_delivery_mode(event_type) == DeliveryMode.RELIABLE


class TestToolSchemaValidationFailedReliableUpgrade:
    """ToolSchemaValidationFailed 由 realtime-only 升级 reliable（4.3 预留债清偿）."""

    def test_yaml_has_reliable_with_routing_key(self) -> None:
        """YAML：delivery_mode=reliable + rabbitmq_routing_key 补齐."""
        yaml_cfg = _yaml_channels()["ToolSchemaValidationFailed"]
        assert yaml_cfg["delivery_mode"] == "reliable"
        assert yaml_cfg["rabbitmq_routing_key"]

    def test_default_mappings_reliable(self) -> None:
        """DEFAULT_MAPPINGS：delivery_mode=RELIABLE + routing_key 补齐."""
        mapping = ChannelRouter.DEFAULT_MAPPINGS["ToolSchemaValidationFailed"]
        assert mapping.delivery_mode is DeliveryMode.RELIABLE
        assert mapping.rabbitmq_routing_key

    def test_two_places_consistent(self) -> None:
        """两处逐字段一致."""
        yaml_cfg = _yaml_channels()["ToolSchemaValidationFailed"]
        mapping = ChannelRouter.DEFAULT_MAPPINGS["ToolSchemaValidationFailed"]
        assert yaml_cfg["redis_channel"] == mapping.redis_channel
        assert yaml_cfg["rabbitmq_routing_key"] == mapping.rabbitmq_routing_key
        assert yaml_cfg["delivery_mode"] == mapping.delivery_mode.value

    def test_router_lookup_reliable(self) -> None:
        """实际查询路径返回 RELIABLE."""
        router = ChannelRouter.from_default_config()
        assert router.get_delivery_mode("ToolSchemaValidationFailed") == DeliveryMode.RELIABLE
