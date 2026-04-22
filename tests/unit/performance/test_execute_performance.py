"""Performance benchmarks for execute mechanism (AC-5: P95<100ms, 100 exec/sec)."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.services.execute_service import ExecuteService
from src.infrastructure.sandbox.docker_sandbox_adapter import DockerSandboxAdapter


@dataclass
class BenchmarkResult:
    """Result of a performance benchmark."""

    operation: str
    iterations: int
    total_time_seconds: float
    avg_time_ms: float
    p95_ms: float
    throughput_per_sec: float


def benchmark_operation(
    operation: Callable,
    iterations: int = 1000,
    warmup: int = 10,
) -> BenchmarkResult:
    """Benchmark a synchronous or async operation.

    Args:
        operation: Callable to benchmark (sync or async)
        iterations: Number of iterations to run
        warmup: Number of warmup iterations before benchmarking

    Returns:
        BenchmarkResult with timing statistics
    """
    operation_name = operation.__name__ if hasattr(operation, "__name__") else str(operation)

    # Warmup
    for _ in range(warmup):
        result = operation()
        if asyncio.iscoroutine(result):
            asyncio.get_event_loop().run_until_complete(result)

    # Benchmark
    times_ms: list[float] = []
    start = time.perf_counter()

    for _ in range(iterations):
        iter_start = time.perf_counter()
        result = operation()
        if asyncio.iscoroutine(result):
            asyncio.get_event_loop().run_until_complete(result)
        iter_end = time.perf_counter()
        times_ms.append((iter_end - iter_start) * 1000)

    end = time.perf_counter()
    total_time = end - start

    # Calculate statistics
    avg_time = sum(times_ms) / len(times_ms)
    sorted_times = sorted(times_ms)
    p95_index = int(len(sorted_times) * 0.95)
    p95_time = sorted_times[p95_index] if sorted_times else 0
    throughput = iterations / total_time if total_time > 0 else 0

    return BenchmarkResult(
        operation=operation_name,
        iterations=iterations,
        total_time_seconds=total_time,
        avg_time_ms=avg_time,
        p95_ms=p95_time,
        throughput_per_sec=throughput,
    )


class TestExecutePerformanceBenchmarks:
    """Performance benchmarks for execute mechanism.

    AC-5 Requirements:
    - Sandbox startup latency P95 < 100ms
    - Snapshot latency P95 < 50ms
    - Throughput: 100 executions/second
    """

    @pytest.fixture
    def sandbox(self):
        """Create DockerSandboxAdapter for benchmarking."""
        adapter = DockerSandboxAdapter()
        yield adapter
        adapter.reset_all_containers()

    @pytest.fixture
    def execute_service(self, sandbox: DockerSandboxAdapter) -> ExecuteService:
        """Create ExecuteService with sandbox for benchmarking."""
        return ExecuteService(sandbox=sandbox, snapshot_repo=None)

    def test_sandbox_startup_latency(self, sandbox: DockerSandboxAdapter) -> None:
        """Benchmark sandbox container startup latency.

        AC-5: P95 startup latency should be < 100ms.
        """
        session_ids = [f"perf-session-{uuid.uuid4().hex[:8]}" for _ in range(100)]

        def startup_container() -> None:
            # Use deterministic session to avoid growing dict
            idx = hash(time.time()) % len(session_ids)
            asyncio.get_event_loop().run_until_complete(sandbox.start_container(f"startup-{idx}"))

        # Reset state between runs
        sandbox.reset_all_containers()

        result = benchmark_operation(startup_container, iterations=1000, warmup=100)

        print("\n  Sandbox Startup Latency:")
        print(f"    Iterations: {result.iterations}")
        print(f"    Total time: {result.total_time_seconds:.4f}s")
        print(f"    Avg time: {result.avg_time_ms:.4f}ms")
        print(f"    P95 time: {result.p95_ms:.4f}ms")
        print(f"    Throughput: {result.throughput_per_sec:.0f}/sec")

        # AC-5: P95 < 100ms
        assert result.p95_ms < 100.0, f"Sandbox startup P95 too high: {result.p95_ms:.4f}ms (requirement: <100ms)"

    @pytest.mark.asyncio
    async def test_sandbox_startup_latency_async(self, sandbox: DockerSandboxAdapter) -> None:
        """Benchmark async sandbox container startup latency.

        AC-5: P95 startup latency should be < 100ms.
        """
        iterations = 1000
        warmup = 100
        times_ms: list[float] = []

        # Warmup
        for i in range(warmup):
            await sandbox.start_container(f"warmup-{i}")

        sandbox.reset_all_containers()

        # Benchmark
        start = time.perf_counter()
        for i in range(iterations):
            iter_start = time.perf_counter()
            await sandbox.start_container(f"startup-{i}")
            iter_end = time.perf_counter()
            times_ms.append((iter_end - iter_start) * 1000)
        end = time.perf_counter()

        total_time = end - start
        avg_time = sum(times_ms) / len(times_ms)
        sorted_times = sorted(times_ms)
        p95_index = int(len(sorted_times) * 0.95)
        p95_time = sorted_times[p95_index]
        throughput = iterations / total_time if total_time > 0 else 0

        print("\n  Sandbox Startup Latency (async):")
        print(f"    Iterations: {iterations}")
        print(f"    Total time: {total_time:.4f}s")
        print(f"    Avg time: {avg_time:.4f}ms")
        print(f"    P95 time: {p95_time:.4f}ms")
        print(f"    Throughput: {throughput:.0f}/sec")

        # AC-5: P95 < 100ms
        assert p95_time < 100.0, f"Sandbox startup P95 too high: {p95_time:.4f}ms (requirement: <100ms)"

    @pytest.mark.asyncio
    async def test_execute_service_execution_latency(self, execute_service: ExecuteService) -> None:
        """Benchmark ExecuteService task execution latency.

        AC-5: P95 execution latency should be < 200ms (includes sandbox + snapshot).
        """
        from src.domain.events.route_events import Routed

        event = Routed(
            route_type="hash",
            session_id=f"exec-latency-{uuid.uuid4().hex[:8]}",
            task_context={
                "code": "print('hello')",
                "business_event_type": "ToolExecuted",
            },
            route_target="docker-sandbox",
            route_score=0.95,
        )

        iterations = 1000
        warmup = 100
        times_ms: list[float] = []

        # Warmup
        for _ in range(warmup):
            await execute_service.on_routed_event(event)

        # Benchmark
        start = time.perf_counter()
        for i in range(iterations):
            iter_start = time.perf_counter()
            await execute_service.on_routed_event(event)
            iter_end = time.perf_counter()
            times_ms.append((iter_end - iter_start) * 1000)
        end = time.perf_counter()

        total_time = end - start
        avg_time = sum(times_ms) / len(times_ms)
        sorted_times = sorted(times_ms)
        p95_index = int(len(sorted_times) * 0.95)
        p95_time = sorted_times[p95_index]
        throughput = iterations / total_time if total_time > 0 else 0

        print("\n  ExecuteService Execution Latency:")
        print(f"    Iterations: {iterations}")
        print(f"    Total time: {total_time:.4f}s")
        print(f"    Avg time: {avg_time:.4f}ms")
        print(f"    P95 time: {p95_time:.4f}ms")
        print(f"    Throughput: {throughput:.0f}/sec")

        # AC-5: P95 execution < 200ms (includes sandbox + snapshot overhead)
        assert p95_time < 200.0, f"Execution P95 too high: {p95_time:.4f}ms (requirement: <200ms)"

    @pytest.mark.asyncio
    async def test_snapshot_creation_latency(self, execute_service: ExecuteService) -> None:
        """Benchmark CheckpointSnapshot creation latency.

        AC-5: P95 snapshot latency should be < 50ms.
        """
        session_id = f"snap-latency-{uuid.uuid4().hex[:8]}"
        state = {
            "execution_result": {"status": "completed"},
            "route_target": "test-route",
            "route_score": 0.9,
        }

        iterations = 1000
        warmup = 100
        times_ms: list[float] = []

        # Warmup
        for _ in range(warmup):
            await execute_service.create_snapshot(session_id, state, "warmup")

        # Benchmark
        start = time.perf_counter()
        for i in range(iterations):
            iter_start = time.perf_counter()
            await execute_service.create_snapshot(f"snap-{i}", state, "benchmark")
            iter_end = time.perf_counter()
            times_ms.append((iter_end - iter_start) * 1000)
        end = time.perf_counter()

        total_time = end - start
        avg_time = sum(times_ms) / len(times_ms)
        sorted_times = sorted(times_ms)
        p95_index = int(len(sorted_times) * 0.95)
        p95_time = sorted_times[p95_index]
        throughput = iterations / total_time if total_time > 0 else 0

        print("\n  Snapshot Creation Latency:")
        print(f"    Iterations: {iterations}")
        print(f"    Total time: {total_time:.4f}s")
        print(f"    Avg time: {avg_time:.4f}ms")
        print(f"    P95 time: {p95_time:.4f}ms")
        print(f"    Throughput: {throughput:.0f}/sec")

        # AC-5: P95 < 50ms
        assert p95_time < 50.0, f"Snapshot P95 too high: {p95_time:.4f}ms (requirement: <50ms)"

    @pytest.mark.asyncio
    async def test_execution_throughput_100_per_second(self, execute_service: ExecuteService) -> None:
        """Benchmark execute throughput.

        AC-5: System should support 100 executions/second.
        """
        from src.domain.events.route_events import Routed

        async def process_event(idx: int) -> None:
            event = Routed(
                route_type="hash",
                session_id=f"throughput-{uuid.uuid4().hex[:8]}",
                task_context={
                    "code": "print('hello')",
                    "business_event_type": "ToolExecuted",
                },
                route_target="docker-sandbox",
                route_score=0.95,
            )
            await execute_service.on_routed_event(event)

        # Run for 1 second and count events
        iterations = 0
        start = time.perf_counter()
        target_duration = 1.0  # 1 second

        while (time.perf_counter() - start) < target_duration:
            await process_event(iterations)
            iterations += 1

        actual_duration = time.perf_counter() - start
        throughput = iterations / actual_duration

        print("\n  Execution Throughput:")
        print(f"    Duration: {actual_duration:.4f}s")
        print(f"    Events processed: {iterations}")
        print(f"    Throughput: {throughput:.0f}/sec")

        # AC-5: 100 executions/second
        assert throughput >= 100, f"Throughput too low: {throughput:.0f}/sec (requirement: >=100/sec)"

    @pytest.mark.asyncio
    async def test_execution_idempotency(self, execute_service: ExecuteService) -> None:
        """Benchmark execution idempotency - same input produces same output.

        AC-5: Execution should be idempotent (10 consecutive runs produce same result).
        """
        from src.domain.events.route_events import Routed

        session_id = f"idempotent-{uuid.uuid4().hex[:8]}"
        event = Routed(
            route_type="hash",
            session_id=session_id,
            task_context={
                "code": "x = 1 + 1; result = x",
                "business_event_type": "ToolExecuted",
            },
            route_target="docker-sandbox",
            route_score=0.95,
        )

        results: list[dict[str, Any]] = []

        for _ in range(10):
            executed = await execute_service.on_routed_event(event)
            if executed:
                results.append(
                    {
                        "status": executed.execution_result.get("status") if executed.execution_result else None,
                        "business_event_type": executed.business_event_type,
                        "route_target": executed.route_target,
                    }
                )

        print("\n  Execution Idempotency:")
        print(f"    Runs: {len(results)}")
        print(f"    Unique results: {len(set(str(r) for r in results))}")

        # All results should be identical
        assert len(results) == 10, f"Expected 10 runs, got {len(results)}"
        unique_results = set(str(r) for r in results)
        assert len(unique_results) == 1, f"Results not idempotent: {unique_results}"

    @pytest.mark.asyncio
    async def test_executed_event_serialization_latency(self) -> None:
        """Benchmark Executed event serialization.

        Should be fast (< 0.5ms per event).
        """
        from src.domain.events.execute_events import Executed

        event = Executed(
            session_id=f"serial-{uuid.uuid4().hex[:8]}",
            task_context={
                "code": "print('test')",
                "business_event_type": "ToolExecuted",
            },
            execution_result={"status": "completed", "output": "test"},
            cost_estimate=0.01,
            latency_ms=50.0,
            business_event_type="ToolExecuted",
            route_target="docker-sandbox",
            route_score=0.95,
        )

        def serialize_event() -> dict:
            return event.to_dict()

        result = benchmark_operation(serialize_event, iterations=10000, warmup=100)

        print("\n  Executed Event Serialization:")
        print(f"    Iterations: {result.iterations}")
        print(f"    Avg time: {result.avg_time_ms:.4f}ms")
        print(f"    P95 time: {result.p95_ms:.4f}ms")

        # Serialization should be fast (< 0.5ms)
        assert result.avg_time_ms < 0.5, f"Serialization too slow: {result.avg_time_ms:.4f}ms"

    def test_checkpoint_snapshot_serialization_latency(self) -> None:
        """Benchmark CheckpointSnapshot serialization.

        Should be fast (< 1ms per snapshot).
        """
        snapshot = CheckpointSnapshot(
            session_id=f"snap-serial-{uuid.uuid4().hex[:8]}",
            stage_id="completed",
            state_version=1,
            state_data={
                "execution_result": {"status": "completed"},
                "route_target": "docker-sandbox",
                "route_score": 0.95,
            },
        )

        def serialize_snapshot() -> dict:
            return snapshot.to_redis_hash()

        result = benchmark_operation(serialize_snapshot, iterations=10000, warmup=100)

        print("\n  CheckpointSnapshot Serialization:")
        print(f"    Iterations: {result.iterations}")
        print(f"    Avg time: {result.avg_time_ms:.4f}ms")
        print(f"    P95 time: {result.p95_ms:.4f}ms")

        # Serialization should be fast (< 1ms)
        assert result.avg_time_ms < 1.0, f"Serialization too slow: {result.avg_time_ms:.4f}ms"
