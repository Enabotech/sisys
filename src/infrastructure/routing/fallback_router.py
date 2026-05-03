"""FallbackRouter infrastructure service for model fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.ports.health_check import HealthCheckPort


TIMEOUT_THRESHOLD_MS = 30000  # 30 seconds


class FallbackRouter:
    """Router that falls back to cloud model when local model is unavailable.

    Implements the fallback logic for UDMRouter when:
    - Local model health check fails
    - Local model response exceeds timeout threshold
    """

    def __init__(self, health_checker: HealthCheckPort | None = None) -> None:
        """Initialize FallbackRouter with optional health checker.

        Args:
            health_checker: Optional HealthCheckPort instance for dependency injection.
                           Supports any health check adapter (Ollama, vLLM, etc.)
        """
        self._health_checker = health_checker
        self._last_latency_ms: float = 0.0

    async def route(self, task_id: str, primary_model: str, fallback_model: str) -> str:
        """Route to primary model or fallback based on health and timeout.

        Args:
            task_id: The task identifier
            primary_model: Primary model to route to (usually local)
            fallback_model: Fallback model (usually cloud)

        Returns:
            Selected model name
        """
        if await self._is_healthy() and not self._is_timeout():
            return primary_model
        return fallback_model

    async def _is_healthy(self) -> bool:
        """Check if primary model is healthy via health checker.

        Returns:
            True if healthy, False otherwise.
        """
        if self._health_checker is not None:
            return await self._health_checker.check()
        return True

    def _is_timeout(self) -> bool:
        """Check if last response exceeded timeout threshold.

        Returns:
            True if timeout exceeded, False otherwise.
        """
        return self._last_latency_ms > TIMEOUT_THRESHOLD_MS

    def record_latency(self, latency_ms: float) -> None:
        """Record latency for timeout tracking.

        Args:
            latency_ms: Response latency in milliseconds
        """
        self._last_latency_ms = latency_ms
