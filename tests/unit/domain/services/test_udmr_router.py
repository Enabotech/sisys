"""Unit tests for UDMRouter domain service."""

from __future__ import annotations

from unittest.mock import patch

from src.domain.services.udmr_router import UDMRouter


class TestUDMRouter:
    """Test suite for UDMRouter domain service."""

    def test_route_local_first_when_available(self) -> None:
        """Should route to local model when local is available."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }
        with patch.object(router, "_check_local_health", return_value=True):
            decision = router.route(task_context)
        assert decision.route_type == "local"
        assert decision.selected_model == "qwen2.5:7b"

    def test_route_cloud_when_local_unavailable(self) -> None:
        """Should route to cloud model when local is unavailable."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }
        with patch.object(router, "_check_local_health", return_value=False):
            decision = router.route(task_context)
        assert decision.route_type == "cloud"
        assert decision.fallback_reason == "unavailable"

    def test_route_cloud_when_timeout_exceeds_threshold(self) -> None:
        """Should route to cloud when local response exceeds timeout."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }
        with patch.object(router, "_check_local_health", return_value=True):
            with patch.object(router, "_is_timeout", return_value=True):
                decision = router.route(task_context)
        assert decision.route_type == "cloud"
        assert decision.fallback_reason == "timeout"

    def test_route_decision_contains_required_fields(self) -> None:
        """Should return RoutingDecision with all required fields."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }
        with patch.object(router, "_check_local_health", return_value=True):
            decision = router.route(task_context)
        assert decision.task_id == "task-001"
        assert decision.session_id == "session-001"
        assert decision.selected_model is not None
        assert decision.cost_estimate >= 0
        assert decision.latency_ms >= 0

    def test_check_local_health_returns_bool(self) -> None:
        """Should return boolean from health check."""
        router = UDMRouter()
        result = router.check_local_health()
        assert isinstance(result, bool)

    def test_route_decision_logging(self) -> None:
        """Should return routing decision with logging fields."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }
        with patch.object(router, "_check_local_health", return_value=True):
            decision = router.route(task_context)
        assert decision.timestamp is not None
        assert decision.log_id is not None

    def test_route_local_sets_fallback_reason_none(self) -> None:
        """When routing to local, fallback_reason should be None."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }
        with patch.object(router, "_check_local_health", return_value=True):
            decision = router.route(task_context)
        assert decision.fallback_reason is None
