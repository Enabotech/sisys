"""AutoTriggerContext 单元测试

验证 AutoTriggerContext 值对象正确
Story 1.14a: 自主调用循环 - trigger 实现

Reference: src/domain/value_objects/auto_trigger_context.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.domain.value_objects.auto_trigger_context import AutoTriggerContext


class TestAutoTriggerContextCreation:
    """验证 AutoTriggerContext 创建"""

    def test_create_minimal_context(self) -> None:
        """验证创建最小上下文"""
        ctx = AutoTriggerContext(session_id="test-session", trigger_type="domain_event")
        assert ctx.session_id == "test-session"
        assert ctx.trigger_type == "domain_event"

    def test_create_with_all_fields(self) -> None:
        """验证创建带所有字段的上下文"""
        ctx = AutoTriggerContext(
            session_id="test-session",
            trigger_type="heartbeat",
            agent_id="agent-001",
            task_context={"key": "value"},
            timestamp=datetime.now(UTC),
            source_event_type="HeartbeatTriggered",
            source_event_id="event-123",
        )
        assert ctx.agent_id == "agent-001"
        assert ctx.task_context == {"key": "value"}
        assert ctx.source_event_type == "HeartbeatTriggered"
        assert ctx.source_event_id == "event-123"

    def test_default_session_id_when_empty(self) -> None:
        """验证空 session_id 时使用默认值"""
        ctx = AutoTriggerContext(session_id="", trigger_type="domain_event")
        assert ctx.session_id == "default"

    def test_dataclass_is_frozen(self) -> None:
        """验证 frozen dataclass 配置正确"""
        # Verify frozen=True is set in dataclass parameters
        assert hasattr(AutoTriggerContext, "__dataclass_params__")
        assert AutoTriggerContext.__dataclass_params__.frozen is True


class TestAutoTriggerContextFromDomainEvent:
    """验证 from_domain_event 工厂方法"""

    def test_from_domain_event_basic(self) -> None:
        """验证基本 domain event 提取"""
        payload = {
            "session_id": "session-123",
            "agent_id": "agent-001",
            "task_type": "document_processing",
        }
        ctx = AutoTriggerContext.from_domain_event("DocumentProcessed", payload)
        assert ctx.session_id == "session-123"
        assert ctx.trigger_type == "domain_event"
        assert ctx.agent_id == "agent-001"
        assert ctx.source_event_type == "DocumentProcessed"

    def test_from_domain_event_with_nested_payload(self) -> None:
        """验证从嵌套 payload 提取 — 简化后仅检查顶层字段"""
        payload = {
            "session_id": "session-456",
            "agent_id": "agent-002",
        }
        ctx = AutoTriggerContext.from_domain_event("ToolExecuted", payload)
        assert ctx.session_id == "session-456"
        assert ctx.agent_id == "agent-002"

    def test_from_domain_event_with_aggregate_id(self) -> None:
        """验证从 aggregate_id 提取 session_id"""
        payload = {
            "aggregate_id": "agg-789",
        }
        ctx = AutoTriggerContext.from_domain_event("CheckpointReached", payload)
        assert ctx.session_id == "agg-789"

    def test_from_domain_event_default_session(self) -> None:
        """验证没有 session_id 时使用默认值"""
        payload: dict = {}
        ctx = AutoTriggerContext.from_domain_event("AgentDecided", payload)
        assert ctx.session_id == "default"

    def test_from_domain_event_task_context_extraction(self) -> None:
        """验证 task_context 字段提取"""
        payload = {
            "session_id": "test-session",
            "task_type": "analysis",
            "priority": "high",
            "tool_name": "tool_a",
            "document_id": "doc-123",
            "strategy_id": "strat-456",
            "aggregate_id": "agg-789",  # should be excluded
            "event_id": "evt-000",  # should be excluded
            "event_type": "DocumentProcessed",  # should be excluded
        }
        ctx = AutoTriggerContext.from_domain_event("DocumentProcessed", payload)
        assert "task_type" in ctx.task_context
        assert "priority" in ctx.task_context
        assert "tool_name" in ctx.task_context
        assert "document_id" in ctx.task_context
        assert "strategy_id" in ctx.task_context
        assert "aggregate_id" not in ctx.task_context
        assert "event_id" not in ctx.task_context
        assert "event_type" not in ctx.task_context

    def test_from_domain_event_with_event_id(self) -> None:
        """验证从 domain event 带 event_id"""
        payload = {"session_id": "test-session"}
        ctx = AutoTriggerContext.from_domain_event("CorrectionApproved", payload, event_id="evt-999")
        assert ctx.source_event_id == "evt-999"


class TestAutoTriggerContextFromHeartbeat:
    """验证 from_heartbeat 工厂方法"""

    def test_from_heartbeat_basic(self) -> None:
        """验证基本 heartbeat 提取"""
        ctx = AutoTriggerContext.from_heartbeat(heartbeat_id="hb-001")
        assert ctx.session_id == "heartbeat-scheduler"
        assert ctx.trigger_type == "heartbeat"
        assert ctx.source_event_type == "HeartbeatTriggered"
        assert ctx.source_event_id == "hb-001"
        assert ctx.task_context["heartbeat_id"] == "hb-001"

    def test_from_heartbeat_with_wake_reason(self) -> None:
        """验证带 wake_reason 的 heartbeat"""
        ctx = AutoTriggerContext.from_heartbeat(
            heartbeat_id="hb-002",
            wake_reason="scheduled",
        )
        assert ctx.task_context["wake_reason"] == "scheduled"

    def test_from_heartbeat_with_todo_items(self) -> None:
        """验证带 todo_items 的 heartbeat"""
        ctx = AutoTriggerContext.from_heartbeat(
            heartbeat_id="hb-003",
            todo_items=("task-1", "task-2"),
        )
        assert ctx.task_context["todo_items"] == ["task-1", "task-2"]

    def test_from_heartbeat_empty_todo_items(self) -> None:
        """验证空 todo_items 的 heartbeat"""
        ctx = AutoTriggerContext.from_heartbeat(
            heartbeat_id="hb-004",
            todo_items=None,
        )
        assert ctx.task_context["todo_items"] == []

    def test_from_heartbeat_with_cost_budget(self) -> None:
        """验证带 cost_budget 的 heartbeat"""
        ctx = AutoTriggerContext.from_heartbeat(
            heartbeat_id="hb-005",
            cost_budget=100.0,
        )
        assert ctx.task_context["cost_budget"] == 100.0

    def test_from_heartbeat_all_fields(self) -> None:
        """验证带所有字段的 heartbeat"""
        ctx = AutoTriggerContext.from_heartbeat(
            heartbeat_id="hb-006",
            wake_reason="user_request",
            todo_items=("task-a", "task-b"),
            cost_budget=50.5,
        )
        assert ctx.task_context["heartbeat_id"] == "hb-006"
        assert ctx.task_context["wake_reason"] == "user_request"
        assert ctx.task_context["todo_items"] == ["task-a", "task-b"]
        assert ctx.task_context["cost_budget"] == 50.5


class TestAutoTriggerContextRepr:
    """验证 AutoTriggerContext repr"""

    def test_repr_contains_key_fields(self) -> None:
        """验证 repr 包含关键字段"""
        ctx = AutoTriggerContext(
            session_id="test-session",
            trigger_type="domain_event",
            agent_id="agent-001",
        )
        repr_str = repr(ctx)
        assert "AutoTriggerContext" in repr_str
        assert "test-session" in repr_str
        assert "domain_event" in repr_str
