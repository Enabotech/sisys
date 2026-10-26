"""Story 5.6: IsolationSwitchLog 实体单元测试

覆盖 AC-1（from_event 六字段映射 / 实体不变量 / to_dict / frozen）:
- from_event 工厂: 六字段零加工映射（approval_chain list→tuple 冻结拷贝）/
  switch_timestamp 取事件 switch_timestamp（单钟纪律——非 event.timestamp）/
  log_id 自铸 UUID4 / worm_ref 默认 None（OD-1 预留）
- __post_init__ 不变量五场景（242——context 形态 {字段名: 实际值/类型}，对齐
  isolation_state 先例）: agent_id/log_id 非 UUID 实例拒；previous_level/target_level
  非 IsolationLevel 枚举实例拒（双条件 isinstance 先行——str,Enum 混入语义
  hash 穿透教训 5-4 R3-F01）；previous_level == target_level 拒（切换语义不变量
  ——no-op 不得产生日志）；trigger_reason 非 str 或空白拒；approval_chain 非 tuple 拒
  + 元素非 str 或空白串拒
  注: log_id/approval_chain 两场景的非法值经 dataclass 直构造注入（from_event
  自铸合法值无法产出非法输入——测试专用通道，生产构造通道唯一性 DC-1 不受影响）
- to_dict: 全字段可序列化（UUID→str / Enum→value / datetime→ISO 8601 / tuple→list）
- frozen: 赋值拒绝（dataclasses.FrozenInstanceError——追加型日志事实不可变）

Run with:
    poetry run pytest tests/unit/domain/entities/test_isolation_switch_log.py -v
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from src.domain.entities.isolation_switch_log import IsolationSwitchLog
from src.domain.events.enums import IsolationLevel
from src.domain.events.isolation_events import IsolationLevelSwitched
from src.domain.exceptions import EntityValidationError


def _make_event(
    previous: IsolationLevel = IsolationLevel.L4_HARD,
    target: IsolationLevel = IsolationLevel.L3_SOFT,
    reason: str = "单测事件构造",
    chain: list[str] | None = None,
    switch_ts: datetime | None = None,
) -> IsolationLevelSwitched:
    """合法六字段事件构造辅助（from_event 映射唯一源）."""
    return IsolationLevelSwitched(
        agent_id=uuid.uuid4(),
        previous_level=previous,
        target_level=target,
        trigger_reason=reason,
        approval_chain=chain if chain is not None else ["合规负责人", "安全官"],
        switch_timestamp=switch_ts if switch_ts is not None else datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC),
    )


def _valid_kwargs() -> dict[str, Any]:
    """合法八字段直构造辅助（__post_init__ 非法注入的基线）。"""
    return {
        "log_id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "previous_level": IsolationLevel.L4_HARD,
        "target_level": IsolationLevel.L3_SOFT,
        "trigger_reason": "合法输入",
        "approval_chain": ("审批人",),
        "switch_timestamp": datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC),
    }


class TestFromEventFactory:
    """from_event 类方法工厂（事件 payload 单一真源——DC-1）。"""

    def test_six_fields_zero_processing_mapping(self) -> None:
        """六字段逐项零加工映射（FR-AC-06 六要素完整）。"""
        event = _make_event()
        log = IsolationSwitchLog.from_event(event)
        assert log.agent_id == event.agent_id
        assert log.previous_level == event.previous_level
        assert log.target_level == event.target_level
        assert log.trigger_reason == event.trigger_reason
        assert list(log.approval_chain) == list(event.approval_chain)
        assert log.switch_timestamp == event.switch_timestamp

    def test_switch_timestamp_takes_event_switch_timestamp(self) -> None:
        """单钟纪律: 取事件 switch_timestamp 而非 event.timestamp（事件时刻=状态变更时刻）。"""
        fixed = datetime(2026, 10, 25, 9, 30, 0, tzinfo=UTC)
        event = _make_event(switch_ts=fixed)
        log = IsolationSwitchLog.from_event(event)
        assert log.switch_timestamp == fixed
        assert log.switch_timestamp == event.switch_timestamp
        assert log.switch_timestamp != event.timestamp

    def test_approval_chain_list_frozen_to_tuple(self) -> None:
        """审批链 list→tuple 冻结拷贝（不可变审计事实）。"""
        source = ["合规负责人", "安全官"]
        event = _make_event(chain=source)
        log = IsolationSwitchLog.from_event(event)
        assert isinstance(log.approval_chain, tuple)
        assert log.approval_chain == ("合规负责人", "安全官")
        # 冻结拷贝: 源 list 后续变异不影响实体（防御性拷贝）
        source.append("后加审批人")
        assert log.approval_chain == ("合规负责人", "安全官")

    def test_empty_approval_chain_rounds_to_empty_tuple(self) -> None:
        """空审批链 → 空 tuple（MVP 用户请求通道的真实事实记录——空集非缺失）。"""
        event = _make_event(chain=[])
        log = IsolationSwitchLog.from_event(event)
        assert log.approval_chain == ()

    def test_log_id_self_minted_uuid4(self) -> None:
        """log_id 自铸 UUID4（from_event 不收外部 log_id——构造通道唯一性）。"""
        log = IsolationSwitchLog.from_event(_make_event())
        assert isinstance(log.log_id, uuid.UUID)
        assert log.log_id.version == 4

    def test_worm_ref_defaults_none(self) -> None:
        """worm_ref 默认 None（OD-1——WORM 归档归 V1 Story 13-4，字段预留）。"""
        log = IsolationSwitchLog.from_event(_make_event())
        assert log.worm_ref is None

    def test_two_logs_from_same_event_have_distinct_ids(self) -> None:
        """同事件两次映射产独立 log_id（uuid4 随机性——每条日志独立审计事实）。"""
        event = _make_event()
        log1 = IsolationSwitchLog.from_event(event)
        log2 = IsolationSwitchLog.from_event(event)
        assert log1.log_id != log2.log_id


class TestEntityInvariants:
    """__post_init__ 不变量五场景（242 三段式: isinstance → code → context）。"""

    def test_agent_id_non_uuid_rejected(self) -> None:
        """场景①: agent_id 非 UUID 实例 → 242（context 携带 agent_id）。"""
        kwargs = _valid_kwargs()
        kwargs["agent_id"] = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"  # 合法 UUID 字符串非实例
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLog(**kwargs)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "agent_id" in exc_info.value.context

    def test_log_id_non_uuid_rejected(self) -> None:
        """场景①: log_id 非 UUID 实例 → 242（直构造注入——from_event 自铸合法值）。"""
        kwargs = _valid_kwargs()
        kwargs["log_id"] = 12345
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLog(**kwargs)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "log_id" in exc_info.value.context

    def test_previous_level_non_enum_rejected(self) -> None:
        """场景②: previous_level 非 IsolationLevel 枚举实例 → 242（isinstance 先行——
        str,Enum 混入语义下 "L4" 与 L4_HARD 相等但 isinstance 为 False，单值比对拦不住）。"""
        kwargs = _valid_kwargs()
        kwargs["previous_level"] = "L4"  # str,Enum 混入: == 比较为 True 但类型非法
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLog(**kwargs)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "previous_level" in exc_info.value.context

    def test_target_level_non_enum_rejected(self) -> None:
        """场景②: target_level 非枚举实例 → 242。"""
        kwargs = _valid_kwargs()
        kwargs["target_level"] = "L3"
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLog(**kwargs)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "target_level" in exc_info.value.context

    def test_levels_equal_rejected(self) -> None:
        """场景③: previous_level == target_level → 242（切换语义不变量——no-op
        不得产生日志；与 DB CheckConstraint 双层防线）。"""
        kwargs = _valid_kwargs()
        kwargs["target_level"] = IsolationLevel.L4_HARD
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLog(**kwargs)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_trigger_reason_blank_rejected(self) -> None:
        """场景④: trigger_reason 空白 → 242。"""
        kwargs = _valid_kwargs()
        kwargs["trigger_reason"] = "   "
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLog(**kwargs)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "trigger_reason" in exc_info.value.context

    def test_trigger_reason_non_str_rejected(self) -> None:
        """场景④: trigger_reason 非 str → 242。"""
        kwargs = _valid_kwargs()
        kwargs["trigger_reason"] = None
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLog(**kwargs)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_approval_chain_non_tuple_rejected(self) -> None:
        """场景⑤: approval_chain 非 tuple（list 形态）→ 242（直构造注入——
        from_event 冻结拷贝必产 tuple）。"""
        kwargs = _valid_kwargs()
        kwargs["approval_chain"] = ["审批人"]
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLog(**kwargs)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "approval_chain" in exc_info.value.context

    def test_approval_chain_blank_element_rejected(self) -> None:
        """场景⑤: approval_chain 元素空白串 → 242。"""
        kwargs = _valid_kwargs()
        kwargs["approval_chain"] = ("审批人", "  ")
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLog(**kwargs)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "approval_chain" in exc_info.value.context

    def test_approval_chain_non_str_element_rejected(self) -> None:
        """场景⑤: approval_chain 元素非 str → 242。"""
        kwargs = _valid_kwargs()
        kwargs["approval_chain"] = ("审批人", 42)
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLog(**kwargs)
        assert exc_info.value.code == "EXCEPTION_242"


class TestToDict:
    """to_dict 序列化惯例（对齐 audit_log.to_dict——JSONB 写入前置形态）。"""

    def test_full_field_serialization(self) -> None:
        """全字段类型转换: UUID→str / Enum→value / datetime→ISO 8601 / tuple→list。"""
        log = IsolationSwitchLog.from_event(_make_event())
        d = log.to_dict()
        assert d["log_id"] == str(log.log_id)
        assert isinstance(d["log_id"], str)
        assert d["agent_id"] == str(log.agent_id)
        assert d["previous_level"] == "L4"
        assert d["target_level"] == "L3"
        assert d["trigger_reason"] == "单测事件构造"
        assert d["approval_chain"] == ["合规负责人", "安全官"]
        assert isinstance(d["approval_chain"], list)
        assert d["switch_timestamp"] == "2026-10-25T10:00:00+00:00"
        assert d["worm_ref"] is None

    def test_key_set_complete(self) -> None:
        """键集完整（八字段——与实体字段一一对应）。"""
        d = IsolationSwitchLog.from_event(_make_event()).to_dict()
        assert set(d) == {
            "log_id",
            "agent_id",
            "previous_level",
            "target_level",
            "trigger_reason",
            "approval_chain",
            "switch_timestamp",
            "worm_ref",
        }


class TestFrozenImmutability:
    """frozen 不可变（追加型日志事实——审计防篡改的实体层面）。"""

    def test_assignment_rejected(self) -> None:
        """字段赋值 → FrozenInstanceError。"""
        log = IsolationSwitchLog.from_event(_make_event())
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(log, "trigger_reason", "篡改尝试")

    def test_is_frozen_dataclass(self) -> None:
        """dataclasses.is_dataclass(frozen=True) 形态断言。"""
        assert dataclasses.is_dataclass(IsolationSwitchLog)
        log = IsolationSwitchLog.from_event(_make_event())
        assert not hasattr(log, "__dict__") or log.__dict__.get("trigger_reason") is not None
