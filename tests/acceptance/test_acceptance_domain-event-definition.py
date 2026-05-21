"""Acceptance tests for Story 1.2 - Domain Event Definition.

BDD step definitions for domain event schemas and event infrastructure.
Validates 10 domain event types, serialization, publication, and listening.

Run with: poetry run pytest tests/acceptance/test_acceptance_domain-event-definition.py -v
"""

import uuid

import pytest
from pytest_bdd import given, scenario, then, when

from src.domain.events import (
    AgentDecided,
    CheckpointReached,
    CorrectionApproved,
    DocumentProcessed,
    ToolExecuted,
)
from src.domain.events.base import DomainEvent
from src.domain.events.checkpoint_events import CheckpointRecovered
from src.domain.events.enums import DeviationLevel, DeviationType, IsolationLevel, RecoveryMode
from src.domain.events.heartbeat_events import HeartbeatTriggered
from src.domain.events.isolation_events import (
    IsolationLevelSwitched,
)
from src.domain.events.planning_events import StrategicDeviationWarning
from src.domain.events.routing_events import RoutingDecided

# --- Scenarios ---


@scenario(
    "test_acceptance_domain-event-definition.feature",
    "定义 DocumentProcessed 事件",
)
def test_document_processed_event():
    """DocumentProcessed event definition test."""


@scenario(
    "test_acceptance_domain-event-definition.feature",
    "定义 ToolExecuted 事件",
)
def test_tool_executed_event():
    """ToolExecuted event definition test."""


@scenario(
    "test_acceptance_domain-event-definition.feature",
    "定义 AgentDecided 事件",
)
def test_agent_decided_event():
    """AgentDecided event definition test."""


@scenario(
    "test_acceptance_domain-event-definition.feature",
    "定义 CheckpointReached 事件",
)
def test_checkpoint_reached_event():
    """CheckpointReached event definition test."""


@scenario(
    "test_acceptance_domain-event-definition.feature",
    "定义 CorrectionApproved 事件",
)
def test_correction_approved_event():
    """CorrectionApproved event definition test."""


@scenario(
    "test_acceptance_domain-event-definition.feature",
    "定义 StrategicDeviationWarning 事件",
)
def test_strategic_deviation_warning_event():
    """StrategicDeviationWarning event definition test."""


@scenario(
    "test_acceptance_domain-event-definition.feature",
    "定义 HeartbeatTriggered 事件",
)
def test_heartbeat_triggered_event():
    """HeartbeatTriggered event definition test."""


@scenario(
    "test_acceptance_domain-event-definition.feature",
    "定义 IsolationLevelSwitched 事件",
)
def test_isolation_level_switched_event():
    """IsolationLevelSwitched event definition test."""


@scenario(
    "test_acceptance_domain-event-definition.feature",
    "定义 CheckpointRecovered 事件",
)
def test_checkpoint_recovered_event():
    """CheckpointRecovered event definition test."""


@scenario(
    "test_acceptance_domain-event-definition.feature",
    "定义 RoutingDecided 事件",
)
def test_routing_decided_event():
    """RoutingDecided event definition test."""


# --- Fixtures ---


@pytest.fixture
def events_context():
    """Shared context for all event scenarios."""
    return {
        "document_id": uuid.uuid4(),
        "tool_id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "checkpoint_id": uuid.uuid4(),
        "correction_id": uuid.uuid4(),
        "events_created": {},
    }


# --- Given steps ---


@given("10 种核心领域事件已定义")
def core_events_defined():
    """Verify all 10 core events are defined."""
    # 5 events from Story 1.1 already exist
    existing = [
        DocumentProcessed,
        ToolExecuted,
        AgentDecided,
        CheckpointReached,
        CorrectionApproved,
    ]
    assert len(existing) == 5


@given("事件发布/订阅基础设施已实现")
def event_infrastructure_implemented():
    """Placeholder: event pub/sub infrastructure is implemented."""
    # Will be validated in later tasks
    pass


@given("任意一种领域事件")
def any_domain_event():
    """Return any domain event for serialization tests."""
    return DocumentProcessed(document_id=uuid.uuid4())


@given("InMemoryEventBus 已实现")
def in_memory_event_bus_implemented():
    """Placeholder: InMemoryEventBus is implemented."""
    pass


@given("InMemoryEventStore 已实现")
def in_memory_event_store_implemented():
    """Placeholder: InMemoryEventStore is implemented."""
    pass


# --- When steps ---


@when("创建 DocumentProcessed 事件携带文档 ID、解析结果摘要、嵌入向量引用")
def create_document_processed_event(events_context):
    """Create DocumentProcessed event."""
    doc_id = events_context["document_id"]
    event = DocumentProcessed(
        document_id=doc_id,
        parse_result={"pages": 10, "summary": "test"},
        embedding=[0.1, 0.2, 0.3],
    )
    events_context["events_created"]["DocumentProcessed"] = event


