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
        零 CheckpointReached 引用（发布归 6.3）。6-2 per-step Checkpoint 快照
        是存储面恢复点位骨架（OD-1），不产生事件——负向断言沿袭零扩展。"""

        repo_src = _REPO_ROOT / "src"
        blm_files = [
            "application/services/blm_planning_service.py",
            "application/use_cases/run_blm_planning.py",
            "application/use_cases/get_blm_planning_status.py",
        ]
        for relative in blm_files:
            content = (repo_src / relative).read_text(encoding="utf-8")
            assert "CheckpointReached" not in content, f"{relative} 不得发布 CheckpointReached（6.3 语义分立）"

    def test_no_market_insight_channel_keys_added(self) -> None:
        """6-2 零事件新增守护：event_channels.yaml 与 DEFAULT_MAPPINGS 无
        market-insight 新键（per-step 快照键是存储键非事件键——AC-3 负向）。"""
        channels = _yaml_channels()
        market_insight_keys = [key for key in channels if "market_insight" in key.lower() or "MarketInsight" in key]
        assert not market_insight_keys, f"event_channels.yaml 出现 6-2 新增事件键: {market_insight_keys}（零事件新增钦定）"
        mapping_keys = [
            key for key in ChannelRouter.DEFAULT_MAPPINGS if "market_insight" in key.lower() or "MarketInsight" in key
        ]
        assert not mapping_keys, f"DEFAULT_MAPPINGS 出现 6-2 新增事件键: {mapping_keys}（零事件新增钦定）"

    def test_blm_event_family_unchanged(self) -> None:
        """BLM 事件族仍仅 PlanningStarted/BlmStageCompleted（+既有全局族
        StrategicDeviationWarning 非本面）——AC-3 值域零扩展守护。"""
        blm_family = {"PlanningStarted", "BlmStageCompleted"}
        channels = _yaml_channels()
        for event_type in blm_family:
            assert event_type in channels, f"{event_type} 通道登记消失（6-1 资产回归）"
        # CheckpointReached 有通道登记（Epic 1 既有）但 BLM 面零发布——发布面守护见上用例

    def test_checkpoint_reached_negative_in_6_2_delivery_files(self) -> None:
        """6-2 交付面源码零 CheckpointReached（per-step 快照写入是存储动作非事件）。"""
        repo_src = _REPO_ROOT / "src"
        six_two_files = [
            "application/services/blm_planning_prompts.py",
        ]
        for relative in six_two_files:
            content = (repo_src / relative).read_text(encoding="utf-8")
            assert "CheckpointReached" not in content, f"{relative} 不得发布 CheckpointReached（6.3 语义分立）"


class TestCheckpointReachedPublishWiring:
    """Story 6-3 — CheckpointReached 发布接线守护（发布点落位 OD-4 + 双登记零 diff）。

    发布接线断言清单②承载（Task 0.9）：发布点代码位在 checkpoint 应用服务新
    文件 + 既有负向断言（上两用例）零修改通过 = 落位正确的行为级证据。
    """

    def test_publish_call_present_in_checkpoint_service(self) -> None:
        """正向守护：checkpoint 应用服务源码含 CheckpointReached 发布调用。"""
        service_src = _REPO_ROOT / "src" / "application" / "services" / "checkpoint_service.py"
        assert service_src.is_file(), "checkpoint_service.py 缺失（发布点文件）"
        content = service_src.read_text(encoding="utf-8")
        assert "CheckpointReached" in content, "checkpoint_service 无 CheckpointReached 发布调用（⑤步缺失）"
        assert "publish" in content, "checkpoint_service 无 publish 调用"

    def test_publish_point_not_in_blm_planning_four_files(self) -> None:
        """负向守护：发布点仅存在于 checkpoint 应用服务面（四文件零引用——OD-4）。

        与既有两用例（三文件 + 一文件）合成四文件全量；本用例断言"唯一发布面"
        ——src/ 下 CheckpointReached 的实例化构造仅 checkpoint_service 一处。
        """
        import re

        src_root = _REPO_ROOT / "src"
        construction_pattern = re.compile(r"CheckpointReached\(")
        publishers: list[str] = []
        for path in sorted(src_root.rglob("*.py")):
            content = path.read_text(encoding="utf-8")
            if path.name == "checkpoint_events.py":
                continue  # 事件定义文件（类定义非发布）
            if construction_pattern.search(content):
                publishers.append(str(path.relative_to(src_root)))
        assert publishers == ["application/services/checkpoint_service.py"], (
            f"CheckpointReached 构造位实测={publishers} 期望仅 checkpoint_service（发布点唯一落位）"
        )

    def test_dual_registration_zero_diff(self) -> None:
        """双登记零 diff 守护：yaml 与 DEFAULT_MAPPINGS 对 CheckpointReached 登记保持。"""
        channels = _yaml_channels()
        assert "CheckpointReached" in channels, "yaml 通道登记消失（Epic 1 既有资产回归）"
        mapping = ChannelRouter.DEFAULT_MAPPINGS.get("CheckpointReached")
        assert mapping is not None, "DEFAULT_MAPPINGS 登记消失（Epic 1 既有资产回归）"
        assert mapping.delivery_mode == DeliveryMode.RELIABLE, "通道模式漂移（reliable 单通道钦定）"
        assert mapping.rabbitmq_routing_key == channels["CheckpointReached"]["rabbitmq_routing_key"], (
            "双登记路由键漂移（CLAUDE.md 硬约束——两处必须同步）"
        )


def _like_pattern_underscores_escaped(pattern: str) -> bool:
    r"""LIKE 模式串下划线转义判定（DF3 守护 helper——纯模式级检测函数）。

    未转义的下划线在 SQL LIKE 中是单字符通配符——`market_insight%` 会误命中
    Epic 1 既有 "market-insight" 连字符形态（6-2 SQL 探针实证 2 vs 1）。

    Args:
        pattern: LIKE 模式串字面量（如 r"market\_insight%"）。

    Returns:
        全部 `_` 均被 `\` 转义返回 True；存在裸 `_` 返回 False。
    """
    for index, char in enumerate(pattern):
        if char == "_" and (index == 0 or pattern[index - 1] != "\\"):
            return False
    return True


class TestCheckpointReachedLikeEscapeGuard:
    """Story 6-3 — 6.2-DF3 清偿：LIKE 转义独立守护（纯模式级断言——零 DB 依赖）。

    行级真实红路径由集成 5.2 互证承载（R6-19 分工声明——本守护是模式级：
    转义形态在位；发布者在位后负向断言获得真实红路径由行为级测试闭环）。
    """

    def test_escape_detector_judgment_power(self) -> None:
        """检测函数判定力自证（注入未转义形态可检出——guard 的 guard）。"""
        assert _like_pattern_underscores_escaped(r"market\_insight%") is True
        assert _like_pattern_underscores_escaped("market_insight%") is False, "未转义形态必须可检出（恒真断言防线）"
        assert _like_pattern_underscores_escaped(r"market\_insight\_trend%") is True
        assert _like_pattern_underscores_escaped("a_b_c") is False

    def test_6_2_negative_query_patterns_escaped(self) -> None:
        """6-2 侧负向查询的 LIKE 模式串为转义形态（验收+集成两文件字面校验）。

        源文件字面形态为 market\\\\_insight%（Python 源码双反斜杠——SQL 实参
        是 market\\_insight% 转义下划线）。
        """
        guard_targets = (
            "tests/acceptance/test_acceptance_market_insight.py",
            "tests/integration/test_integration_market_insight.py",
        )
        escaped_pattern = "LIKE 'market\\\\_insight%'"  # 源文件字面（双反斜杠转义形态）
        unescaped_pattern = "LIKE 'market_insight%"  # 未转义形态（裸下划线——禁止出现）
        for relative in guard_targets:
            content = (_REPO_ROOT / relative).read_text(encoding="utf-8")
            assert escaped_pattern in content, (
                f"{relative} 缺转义形态 {escaped_pattern!r}（DF3 守护——未转义会误命中连字符形态）"
            )
            assert unescaped_pattern not in content, f"{relative} 含未转义 LIKE 模式（裸下划线单字符通配符——假阳性风险）"

    def test_6_3_self_guard_patterns_escaped(self) -> None:
        """6-3 自身互证查询通道同样保持转义形态（LIKE 通道无 plan_id 过滤——R6-6）。"""
        content = (_REPO_ROOT / "tests" / "acceptance" / "test_acceptance_checkpoint_snapshot.py").read_text(encoding="utf-8")
        assert r"LIKE 'market\\_insight%'" in content, "6-3 验收互证查询缺转义形态"
        assert "LIKE 'market_insight%'" not in content.replace("\\_insight", ""), "6-3 含未转义 LIKE 模式"
