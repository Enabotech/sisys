"""AgentInstantiated 领域事件单元测试（Story 5-1）

覆盖 AgentInstantiated（Agent 实例化完成事件）：
- 字段构造（agent_id/role/name/config_version 全 kw_only 必填）
- aggregate_id/aggregate_type 自动设置（对齐 AgentDecided 先例）
- event_type 固定默认值（init=False + 注册表自动登记）
- frozen 冻结性
- to_dict 序列化（子类非核心字段合并 payload）

既有 AgentDecided 的测试位于 test_core_events.py（本文件不动它，仅新增事件测试）。

Run with:
    poetry run pytest tests/unit/domain/events/test_agent_events.py -v
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from src.domain.events import AgentInstantiated


def _make_event(**kwargs) -> AgentInstantiated:
    """工厂：构造 CEO 实例化事件（可覆盖任意 kw_only 字段）。"""
    defaults: dict = {
        "agent_id": uuid.uuid4(),
        "role": "ceo",
        "name": "CEO Agent",
        "config_version": "1.0.0",
    }
    defaults.update(kwargs)
    return AgentInstantiated(**defaults)


# ===================================================================
# 构造与默认值
# ===================================================================


class TestAgentInstantiatedCreation:
    """AgentInstantiated 事件构造契约。"""

    def test_create_event_with_all_fields(self) -> None:
        agent_id = uuid.uuid4()
        event = AgentInstantiated(
            agent_id=agent_id,
            role="ceo",
            name="CEO Agent",
            config_version="1.0.0",
        )
        assert event.agent_id == agent_id
        assert event.role == "ceo"
        assert event.name == "CEO Agent"
        assert event.config_version == "1.0.0"

    def test_event_type_default(self) -> None:
        event = _make_event()
        assert event.event_type == "AgentInstantiated"

    def test_required_fields_are_kw_only(self) -> None:
        """必填字段必须 kw_only（DomainEvent 基类字段全带默认值，位置声明会类定义即炸）。"""
        with pytest.raises(TypeError):
            AgentInstantiated()  # type: ignore[call-arg]  # 缺全部必填 kw_only 字段

    def test_missing_single_required_field(self) -> None:
        """省略单个必填 kw_only 字段 → TypeError（构造契约守护）。

        kwargs 经字典动态解包（缺 config_version 是本用例的测试意图，
        动态解包使静态检查器不误报「测试故意触发 TypeError」的构造）。
        """
        kwargs: dict[str, Any] = {
            "agent_id": uuid.uuid4(),
            "role": "ceo",
            "name": "CEO Agent",
            # config_version 故意缺失
        }
        with pytest.raises(TypeError):
            AgentInstantiated(**kwargs)


# ===================================================================
# aggregate 设置（对齐 AgentDecided 先例）
# ===================================================================


class TestAggregateSettings:
    """__post_init__ 自动设置 aggregate_id（UUID 对象）/aggregate_type。"""

    def test_aggregate_id_set_to_agent_id_uuid_object(self) -> None:
        agent_id = uuid.uuid4()
        event = _make_event(agent_id=agent_id)
        assert event.aggregate_id == agent_id
        assert isinstance(event.aggregate_id, uuid.UUID), "aggregate_id 须为 UUID 对象非 str"

    def test_aggregate_type_is_agent(self) -> None:
        event = _make_event()
        assert event.aggregate_type == "Agent"

    def test_explicit_aggregate_id_not_overwritten(self) -> None:
        """aggregate_id 已显式传入时不覆盖（__post_init__ 守卫）。"""
        explicit = uuid.uuid4()
        event = _make_event(aggregate_id=explicit)
        assert event.aggregate_id == explicit


# ===================================================================
# 冻结性与注册表
# ===================================================================


class TestFrozenAndRegistry:
    """frozen dataclass 不可变 + 事件注册表自动登记（event_type init=False）。"""

    def test_frozen_immutable(self) -> None:
        event = _make_event()
        with pytest.raises(Exception, match="cannot assign|frozen"):
            event.role = "cfo"  # type: ignore[misc]

    def test_registered_in_event_registry(self) -> None:
        from src.domain.events.base import DomainEvent

        assert DomainEvent._registry.get("AgentInstantiated") is AgentInstantiated


# ===================================================================
# to_dict 序列化
# ===================================================================


class TestToDict:
    """to_dict：子类非核心字段（agent_id/role/name/config_version）合并进 payload。"""

    def test_to_dict_top_level_fields(self) -> None:
        agent_id = uuid.uuid4()
        event = _make_event(agent_id=agent_id)
        data = event.to_dict()
        assert data["event_type"] == "AgentInstantiated"
        assert data["aggregate_id"] == str(agent_id), "to_dict 序列化时 UUID 自转 str"
        assert data["aggregate_type"] == "Agent"

    def test_to_dict_payload_merges_subclass_fields(self) -> None:
        event = _make_event(role="ceo", name="CEO Agent", config_version="1.0.0")
        payload = event.to_dict()["payload"]
        assert payload["role"] == "ceo"
        assert payload["name"] == "CEO Agent"
        assert payload["config_version"] == "1.0.0"
        assert payload["agent_id"] == str(event.agent_id)
