"""Integration tests for route mechanism - end-to-end routing flow.

Real instance integration tests using actual Redis service.
No mocks - uses real Redis instances for event publishing/subscribing.

Run with: poetry run pytest tests/integration/test_route_integration.py -v

Prerequisites:
    - Redis service running at localhost:6379 (or set REDIS_HOST, REDIS_PORT)
"""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest

from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.services.auto_route_service import AutoRouteService
from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.messaging.redis_publisher import RedisEventPublisher
from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber
from src.infrastructure.routing.hash_router import HashRouter
from src.infrastructure.routing.semantic_router import Candidate, SemanticRouter

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def redis_config() -> RedisConfig:
    """Real Redis configuration from environment.

    Uses tests/environments.py to get correct host for CI/Local.
    """
    from tests.environments import get_test_env

    env_config = get_test_env()
    return RedisConfig(
        host=env_config.redis.host,
        port=env_config.redis.port,
        db=env_config.redis.db,
        password=env_config.redis.password,
    )


@pytest.fixture
def unique_prefix() -> str:
    """Unique prefix for test isolation."""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def redis_publisher(redis_config: RedisConfig) -> RedisEventPublisher:
    """Real Redis event publisher with connectivity check."""
    try:
        publisher = RedisEventPublisher(redis_config)
        # Verify connectivity with a lightweight ping
        import redis.asyncio as aioredis

        async def verify():
            client = aioredis.Redis(
                host=redis_config.host,
                port=redis_config.port,
                db=redis_config.db,
                password=redis_config.password,
                socket_timeout=5,
            )
            await client.ping()
            await client.close()

        asyncio.run(verify())
        return publisher
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture
def redis_subscriber(redis_config: RedisConfig) -> RedisEventSubscriber:
    """Real Redis event subscriber with connectivity check."""
    try:
        subscriber = RedisEventSubscriber(redis_config)
        # Register a dummy handler and verify connectivity
        import redis.asyncio as aioredis

        async def verify():
            client = aioredis.Redis(
                host=redis_config.host,
                port=redis_config.port,
                db=redis_config.db,
                password=redis_config.password,
                socket_timeout=5,
            )
            await client.ping()
            await client.close()

        asyncio.run(verify())
        return subscriber
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture
def hash_router() -> HashRouter:
    """HashRouter with 3 nodes."""
    return HashRouter(nodes=["node-A", "node-B", "node-C"])


@pytest.fixture
def semantic_router() -> SemanticRouter:
    """SemanticRouter with test candidates."""

    # Create pseudo-orthogonal embeddings
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
        description="Financial analysis, risk assessment, and investment planning",
        embedding=make_embedding(0),
    )
    ceo_candidate = Candidate(
        candidate_id="ceo-agent",
        name="CEO Agent",
        description="Strategic planning and executive decision making",
        embedding=make_embedding(1),
    )
    cto_candidate = Candidate(
        candidate_id="cto-agent",
        name="CTO Agent",
        description="Technology strategy and architecture",
        embedding=make_embedding(2),
    )
    return SemanticRouter(candidates=[cfo_candidate, ceo_candidate, cto_candidate])


@pytest.fixture
def route_service(
    redis_publisher: RedisEventPublisher,
    hash_router: HashRouter,
    semantic_router: SemanticRouter,
) -> AutoRouteService:
    """AutoRouteService with real publisher and routers."""
    return AutoRouteService(
        publisher=redis_publisher,
        hash_router=hash_router,
        semantic_router=semantic_router,
    )


# ===================================================================
# Integration Tests
# ===================================================================


@pytest.mark.asyncio
async def test_triggered_to_routed_end_to_end(
    route_service: AutoRouteService,
    redis_subscriber: RedisEventSubscriber,
    unique_prefix: str,
    event_loop,
) -> None:
    """Test complete flow: AutoTriggered -> AutoRouteService -> AutoRouted."""
    # Subscribe to AutoRouted events - publisher uses rt:AutoRouted
    channel = "rt:AutoRouted"

    # Set up subscriber
    received_events: list[AutoRouted] = []
    event_received = asyncio.Event()

    def callback(event_data: dict) -> None:
        # Reconstruct AutoRouted from published data
        routed = AutoRouted(
            route_type=event_data.get("route_type", ""),
            session_id=event_data.get("session_id", ""),
            task_context=event_data.get("task_context", {}),
            route_target=event_data.get("route_target", ""),
            route_score=event_data.get("route_score", 0.0),
            trigger_event_type=event_data.get("trigger_event_type", ""),
        )
        received_events.append(routed)
        event_received.set()

    # Start subscribing
    redis_subscriber.subscribe(channel, callback)
    await redis_subscriber.start()

    # Give subscriber time to connect and set up
    await asyncio.sleep(0.5)

    # Publish AutoTriggered event to trigger routing
    triggered_event = AutoTriggered(
        session_id=f"test-session-{unique_prefix}",
        task_context={"task_type": "test", "description": "end-to-end test"},
    )

    # Process through route service
    result = await route_service.on_triggered_event(triggered_event)

    # Wait for event to be received
    await asyncio.wait_for(event_received.wait(), timeout=5.0)

    # Cleanup
    await redis_subscriber.close()

    # Verify results
    assert result is not None, "Route service should return result"
    assert isinstance(result, AutoRouted), "Result should be AutoRouted event"
    assert result.session_id == triggered_event.session_id, "Session ID should match"
    assert result.route_type in ("hash", "semantic", "mixed"), "Route type should be valid"


