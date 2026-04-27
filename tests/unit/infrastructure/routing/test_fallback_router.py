"""Unit tests for FallbackRouter infrastructure service."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.infrastructure.routing.fallback_router import FallbackRouter


class TestFallbackRouter:
    """Test suite for FallbackRouter."""

    def test_returns_primary_when_healthy(self) -> None:
        """Should return primary model when it's healthy."""
        router = FallbackRouter()
        mock_health = MagicMock()
        mock_health.check.return_value = True
        router._health_checker = mock_health

        result = router.route("test-task", primary_model="qwen2.5:7b", fallback_model="qwen-turbo")
        assert result == "qwen2.5:7b"

    def test_returns_fallback_when_primary_unhealthy(self) -> None:
        """Should return fallback model when primary is unhealthy."""
        router = FallbackRouter()
        mock_health = MagicMock()
        mock_health.check.return_value = False
        router._health_checker = mock_health

        result = router.route("test-task", primary_model="qwen2.5:7b", fallback_model="qwen-turbo")
        assert result == "qwen-turbo"

    def test_returns_fallback_when_timeout_exceeded(self) -> None:
        """Should return fallback when response exceeds timeout."""
        router = FallbackRouter()
        mock_health = MagicMock()
        mock_health.check.return_value = True
        router._health_checker = mock_health

        router.record_latency(35000)  # 35 seconds > 30 second threshold
        result = router.route("test-task", primary_model="qwen2.5:7b", fallback_model="qwen-turbo")
        assert result == "qwen-turbo"

    def test_returns_primary_when_within_timeout(self) -> None:
        """Should return primary when response is within timeout."""
        router = FallbackRouter()
        mock_health = MagicMock()
        mock_health.check.return_value = True
        router._health_checker = mock_health

        router.record_latency(5000)  # 5 seconds < 30 second threshold
        result = router.route("test-task", primary_model="qwen2.5:7b", fallback_model="qwen-turbo")
        assert result == "qwen2.5:7b"

    def test_injects_health_checker_via_constructor(self) -> None:
        """Should allow health checker injection via constructor."""
        mock_health = MagicMock()
        mock_health.check.return_value = False
        router = FallbackRouter(health_checker=mock_health)

        result = router.route("test-task", primary_model="qwen2.5:7b", fallback_model="qwen-turbo")
        assert result == "qwen-turbo"

    def test_route_includes_task_id(self) -> None:
        """Should pass task_id to routing decision."""
        router = FallbackRouter()
        mock_health = MagicMock()
        mock_health.check.return_value = True
        router._health_checker = mock_health

        result = router.route("test-task-123", primary_model="qwen2.5:7b", fallback_model="qwen-turbo")
        assert result == "qwen2.5:7b"
