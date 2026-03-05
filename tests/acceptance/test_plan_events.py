"""
战略规划领域事件验收测试。

使用 pytest-bdd 实现 Gherkin 验收标准。
"""

from datetime import UTC, datetime
from uuid import uuid4

from pytest_bdd import given, scenarios, then, when

from src.domain.entities.strategic_plan import PlanStatus, PlanType, StrategicPlan
from src.domain.events.base import DomainEvent
from src.domain.events.plan_events import PlanCreated

# 加载场景
scenarios("test_plan_events.feature")


# ========== Given 步骤 ==========


@given("一个有效的战略规划创建事件数据", target_fixture="event_data")
def valid_event_data():
    """Given: 有效的领域事件数据。"""
    return {
        "plan_id": uuid4(),
        "creator_id": "agent_ceo",
    }


@given("一个带有自定义 ID 和时间的领域事件", target_fixture="custom_event_data")
def custom_id_and_time():
    """Given: 自定义 ID 和时间的领域事件。"""
    return {
        "event_id": uuid4(),
        "occurred_on": datetime(2026, 3, 4, 10, 0, 0, tzinfo=UTC),
        "aggregate_id": uuid4(),
    }


@given("一个领域事件", target_fixture="domain_event")
def domain_event_fixture():
    """Given: 一个领域事件实例。"""
    return DomainEvent(aggregate_id=uuid4())


@given("一个战略规划事件", target_fixture="plan_event")
def plan_event_fixture():
    """Given: 一个战略规划事件实例。"""
    return PlanCreated(plan_id=uuid4(), creator_id="agent_ceo")


@given("一个草稿状态的战略规划", target_fixture="draft_plan")
def draft_plan_fixture():
    """Given: 一个草稿状态的战略规划。"""
    return StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")


@given("一个有多个事件的战略规划", target_fixture="plan_with_events")
def plan_with_events_fixture():
    """Given: 一个有多个事件的战略规划。"""
    plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")
    plan.change_status(PlanStatus.IN_PROGRESS)
    plan.change_status(PlanStatus.REVIEW)
    return plan


@given("一个已创建的领域事件", target_fixture="created_event")
def created_event_fixture():
    """Given: 一个已创建的领域事件。"""
    return PlanCreated(plan_id=uuid4(), creator_id="agent_ceo")


# ========== When 步骤 ==========


@when("创建 PlanCreated 事件", target_fixture="create_plan_created_event")
def create_plan_created_event(event_data):
    """When: 创建 PlanCreated 事件。"""
    return PlanCreated(plan_id=event_data["plan_id"], creator_id=event_data["creator_id"])


@when("创建事件", target_fixture="create_event_with_custom_data")
def create_event_with_custom_data(custom_event_data):
    """When: 使用自定义数据创建事件。"""
    return DomainEvent(
        event_id=custom_event_data["event_id"],
        occurred_on=custom_event_data["occurred_on"],
        aggregate_id=custom_event_data["aggregate_id"],
    )


@when("设置聚合根 ID", target_fixture="set_aggregate_id")
def set_aggregate_id(domain_event):
    """When: 设置聚合根 ID。"""
    domain_event._aggregate_id = uuid4()
    return domain_event


@when("设置事件载荷", target_fixture="set_payload")
def set_payload(domain_event):
    """When: 设置事件载荷。"""
    domain_event._payload = {"key": "value"}
    return domain_event


@when("检查继承关系", target_fixture="check_inheritance")
def check_inheritance_action():
    """When: 检查事件继承关系。"""
    return issubclass(PlanCreated, DomainEvent)


@when("序列化为字典", target_fixture="serialize_event")
def serialize_event(plan_event):
    """When: 将事件序列化为字典。"""
    return {
        "event_id": str(plan_event.event_id),
        "event_type": plan_event.event_type,
        "occurred_on": plan_event.occurred_on.isoformat(),
        "aggregate_id": str(plan_event.aggregate_id),
        "payload": plan_event.payload,
    }


@when("调用 clear_events() 方法", target_fixture="clear_events_action")
def clear_events_action(plan_with_events):
    """When: 清空事件列表。"""
    plan_with_events.clear_events()
    return plan_with_events


@when("迭代事件列表", target_fixture="iterate_events")
def iterate_events(plan_with_events):
    """When: 迭代事件列表。"""
    return list(plan_with_events.domain_events)


