"""Story 6-6 — Checkpoint 恢复事件通道守护契约测试。

承载（Task 4.2）：CheckpointRecovered 发布接线正向（唯一构造位+发布调用）/
双登记零 diff（yaml ↔ router 等值）/ 冻结键数 56 零变化 / CorrectionApproved
保持零生产方守护（缺席断言——OD-2 裁定不激活）。

形态对齐 test_event_channel_mapping_blm_planning.py TestCheckpointReached
PublishWiring（6-3 先例）：源码含发布+唯一构造位 grep（构造位形态天然避开
auto_trigger/yaml/router 三处合法登记的裸 token 撞击——6-4 CR1-R3 缺席断言
先例）+ 排除事件定义文件（类定义行假阳性——6-3 契约 :161-170 排除形态复刻）。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC_ROOT = _REPO_ROOT / "src"


def _yaml_channels() -> dict[str, dict[str, str]]:
    """读取 event_channels.yaml 事件登记（event_channels 键 → 配置 dict）。"""
    channels_path = _REPO_ROOT / "configs" / "event_channels.yaml"
    with channels_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    channels = data["event_channels"]
    assert isinstance(channels, dict)
    return channels


class TestCheckpointRecoveredPublishWiring:
    """CheckpointRecovered 发布接线（Story 6-6 恢复引擎⑤步——首激活）。"""

    def test_publish_call_present_in_checkpoint_service(self) -> None:
        """发布调用在 checkpoint 应用服务（恢复引擎⑤步——发布点代码位）。"""
        service_src = _SRC_ROOT / "application" / "services" / "checkpoint_service.py"
        assert service_src.is_file(), "checkpoint 应用服务文件缺失"
        content = service_src.read_text(encoding="utf-8")
        assert "CheckpointRecovered" in content, "checkpoint_service 无 CheckpointRecovered 发布接线"
        assert "publish" in content, "checkpoint_service 无发布调用"

    def test_construction_point_unique_in_src(self) -> None:
        """唯一构造位 = checkpoint_service 恢复引擎（排除事件定义文件——类定义行假阳性）。"""
        construction_pattern = re.compile(r"CheckpointRecovered\(")
        publishers: list[str] = []
        for path in sorted(_SRC_ROOT.rglob("*.py")):
            content = path.read_text(encoding="utf-8")
            if path.name == "checkpoint_events.py":
                continue  # 事件定义文件（类定义非发布——6-3 契约先例排除形态）
            if construction_pattern.search(content):
                publishers.append(str(path.relative_to(_SRC_ROOT)))
        assert publishers == ["application/services/checkpoint_service.py"], (
            f"CheckpointRecovered 构造位实测={publishers} 期望仅 checkpoint_service（发布点唯一落位）"
        )

    def test_dual_registration_zero_diff(self) -> None:
        """双登记等值（yaml ↔ DEFAULT_MAPPINGS——reliable 单通道）。"""
        channels = _yaml_channels()
        assert "CheckpointRecovered" in channels, "yaml 缺 CheckpointRecovered 登记"
        mapping = ChannelRouter.DEFAULT_MAPPINGS.get("CheckpointRecovered")
        assert mapping is not None, "DEFAULT_MAPPINGS 缺 CheckpointRecovered 登记"
        assert mapping.delivery_mode == DeliveryMode.RELIABLE
        assert mapping.rabbitmq_routing_key == channels["CheckpointRecovered"]["rabbitmq_routing_key"], (
            "双登记路由键不等值（yaml ↔ router 零 diff 破坏）"
        )

    def test_frozen_event_count_unchanged(self) -> None:
        """冻结键数 56 零变化（零新增事件=登记数不变——OD-2）。"""
        channels = _yaml_channels()
        assert len(channels) == 56, f"事件登记键数实测={len(channels)} 期望=56（_FROZEN_EVENT_COUNT——零新增事件纪律）"

    def test_auto_trigger_listener_registered(self) -> None:
        """auto_trigger 监听在位（监听已注册只欠发布——发布点本 Story 落地）。"""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        handler = AutoTriggerHandler.__new__(AutoTriggerHandler)  # 零依赖构造（仅查类内清单）
        registered = getattr(handler, "_registered_event_types", None)
        if registered is None:
            # 实例属性在 __init__ 设置——经 __new__ 不可达时退回源码断言
            source = (_SRC_ROOT / "application" / "event_handlers" / "auto_trigger_handler.py").read_text(encoding="utf-8")
            assert '"CheckpointRecovered"' in source, "auto_trigger 监听清单缺 CheckpointRecovered"
            return
        assert "CheckpointRecovered" in registered


class TestCorrectionApprovedZeroProducerGuard:
    """CorrectionApproved 保持零生产方（OD-2 裁定不激活——缺席断言守护）。"""

    def test_construction_point_absent_in_src(self) -> None:
        """全仓零构造位（排除事件定义文件；裸 token 会撞 auto_trigger/yaml/router
        三处合法登记——构造位形态 grep 天然避开，6-4 CR1-R3 缺席断言先例）。"""
        construction_pattern = re.compile(r"CorrectionApproved\(")
        constructors: list[str] = []
        for path in sorted(_SRC_ROOT.rglob("*.py")):
            content = path.read_text(encoding="utf-8")
            if path.name == "correction_events.py":
                continue  # 事件定义文件（类定义非发布）
            if construction_pattern.search(content):
                constructors.append(str(path.relative_to(_SRC_ROOT)))
        assert constructors == [], (
            f"CorrectionApproved 出现生产构造位={constructors}（OD-2 裁定不激活——"
            "apply_correction 是 6-3 冻结行为面，加发布会动 call_order 断言族）"
        )

    def test_dual_registration_in_place_dormant(self) -> None:
        """双登记在位休眠（yaml ↔ router 等值——登记面零 diff，仅零生产方）。"""
        channels = _yaml_channels()
        assert "CorrectionApproved" in channels, "yaml 缺 CorrectionApproved 登记（既有资产）"
        mapping = ChannelRouter.DEFAULT_MAPPINGS.get("CorrectionApproved")
        assert mapping is not None
        assert mapping.rabbitmq_routing_key == channels["CorrectionApproved"]["rabbitmq_routing_key"]


class TestCheckpointReachedExistingAssertionsUntouched:
    """6-3 CheckpointReached 既有断言面零修改复跑（Task 4.2 回归承载）。"""

    def test_publish_point_still_in_checkpoint_service_only(self) -> None:
        """6-3 唯一构造位断言复跑（6-6 新增 CheckpointRecovered 构造不误伤——
        字面类名 grep 天然互异）。"""
        construction_pattern = re.compile(r"CheckpointReached\(")
        publishers: list[str] = []
        for path in sorted(_SRC_ROOT.rglob("*.py")):
            content = path.read_text(encoding="utf-8")
            if path.name == "checkpoint_events.py":
                continue
            if construction_pattern.search(content):
                publishers.append(str(path.relative_to(_SRC_ROOT)))
        assert publishers == ["application/services/checkpoint_service.py"], (
            f"CheckpointReached 构造位实测={publishers}（6-3 发布点唯一性——6-6 零干扰）"
        )