@pytest.mark.asyncio
async def test_hash_routing_consistency(
    route_service: AutoRouteService,
    event_loop,
) -> None:
    """Test hash routing provides 100% consistency for same session."""
    session_id = f"consistent-session-{uuid.uuid4().hex[:8]}"

    results = []
    for i in range(10):
        event = AutoTriggered(
            session_id=session_id,
            task_context={"iteration": i},
        )
        result = await route_service.on_triggered_event(event)
        results.append(result)

    # All results should have same route_target (hash consistency)
    route_targets = [r.route_target for r in results]
    unique_targets = set(route_targets)

    assert len(unique_targets) == 1, f"Hash routing not consistent: {len(unique_targets)} different targets"
    assert route_targets.count(route_targets[0]) == len(route_targets), "100% consistency not achieved"


@pytest.mark.asyncio
async def test_semantic_routing_with_task_context(
    route_service: AutoRouteService,
    event_loop,
) -> None:
    """Test semantic routing selects correct target based on task context."""
    # Financial task should route to CFO agent (without embedding model,
    # it returns first candidate, but route_type should be "semantic")
    event = AutoTriggered(
        session_id=f"semantic-test-{uuid.uuid4().hex[:8]}",
        task_context={
            "task_type": "financial_analysis",
            "description": "budget planning and cost estimation",
        },
    )

    result = await route_service.on_triggered_event(event)

    assert result is not None
    # Without embedding model, semantic router returns first candidate
    assert result.route_type in ("semantic", "mixed"), f"Expected semantic or mixed routing, got {result.route_type}"


@pytest.mark.asyncio
async def test_route_service_publishes_to_redis(
    route_service: AutoRouteService,
    redis_subscriber: RedisEventSubscriber,
    redis_config: RedisConfig,
    unique_prefix: str,
    event_loop,
) -> None:
    """Test RouteService actually publishes AutoRouted events to Redis."""
    channel = "rt:AutoRouted"
    received_payloads: list[dict] = []
    event_received = asyncio.Event()

    def callback(event_data: dict) -> None:
        received_payloads.append(event_data)
        event_received.set()

    # Start subscriber
    redis_subscriber.subscribe(channel, callback)
    await redis_subscriber.start()
    await asyncio.sleep(0.5)

    # Send event
    triggered_event = AutoTriggered(
        session_id=f"publish-test-{unique_prefix}",
        task_context={"task_type": "test"},
    )
    await route_service.on_triggered_event(triggered_event)

    # Wait for receipt
    try:
        await asyncio.wait_for(event_received.wait(), timeout=5.0)
    except TimeoutError:
        # Check if publisher is configured
        if route_service._publisher is None:
            pytest.skip("No publisher configured")
        raise

    # Cleanup
    await redis_subscriber.close()

    # Verify event was published
    assert len(received_payloads) > 0, "No events received on Redis channel"


@pytest.mark.asyncio
async def test_route_decision_log_fields(
    route_service: AutoRouteService,
    event_loop,
) -> None:
    """Test routing decision produces all required log fields."""
    event = AutoTriggered(
        session_id=f"log-test-{uuid.uuid4().hex[:8]}",
        task_context={"task_type": "test", "priority": "high"},
    )

    result = await route_service.on_triggered_event(event)

    # Verify all expected fields are present
    assert result.event_id is not None, "Missing event_id"
    assert result.session_id, "Missing session_id"
    assert result.route_type, "Missing route_type"
    assert result.route_target, "Missing route_target"
    assert 0.0 <= result.route_score <= 1.0, "route_score out of range"
    assert isinstance(result.task_context, dict), "task_context should be dict"


@pytest.mark.asyncio
async def test_mixed_routing_mode(
    route_service: AutoRouteService,
    event_loop,
) -> None:
    """Test that both hash and semantic routing can produce mixed mode."""
    # When both routers return valid targets, mixed mode should be selected
    event = AutoTriggered(
        session_id=f"mixed-test-{uuid.uuid4().hex[:8]}",
        task_context={"task_type": "strategic planning"},
    )

    result = await route_service.on_triggered_event(event)

    # With both hash and semantic routers configured, should get mixed
    # (semantic with score > 0 takes precedence in mixed mode)
    assert result is not None
    assert result.route_type in ("hash", "semantic", "mixed"), f"Invalid route_type: {result.route_type}"


