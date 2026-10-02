"""Story 4.5: DebateCompleted 双通道映射契约测试

验证 configs/event_channels.yaml 与 ChannelRouter.DEFAULT_MAPPINGS 两处
DebateCompleted 条目逐字段一致（新增事件双处同步的门禁，防配置漂移）。

对齐 ToolExecuted 双通道模式（reliable：realtime Redis pub/sub + reliable RabbitMQ）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

EVENT_TYPE = "DebateCompleted"
EXPECTED_REDIS_CHANNEL = "sisys:rt:debate_completed"
EXPECTED_RABBITMQ_ROUTING_KEY = "sisys.events.reliable.debate_completed"


def _yaml_channels() -> dict[str, Any]:
    """读取 event_channels.yaml 的 event_channels 段。"""
    config_path = Path("configs/event_channels.yaml")
    with config_path.open(encoding="utf-8") as fh:
        config: dict[str, Any] = yaml.safe_load(fh)
    return cast(dict[str, Any], config["event_channels"])


class TestDebateCompletedChannelMapping:
    """DebateCompleted 双通道映射一致性。"""

    def test_registered_in_default_mappings(self) -> None:
        """DEFAULT_MAPPINGS 已注册 DebateCompleted。"""
        mapping = ChannelRouter.DEFAULT_MAPPINGS.get(EVENT_TYPE)
        assert mapping is not None, "DEFAULT_MAPPINGS 未注册 DebateCompleted"

    def test_registered_in_yaml(self) -> None:
        """event_channels.yaml 已配置 DebateCompleted。"""
        yaml_cfg = _yaml_channels().get(EVENT_TYPE)
        assert yaml_cfg is not None, "event_channels.yaml 未配置 DebateCompleted"

    def test_redis_channel_consistent(self) -> None:
        """redis_channel 两处一致且为期望值。"""
        yaml_cfg = _yaml_channels()[EVENT_TYPE]
        mapping = ChannelRouter.DEFAULT_MAPPINGS[EVENT_TYPE]
        assert yaml_cfg["redis_channel"] == mapping.redis_channel == EXPECTED_REDIS_CHANNEL

    def test_rabbitmq_routing_key_consistent(self) -> None:
        """rabbitmq_routing_key 两处一致且为期望值。"""
        yaml_cfg = _yaml_channels()[EVENT_TYPE]
        mapping = ChannelRouter.DEFAULT_MAPPINGS[EVENT_TYPE]
        assert yaml_cfg["rabbitmq_routing_key"] == mapping.rabbitmq_routing_key == EXPECTED_RABBITMQ_ROUTING_KEY

    def test_delivery_mode_reliable_in_both(self) -> None:
        """delivery_mode 两处一致且为 reliable（RELIABLE）。"""
        yaml_cfg = _yaml_channels()[EVENT_TYPE]
        mapping = ChannelRouter.DEFAULT_MAPPINGS[EVENT_TYPE]
        assert yaml_cfg["delivery_mode"] == "reliable"
        assert mapping.delivery_mode is DeliveryMode.RELIABLE

    def test_description_non_empty(self) -> None:
        """两处 description 非空（运维可读性）。"""
        yaml_cfg = _yaml_channels()[EVENT_TYPE]
        mapping = ChannelRouter.DEFAULT_MAPPINGS[EVENT_TYPE]
        assert yaml_cfg["description"]
        assert mapping.description

    def test_router_delivery_mode_lookup(self) -> None:
        """服务发布事件后 get_delivery_mode 返回 RELIABLE。"""
        router = ChannelRouter.from_default_config()
        assert router.get_delivery_mode(EVENT_TYPE) is DeliveryMode.RELIABLE