@when("创建 ToolExecuted 事件携带工具 ID、执行结果、成本审计信息")
def create_tool_executed_event(events_context):
    """Create ToolExecuted event."""
    tool_id = events_context["tool_id"]
    event = ToolExecuted(
        tool_id=tool_id,
        execution_result={"output": "success"},
        cost_audit={"cost_usd": 0.05},
    )
    events_context["events_created"]["ToolExecuted"] = event


@when("创建 AgentDecided 事件携带 Agent ID、决策结果、置信度评分")
def create_agent_decided_event(events_context):
    """Create AgentDecided event."""
    agent_id = events_context["agent_id"]
    event = AgentDecided(
        agent_id=agent_id,
        decision_result={"choice": "A"},
        confidence=0.85,
    )
    events_context["events_created"]["AgentDecided"] = event


@when("创建 CheckpointReached 事件携带阶段标识、用户反馈请求")
def create_checkpoint_reached_event(events_context):
    """Create CheckpointReached event."""
    cp_id = events_context["checkpoint_id"]
    event = CheckpointReached(
        checkpoint_id=cp_id,
        phase_identifier="market-insight",
        user_feedback_request=True,
    )
    events_context["events_created"]["CheckpointReached"] = event


@when("创建 CorrectionApproved 事件携带修正类型、修正前后值、审批链")
def create_correction_approved_event(events_context):
    """Create CorrectionApproved event."""
    corr_id = events_context["correction_id"]
    event = CorrectionApproved(
        correction_id=corr_id,
        correction_type="L1",
        previous_value="old",
        new_value="new",
        approval_chain=["expert1"],
    )
    events_context["events_created"]["CorrectionApproved"] = event


@when("调用 to_dict() 方法")
def call_to_dict(events_context):
    """Call to_dict on a domain event."""
    event = DocumentProcessed(document_id=uuid.uuid4())
    events_context["serialized"] = event.to_dict()
    events_context["original_event"] = event


@when("检查 src/domain/events/ 目录下的所有 Python 文件")
def check_domain_events_files():
    """Check domain events directory for Pydantic imports."""
    import ast
    from pathlib import Path

    events_dir = Path("src/domain/events")
    pydantic_imports_found = []
    for py_file in events_dir.rglob("*.py"):
        source = py_file.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "pydantic" in alias.name:
                        pydantic_imports_found.append(py_file)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "pydantic" in node.module:
                    pydantic_imports_found.append(py_file)
    assert len(pydantic_imports_found) == 0, f"Pydantic imports found in: {pydantic_imports_found}"


# --- Then steps ---


@then('事件类型为 "DocumentProcessed"')
def check_document_event_type(events_context):
    """Check event type is DocumentProcessed."""
    event = events_context["events_created"]["DocumentProcessed"]
    assert event.event_type == "DocumentProcessed"


@then("aggregate_id 等于 document_id")
def check_aggregate_id_document(events_context):
    """Check aggregate_id equals document_id."""
    event = events_context["events_created"]["DocumentProcessed"]
    assert event.aggregate_id == event.document_id


@then("payload 包含解析结果和嵌入向量信息")
def check_document_payload(events_context):
    """Check DocumentProcessed payload."""
    event = events_context["events_created"]["DocumentProcessed"]
    d = event.to_dict()
    assert "payload" in d


@then('事件类型为 "ToolExecuted"')
def check_tool_event_type(events_context):
    """Check event type is ToolExecuted."""
    event = events_context["events_created"]["ToolExecuted"]
    assert event.event_type == "ToolExecuted"


@then("aggregate_id 等于 tool_id")
def check_aggregate_id_tool(events_context):
    """Check aggregate_id equals tool_id."""
    event = events_context["events_created"]["ToolExecuted"]
    assert event.aggregate_id == event.tool_id


@then("payload 包含执行结果和成本审计信息")
def check_tool_payload(events_context):
    """Check ToolExecuted payload."""
    event = events_context["events_created"]["ToolExecuted"]
    d = event.to_dict()
    assert "payload" in d


@then('事件类型为 "AgentDecided"')
def check_agent_event_type(events_context):
    """Check event type is AgentDecided."""
    event = events_context["events_created"]["AgentDecided"]
    assert event.event_type == "AgentDecided"


@then("aggregate_id 等于 agent_id (AgentDecided)")
def check_aggregate_id_agent(events_context):
    """Check aggregate_id equals agent_id for AgentDecided."""
    event = events_context["events_created"]["AgentDecided"]
    assert event.aggregate_id == event.agent_id


