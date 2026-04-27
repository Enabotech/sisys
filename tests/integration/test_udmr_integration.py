"""Integration tests for UDMRouter end-to-end routing flow."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from src.domain.services.udmr_router import UDMRouter
from src.domain.value_objects.routing_decision import RoutingDecision
from src.infrastructure.routing.fallback_router import FallbackRouter


class TestUDMRIntegration:
    """Integration test suite for UDMRouter end-to-end flow."""

    def test_end_to_end_routing_local_when_healthy(self) -> None:
        """End-to-end test: local routing when Ollama is available."""
        router = UDMRouter()
        mock_health = MagicMock()
        mock_health.check.return_value = True
        router._health_checker = mock_health  # type: ignore

        task_context = {
            "task_id": "integration-001",
            "session_id": "integration-session-001",
            "complexity": "medium",
        }
        decision = router.route(task_context)

        assert decision.route_type == "local"
        assert decision.selected_model == "qwen2.5:7b"
        assert decision.fallback_reason is None

    def test_end_to_end_routing_cloud_when_unhealthy(self) -> None:
        """End-to-end test: cloud routing when Ollama is unavailable."""
        router = UDMRouter()
        mock_health = MagicMock()
        mock_health.check.return_value = False
        router._health_checker = mock_health  # type: ignore

        task_context = {
            "task_id": "integration-002",
            "session_id": "integration-session-002",
            "complexity": "high",
        }
        decision = router.route(task_context)

        assert decision.route_type == "cloud"
        assert decision.selected_model == "qwen-turbo"
        assert decision.fallback_reason == "unavailable"

    def test_fallback_router_with_healthy_local(self) -> None:
        """Test FallbackRouter with healthy local model."""
        router = FallbackRouter()
        mock_health = MagicMock()
        mock_health.check.return_value = True
        router._health_checker = mock_health

        result = router.route("test-task", primary_model="qwen2.5:7b", fallback_model="qwen-turbo")

        assert result == "qwen2.5:7b"

    def test_fallback_router_with_unhealthy_local(self) -> None:
        """Test FallbackRouter with unhealthy local model."""
        router = FallbackRouter()
        mock_health = MagicMock()
        mock_health.check.return_value = False
        router._health_checker = mock_health

        result = router.route("test-task", primary_model="qwen2.5:7b", fallback_model="qwen-turbo")

        assert result == "qwen-turbo"

    def test_routing_decision_log_creation(self) -> None:
        """Test that RoutingDecision can be created with all UDMR fields."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="test-task-001",
            session_id="test-session-001",
            route_type="local",
            selected_model="qwen2.5:7b",
            cost_estimate=0.001,
            cost_actual=0.001,
            latency_ms=5.0,
            fallback_reason=None,
        )

        assert decision.task_id == "test-task-001"
        assert decision.route_type == "local"
        assert decision.selected_model == "qwen2.5:7b"

    def test_routing_decision_with_fallback_reason(self) -> None:
        """Test that RoutingDecision captures fallback reason correctly."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="test-task-002",
            session_id="test-session-002",
            route_type="cloud",
            selected_model="qwen-turbo",
            cost_estimate=0.005,
            cost_actual=0.0,
            latency_ms=0.0,
            fallback_reason="timeout",
        )

        assert decision.route_type == "cloud"
        assert decision.fallback_reason == "timeout"
