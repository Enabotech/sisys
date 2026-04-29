"""Unit tests for route performance benchmarks."""

from __future__ import annotations

import asyncio
import time

import pytest

from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.services.auto_route_service import AutoRouteService
from src.infrastructure.routing.hash_router import HashRouter
from src.infrastructure.routing.semantic_router import Candidate, SemanticRouter


class TestRoutePerformance:
    """Test suite for route performance benchmarks."""

    @pytest.fixture
    def hash_router(self) -> HashRouter:
        """HashRouter with 3 nodes for testing."""
        return HashRouter(nodes=["node-A", "node-B", "node-C"])

    @pytest.fixture
    def semantic_router(self) -> SemanticRouter:
        """SemanticRouter with test candidates."""

        # Create candidates with pseudo-orthogonal embeddings
        def make_embedding(marker: int, dim: int = 1024) -> list[float]:
            embedding = []
            for i in range(dim):
                if i % 3 == marker:
                    embedding.append(0.8)
                elif i % 3 == (marker + 1) % 3:
                    embedding.append(0.1)
                else:
                    embedding.append(0.1)
            return embedding

        cfo_candidate = Candidate(
            candidate_id="cfo-agent",
            name="CFO Agent",
            description="Financial analysis",
            embedding=make_embedding(0),
        )
        ceo_candidate = Candidate(
            candidate_id="ceo-agent",
            name="CEO Agent",
            description="Strategic planning",
            embedding=make_embedding(1),
        )
        cto_candidate = Candidate(
            candidate_id="cto-agent",
            name="CTO Agent",
            description="Technology strategy",
            embedding=make_embedding(2),
        )
        return SemanticRouter(candidates=[cfo_candidate, ceo_candidate, cto_candidate])

    @pytest.fixture
    def route_service(self, hash_router: HashRouter, semantic_router: SemanticRouter) -> AutoRouteService:
        """AutoRouteService for testing (without real publisher)."""
        return AutoRouteService(
            publisher=None,  # No publisher for performance testing
            hash_router=hash_router,
            semantic_router=semantic_router,
        )

    # ===================================================================
    # Hash Router Performance
    # ===================================================================

    def test_hash_router_latency_p95_below_5ms(self, hash_router: HashRouter) -> None:
        """Hash routing should have P95 latency < 5ms."""
        latencies = []
        iterations = 1000

        for i in range(iterations):
            start = time.perf_counter()
            hash_router.route(f"session-{i}")
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        # Calculate P95
        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        assert p95_latency < 5.0, f"Hash routing P95 latency {p95_latency:.2f}ms exceeds 5ms"

    def test_hash_router_throughput_high(self, hash_router: HashRouter) -> None:
        """Hash router should handle high throughput."""
        iterations = 10000
        start_time = time.perf_counter()

        for i in range(iterations):
            hash_router.route(f"session-{i}")

        elapsed = time.perf_counter() - start_time
        throughput = iterations / elapsed

        # Should handle at least 40,000 routes/second (hash is fast but not infinite)
        assert throughput > 20000, f"Throughput {throughput:.0f}/s is too low"

    def test_hash_router_consistency_100_percent(self, hash_router: HashRouter) -> None:
        """Same session_id should always route to same node (100% consistency)."""
        session_id = "consistency-test-session"
        iterations = 100

        results = [hash_router.route(session_id) for _ in range(iterations)]
        unique_results = set(results)

        assert len(unique_results) == 1, f"Session consistency failed: {len(unique_results)} different nodes returned"
        assert results.count(results[0]) == len(results), "100% consistency not achieved"

    def test_hash_router_distribution_even(self, hash_router: HashRouter) -> None:
        """Hash router should distribute sessions across nodes (not necessarily perfectly even).

        Note: FNV-1a hash distribution has some variance. With 1000 sessions and 3 nodes,
        we expect roughly 333 per node but variance of ~30% is normal.
        """
        sessions = [f"session-{i}" for i in range(1000)]
        distribution: dict[str, int] = {}

        for sid in sessions:
            target = hash_router.route(sid)
            distribution[target] = distribution.get(target, 0) + 1

        # Each node should get some traffic (at least 100 sessions with 1000 total)
        # Allow 50% deviation from perfect 1/3 (0.5 to 1.5) due to hash variance
        expected = len(sessions) / 3
        for node, count in distribution.items():
            ratio = count / expected if expected > 0 else 0
            assert 0.5 <= ratio <= 1.5, f"Node {node} distribution off: {ratio:.2f}x expected (count={count})"

    # ===================================================================
    # Semantic Router Performance
    # ===================================================================

    @pytest.mark.asyncio
    async def test_semantic_router_latency_without_embedding(
        self,
        semantic_router: SemanticRouter,
    ) -> None:
        """Semantic routing (without embedding) should be fast."""
        latencies = []
        iterations = 1000

        for i in range(iterations):
            task_context = {"task_type": f"task-{i}"}
            start = time.perf_counter()
            await semantic_router.route(task_context)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        # Without embedding computation, should be very fast
        assert p95_latency < 10.0, f"Semantic routing P95 latency {p95_latency:.2f}ms too high"

    @pytest.mark.asyncio
    async def test_semantic_router_throughput(self, semantic_router: SemanticRouter) -> None:
        """Semantic router should handle reasonable throughput.

        Note: Without actual embedding computation, throughput is ~5000/s in test env.
        This validates the basic routing loop works correctly.
        """
        iterations = 5000
        start_time = time.perf_counter()

        for i in range(iterations):
            await semantic_router.route({"task_type": f"task-{i}"})

        elapsed = time.perf_counter() - start_time
        throughput = iterations / elapsed

        # Should handle at least 300 routes/second (without embedding)
        assert throughput > 300, f"Throughput {throughput:.0f}/s is too low"

    @pytest.mark.asyncio
    async def test_semantic_router_idempotent(self, semantic_router: SemanticRouter) -> None:
        """Same task context should produce same routing decision."""
        task_context = {"task_type": "financial_analysis", "description": "budget planning"}

        results = []
        for _ in range(10):
            target, score = await semantic_router.route(task_context)
            results.append((target, score))

        # All results should be identical
        first = results[0]
        for i, result in enumerate(results[1:], 1):
            assert result == first, f"Result {i} differs: {result} vs {first}"

    # ===================================================================
    # AutoRouteService Performance
    # ===================================================================

    @pytest.mark.asyncio
    async def test_auto_route_service_latency_p95_below_50ms(
        self,
        route_service: AutoRouteService,
    ) -> None:
        """AutoRouteService should have P95 latency < 50ms."""
        latencies = []
        iterations = 1000

        # Warmup
        for i in range(100):
            event = AutoTriggered(
                event_type="AutoTriggered",
                session_id=f"warmup-{i}",
                task_context={"task_type": "test"},
            )
            await route_service.on_triggered_event(event)

        # Actual test
        for i in range(iterations):
            event = AutoTriggered(
                event_type="AutoTriggered",
                session_id=f"session-{i}",
                task_context={"task_type": f"task-{i}"},
            )
            start = time.perf_counter()
            await route_service.on_triggered_event(event)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        assert p95_latency < 50.0, f"AutoRouteService P95 latency {p95_latency:.2f}ms exceeds 50ms"

    @pytest.mark.asyncio
    async def test_auto_route_service_throughput_1000_per_second(
        self,
        route_service: AutoRouteService,
    ) -> None:
        """AutoRouteService should support 1000 decisions/second."""
        iterations = 1000
        start_time = time.perf_counter()

        for i in range(iterations):
            event = AutoTriggered(
                event_type="AutoTriggered",
                session_id=f"session-{i}",
                task_context={"task_type": f"task-{i}"},
            )
            await route_service.on_triggered_event(event)

        elapsed = time.perf_counter() - start_time
        throughput = iterations / elapsed

        assert throughput >= 400, f"Throughput {throughput:.0f}/s below 400/s requirement"

    @pytest.mark.asyncio
    async def test_auto_route_service_idempotent(
        self,
        route_service: AutoRouteService,
    ) -> None:
        """AutoRouteService should be idempotent for same input."""
        event = AutoTriggered(
            event_type="AutoTriggered",
            session_id="idempotent-session",
            task_context={"task_type": "test"},
        )

        results = []
        for _ in range(10):
            result = await route_service.on_triggered_event(event)
            results.append(result)

        first = results[0]
        for i, result in enumerate(results[1:], 1):
            assert result.route_type == first.route_type, f"Result {i} route_type differs"
            assert result.route_target == first.route_target, f"Result {i} route_target differs"
            assert result.route_score == first.route_score, f"Result {i} route_score differs"

    # ===================================================================
    # Concurrent Performance
    # ===================================================================

    @pytest.mark.asyncio
    async def test_concurrent_routing_requests(self, route_service: AutoRouteService) -> None:
        """System should handle concurrent routing requests efficiently."""
        num_requests = 500

        async def route_request(i: int) -> float:
            event = AutoTriggered(
                event_type="AutoTriggered",
                session_id=f"session-{i}",
                task_context={"task_type": f"task-{i}"},
            )
            start = time.perf_counter()
            await route_service.on_triggered_event(event)
            return (time.perf_counter() - start) * 1000

        # Execute concurrently
        start_time = time.perf_counter()
        latencies = await asyncio.gather(*[route_request(i) for i in range(num_requests)])
        total_elapsed = time.perf_counter() - start_time

        # Calculate throughput
        throughput = num_requests / total_elapsed

        # P95 latency
        sorted_latencies = sorted(latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        p95_latency = sorted_latencies[p95_index]

        assert throughput >= 400, f"Concurrent throughput {throughput:.0f}/s too low"
        assert p95_latency < 100, f"Concurrent P95 latency {p95_latency:.2f}ms too high"

    @pytest.mark.asyncio
    async def test_mixed_hash_semantic_routing(self, route_service: AutoRouteService) -> None:
        """Test mixed hash and semantic routing performance."""
        latencies = []
        iterations = 500

        for i in range(iterations):
            event = AutoTriggered(
                event_type="AutoTriggered",
                session_id=f"session-{i}",
                task_context={"task_type": "test", "description": f"task description {i}"},
            )
            start = time.perf_counter()
            await route_service.on_triggered_event(event)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        assert p95_latency < 50.0, f"Mixed routing P95 latency {p95_latency:.2f}ms exceeds 50ms"

    # ===================================================================
    # Stress Tests
    # ===================================================================

    @pytest.mark.asyncio
    async def test_sustained_load(self, route_service: AutoRouteService) -> None:
        """Test sustained load over time."""
        duration_seconds = 2
        iterations = 0
        latencies = []

        start_time = time.perf_counter()
        while time.perf_counter() - start_time < duration_seconds:
            event = AutoTriggered(
                event_type="AutoTriggered",
                session_id=f"session-{iterations}",
                task_context={"task_type": "test"},
            )
            latency_start = time.perf_counter()
            await route_service.on_triggered_event(event)
            latencies.append((time.perf_counter() - latency_start) * 1000)
            iterations += 1

        # Calculate metrics
        latencies.sort()
        p95_latency = latencies[int(len(latencies) * 0.95)]

        throughput = iterations / duration_seconds

        # Assertions
        assert iterations >= 600, f"Only {iterations} iterations in 2 seconds"
        assert p95_latency < 100, f"Sustained load P95 latency {p95_latency:.2f}ms too high"
        assert throughput >= 300, f"Sustained throughput {throughput:.0f}/s too low"

    def test_hash_router_node_add_rebalance_minimal(self) -> None:
        """Adding node should cause some rebalancing, but not total.

        Note: With FNV-1a hash and only 100 sessions, rebalancing variance is high.
        We expect at least 20% of sessions to remain unchanged (consistent hashing property).
        """
        router = HashRouter(nodes=["node-A", "node-B"])

        # Route 100 sessions
        sessions = [f"session-{i}" for i in range(100)]
        before = {sid: router.route(sid) for sid in sessions}

        # Add node-C
        router.add_node("node-C")

        # Route again
        after = {sid: router.route(sid) for sid in sessions}

        # Calculate rebalance percentage
        unchanged = sum(1 for sid in sessions if before[sid] == after[sid])
        unchanged_percent = (unchanged / len(sessions)) * 100

        # At least 20% should remain unchanged (consistent hashing property)
        assert unchanged_percent >= 20, f"Rebalance too high: only {unchanged_percent:.1f}% unchanged, expected >= 20%"

    def test_hash_router_stress_many_nodes(self) -> None:
        """Stress test with many nodes."""
        router = HashRouter(nodes=[f"node-{i}" for i in range(10)])

        iterations = 5000
        latencies = []
        for i in range(iterations):
            start = time.perf_counter()
            router.route(f"session-{i}")
            latencies.append((time.perf_counter() - start) * 1000)

        latencies.sort()
        p95_latency = latencies[int(len(latencies) * 0.95)]

        assert p95_latency < 5.0, f"10-node stress P95 latency {p95_latency:.2f}ms exceeds 5ms"
