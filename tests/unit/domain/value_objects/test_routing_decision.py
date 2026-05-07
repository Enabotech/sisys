"""Unit tests for RoutingDecision value object."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.value_objects.routing_decision import RoutingDecision


class TestRoutingDecisionValidation:
    """Test RoutingDecision.validate method."""

    def test_valid_decision_with_defaults(self) -> None:
        """Should create a valid decision with default values."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
        )
        decision.validate()  # Should not raise

    def test_valid_decision_with_all_fields(self) -> None:
        """Should create a valid decision with all fields specified."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            selected_model="qwen-turbo",
            cost_estimate=0.002,
            cost_actual=0.0015,
            latency_ms=150.0,
            fallback_reason="timeout",
        )
        decision.validate()  # Should not raise

    def test_validate_log_id_not_uuid(self) -> None:
        """Should raise if log_id is not a UUID."""
        decision = RoutingDecision(
            log_id="not-a-uuid",  # type: ignore
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
        )
        with pytest.raises(ValueError, match="log_id must be a valid UUID"):
            decision.validate()

    def test_validate_task_id_empty(self) -> None:
        """Should raise if task_id is empty."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="",
            session_id="session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
        )
        with pytest.raises(ValueError, match="task_id must not be empty"):
            decision.validate()

    def test_validate_task_id_whitespace_only(self) -> None:
        """Should raise if task_id is whitespace only."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="   ",
            session_id="session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
        )
        with pytest.raises(ValueError, match="task_id must not be empty"):
            decision.validate()

    def test_validate_session_id_empty(self) -> None:
        """Should raise if session_id is empty."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="",
            route_type="local",
            selected_model="qwen2.5:7b",
        )
        with pytest.raises(ValueError, match="session_id must not be empty"):
            decision.validate()

    def test_validate_session_id_whitespace_only(self) -> None:
        """Should raise if session_id is whitespace only."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="   ",
            route_type="local",
            selected_model="qwen2.5:7b",
        )
        with pytest.raises(ValueError, match="session_id must not be empty"):
            decision.validate()

    def test_validate_cost_estimate_negative(self) -> None:
        """Should raise if cost_estimate is negative."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
            cost_estimate=-0.01,
        )
        with pytest.raises(ValueError, match="cost_estimate must be non-negative"):
            decision.validate()

    def test_validate_cost_actual_negative(self) -> None:
        """Should raise if cost_actual is negative."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
            cost_actual=-0.01,
        )
        with pytest.raises(ValueError, match="cost_actual must be non-negative"):
            decision.validate()

    def test_validate_latency_ms_negative(self) -> None:
        """Should raise if latency_ms is negative."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
            latency_ms=-1.0,
        )
        with pytest.raises(ValueError, match="latency_ms must be non-negative"):
            decision.validate()

    def test_validate_selected_model_empty(self) -> None:
        """Should raise if selected_model is empty."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            selected_model="",
        )
        with pytest.raises(ValueError, match="selected_model must not be empty"):
            decision.validate()

    def test_validate_selected_model_whitespace_only(self) -> None:
        """Should raise if selected_model is whitespace only."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            selected_model="   ",
        )
        with pytest.raises(ValueError, match="selected_model must not be empty"):
            decision.validate()

    def test_validate_fallback_reason_invalid_value(self) -> None:
        """Should raise if fallback_reason is not one of valid values."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            selected_model="qwen-turbo",
            fallback_reason="invalid_reason",
        )
        with pytest.raises(ValueError, match="fallback_reason must be one of"):
            decision.validate()

    def test_validate_fallback_reason_none_is_valid(self) -> None:
        """Should allow fallback_reason to be None."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
            fallback_reason=None,
        )
        decision.validate()  # Should not raise

    def test_validate_fallback_reason_timeout(self) -> None:
        """Should accept fallback_reason=timeout."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            selected_model="qwen-turbo",
            fallback_reason="timeout",
        )
        decision.validate()  # Should not raise

    def test_validate_fallback_reason_unavailable(self) -> None:
        """Should accept fallback_reason=unavailable."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            selected_model="qwen-turbo",
            fallback_reason="unavailable",
        )
        decision.validate()  # Should not raise

    def test_validate_fallback_reason_health_check_failed(self) -> None:
        """Should accept fallback_reason=health_check_failed."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            selected_model="qwen-turbo",
            fallback_reason="health_check_failed",
        )
        decision.validate()  # Should not raise


class TestRoutingDecisionAttributes:
    """Test RoutingDecision attribute access."""

    def test_default_values(self) -> None:
        """Should have correct default values."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
        )
        assert decision.cost_estimate == 0.0
        assert decision.cost_actual == 0.0
        assert decision.latency_ms == 0.0
        assert decision.fallback_reason is None
        assert decision.timestamp is not None

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        log_id = uuid.uuid4()
        now = datetime.now(UTC)
        decision = RoutingDecision(
            log_id=log_id,
            task_id="task-002",
            session_id="session-002",
            route_type="cloud",
            selected_model="qwen-turbo",
            cost_estimate=0.003,
            cost_actual=0.0025,
            latency_ms=200.0,
            fallback_reason="timeout",
            timestamp=now,
        )
        assert decision.log_id == log_id
        assert decision.task_id == "task-002"
        assert decision.session_id == "session-002"
        assert decision.route_type == "cloud"
        assert decision.selected_model == "qwen-turbo"
        assert decision.cost_estimate == 0.003
        assert decision.cost_actual == 0.0025
        assert decision.latency_ms == 200.0
        assert decision.fallback_reason == "timeout"
        assert decision.timestamp == now


class TestRoutingDecisionRepr:
    """Test RoutingDecision repr."""

    def test_repr_contains_key_fields(self) -> None:
        """Should contain key fields in repr."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
        )
        repr_str = repr(decision)
        assert "RoutingDecision" in repr_str
        assert "task-001" in repr_str
        assert "session-001" in repr_str
        assert "local" in repr_str
