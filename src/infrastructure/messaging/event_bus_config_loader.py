"""EventBusConfigLoader — YAML configuration loader for event channels."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.infrastructure.messaging.channel_router import ChannelMapping, ChannelRouter, DeliveryMode

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "event_channels.yaml"


class EventBusConfigLoader:
    """事件通道配置加载器。

    从 YAML 文件加载通道配置，通过 ChannelRouter.register() 注册。
    """

    @classmethod
    def from_default_path(cls) -> EventBusConfigLoader:
        """从默认路径创建配置加载器。

        Returns:
            EventBusConfigLoader: 配置加载器实例
        """
        return cls()

    def load(self, router: ChannelRouter, config_path: str | Path) -> None:
        """从 YAML 文件加载通道配置并注册到路由器。

        Args:
            router: 通道路由器
            config_path: 配置文件路径
        """
        path = Path(config_path)
        if not path.exists():
            return

        with open(path) as f:
            config: dict[str, Any] = yaml.safe_load(f) or {}

        event_channels = config.get("event_channels", {})
        for event_type, channel_config in event_channels.items():
            redis_channel = channel_config.get("redis_channel")
            rabbitmq_routing_key = channel_config.get("rabbitmq_routing_key")
            delivery_mode_str = channel_config.get("delivery_mode", "reliable")
            description = channel_config.get("description", "")

            delivery_mode = DeliveryMode.REALTIME if delivery_mode_str == "realtime" else DeliveryMode.RELIABLE

            mapping = ChannelMapping(
                event_type=event_type,
                redis_channel=redis_channel,
                rabbitmq_routing_key=rabbitmq_routing_key,
                delivery_mode=delivery_mode,
                description=description,
            )
            router.register(mapping)
