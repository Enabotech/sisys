"""DriftDetected 事件通道映射契约测试——Story 5.9 双登记一致门禁。

reliable 版先例形态（test_event_channel_mapping_tool_version.py 的 reliable 单通道
变体）：configs/event_channels.yaml 与 ChannelRouter.DEFAULT_MAPPINGS 双处存在 +
rabbitmq_routing_key 逐字段一致 + delivery_mode reliable + description 非空 +
router 派发查询可达。

Run with:
    poetry run pytest tests/contracts/test_event_channel_mapping_drift.py -v
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

EVENT_TYPE = "DriftDetected"
EXPECTED_ROUTING_KEY = "sisys.events.reliable.drift_detected"

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _yaml_channels() -> dict[str, dict[str, str]]:
    """读取 event_channels.yaml 的 event_channels 段。"""
    config: dict[str, dict[str, dict[str, str]]] = yaml.safe_load(
        (_REPO_ROOT / "configs" / "event_channels.yaml").read_text(encoding="utf-8")
    )
    return config["event_channels"]


class TestDriftDetectedChannelMapping:
    """双登记逐字段一致门禁（CLAUDE.md 硬约束：新事件必须双处登记）。"""

    def test_registered_in_default_mappings(self) -> None:
        """DEFAULT_MAPPINGS 存在条目（编译时 baseline——yaml 缺失时兜底）。"""
        assert ChannelRouter.DEFAULT_MAPPINGS.get(EVENT_TYPE) is not None, "DEFAULT_MAPPINGS 应含 DriftDetected"

    def test_registered_in_yaml(self) -> None:
        """yaml 存在条目（运行时主配置）。"""
        assert _yaml_channels().get(EVENT_TYPE) is not None, "event_channels.yaml 应含 DriftDetected"

    def test_rabbitmq_routing_key_consistent(self) -> None:
        """rabbitmq_routing_key 三重等值（yaml == mapping == 期望值——命名惯例锚）。"""
        yaml_entry = _yaml_channels()[EVENT_TYPE]
        mapping = ChannelRouter.DEFAULT_MAPPINGS[EVENT_TYPE]
        assert yaml_entry["rabbitmq_routing_key"] == EXPECTED_ROUTING_KEY
        assert mapping.rabbitmq_routing_key == EXPECTED_ROUTING_KEY

    def test_delivery_mode_reliable_in_both(self) -> None:
        """delivery_mode 双处 reliable（告警不可丢——RabbitMQ + Outbox 投递）。"""
        yaml_entry = _yaml_channels()[EVENT_TYPE]
        mapping = ChannelRouter.DEFAULT_MAPPINGS[EVENT_TYPE]
        assert yaml_entry["delivery_mode"] == "reliable"
        assert mapping.delivery_mode is DeliveryMode.RELIABLE

    def test_no_redis_channel_single_reliable(self) -> None:
        """reliable 单通道（无 redis_channel 键——realtime 对告警消费方无订阅面）。"""
        yaml_entry = _yaml_channels()[EVENT_TYPE]
        mapping = ChannelRouter.DEFAULT_MAPPINGS[EVENT_TYPE]
        assert "redis_channel" not in yaml_entry, "reliable 单通道不应配 redis_channel"
        assert mapping.redis_channel is None

    def test_description_non_empty(self) -> None:
        """description 双处非空（运维可读性）。"""
        yaml_entry = _yaml_channels()[EVENT_TYPE]
        mapping = ChannelRouter.DEFAULT_MAPPINGS[EVENT_TYPE]
        assert yaml_entry.get("description"), "yaml description 应非空"
        assert mapping.description, "DEFAULT_MAPPINGS description 应非空"

    def test_router_delivery_mode_lookup(self) -> None:
        """ChannelRouter 实例派发查询（事件可达性前提——无映射发布失败实证）。"""
        router = ChannelRouter.from_default_config()
        assert router.get_delivery_mode(EVENT_TYPE) is DeliveryMode.RELIABLE
