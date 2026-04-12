"""
测试数据工厂 - Factory Boy 实现。

提供可复用的测试数据构建器，支持复杂对象构建。
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import factory

from src.domain.entities.strategic_plan import PlanStatus, PlanType, StrategicPlan


class StrategicPlanFactory(factory.Factory):
    """
    战略规划工厂。

    使用 Factory Boy 模式创建战略规划测试数据。
    """

    class Meta:
        model = StrategicPlan

    id = factory.LazyFunction(uuid.uuid4)
    plan_type = factory.LazyFunction(lambda: PlanType.SP)
    status = factory.LazyFunction(lambda: PlanStatus.DRAFT)
    creator_id = "agent_ceo"
    created_at = factory.LazyFunction(lambda: datetime.now(UTC))
    updated_at = factory.LazyFunction(lambda: datetime.now(UTC))

    class Params:
        # 简化创建特定状态的规划
        in_progress = factory.Trait(
            status=PlanStatus.IN_PROGRESS,
        )
        approved = factory.Trait(
            status=PlanStatus.APPROVED,
        )
        completed = factory.Trait(
            status=PlanStatus.COMPLETED,
        )


class AgentFactory(factory.Factory):
    """
    Agent 工厂。

    使用 Factory Boy 模式创建 Agent 测试数据。
    """

    class Meta:
        model = dict  # 使用 dict 作为模型，直到 Agent 实体定义

    id = factory.Sequence(lambda n: f"agent_{n}")
    role = factory.LazyFunction(lambda: "CEO")
    status = "active"
    name = factory.Sequence(lambda n: f"Agent {n}")
    created_at = factory.LazyFunction(lambda: datetime.now(UTC))


class TestDataBuilder:
    """
    通用测试数据构建器。

    提供链式 API 构建任意测试数据。
    """

    def __init__(self, base_data: dict[str, Any] | None = None):
        self._data = base_data or {}

    def with_id(self, id_value: Any) -> "TestDataBuilder":
        """设置 ID。"""
        self._data["id"] = id_value
        return self

    def with_field(self, key: str, value: Any) -> "TestDataBuilder":
        """设置任意字段。"""
        self._data[key] = value
        return self

    def with_status(self, status: str) -> "TestDataBuilder":
        """设置状态。"""
        self._data["status"] = status
        return self

    def with_creator(self, creator_id: str) -> "TestDataBuilder":
        """设置创建者。"""
        self._data["creator_id"] = creator_id
        return self

    def build(self) -> dict[str, Any]:
        """构建最终数据。"""
        return self._data.copy()
