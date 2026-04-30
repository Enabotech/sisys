"""Tests for EventBusConfigLoader — YAML configuration loader."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.infrastructure.messaging.event_bus_config_loader import EventBusConfigLoader


class TestEventBusConfigLoaderLoad:
    """Test EventBusConfigLoader.load method."""

    def test_load_accepts_router_and_config_path(self) -> None:
        """load should accept router and config path."""
        from src.infrastructure.messaging.channel_router import ChannelRouter

        router = ChannelRouter(load_defaults=False)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("event_channels: {}")
            config_path = f.name

        try:
            loader = EventBusConfigLoader()
            loader.load(router, config_path)
        finally:
            Path(config_path).unlink()

    def test_load_registers_channels_from_yaml(self) -> None:
        """load should register channels from YAML using router.register()."""
        from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

        router = ChannelRouter(load_defaults=False)
        config_content = """
event_channels:
  TestEvent:
    redis_channel: "test:channel"
    delivery_mode: "realtime"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            loader = EventBusConfigLoader()
            loader.load(router, config_path)
            assert router.get_redis_channel("TestEvent") == "test:channel"
            assert router.get_delivery_mode("TestEvent") == DeliveryMode.REALTIME
        finally:
            Path(config_path).unlink()


class TestEventBusConfigLoaderFromDefaultPath:
    """Test EventBusConfigLoader.from_default_path method."""

    def test_from_default_path_returns_loader_instance(self) -> None:
        """from_default_path should return EventBusConfigLoader instance."""
        loader = EventBusConfigLoader.from_default_path()
        assert isinstance(loader, EventBusConfigLoader)
