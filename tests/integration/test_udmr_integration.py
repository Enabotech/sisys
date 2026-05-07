"""Integration tests for UDMRouter end-to-end routing flow."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.ports.health_check import HealthCheckPort
from src.domain.services.udmr_router import UDMRouter
from src.domain.value_objects.routing_decision import RoutingDecision
from src.infrastructure.routing.fallback_router import FallbackRouter


class TestUDMRIntegration:
    """Integration test suite for UDMRouter end-to-end flow."""

    @pytest.mark.asyncio
    async def test_end_to_end_routing_local_when_healthy(self) -> None:
        """End-to-end test: local routing when Ollama is available."""
        router = UDMRouter()
        mock_health = AsyncMock(spec=HealthCheckPort)
        mock_health.check.return_value = True
        router._health_checker = mock_health

        task_context = {
            "task_id": "integration-001",
            "session_id": "integration-session-001",
            "complexity": "medium",
        }
        decision = await router.route_async(task_context)

        assert decision.route_type == "local"
        assert decision.selected_model == "qwen2.5:7b"
        assert decision.fallback_reason is None

    @pytest.mark.asyncio
    async def test_end_to_end_routing_cloud_when_unhealthy(self) -> None:
        """End-to-end test: cloud routing when Ollama is unavailable."""
        router = UDMRouter()
        mock_health = AsyncMock(spec=HealthCheckPort)
        mock_health.check.return_value = False
        router._health_checker = mock_health

        task_context = {
            "task_id": "integration-002",
            "session_id": "integration-session-002",
            "complexity": "high",
        }
        decision = await router.route_async(task_context)

        assert decision.route_type == "cloud"
        assert decision.selected_model == "qwen-turbo"
        assert decision.fallback_reason == "unavailable"

    @pytest.mark.asyncio
    async def test_fallback_router_with_healthy_local(self) -> None:
        """Test FallbackRouter with healthy local model."""
        router = FallbackRouter()
        mock_health = MagicMock()
        mock_health.check = AsyncMock(return_value=True)
        router._health_checker = mock_health

        result = await router.route("test-task", primary_model="qwen2.5:7b", fallback_model="qwen-turbo")

        assert result == "qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_fallback_router_with_unhealthy_local(self) -> None:
        """Test FallbackRouter with unhealthy local model."""
        router = FallbackRouter()
        mock_health = MagicMock()
        mock_health.check = AsyncMock(return_value=False)
        router._health_checker = mock_health

        result = await router.route("test-task", primary_model="qwen2.5:7b", fallback_model="qwen-turbo")

        assert result == "qwen-turbo"

    @pytest.mark.asyncio
    async def test_routing_decision_log_creation(self) -> None:
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

    @pytest.mark.asyncio
    async def test_routing_decision_with_fallback_reason(self) -> None:
        """Test that RoutingDecision captures fallback reason correctly."""
        decision = RoutingDecision(
            log_id=uuid.uuid4(),
            task_id="test-task-002",
            session_id="test-session-002",
            route_type="cloud",
            selected_model="qwen-turbo",
            cost_estimate=0.01,
            cost_actual=0.009,
            latency_ms=100.0,
            fallback_reason="unavailable",
        )

        assert decision.fallback_reason == "unavailable"
        assert decision.route_type == "cloud"
