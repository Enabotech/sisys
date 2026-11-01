"""Story 6-1 — BLM 规划事件双登记守护测试（ PlanningStarted/BlmStageCompleted）。

Task 4 循环 A 载体：event_channels.yaml + ChannelRouter.DEFAULT_MAPPINGS
双登记逐字段一致门禁（CLAUDE.md 硬约束——新事件必须双处登记）；两事件
均钦定 reliable 单通道（DC-8）；CheckpointReached 零发布负向断言。

形态对齐 test_event_channel_mapping_drift.py（七断言）。

Run with:
    poetry run pytest tests/contracts/test_event_channel_mapping_blm_planning.py -v
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EVENTS = ("PlanningStarted", "BlmStageCompleted")
_ROUTING_KEYS = {
    "PlanningStarted": "sisys.events.reliable.planning_started",
    "BlmStageCompleted": "sisys.events.reliable.blm_stage_completed",
}


def _yaml_channels() -> dict:
    """读取 event_channels.yaml 的 event_channels 段（isinstance 收窄——结构异常即断言红）。"""
    config = _REPO_ROOT / "configs" / "event_channels.yaml"
    channels = yaml.safe_load(config.read_text(encoding="utf-8"))["event_channels"]
    assert isinstance(channels, dict), "event_channels.yaml 结构异常（event_channels 段非 mapping）"
    return channels


class TestBlmPlanningEventChannelMapping:
    """双登记守护（存在性×2/键一致/mode 一致/单通道/description 非空）。"""

    def test_registered_in_default_mappings(self) -> None:
        """yaml 缺失时编译期 baseline 兜底——DEFAULT_MAPPINGS 两事件在位。"""
        for event_type in _EVENTS:
            assert ChannelRouter.DEFAULT_MAPPINGS.get(event_type) is not None, f"{event_type} 未登记 DEFAULT_MAPPINGS"

    def test_registered_in_yaml(self) -> None:
        """event_channels.yaml 两事件在位。"""
        channels = _yaml_channels()
        for event_type in _EVENTS:
            assert channels.get(event_type) is not None, f"{event_type} 未登记 event_channels.yaml"

    def test_rabbitmq_routing_key_consistent(self) -> None:
        """routing key 三重等值（yaml == mapping == 钦定键）。"""
        channels = _yaml_channels()
        for event_type, expected_key in _ROUTING_KEYS.items():
            yaml_key = channels[event_type].get("rabbitmq_routing_key")
            mapping_key = ChannelRouter.DEFAULT_MAPPINGS[event_type].rabbitmq_routing_key
            assert yaml_key == mapping_key == expected_key, (
                f"{event_type} routing key 不一致: yaml={yaml_key} mapping={mapping_key}"
            )

    def test_delivery_mode_reliable_in_both(self) -> None:
        """两事件均钦定 reliable 单通道（DC-8——对齐 AgentDecided 先例）。"""
        channels = _yaml_channels()
        for event_type in _EVENTS:
            assert channels[event_type].get("delivery_mode") == "reliable", f"{event_type} yaml delivery_mode 应为 reliable"
            assert ChannelRouter.DEFAULT_MAPPINGS[event_type].delivery_mode is DeliveryMode.RELIABLE

    def test_no_redis_channel_single_reliable(self) -> None:
        """reliable 单通道不配 redis_channel（一事件不走双通道）。"""
        channels = _yaml_channels()
        for event_type in _EVENTS:
            assert "redis_channel" not in channels[event_type], f"{event_type} 不应配 redis_channel"
            assert ChannelRouter.DEFAULT_MAPPINGS[event_type].redis_channel is None

    def test_description_non_empty(self) -> None:
        """description 双处非空（登记完整性）。"""
        channels = _yaml_channels()
        for event_type in _EVENTS:
            assert channels[event_type].get("description"), f"{event_type} yaml description 空"
            assert ChannelRouter.DEFAULT_MAPPINGS[event_type].description, f"{event_type} mapping description 空"

    def test_router_delivery_mode_lookup(self) -> None:
        """运行时路由查表（from_default_config 装配链）。"""
        router = ChannelRouter.from_default_config()
        for event_type in _EVENTS:
            assert router.get_delivery_mode(event_type) is DeliveryMode.RELIABLE

    def test_checkpoint_reached_not_published_by_blm(self) -> None:
        """CheckpointReached 零发布负向断言（6.3 语义分立——5-10 OD-6/DC-8 先例）。

        CheckpointReached 事件类与通道登记是 Epic 1 既有资产（1-2 领域事件
        定义）——断言语义是「本 Story 交付面零发布点」：BLM 服务与用例源码
        零 CheckpointReached 引用（发布归 6.3）。"""

        repo_src = _REPO_ROOT / "src"
        blm_files = [
            "application/services/blm_planning_service.py",
            "application/use_cases/run_blm_planning.py",
            "application/use_cases/get_blm_planning_status.py",
        ]
        for relative in blm_files:
            content = (repo_src / relative).read_text(encoding="utf-8")
            assert "CheckpointReached" not in content, f"{relative} 不得发布 CheckpointReached（6.3 语义分立）"
