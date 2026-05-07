"""Unit tests for UDMRouter domain service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.domain.services.udmr_router import UDMRouter


class TestUDMRouter:
    """Test suite for UDMRouter domain service."""

    @pytest.mark.asyncio
    async def test_route_local_first_when_available(self) -> None:
        """Should route to local model when local is available."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }

        mock_health_checker = AsyncMock()
        mock_health_checker.check.return_value = True
        router._health_checker = mock_health_checker

        decision = await router.route_async(task_context)
        assert decision.route_type == "local"
        assert decision.selected_model == "qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_route_cloud_when_local_unavailable(self) -> None:
        """Should route to cloud model when local is unavailable."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }

        mock_health_checker = AsyncMock()
        mock_health_checker.check.return_value = False
        router._health_checker = mock_health_checker

        decision = await router.route_async(task_context)
        assert decision.route_type == "cloud"
        assert decision.fallback_reason == "unavailable"

    @pytest.mark.asyncio
    async def test_route_cloud_when_timeout_exceeds_threshold(self) -> None:
        """Should route to cloud when local response exceeds timeout."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }

        mock_health_checker = AsyncMock()
        mock_health_checker.check.return_value = True
        router._health_checker = mock_health_checker

        # Mock _is_timeout to return True
        with patch.object(router, "_is_timeout", return_value=True):
            decision = await router.route_async(task_context)
        assert decision.route_type == "cloud"
        assert decision.fallback_reason == "timeout"

    @pytest.mark.asyncio
    async def test_route_decision_contains_required_fields(self) -> None:
        """Should return RoutingDecision with all required fields."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }

        mock_health_checker = AsyncMock()
        mock_health_checker.check.return_value = True
        router._health_checker = mock_health_checker

        decision = await router.route_async(task_context)
        assert decision.task_id == "task-001"
        assert decision.session_id == "session-001"
        assert decision.selected_model is not None
        assert decision.cost_estimate >= 0
        assert decision.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_check_local_health_returns_bool(self) -> None:
        """Should return boolean from health check."""
        router = UDMRouter()

        mock_health_checker = AsyncMock()
        mock_health_checker.check.return_value = True
        router._health_checker = mock_health_checker

        result = await router.check_local_health()
        assert isinstance(result, bool)
        assert result is True

    @pytest.mark.asyncio
    async def test_route_decision_logging(self) -> None:
        """Should return routing decision with logging fields."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }

        mock_health_checker = AsyncMock()
        mock_health_checker.check.return_value = True
        router._health_checker = mock_health_checker

        decision = await router.route_async(task_context)
        assert decision.timestamp is not None
        assert decision.log_id is not None

    @pytest.mark.asyncio
    async def test_route_local_sets_fallback_reason_none(self) -> None:
        """When routing to local, fallback_reason should be None."""
        router = UDMRouter()
        task_context = {
            "task_id": "task-001",
            "session_id": "session-001",
            "complexity": "medium",
        }

        mock_health_checker = AsyncMock()
        mock_health_checker.check.return_value = True
        router._health_checker = mock_health_checker

        decision = await router.route_async(task_context)
        assert decision.fallback_reason is None


class TestUDMRouterSync:
    """Test suite for UDMRouter sync methods (backward compatibility)."""

    def test_route_accepts_none_task_context(self) -> None:
        """Should raise ValueError when task_context is None."""
        router = UDMRouter()

        with pytest.raises(ValueError, match="task_context must not be None"):
            router.route(None)

    def test_route_accepts_empty_task_id(self) -> None:
        """Should raise ValueError when task_id is empty."""
        router = UDMRouter()
        task_context = {"task_id": "", "session_id": "session-001"}

        with pytest.raises(ValueError, match="task_id must not be empty"):
            router.route(task_context)

    def test_route_accepts_empty_session_id(self) -> None:
        """Should raise ValueError when session_id is empty."""
        router = UDMRouter()
        task_context = {"task_id": "task-001", "session_id": ""}

        with pytest.raises(ValueError, match="session_id must not be empty"):
            router.route(task_context)