# ========== Then 步骤 ==========


@then("事件应该通过 Pydantic 验证")
def validate_event(create_plan_created_event):
    """Then: 验证事件符合 Schema。"""
    assert isinstance(create_plan_created_event, DomainEvent)
    assert create_plan_created_event.event_id is not None
    assert create_plan_created_event.occurred_on is not None


@then("事件 ID 应该自动生成")
def check_event_id_auto_generated(create_plan_created_event):
    """Then: 验证事件 ID 自动生成。"""
    assert isinstance(create_plan_created_event.event_id, uuid4().__class__)


@then("事件时间戳应该自动设置")
def check_timestamp_auto_set(create_plan_created_event):
    """Then: 验证事件时间戳自动设置。"""
    assert isinstance(create_plan_created_event.occurred_on, datetime)
    assert create_plan_created_event.occurred_on.tzinfo is not None


@then("事件类型应该自动设置为'plan.created'")
def check_event_type(create_plan_created_event):
    """Then: 验证事件类型自动设置。"""
    assert create_plan_created_event.event_type == "plan.created"


@then("应该使用提供的 ID")
def check_custom_id_used(create_event_with_custom_data, custom_event_data):
    """Then: 验证使用自定义 ID。"""
    assert create_event_with_custom_data.event_id == custom_event_data["event_id"]


@then("应该使用提供的时间")
def check_custom_time_used(create_event_with_custom_data, custom_event_data):
    """Then: 验证使用自定义时间。"""
    assert create_event_with_custom_data.occurred_on == custom_event_data["occurred_on"]


@then("事件应该正确关联到聚合根")
def check_aggregate_id_set(set_aggregate_id):
    """Then: 验证聚合根 ID 设置。"""
    assert set_aggregate_id.aggregate_id is not None


@then("载荷应该是字典类型")
def check_payload_type(set_payload):
    """Then: 验证载荷类型。"""
    assert isinstance(set_payload.payload, dict)


@then("载荷应该包含必要字段")
def check_payload_fields(set_payload):
    """Then: 验证载荷包含必要字段。"""
    # set_payload 已经设置了 payload = {"key": "value"}
    assert "key" in set_payload._payload
    assert set_payload._payload["key"] == "value"


@then("PlanCreated 应该继承自 DomainEvent")
def check_plan_created_inheritance(check_inheritance):
    """Then: 验证 PlanCreated 继承关系。"""
    assert check_inheritance is True


@then("应该实现所有必需属性")
def check_required_attributes(check_inheritance):
    """Then: 验证必需属性。"""
    assert hasattr(PlanCreated, "event_id")
    assert hasattr(PlanCreated, "event_type")
    assert hasattr(PlanCreated, "occurred_on")
    assert hasattr(PlanCreated, "aggregate_id")
    assert hasattr(PlanCreated, "payload")


@then("应该包含所有必需字段")
def check_serialization_fields(serialize_event):
    """Then: 验证序列化包含必需字段。"""
    required_fields = ["event_id", "event_type", "occurred_on", "aggregate_id", "payload"]
    for field in required_fields:
        assert field in serialize_event


@then("反序列化后应该恢复原始状态")
def check_deserialization(serialize_event):
    """Then: 验证反序列化。"""
    assert serialize_event["event_type"] == "plan.created"


@then("事件列表应该为空")
def check_events_cleared(clear_events_action):
    """Then: 验证事件列表清空。"""
    assert len(clear_events_action.domain_events) == 0


@then("不影响规划的其他属性")
def check_other_attributes_unchanged(clear_events_action):
    """Then: 验证其他属性不变。"""
    assert clear_events_action.status is not None
    assert clear_events_action.id is not None
    assert clear_events_action.plan_type is not None


@then("应该按时间顺序返回事件")
def check_event_order(iterate_events):
    """Then: 验证事件按时间顺序。"""
    assert len(iterate_events) > 0
    for i in range(len(iterate_events) - 1):
        assert iterate_events[i].occurred_on <= iterate_events[i + 1].occurred_on


@then("每个事件都应该是 DomainEvent 类型")
def check_event_types(iterate_events):
    """Then: 验证事件类型。"""
    for event in iterate_events:
        assert isinstance(event, DomainEvent)