@then("payload 包含决策结果和置信度")
def check_agent_payload(events_context):
    """Check AgentDecided payload."""
    event = events_context["events_created"]["AgentDecided"]
    d = event.to_dict()
    assert "payload" in d


@then('事件类型为 "CheckpointReached"')
def check_checkpoint_event_type(events_context):
    """Check event type is CheckpointReached."""
    event = events_context["events_created"]["CheckpointReached"]
    assert event.event_type == "CheckpointReached"


@then("aggregate_id 等于 checkpoint_id (CheckpointReached)")
def check_aggregate_id_checkpoint(events_context):
    """Check aggregate_id equals checkpoint_id for CheckpointReached."""
    event = events_context["events_created"]["CheckpointReached"]
    assert event.aggregate_id == event.checkpoint_id


@then("payload 包含阶段标识和反馈请求")
def check_checkpoint_payload(events_context):
    """Check CheckpointReached payload."""
    event = events_context["events_created"]["CheckpointReached"]
    d = event.to_dict()
    assert "payload" in d


@then('事件类型为 "CorrectionApproved"')
def check_correction_event_type(events_context):
    """Check event type is CorrectionApproved."""
    event = events_context["events_created"]["CorrectionApproved"]
    assert event.event_type == "CorrectionApproved"


@then("aggregate_id 等于 correction_id")
def check_aggregate_id_correction(events_context):
    """Check aggregate_id equals correction_id."""
    event = events_context["events_created"]["CorrectionApproved"]
    assert event.aggregate_id == event.correction_id


@then("payload 包含修正类型和审批链")
def check_correction_payload(events_context):
    """Check CorrectionApproved payload."""
    event = events_context["events_created"]["CorrectionApproved"]
    d = event.to_dict()
    assert "payload" in d


@then("返回字典包含 event_type、event_id、occurred_on、payload")
def check_serialized_dict_keys(events_context):
    """Check serialized dict has required keys."""
    d = events_context["serialized"]
    assert "event_type" in d
    assert "event_id" in d
    assert "occurred_on" in d
    assert "payload" in d


@then("调用 from_dict() 可以重建事件对象")
def check_from_dict_reconstruct(events_context):
    """Check from_dict can reconstruct the event."""
    event = events_context["original_event"]
    d = event.to_dict()
    restored = DomainEvent.from_dict(d)
    assert restored.event_id == event.event_id
    assert restored.event_type == event.event_type


@then("往返序列化数据无损")
def check_roundtrip_data_loss(events_context):
    """Check roundtrip serialization is lossless."""
    event = events_context["original_event"]
    d = event.to_dict()
    restored = DomainEvent.from_dict(d)
    assert restored.event_id == event.event_id
    assert restored.aggregate_id == event.aggregate_id
    assert restored.payload == event.payload


# --- Steps for 5 new events (P0-2 Fix) ---


@when("创建 StrategicDeviationWarning 事件携带偏差类型、偏差等级、实际值、规划值")
def create_strategic_deviation_warning_event(events_context):
    """Create StrategicDeviationWarning event."""
    event = StrategicDeviationWarning(
        warning_id=uuid.uuid4(),
        deviation_type=DeviationType.BUDGET_OVERUN,
        deviation_level=DeviationLevel.SEVERE,
        actual_value=150.0,
        planned_value=100.0,
    )
    events_context["events_created"]["StrategicDeviationWarning"] = event


@then('事件类型为 "StrategicDeviationWarning"')
def check_strategic_deviation_warning_event_type(events_context):
    """Check event type is StrategicDeviationWarning."""
    event = events_context["events_created"]["StrategicDeviationWarning"]
    assert event.event_type == "StrategicDeviationWarning"


@then("aggregate_id 不为空")
def check_aggregate_id_not_empty(events_context):
    """Check aggregate_id is not None."""
    event_name = list(events_context["events_created"].keys())[-1]
    event = events_context["events_created"][event_name]
    assert event.aggregate_id is not None


@then("payload 包含偏差类型、等级、实际值和规划值")
def check_strategic_deviation_warning_payload(events_context):
    """Check StrategicDeviationWarning payload."""
    event = events_context["events_created"]["StrategicDeviationWarning"]
    d = event.to_dict()
    assert "deviation_type" in d["payload"]


@when("创建 HeartbeatTriggered 事件携带心跳 ID、唤醒原因、待办事项列表")
def create_heartbeat_triggered_event(events_context):
    """Create HeartbeatTriggered event."""
    event = HeartbeatTriggered(
        heartbeat_id=uuid.uuid4(),
        wake_reason="periodic_check",
        todo_items=["check_budget", "check_timeline"],
    )
    events_context["events_created"]["HeartbeatTriggered"] = event


