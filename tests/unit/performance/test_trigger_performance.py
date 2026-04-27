"""Performance benchmarks for trigger mechanism (AC-5: P95<10ms, 1000 events/sec)."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.events.base import DomainEvent
from src.domain.services.auto_trigger_service import AutoTriggerService


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
            asyncio.run(result)

    # Benchmark
    times_ms: list[float] = []
    start = time.perf_counter()

    for _ in range(iterations):
        iter_start = time.perf_counter()
        result = operation()
        if asyncio.iscoroutine(result):
            asyncio.run(result)
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


class TestTriggerPerformanceBenchmarks:
    """Performance benchmarks for trigger mechanism.

    AC-5 Requirements:
    - Trigger latency P95 < 10ms
    - Throughput: 1000 events/second
    """

    @pytest.fixture
    def trigger_service(self) -> AutoTriggerService:
        """Create AutoTriggerService with no-op publisher for benchmarking."""
        return AutoTriggerService(publisher=None)

    def test_trigger_context_creation_latency(self, trigger_service: AutoTriggerService) -> None:
        """Benchmark TriggerContext creation from domain event.

        AC-5: Trigger context extraction should be < 1ms per event.
        """
        event = DomainEvent(
            event_type="DocumentProcessed",
            payload={
                "session_id": "session-perf-test",
                "agent_id": "agent-001",
                "task_type": "document_ocr",
                "priority": "high",
            },
        )

        def extract_context() -> None:
            trigger_service.extract_context(event)

        result = benchmark_operation(extract_context, iterations=10000, warmup=100)

        print("\n  TriggerContext Creation:")
        print(f"    Iterations: {result.iterations}")
        print(f"    Total time: {result.total_time_seconds:.4f}s")
        print(f"    Avg time: {result.avg_time_ms:.4f}ms")
        print(f"    P95 time: {result.p95_ms:.4f}ms")
        print(f"    Throughput: {result.throughput_per_sec:.0f}/sec")

        # Context extraction should be very fast (< 1ms)
        assert result.avg_time_ms < 1.0, f"Context extraction too slow: {result.avg_time_ms:.4f}ms"

    @pytest.mark.asyncio
    async def test_trigger_service_event_processing_latency(self) -> None:
        """Benchmark AutoTriggerService event processing end-to-end.

        AC-5: P95 trigger latency should be < 10ms.
        """
        service = AutoTriggerService(publisher=None)

        event = DomainEvent(
            event_type="ToolExecuted",
            payload={
                "session_id": "session-latency-test",
                "agent_id": "agent-002",
                "tool_name": "web_search",
                "priority": "medium",
            },
        )

        async def process_event() -> AutoTriggered | None:
            return await service.on_domain_event(event)

        # Run benchmark
        iterations = 5000
        warmup = 100
        times_ms: list[float] = []

        # Warmup
        for _ in range(warmup):
            await process_event()

        # Benchmark
        start = time.perf_counter()
        for _ in range(iterations):
            iter_start = time.perf_counter()
            await process_event()
            iter_end = time.perf_counter()
            times_ms.append((iter_end - iter_start) * 1000)
        end = time.perf_counter()

        total_time = end - start
        avg_time = sum(times_ms) / len(times_ms)
        sorted_times = sorted(times_ms)
        p95_index = int(len(sorted_times) * 0.95)
        p95_time = sorted_times[p95_index]
        throughput = iterations / total_time if total_time > 0 else 0

        print("\n  AutoTriggerService Event Processing:")
        print(f"    Iterations: {iterations}")
        print(f"    Total time: {total_time:.4f}s")
        print(f"    Avg time: {avg_time:.4f}ms")
        print(f"    P95 time: {p95_time:.4f}ms")
        print(f"    Throughput: {throughput:.0f}/sec")

        # AC-5: P95 < 10ms
        assert p95_time < 10.0, f"P95 trigger latency too high: {p95_time:.4f}ms (requirement: <10ms)"

    @pytest.mark.asyncio
    async def test_trigger_throughput_1000_events_per_second(self) -> None:
        """Benchmark trigger throughput.

        AC-5: System should support 1000 events/second.
        """
        service = AutoTriggerService(publisher=None)

        event = DomainEvent(
            event_type="AgentDecided",
            payload={
                "session_id": "session-throughput-test",
                "agent_id": "agent-003",
                "routing_decision": "route-to-specialist",
            },
        )

        async def process_event() -> AutoTriggered | None:
            return await service.on_domain_event(event)

        # Run for 1 second and count events
        iterations = 0
        start = time.perf_counter()
        target_duration = 1.0  # 1 second

        while (time.perf_counter() - start) < target_duration:
            await process_event()
            iterations += 1

        actual_duration = time.perf_counter() - start
        throughput = iterations / actual_duration

        print("\n  Trigger Throughput:")
        print(f"    Duration: {actual_duration:.4f}s")
        print(f"    Events processed: {iterations}")
        print(f"    Throughput: {throughput:.0f}/sec")

        # AC-5: 1000 events/second
        assert throughput >= 1000, f"Throughput too low: {throughput:.0f}/sec (requirement: >=1000/sec)"

    def test_triggered_event_serialization_latency(self) -> None:
        """Benchmark AutoTriggered event serialization.

        Should be very fast (< 0.5ms per event).
        """
        event = AutoTriggered(
            trigger_type="domain_event",
            session_id="session-serialization-test",
            agent_id="agent-004",
            task_context={
                "task_type": "checkpoint_reached",
                "checkpoint_id": "cp-001",
                "priority": "high",
            },
            source_event_type="CheckpointReached",
            source_event_id=str(uuid.uuid4()),
        )

        def serialize_event() -> dict:
            return event.to_dict()

        result = benchmark_operation(serialize_event, iterations=10000, warmup=100)

        print("\n  AutoTriggered Event Serialization:")
        print(f"    Iterations: {result.iterations}")
        print(f"    Avg time: {result.avg_time_ms:.4f}ms")
        print(f"    P95 time: {result.p95_ms:.4f}ms")

        # Serialization should be fast (< 0.5ms)
        assert result.avg_time_ms < 0.5, f"Serialization too slow: {result.avg_time_ms:.4f}ms"

    def test_triggered_event_deserialization_latency(self) -> None:
        """Benchmark AutoTriggered event deserialization.

        Should be fast (< 1ms per event).
        """
        original = AutoTriggered(
            trigger_type="heartbeat",
            session_id="session-deserialization-test",
            task_context={
                "heartbeat_id": "hb-001",
                "wake_reason": "scheduled",
                "todo_items": ["task1", "task2"],
                "cost_budget": 100.0,
            },
            source_event_type="HeartbeatTriggered",
            source_event_id=str(uuid.uuid4()),
        )

        serialized = original.to_dict()

        def deserialize_event() -> AutoTriggered:
            return AutoTriggered.from_dict(serialized)  # type: ignore[return-value]

        result = benchmark_operation(deserialize_event, iterations=10000, warmup=100)

        print("\n  AutoTriggered Event Deserialization:")
        print(f"    Iterations: {result.iterations}")
        print(f"    Avg time: {result.avg_time_ms:.4f}ms")
        print(f"    P95 time: {result.p95_ms:.4f}ms")

        # Deserialization should be fast (< 1ms)
        assert result.avg_time_ms < 1.0, f"Deserialization too slow: {result.avg_time_ms:.4f}ms"
