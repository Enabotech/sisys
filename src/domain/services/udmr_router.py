"""UDMRouter domain service for unified dynamic model routing."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from src.domain.ports.health_check import HealthCheckPort
from src.domain.value_objects.routing_decision import RoutingDecision

DEFAULT_LOCAL_MODEL = "qwen2.5:7b"
DEFAULT_CLOUD_MODELS = ["qwen-turbo", "qwen-plus", "claude-3-haiku"]
DEFAULT_TIMEOUT_MS = 30000  # 30 seconds
LOCAL_COST_ESTIMATE = 0.0001  # Local model cost per request
CLOUD_COST_ESTIMATE = 0.001  # Cloud model cost per request


class RouterConfig(Protocol):
    """Protocol for router configuration."""

    @property
    def local_model(self) -> str:
        """Get local model name."""
        ...

    @property
    def cloud_models(self) -> list[str]:
        """Get list of cloud models."""
        ...

    @property
    def local_timeout(self) -> int:
        """Get timeout in seconds."""
        ...

    @property
    def local_first(self) -> bool:
        """Check if local first is enabled."""
        ...


@dataclass
class UDMRouter:
    """Unified Dynamic Model Router (UDMRouter).

    Implements local-first static routing with fallback to cloud.

    Responsibilities:
    - Receive task context and execute local-first routing decisions
    - Check local model health before routing (via HealthCheckPort)
    - Fallback to cloud when local is unavailable or timeout exceeds threshold
    - Publish routing decision events

    Routing Logic:
    1. Check local model health (Ollama ping) via HealthCheckPort
    2. If local available → route to local model
    3. If local unavailable OR timeout > 30s → fallback to cloud model
    """

    _health_checker: HealthCheckPort | None = None
    _config: RouterConfig | None = None

    def __post_init__(self) -> None:
        """Initialize instance variables to avoid thread safety issues."""
        pass

    def with_config(self, config: RouterConfig) -> UDMRouter:
        """Create a new router instance with the given config.

        Args:
            config: RouterConfig instance with routing configuration.

        Returns:
            New UDMRouter instance with config applied.
        """
        router = UDMRouter()
        router._config = config
        router._health_checker = self._health_checker
        return router

    def _get_local_model(self) -> str:
        """Get local model name from config or default."""
        if self._config is not None:
            return self._config.local_model
        return DEFAULT_LOCAL_MODEL

    def _get_cloud_models(self) -> list[str]:
        """Get cloud models list from config or default."""
        if self._config is not None:
            return self._config.cloud_models
        return DEFAULT_CLOUD_MODELS.copy()

    def _get_timeout_ms(self) -> int:
        """Get timeout threshold in milliseconds from config or default."""
        if self._config is not None:
            return self._config.local_timeout * 1000
        return DEFAULT_TIMEOUT_MS

    def _is_local_first(self) -> bool:
        """Check if local_first preference is enabled."""
        if self._config is not None:
            return self._config.local_first
        return True  # Default to local-first

    def _get_cost_estimate(self, route_type: Literal["local", "cloud"]) -> float:
        """Get cost estimate based on route type."""
        if route_type == "local":
            return LOCAL_COST_ESTIMATE
        return CLOUD_COST_ESTIMATE

    async def _check_local_health_async(self) -> bool:
        """Internal async health check implementation via HealthCheckPort.

        Returns:
            True if healthy, False otherwise.
        """
        if self._health_checker is not None:
            return await self._health_checker.check()
        return True

    def _is_timeout(self, latency_ms: float, timeout_ms: int) -> bool:
        """Check if latency exceeds timeout threshold.

        Args:
            latency_ms: Current latency in milliseconds
            timeout_ms: Timeout threshold in milliseconds

        Returns:
            True if timeout exceeded, False otherwise.
        """
        return latency_ms > timeout_ms

    def _build_decision(
        self,
        route_type: Literal["local", "cloud"],
        selected_model: str,
        fallback_reason: str | None,
        latency_ms: float,
        task_id: str,
        session_id: str,
    ) -> RoutingDecision:
        """Build RoutingDecision from route parameters."""
        log_id = uuid.uuid4()
        cost_estimate = self._get_cost_estimate(route_type)
        return RoutingDecision(
            log_id=log_id,
            task_id=task_id,
            session_id=session_id,
            route_type=route_type,
            selected_model=selected_model,
            cost_estimate=cost_estimate,
            latency_ms=latency_ms,
            fallback_reason=fallback_reason,
            timestamp=datetime.now(UTC),
        )

    async def route_async(self, task_context: dict | None) -> RoutingDecision:
        """Execute routing decision based on task context (async version).

        Args:
            task_context: Dictionary containing task_id, session_id, complexity

        Returns:
            RoutingDecision with route_type, selected_model, cost_estimate, etc.

        Raises:
            ValueError: If task_context is None or missing required fields.
        """
        if task_context is None:
            raise ValueError("task_context must not be None")

        task_id = task_context.get("task_id", "")
        session_id = task_context.get("session_id", "")

        if not task_id or not task_id.strip():
            raise ValueError("task_id must not be empty")
        if not session_id or not session_id.strip():
            raise ValueError("session_id must not be empty")

        start_time = time.time()
        health_check_exc: Exception | None = None
        try:
            local_healthy = await self._check_local_health_async()
        except Exception as e:
            local_healthy = False
            health_check_exc = e

        decision_start = time.time()
        latency_ms = (decision_start - start_time) * 1000

        timeout_ms = self._get_timeout_ms()
        is_timeout = self._is_timeout(latency_ms, timeout_ms)

        # Determine route based on local_first config and conditions
        if self._is_local_first() and local_healthy and not is_timeout:
            route_type: Literal["local", "cloud"] = "local"
            selected_model = self._get_local_model()
            fallback_reason: str | None = None
        else:
            route_type = "cloud"
            cloud_models = self._get_cloud_models()
            if not cloud_models:
                raise ValueError("No cloud models available and local model unavailable")
            selected_model = cloud_models[0]
            if health_check_exc is not None:
                fallback_reason = "health_check_failed"
            elif is_timeout:
                fallback_reason = "timeout"
            else:
                fallback_reason = "unavailable"

        return self._build_decision(route_type, selected_model, fallback_reason, latency_ms, task_id, session_id)

    def route(self, task_context: dict | None) -> RoutingDecision:
        """Execute routing decision based on task context (sync wrapper).

        Args:
            task_context: Dictionary containing task_id, session_id, complexity

        Returns:
            RoutingDecision with route_type, selected_model, cost_estimate, etc.

        Raises:
            ValueError: If task_context is None or missing required fields.
        """
        import asyncio

        return asyncio.run(self.route_async(task_context))

    async def check_local_health(self) -> bool:
        """Check if local model (Ollama) is available.

        Returns:
            True if local model is healthy, False otherwise.
        """
        return await self._check_local_health_async()

    def check_local_health_sync(self) -> bool:
        """Check if local model (Ollama) is available (sync version).

        Returns:
            True if local model is healthy, False otherwise.
        """
        import asyncio

        return asyncio.run(self._check_local_health_async())
