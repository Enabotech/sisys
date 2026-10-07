"""Story 4-6: 工具版本管理事件通道映射契约测试（debate 先例形态）

验证 configs/event_channels.yaml 与 ChannelRouter.DEFAULT_MAPPINGS 两处
3 个 tool_version 事件的条目逐字段一致（新增事件双处同步的门禁，防配置漂移）。

通道选择：realtime（管理类事件，无可靠投递诉求——ToolSchemaValidationFailed 先例）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

EVENT_TYPES = ("ToolVersionRegistered", "ToolVersionPublished", "ToolRolledBack")


def _yaml_channels() -> dict[str, Any]:
    """读取 event_channels.yaml 的 event_channels 段。"""
    config_path = Path("configs/event_channels.yaml")
    with config_path.open(encoding="utf-8") as fh:
        config: dict[str, Any] = yaml.safe_load(fh)
    return cast(dict[str, Any], config["event_channels"])


class TestToolVersionEventChannelMapping:
    """3 事件双登记一致性（realtime 通道）。"""

    def test_all_registered_in_default_mappings(self) -> None:
        """DEFAULT_MAPPINGS 已注册 3 事件。"""
        for event_type in EVENT_TYPES:
            assert ChannelRouter.DEFAULT_MAPPINGS.get(event_type) is not None, f"DEFAULT_MAPPINGS 未注册 {event_type}"

    def test_all_registered_in_yaml(self) -> None:
        """event_channels.yaml 已配置 3 事件。"""
        yaml_channels = _yaml_channels()
        for event_type in EVENT_TYPES:
            assert yaml_channels.get(event_type) is not None, f"event_channels.yaml 未配置 {event_type}"

    def test_redis_channel_consistent(self) -> None:
        """redis_channel 两处一致且符合 sisys:rt:<snake_case> 命名。"""
        yaml_channels = _yaml_channels()
        for event_type, snake in (
            ("ToolVersionRegistered", "tool_version_registered"),
            ("ToolVersionPublished", "tool_version_published"),
            ("ToolRolledBack", "tool_rolled_back"),
        ):
            expected = f"sisys:rt:{snake}"
            yaml_cfg = yaml_channels[event_type]
            mapping = ChannelRouter.DEFAULT_MAPPINGS[event_type]
            assert yaml_cfg["redis_channel"] == mapping.redis_channel == expected

    def test_delivery_mode_realtime_in_both(self) -> None:
        """delivery_mode 两处一致且为 realtime（管理类事件）。"""
        yaml_channels = _yaml_channels()
        for event_type in EVENT_TYPES:
            assert yaml_channels[event_type]["delivery_mode"] == "realtime"
            assert ChannelRouter.DEFAULT_MAPPINGS[event_type].delivery_mode is DeliveryMode.REALTIME

    def test_description_non_empty(self) -> None:
        """两处 description 非空（运维可读性）。"""
        yaml_channels = _yaml_channels()
        for event_type in EVENT_TYPES:
            assert yaml_channels[event_type]["description"]
            assert ChannelRouter.DEFAULT_MAPPINGS[event_type].description

    def test_router_delivery_mode_lookup(self) -> None:
        """路由器查询返回 REALTIME。"""
        router = ChannelRouter.from_default_config()
        for event_type in EVENT_TYPES:
            assert router.get_delivery_mode(event_type) is DeliveryMode.REALTIME
