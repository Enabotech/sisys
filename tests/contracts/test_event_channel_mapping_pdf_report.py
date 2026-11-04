"""ReportGenerated 事件通道契约测试（Story 6-5b——零新增守护平移）。

断言形态（6-5a test_event_channel_mapping_report 形态平移——第二次生产
复用零新增零 diff 守护）：
①ReportGenerated 既有登记存在性（yaml 与 DEFAULT_MAPPINGS 双侧——
  report_type="pdf" 经自由 str 字段流经零类改动）
②事件登记键集合与冻结基线全等（键数 56 不变——本 Story 意外新增事件名
  即破断言）

Run with:
    poetry run pytest tests/contracts/test_event_channel_mapping_pdf_report.py -v
"""

from pathlib import Path

import yaml

from src.infrastructure.messaging.channel_router import ChannelMapping, ChannelRouter, DeliveryMode

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXPECTED_ROUTING_KEY = "sisys.events.reliable.report_generated"

#: 事件登记键数冻结基线（Epic 1~6 累计——6-5b 零新增；增减即事件面契约变更）
_FROZEN_EVENT_COUNT: int = 56


def _yaml_channels() -> dict:
    """读取 event_channels.yaml 的 event_channels 配置节。

    Returns:
        事件名 → 通道配置映射。
    """
    config = _REPO_ROOT / "configs" / "event_channels.yaml"
    channels = yaml.safe_load(config.read_text(encoding="utf-8"))["event_channels"]
    assert isinstance(channels, dict)
    return channels


class TestReportGeneratedRegistration:
    """①ReportGenerated 既有登记存在性（6-5b 第二次生产零 diff）。"""

    def test_yaml_registration_present(self) -> None:
        """yaml 侧登记在位（routing key + reliable 单通道）。"""
        channels = _yaml_channels()
        assert "ReportGenerated" in channels
        entry = channels["ReportGenerated"]
        assert entry["rabbitmq_routing_key"] == _EXPECTED_ROUTING_KEY
        assert entry["delivery_mode"] == "reliable"

    def test_default_mappings_registration_present(self) -> None:
        """DEFAULT_MAPPINGS 侧登记在位（与 yaml 逐字段等值）。"""
        mapping = ChannelRouter.DEFAULT_MAPPINGS.get("ReportGenerated")
        assert mapping is not None
        assert isinstance(mapping, ChannelMapping)
        assert mapping.rabbitmq_routing_key == _EXPECTED_ROUTING_KEY
        assert mapping.delivery_mode is DeliveryMode.RELIABLE

    def test_single_reliable_channel_no_redis(self) -> None:
        """reliable 单通道（双侧均无 redis_channel 键）。"""
        channels = _yaml_channels()
        assert "redis_channel" not in channels["ReportGenerated"]
        mapping = ChannelRouter.DEFAULT_MAPPINGS["ReportGenerated"]
        assert mapping.redis_channel is None

    def test_runtime_delivery_mode_lookup(self) -> None:
        """运行时查表 reliable（ChannelRouter.from_default_config 消费面）。"""
        delivery_mode = ChannelRouter.from_default_config().get_delivery_mode("ReportGenerated")
        assert delivery_mode is DeliveryMode.RELIABLE


class TestEventKeySetFrozenBaseline:
    """②事件登记键集合冻结全等（零新增守护——集合全等形态非 token 缺席）。"""

    def test_yaml_key_count_frozen(self) -> None:
        """yaml 事件键数与冻结基线全等（56——本 Story 零新增）。"""
        channels = _yaml_channels()
        assert len(channels) == _FROZEN_EVENT_COUNT, (
            f"事件登记键数漂移: 期望 {_FROZEN_EVENT_COUNT} 实测 {len(channels)}"
            "（本 Story 钦定零新增——新增事件需更新双登记与本基线）"
        )

    def test_yaml_and_default_mappings_key_sets_identical(self) -> None:
        """yaml 键集 == DEFAULT_MAPPINGS 键集（双侧互等——单侧漂移即破）。"""
        channels = _yaml_channels()
        mapping_keys = set(ChannelRouter.DEFAULT_MAPPINGS.keys())
        assert set(channels.keys()) == mapping_keys
