"""ReportGenerated 事件通道契约测试（Story 6-5a——零新增守护）。

断言形态（R1 裁定——登记集合冻结快照相等，非 token 缺席断言）：
①ReportGenerated 既有登记存在性（yaml 与 DEFAULT_MAPPINGS 双侧——routing
  key `sisys.events.reliable.report_generated` + reliable 单通道 + 无
  redis_channel）
②事件登记键集合与冻结基线全等（yaml 键集 == DEFAULT_MAPPINGS 键集互等 +
  键数冻结 56——本 Story 意外新增事件名即破断言；ReportGenerated 是 Epic 1
  既有登记 token，零命中缺席断言必误伤既有登记，故用集合全等形态）

Run with:
    poetry run pytest tests/contracts/test_event_channel_mapping_report.py -v
"""

from pathlib import Path

import yaml

from src.infrastructure.messaging.channel_router import ChannelMapping, ChannelRouter, DeliveryMode

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXPECTED_ROUTING_KEY = "sisys.events.reliable.report_generated"

#: 事件登记键数冻结基线（Epic 1~6 累计——本 Story 零新增；增减即事件面契约变更）
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
    """①ReportGenerated 既有登记存在性（Epic 1 预留——6-5a 首激活零 diff）。"""

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
