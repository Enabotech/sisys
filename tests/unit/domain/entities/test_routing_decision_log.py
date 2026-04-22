"""Unit tests for RoutingDecisionLog domain entity."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.routing_decision_log import RoutingDecisionLog


class TestRoutingDecisionLog:
    """Test suite for RoutingDecisionLog."""

    def test_create_valid_log(self) -> None:
        """Should create a valid routing decision log."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
        )
        log.validate()

    def test_validate_log_id_must_be_uuid(self) -> None:
        """Should raise if log_id is not a UUID."""
        log = RoutingDecisionLog(
            log_id="not-a-uuid",  # type: ignore
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
        )
        with pytest.raises(ValueError, match="log_id must be a valid UUID"):
            log.validate()

    def test_validate_task_id_empty(self) -> None:
        """Should raise if task_id is empty."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
        )
        with pytest.raises(ValueError, match="task_id must not be empty"):
            log.validate()

    def test_validate_task_id_whitespace(self) -> None:
        """Should raise if task_id is only whitespace."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="   ",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
        )
        with pytest.raises(ValueError, match="task_id must not be empty"):
            log.validate()

    def test_validate_session_id_empty(self) -> None:
        """Should raise if session_id is empty."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
        )
        with pytest.raises(ValueError, match="session_id must not be empty"):
            log.validate()

    def test_validate_route_type_invalid(self) -> None:
        """Should raise if route_type is not one of hash/semantic/mixed."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="invalid",
            route_target="cfo-agent",
            route_score=0.95,
        )
        with pytest.raises(ValueError, match="route_type must be one of"):
            log.validate()

    def test_validate_route_type_hash(self) -> None:
        """Should accept route_type=hash."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="hash",
            route_target="node-A",
            route_score=1.0,
        )
        log.validate()

    def test_validate_route_type_semantic(self) -> None:
        """Should accept route_type=semantic."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
        )
        log.validate()

    def test_validate_route_type_mixed(self) -> None:
        """Should accept route_type=mixed."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="mixed",
            route_target="cfo-agent",
            route_score=0.85,
        )
        log.validate()

    def test_validate_score_below_zero(self) -> None:
        """Should raise if route_score < 0.0."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=-0.1,
        )
        with pytest.raises(ValueError, match="route_score must be between 0.0 and 1.0"):
            log.validate()

    def test_validate_score_above_one(self) -> None:
        """Should raise if route_score > 1.0."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=1.1,
        )
        with pytest.raises(ValueError, match="route_score must be between 0.0 and 1.0"):
            log.validate()

    def test_validate_score_zero(self) -> None:
        """Should accept route_score = 0.0."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="hash",
            route_target="default",
            route_score=0.0,
        )
        log.validate()

    def test_validate_cost_estimate_negative(self) -> None:
        """Should raise if cost_estimate < 0."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
            cost_estimate=-1.0,
        )
        with pytest.raises(ValueError, match="cost_estimate must be non-negative"):
            log.validate()

    def test_validate_latency_ms_negative(self) -> None:
        """Should raise if latency_ms < 0."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
            latency_ms=-1.0,
        )
        with pytest.raises(ValueError, match="latency_ms must be non-negative"):
            log.validate()

    def test_default_values(self) -> None:
        """Should have correct default values."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="hash",
            route_target="node-A",
            route_score=1.0,
        )
        assert log.cost_estimate == 0.0
        assert log.latency_ms == 0.0
        assert log.worm_storage_ref == ""
        assert log.timestamp is not None

    def test_custom_timestamp(self) -> None:
        """Should accept custom timestamp."""
        custom_time = datetime(2024, 1, 1, tzinfo=UTC)
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
            timestamp=custom_time,
        )
        assert log.timestamp == custom_time

    def test_worm_storage_ref(self) -> None:
        """Should store WORM storage reference."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
            worm_storage_ref="s3://bucket/worm/route-log-123",
        )
        assert log.worm_storage_ref == "s3://bucket/worm/route-log-123"