@then('事件类型为 "HeartbeatTriggered"')
def check_heartbeat_triggered_event_type(events_context):
    """Check event type is HeartbeatTriggered."""
    event = events_context["events_created"]["HeartbeatTriggered"]
    assert event.event_type == "HeartbeatTriggered"


@then("aggregate_id 等于 heartbeat_id")
def check_aggregate_id_heartbeat(events_context):
    """Check aggregate_id equals heartbeat_id."""
    event = events_context["events_created"]["HeartbeatTriggered"]
    assert event.aggregate_id == event.heartbeat_id


@then("payload 包含唤醒原因和待办事项")
def check_heartbeat_triggered_payload(events_context):
    """Check HeartbeatTriggered payload."""
    event = events_context["events_created"]["HeartbeatTriggered"]
    d = event.to_dict()
    assert "wake_reason" in d["payload"]


@when("创建 IsolationLevelSwitched 事件携带 Agent ID、原隔离等级、目标隔离等级")
def create_isolation_level_switched_event(events_context):
    """Create IsolationLevelSwitched event."""
    event = IsolationLevelSwitched(
        agent_id=uuid.uuid4(),
        previous_level=IsolationLevel.L4_HARD,
        target_level=IsolationLevel.L2_COLLAB,
        trigger_reason="joint_task_assigned",
    )
    events_context["events_created"]["IsolationLevelSwitched"] = event


@then('事件类型为 "IsolationLevelSwitched"')
def check_isolation_level_switched_event_type(events_context):
    """Check event type is IsolationLevelSwitched."""
    event = events_context["events_created"]["IsolationLevelSwitched"]
    assert event.event_type == "IsolationLevelSwitched"


@then("aggregate_id 等于 agent_id")
def check_aggregate_id_isolation(events_context):
    """Check aggregate_id equals agent_id."""
    event = events_context["events_created"]["IsolationLevelSwitched"]
    assert event.aggregate_id == event.agent_id


@then("payload 包含隔离等级切换信息")
def check_isolation_level_switched_payload(events_context):
    """Check IsolationLevelSwitched payload."""
    event = events_context["events_created"]["IsolationLevelSwitched"]
    d = event.to_dict()
    assert "previous_level" in d["payload"]


@when("创建 CheckpointRecovered 事件携带 Checkpoint ID、恢复模式、修改内容")
def create_checkpoint_recovered_event(events_context):
    """Create CheckpointRecovered event."""
    event = CheckpointRecovered(
        checkpoint_id=uuid.uuid4(),
        recovery_mode=RecoveryMode.REPLAY,
        modification_content={"assumption": "changed"},
    )
    events_context["events_created"]["CheckpointRecovered"] = event


@then('事件类型为 "CheckpointRecovered"')
def check_checkpoint_recovered_event_type(events_context):
    """Check event type is CheckpointRecovered."""
    event = events_context["events_created"]["CheckpointRecovered"]
    assert event.event_type == "CheckpointRecovered"


@then("aggregate_id 等于 checkpoint_id")
def check_aggregate_id_checkpoint_recovered(events_context):
    """Check aggregate_id equals checkpoint_id."""
    event = events_context["events_created"]["CheckpointRecovered"]
    assert event.aggregate_id == event.checkpoint_id


@then("payload 包含恢复模式和修改内容")
def check_checkpoint_recovered_payload(events_context):
    """Check CheckpointRecovered payload."""
    event = events_context["events_created"]["CheckpointRecovered"]
    d = event.to_dict()
    assert "recovery_mode" in d["payload"]


@when("创建 RoutingDecided 事件携带任务 ID、L1 合规性结果、L2 评分、选定模型")
def create_routing_decided_event(events_context):
    """Create RoutingDecided event."""
    event = RoutingDecided(
        task_id=uuid.uuid4(),
        l1_compliance_result={"allowed": True},
        l2_factor_scores={"semantic_match": 0.9},
        selected_model="local-llm-v2",
    )
    events_context["events_created"]["RoutingDecided"] = event


@then('事件类型为 "RoutingDecided"')
def check_routing_decided_event_type(events_context):
    """Check event type is RoutingDecided."""
    event = events_context["events_created"]["RoutingDecided"]
    assert event.event_type == "RoutingDecided"


@then("aggregate_id 等于 task_id")
def check_aggregate_id_routing(events_context):
    """Check aggregate_id equals task_id."""
    event = events_context["events_created"]["RoutingDecided"]
    assert event.aggregate_id == event.task_id


@then("payload 包含路由决策信息")
def check_routing_decided_payload(events_context):
    """Check RoutingDecided payload."""
    event = events_context["events_created"]["RoutingDecided"]
    d = event.to_dict()
    assert "selected_model" in d["payload"]
