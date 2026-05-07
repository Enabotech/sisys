"""Performance benchmark tests for UDMRouter."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

from src.domain.services.udmr_router import UDMRouter


class TestUDMRPerformance:
    """Test suite for UDMRouter performance benchmarks."""

    def test_routing_decision_latency_under_100ms(self) -> None:
        """Routing decision should complete within 100ms (P95 target)."""
        router = UDMRouter()
        mock_health_checker = AsyncMock()
        mock_health_checker.check.return_value = True
        router._health_checker = mock_health_checker

        task_context = {
            "task_id": "perf-test-001",
            "session_id": "perf-session-001",
            "complexity": "medium",
        }

        warmup_runs = 10

        for _ in range(warmup_runs):
            router.route(task_context)

        latencies = []
        test_runs = 100
        for _ in range(test_runs):
            start = time.perf_counter()
            router.route(task_context)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        assert p95_latency < 100, f"P95 latency {p95_latency:.2f}ms exceeds 100ms threshold"

    def test_local_routing_ratio_over_80_percent(self) -> None:
        """Local routing should account for >= 80% of decisions."""
        router = UDMRouter()
        mock_health_checker = AsyncMock()
        mock_health_checker.check.return_value = True
        router._health_checker = mock_health_checker

        task_context = {
            "task_id": "ratio-test-001",
            "session_id": "ratio-session-001",
            "complexity": "medium",
        }

        local_count = 0
        total_runs = 100

        for i in range(total_runs):
            decision = router.route(task_context)
            if decision.route_type == "local":
                local_count += 1

        local_ratio = local_count / total_runs
        assert local_ratio >= 0.80, f"Local routing ratio {local_ratio:.1%} is below 80%"

    def test_routing_decision_idempotency(self) -> None:
        """Same input should produce same routing decision."""
        router = UDMRouter()
        mock_health_checker = AsyncMock()
        mock_health_checker.check.return_value = True
        router._health_checker = mock_health_checker

        task_context = {
            "task_id": "idempotent-test-001",
            "session_id": "idempotent-session-001",
            "complexity": "medium",
        }

        decision1 = router.route(task_context)
        decision2 = router.route(task_context)

        assert decision1.route_type == decision2.route_type
        assert decision1.selected_model == decision2.selected_model
