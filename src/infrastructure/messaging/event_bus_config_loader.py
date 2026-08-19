"""基础设施层事件总线配置加载模块

从 config/event_channels.yaml 加载事件通道映射，覆盖 ChannelRouter.DEFAULT_MAPPINGS

优先级：YAML 配置 > DEFAULT_MAPPINGS（baseline fallback）
新增事件必须同时更新两处以保持同步
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.infrastructure.messaging.channel_router import ChannelMapping, ChannelRouter, DeliveryMode

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "event_channels.yaml"


class EventBusConfigLoader:
    """事件通道配置加载器

    从 YAML 文件加载通道配置，覆盖 DEFAULT_MAPPINGS 基线
    YAML 配置优先，支持多环境差异化和运维独立调整
    """

    @classmethod
    def create(cls) -> EventBusConfigLoader:
        """创建配置加载器实例

        Returns:
            EventBusConfigLoader: 配置加载器实例
        """
        return cls()

    def load(self, router: ChannelRouter, config_path: str | Path) -> None:
        """从 YAML 文件加载通道配置并注册到路由器

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