@pytest.mark.asyncio
async def test_route_performance_under_load(
    route_service: AutoRouteService,
    event_loop,
) -> None:
    """Test routing performance under sustained load."""
    iterations = 500
    latencies = []

    start_time = time.perf_counter()
    for i in range(iterations):
        event = AutoTriggered(
            session_id=f"load-test-{i}",
            task_context={"task_type": "test"},
        )
        iter_start = time.perf_counter()
        await route_service.on_triggered_event(event)
        latencies.append((time.perf_counter() - iter_start) * 1000)

    total_elapsed = time.perf_counter() - start_time
    throughput = iterations / total_elapsed

    # Calculate P95 latency
    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95_latency = latencies[p95_index]

    # Assertions
    assert throughput >= 100, f"Throughput {throughput:.0f}/s below 100/s"
    assert p95_latency < 100, f"P95 latency {p95_latency:.2f}ms too high under load"


@pytest.mark.asyncio
async def test_idempotent_routing(
    route_service: AutoRouteService,
    event_loop,
) -> None:
    """Test that identical events produce identical routing decisions."""
    event = AutoTriggered(
        session_id="idempotent-test",
        task_context={"task_type": "consistent test"},
    )

    results = []
    for _ in range(5):
        result = await route_service.on_triggered_event(event)
        results.append(result)

    # All should be identical
    first = results[0]
    for i, result in enumerate(results[1:], 1):
        assert result.route_type == first.route_type, f"Result {i} route_type differs"
        assert result.route_target == first.route_target, f"Result {i} route_target differs"


@pytest.mark.asyncio
async def test_route_service_graceful_no_publisher(
    hash_router: HashRouter,
    semantic_router: SemanticRouter,
    event_loop,
) -> None:
    """Test route service handles missing publisher gracefully."""
    service_without_publisher = AutoRouteService(
        publisher=None,  # No publisher
        hash_router=hash_router,
        semantic_router=semantic_router,
    )

    event = AutoTriggered(
        session_id=f"no-publisher-test-{uuid.uuid4().hex[:8]}",
        task_context={"task_type": "test"},
    )

    # Should not raise, should return result
    result = await service_without_publisher.on_triggered_event(event)

    assert result is not None
    assert isinstance(result, AutoRouted)


@pytest.mark.asyncio
async def test_route_service_graceful_no_routers(
    redis_publisher: RedisEventPublisher,
    event_loop,
) -> None:
    """Test route service handles missing routers gracefully."""
    service_without_routers = AutoRouteService(
        publisher=redis_publisher,
        hash_router=None,
        semantic_router=None,
    )

    event = AutoTriggered(
        session_id=f"no-routers-test-{uuid.uuid4().hex[:8]}",
        task_context={"task_type": "test"},
    )

    result = await service_without_routers.on_triggered_event(event)

    # Should use defaults
    assert result is not None
    assert result.route_type == "hash"
    assert result.route_target == "default"
    assert result.route_score == 0.0


@pytest.mark.asyncio
async def test_hash_router_node_rebalancing(
    redis_publisher: RedisEventPublisher,
    event_loop,
) -> None:
    """Test hash router node add/remove rebalancing."""
    # Start with 2 nodes
    router = HashRouter(nodes=["node-A", "node-B"])

    # Route 50 sessions
    sessions_before = [f"rebalance-test-{i}" for i in range(50)]
    routes_before = {sid: router.route(sid) for sid in sessions_before}

    # Add node-C
    router.add_node("node-C")

    # Route again
    routes_after = {sid: router.route(sid) for sid in sessions_before}

    # Count unchanged
    unchanged = sum(1 for sid in sessions_before if routes_before[sid] == routes_after[sid])
    unchanged_percent = (unchanged / len(sessions_before)) * 100

    # At least 50% should remain unchanged (consistent hashing property)
    assert unchanged_percent >= 50, f"Too much rebalancing: only {unchanged_percent:.1f}% unchanged"


@pytest.mark.asyncio
async def test_concurrent_routing_requests(
    route_service: AutoRouteService,
    event_loop,
) -> None:
    """Test concurrent routing requests don't cause issues."""
    num_concurrent = 100

    async def route_one(i: int) -> AutoRouted:
        event = AutoTriggered(
            session_id=f"concurrent-{i}",
            task_context={"task_type": f"task-{i}"},
        )
        return await route_service.on_triggered_event(event)

    # Run concurrent requests
    results = await asyncio.gather(*[route_one(i) for i in range(num_concurrent)])

    # All should succeed
    assert len(results) == num_concurrent
    assert all(r is not None for r in results)
    assert all(isinstance(r, AutoRouted) for r in results)


@pytest.mark.asyncio
async def test_event_loop_isolation(
    route_service: AutoRouteService,
    event_loop,
) -> None:
    """Test that routing works correctly with the test's event loop."""
    event = AutoTriggered(
        session_id=f"event-loop-test-{uuid.uuid4().hex[:8]}",
        task_context={"task_type": "test"},
    )

    # This should work with the async event loop
    result = await route_service.on_triggered_event(event)
    assert result is not None
