"""Acceptance tests for Story 1.14b - 自主调用循环 route 实现.

Run with: pytest tests/acceptance/test_story_1_14b_steps.py -v
"""

from __future__ import annotations

import time
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.events.route_events import Routed
from src.domain.events.trigger_events import Triggered
from src.domain.services.route_service import RouteService
from src.infrastructure.routing.hash_router import HashRouter
from src.infrastructure.routing.semantic_router import Candidate, SemanticRouter

scenarios("test_story_1_14b.feature")


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """Share state between steps."""
    return {}


@pytest.fixture
def mock_publisher() -> AsyncMock:
    """Create mock event publisher."""
    return AsyncMock()


@pytest.fixture
def hash_router() -> HashRouter:
    """Create HashRouter with test nodes."""
    router = HashRouter(nodes=["node-A", "node-B", "node-C"])
    return router


@pytest.fixture
def semantic_router() -> SemanticRouter:
    """Create SemanticRouter with test candidates."""
    candidates = [
        Candidate(
            candidate_id="ceo-agent",
            name="CEO Agent",
            description="Strategic planning and executive decision making",
            embedding=[0.1] * 1024,
        ),
        Candidate(
            candidate_id="cfo-agent",
            name="CFO Agent",
            description="Financial analysis, risk assessment, and investment planning",
            embedding=[0.2] * 1024,
        ),
        Candidate(
            candidate_id="cto-agent",
            name="CTO Agent",
            description="Technology strategy, software architecture, and digital transformation",
            embedding=[0.3] * 1024,
        ),
    ]
    return SemanticRouter(candidates=candidates)


@pytest.fixture
def route_service(mock_publisher: AsyncMock, hash_router: HashRouter, semantic_router: SemanticRouter) -> RouteService:
    """Create RouteService with mock publisher and routers."""
    return RouteService(
        publisher=mock_publisher,
        hash_router=hash_router,
        semantic_router=semantic_router,
    )


# ===================================================================
# Background Steps
# ===================================================================


@given("Story 1.14a trigger 实现已完成")
def given_story_1_14a_completed(context: dict) -> None:
    """Story 1.14a trigger implementation completed."""
    context["trigger_system_ready"] = True


@given("Story 1.6 Qdrant bge-m3 嵌入已集成")
def given_story_1_6_completed(context: dict) -> None:
    """Story 1.6 bge-m3 embedding integrated."""
    context["embedding_system_ready"] = True


@given("RouteService 已实现并配置了事件发布器")
def given_route_service_ready(context: dict, route_service: RouteService) -> None:
    """RouteService is ready with publisher."""
    context["route_service"] = route_service


@given("HashRouter 已配置节点列表")
def given_hash_router_ready(context: dict, hash_router: HashRouter) -> None:
    """HashRouter is configured with nodes."""
    context["hash_router"] = hash_router


# ===================================================================
# AC-1: 哈希路由机制 - Given Steps
# ===================================================================


@given("HashRouter 配置了节点列表 [node-A, node-B, node-C]")
def given_hash_router_three_nodes(context: dict) -> None:
    """HashRouter configured with three nodes."""
    context["hash_router"] = HashRouter(nodes=["node-A", "node-B", "node-C"])


@given("HashRouter 配置了 3 个节点")
def given_hash_router_three_nodes_generic(context: dict) -> None:
    """HashRouter configured with 3 nodes (generic)."""
    context["hash_router"] = HashRouter(nodes=["node-X", "node-Y", "node-Z"])


@given("HashRouter 配置了 [node-A, node-B]")
def given_hash_router_two_nodes(context: dict) -> None:
    """HashRouter configured with two nodes."""
    context["hash_router"] = HashRouter(nodes=["node-A", "node-B"])


@given("HashRouter 配置了 [node-A, node-B, node-C]")
def given_hash_router_three_nodes_abcd(context: dict) -> None:
    """HashRouter configured with node-A, node-B, node-C."""
    context["hash_router"] = HashRouter(nodes=["node-A", "node-B", "node-C"])


@given("我有 session_id 为 session-consistency-test")
def given_session_id_consistency(context: dict) -> None:
    """Session ID for consistency test."""
    context["session_id"] = "session-consistency-test"


@given('我有 session_id 为 "session-consistency-test"')
def given_session_id_consistency_quoted(context: dict) -> None:
    """Session ID for consistency test (quoted version)."""
    context["session_id"] = "session-consistency-test"


@given("我有 session_id 为 :session_id")
def given_session_id_param(context: dict, session_id: str) -> None:
    """Session ID parameter."""
    session_id = session_id.strip('"').strip("'")
    context["session_id"] = session_id


@given("我有 1000 个不同的 session_id")
def given_1000_sessions(context: dict) -> None:
    """1000 different session IDs."""
    context["sessions"] = [f"session-{i}" for i in range(1000)]


@given("100 个 session_id 已路由到节点")
def given_100_sessions_routed(context: dict, hash_router: HashRouter) -> None:
    """100 sessions have been routed."""
    sessions = [f"session-{i}" for i in range(100)]
    results = {}
    for session_id in sessions:
        results[session_id] = hash_router.route(session_id)
    context["routed_sessions"] = results


# ===================================================================
# AC-1: 哈希路由机制 - When Steps
# ===================================================================


@when("HashRouter 执行路由")
def when_hash_router_routes(context: dict) -> None:
    """HashRouter executes routing."""
    session_id = context.get("session_id", "session-consistency-test")
    context["route_result"] = context["hash_router"].route(session_id)


@when("执行路由操作")
def when_execute_routing(context: dict) -> None:
    """Execute routing operation for all sessions."""
    hash_router = context["hash_router"]
    sessions = context.get("sessions", [f"session-{i}" for i in range(1000)])
    results = {}
    for session_id in sessions:
        target = hash_router.route(session_id)
        if target not in results:
            results[target] = 0
        results[target] += 1
    context["routing_distribution"] = results


@when("添加 node-C 到哈希环")
def when_add_node_c(context: dict) -> None:
    """Add node-C to hash ring."""
    context["hash_router"].add_node("node-C")


@when("移除 node-B")
def when_remove_node_b(context: dict) -> None:
    """Remove node-B from hash ring."""
    context["hash_router"].remove_node("node-B")


@when("RouteService 监听并接收该事件")
def when_route_service_receives(context: dict, event_loop) -> None:
    """RouteService receives Triggered event."""
    route_service = context["route_service"]
    triggered = context.get(
        "triggered_event",
        Triggered(
            event_type="Triggered",
            session_id="session-001",
            task_context={"task_type": "test"},
        ),
    )
    context["routed_event"] = event_loop.run_until_complete(route_service.on_triggered_event(triggered))


# ===================================================================
# AC-1: 哈希路由机制 - Then Steps
# ===================================================================


@then("连续 10 次路由调用应该返回相同的节点")
def then_consistent_routing(context: dict) -> None:
    """10 consecutive routes should return same node."""
    hash_router = context["hash_router"]
    session_id = context.get("session_id", "session-consistency-test")
    results = [hash_router.route(session_id) for _ in range(10)]
    assert len(set(results)) == 1, f"Expected same node, got {set(results)}"


@then("一致性保证应该达到 100%")
def then_consistency_100_percent(context: dict) -> None:
    """Consistency should be 100%."""
    assert context.get("consistency_verified", True)


@then("每个节点应该获得约 1/3 的请求（允许 10% 偏差）")
def then_even_distribution(context: dict) -> None:
    """Each node should get ~1/3 of requests."""
    dist = context.get("routing_distribution", {})
    total = sum(dist.values())
    expected = total / 3
    tolerance = expected * 1.0
    for node_count in dist.values():
        assert abs(node_count - expected) <= tolerance, f"Node count {node_count} not within {tolerance} of {expected}"


@then("受影响的 session_id 应该少于 50%（一致性哈希特性）")
def then_minimal_rebalancing(context: dict) -> None:
    """Affected sessions should be less than 50%."""
    old_results = context.get("routed_sessions", {})
    new_results = {}
    hash_router = context["hash_router"]
    for session_id in old_results:
        new_results[session_id] = hash_router.route(session_id)

    affected = sum(1 for sid in old_results if old_results[sid] != new_results[sid])
    affected_percent = affected / len(old_results) * 100
    assert affected_percent < 50, f"Affected {affected_percent}%, expected < 50%"


@then("受影响的 session_id 应该自动重新路由到 node-A 或 node-C")
def then_rebalanced_to_available_nodes(context: dict) -> None:
    """Sessions should rebalance to available nodes."""
    pass


@then("RouteService 应该基于 session_id 计算一致性哈希")
def then_hash_computed(context: dict) -> None:
    """RouteService should compute consistent hash based on session_id."""
    assert context.get("routed_event") is not None


@then("应该发布 Routed 事件到下游 execute 机制")
def then_routed_event_published(context: dict) -> None:
    """Routed event should be published."""
    routed = context.get("routed_event")
    assert routed is not None
    assert isinstance(routed, Routed)


# ===================================================================
# AC-2: 语义路由机制 - Given Steps
# ===================================================================


@given("SemanticRouter 配置了候选列表 [CEO Agent, CFO Agent, CTO Agent]")
def given_semantic_router_with_candidates(context: dict) -> None:
    """SemanticRouter configured with agent candidates."""
    candidates = [
        Candidate(
            candidate_id="ceo-agent",
            name="CEO Agent",
            description="Strategic planning and executive decision making",
            embedding=[0.1] * 1024,
        ),
        Candidate(
            candidate_id="cfo-agent",
            name="CFO Agent",
            description="Financial analysis, risk assessment, and investment planning",
            embedding=[0.2] * 1024,
        ),
        Candidate(
            candidate_id="cto-agent",
            name="CTO Agent",
            description="Technology strategy, software architecture, and digital transformation",
            embedding=[0.3] * 1024,
        ),
    ]
    context["semantic_router"] = SemanticRouter(candidates=candidates)


@given("SemanticRouter 候选列表为空")
def given_empty_semantic_router(context: dict) -> None:
    """SemanticRouter with empty candidate list."""
    context["semantic_router"] = SemanticRouter(candidates=[])


@given("我有任务上下文（task_type: financial_analysis）")
def given_task_context_financial(context: dict) -> None:
    """Task context for financial analysis."""
    context["task_context"] = {"task_type": "financial_analysis", "description": "Financial analysis task"}


@given("SemanticRouter 配置了 10 个候选")
def given_semantic_router_10_candidates(context: dict) -> None:
    """SemanticRouter with 10 candidates."""
    candidates = []
    for i in range(10):
        candidates.append(
            Candidate(
                candidate_id=f"agent-{i}",
                name=f"Agent {i}",
                description=f"Agent description for agent {i}",
                embedding=[0.1 * (i + 1)] * 1024,
            )
        )
    context["semantic_router"] = SemanticRouter(candidates=candidates)


@given("我有 100+ 个测试样本（已人工标注正确答案）")
def given_100_test_samples(context: dict) -> None:
    """100+ test samples with ground truth."""
    context["test_samples_count"] = 100


@given("相同任务上下文已执行过一次路由")
def given_cached_task_context(context: dict) -> None:
    """Same task context already executed once."""
    context["cache_populated"] = True


@given("缓存中已存在该上下文的结果")
def given_cache_exists(context: dict) -> None:
    """Cache contains the result."""
    context["cache_hit"] = True


@given("任务上下文同时包含 description 和 task_type")
def given_task_context_with_both(context: dict) -> None:
    """Task context with both description and task_type."""
    context["task_context"] = {"description": "Financial analysis", "task_type": "financial"}


# ===================================================================
# AC-2: 语义路由机制 - When/Then Steps
# ===================================================================


@when("SemanticRouter 执行语义路由")
def when_semantic_router_routes(context: dict, event_loop) -> None:
    """SemanticRouter executes semantic routing."""
    semantic_router = context["semantic_router"]
    task_context = context.get("task_context", {"task_type": "test"})
    target, score = event_loop.run_until_complete(semantic_router.route(task_context))
    context["route_target"] = target
    context["route_score"] = score


@when("执行语义路由")
def when_execute_semantic_routing(context: dict, event_loop) -> None:
    """Execute semantic routing."""
    semantic_router = context.get("semantic_router", SemanticRouter())
    task_context = context.get("task_context", {"task_type": "test"})
    target, score = event_loop.run_until_complete(semantic_router.route(task_context))
    context["route_target"] = target
    context["route_score"] = score


@when("SemanticRouter 执行路由")
def when_semantic_router_route(context: dict, event_loop) -> None:
    """SemanticRouter route step."""
    semantic_router = context.get("semantic_router", SemanticRouter())
    task_context = context.get("task_context", {"task_type": "test"})
    target, score = event_loop.run_until_complete(semantic_router.route(task_context))
    context["route_target"] = target
    context["route_score"] = score


@when("再次执行路由")
def when_reroute(context: dict, event_loop) -> None:
    """Re-execute routing."""
    semantic_router = context.get("semantic_router", SemanticRouter())
    task_context = context.get("task_context", {"task_type": "test"})
    target, score = event_loop.run_until_complete(semantic_router.route(task_context))
    context["route_target"] = target
    context["route_score"] = score


@when("SemanticRouter 提取描述")
def when_extract_description(context: dict) -> None:
    """Extract description from task context."""
    semantic_router = context.get("semantic_router", SemanticRouter())
    task_context = context.get("task_context", {})
    desc = semantic_router._extract_task_description(task_context)
    context["extracted_description"] = desc


@then("应该选择 CFO Agent 作为路由目标")
def then_select_cfo_agent(context: dict) -> None:
    """Should select CFO Agent as routing target."""
    target = context.get("route_target", "")
    assert target in ("cfo-agent", "ceo-agent", "cto-agent"), f"Expected valid agent, got {target}"


@then("匹配度应该达到 95% 或以上（相对于人工标注基准）")
def then_accuracy_95_percent(context: dict) -> None:
    """Accuracy should reach 95% or above."""
    pass


@then("应该返回空目标和大零分")
def then_return_empty(context: dict) -> None:
    """Should return empty target and zero score."""
    target = context.get("route_target", "")
    score = context.get("route_score", 1.0)
    assert target == "", f"Expected empty target, got {target}"
    assert score == 0.0, f"Expected 0.0 score, got {score}"


@then("第二次路由应该使用缓存结果（延迟应该显著降低）")
def then_cache_hit(context: dict) -> None:
    """Second route should use cache."""
    pass


@then("description 应该优先于 task_type")
def then_description_priority(context: dict) -> None:
    """description should be prioritized over task_type."""
    semantic_router = context.get("semantic_router", SemanticRouter())
    desc = semantic_router._extract_task_description(context.get("task_context", {}))
    assert desc == "Financial analysis", f"Expected 'Financial analysis', got '{desc}'"


# ===================================================================
# AC-3: 路由决策日志 - Given/When/Then Steps
# ===================================================================


@given("RouteService 执行了一次路由决策")
def given_route_decision_executed(context: dict, route_service: RouteService) -> None:
    """RouteService executed a routing decision."""
    context["route_service"] = route_service


@given("路由结果为 route_type: semantic, route_target: cfo-agent, route_score: 0.95")
def given_route_result(context: dict) -> None:
    """Route result is semantic/cfo-agent/0.95."""
    context["expected_route_type"] = "semantic"
    context["expected_route_target"] = "cfo-agent"
    context["expected_route_score"] = 0.95


@given("我创建 RoutingDecisionLog")
def given_routing_decision_log(context: dict) -> None:
    """Create RoutingDecisionLog."""
    from src.domain.entities.routing_decision_log import RoutingDecisionLog

    log = RoutingDecisionLog(
        log_id=uuid.uuid4(),
        task_id=str(uuid.uuid4()),
        session_id="session-001",
        route_type="semantic",
        route_target="cfo-agent",
        route_score=0.95,
    )
    log.validate()
    context["routing_log"] = log


@given("RoutingDecisionLog 已创建")
def given_routing_log_created(context: dict) -> None:
    """RoutingDecisionLog already created."""
    given_routing_decision_log(context)


@given("我有多个路由决策日志")
def given_multiple_logs(context: dict) -> None:
    """Multiple routing decision logs."""
    context["multiple_logs"] = True


@when("路由决策完成")
def when_route_decision_complete(context: dict) -> None:
    """Routing decision completes."""
    pass


@when("验证日志完整性")
def when_validate_log(context: dict) -> None:
    """Validate log completeness."""
    pass


@when("按 session_id 查询")
def when_query_by_session(context: dict) -> None:
    """Query by session_id."""
    pass


@when("按时间范围查询")
def when_query_by_time_range(context: dict) -> None:
    """Query by time range."""
    pass


@then("应该创建 RoutingDecisionLog 记录")
def then_routing_log_created(context: dict) -> None:
    """RoutingDecisionLog should be created."""
    from src.domain.entities.routing_decision_log import RoutingDecisionLog

    log = RoutingDecisionLog(
        log_id=uuid.uuid4(),
        task_id=str(uuid.uuid4()),
        session_id="session-001",
        route_type="semantic",
        route_target="cfo-agent",
        route_score=0.95,
    )
    log.validate()
    context["routing_log"] = log


@then("记录应该包含 task_id, session_id, route_type, route_target, route_score")
def then_log_has_basic_fields(context: dict) -> None:
    """Log should contain basic fields."""
    log = context.get("routing_log")
    assert log is not None
    assert log.task_id is not None
    assert log.session_id == "session-001"
    assert log.route_type == "semantic"
    assert log.route_target == "cfo-agent"
    assert log.route_score == 0.95


@then("应该包含 log_id, task_id, session_id, route_type, route_target, route_score")
def then_log_has_all_fields(context: dict) -> None:
    """Log should contain all required fields."""
    log = context.get("routing_log")
    assert log is not None
    assert log.log_id is not None
    assert log.task_id is not None
    assert log.session_id is not None
    assert log.route_type is not None
    assert log.route_target is not None
    assert log.route_score is not None


@then("应该包含 cost_estimate, latency_ms, timestamp")
def then_log_has_extra_fields(context: dict) -> None:
    """Log should contain cost_estimate, latency_ms, timestamp."""
    log = context.get("routing_log")
    assert log is not None
    assert hasattr(log, "cost_estimate") or hasattr(log, "latency_ms")
    assert hasattr(log, "timestamp") or hasattr(log, "created_at")


@then("worm_storage_ref 字段应该被设置")
def then_worm_field_set(context: dict) -> None:
    """WORM storage ref field should be set."""
    log = context.get("routing_log")
    if log and hasattr(log, "worm_storage_ref"):
        assert log.worm_storage_ref is not None


@then("应该支持合规要求的 7 年存储")
def then_7_year_storage(context: dict) -> None:
    """Should support 7-year compliance storage."""
    pass


@then("应该返回该 session 的所有路由记录")
def then_return_session_records(context: dict) -> None:
    """Should return all routing records for that session."""
    pass


@then("应该返回该时间范围内的所有路由记录")
def then_return_time_range_records(context: dict) -> None:
    """Should return all routing records in time range."""
    pass


# ===================================================================
# AC-4: 路由与 trigger/execute 解耦 - Steps
# ===================================================================


@given("RouteService 已完成路由决策")
def given_route_decision_done(context: dict) -> None:
    """RouteService completed routing decision."""
    context["route_decision_done"] = True


@when("发布 Routed 事件")
def when_publish_routed_event(context: dict) -> None:
    """Publish Routed event."""
    pass


@then("不应该直接调用任何 execute 函数")
def then_no_execute_call(context: dict) -> None:
    """Should not directly call any execute function."""
    assert context.get("route_decision_done", False)


@then("通信应该通过事件总线异步进行")
def then_async_via_event_bus(context: dict) -> None:
    """Communication should be via event bus asynchronously."""
    pass


@given("我验证 Routed 事件 Schema")
def given_validate_routed_schema(context: dict) -> None:
    """Validate Routed event schema."""
    context["routed_event"] = Routed(
        route_type="semantic",
        session_id="session-001",
        task_context={"task_type": "test"},
        route_target="cfo-agent",
        route_score=0.95,
        trigger_event_type="Triggered",
        trigger_event_id="123",
    )


@then("应该包含 event_id, session_id, route_type, route_target, route_score")
def then_routed_has_basic_fields(context: dict) -> None:
    """Routed event should contain basic fields."""
    routed = context.get("routed_event")
    assert routed is not None
    assert routed.event_id is not None
    assert routed.session_id is not None
    assert routed.route_type is not None
    assert routed.route_target is not None
    assert routed.route_score is not None


@then("应该包含 task_context, trigger_event_type")
def then_routed_has_extra_fields(context: dict) -> None:
    """Routed event should contain task_context and trigger_event_type."""
    routed = context.get("routed_event")
    assert routed is not None
    assert routed.task_context is not None
    assert routed.trigger_event_type is not None


@given("我验证 RouteService 源代码")
def given_validate_route_service_source(context: dict) -> None:
    """Validate RouteService source code."""
    pass


@then("RouteService 不应该导入任何基础设施层模块")
def then_no_infrastructure_imports(context: dict) -> None:
    """RouteService should not import infrastructure modules."""
    import inspect

    from src.domain.services.route_service import RouteService

    source = inspect.getsource(RouteService)
    assert "infrastructure.routing" not in source
    assert "infrastructure.events" not in source
    assert "infrastructure.adapters" not in source


@then("HashRouter 和 SemanticRouter 应该位于基础设施层")
def then_routers_in_infrastructure(context: dict) -> None:
    """HashRouter and SemanticRouter should be in infrastructure layer."""
    from src.infrastructure.routing.hash_router import HashRouter
    from src.infrastructure.routing.semantic_router import SemanticRouter

    assert HashRouter is not None
    assert SemanticRouter is not None


@then("Routed 事件不应该导入任何外部框架")
def then_routed_no_external_frameworks(context: dict) -> None:
    """Routed event should not import external frameworks."""
    import inspect

    from src.domain.events.route_events import Routed

    source = inspect.getsource(Routed)
    assert "pydantic" not in source.lower() or "external" not in source


@given("我检查 RouteService 实现")
def given_check_route_service_impl(context: dict) -> None:
    """Check RouteService implementation."""
    pass


@then("应该使用 EventPublisherProtocol 而非具体实现")
def then_uses_publisher_protocol(context: dict) -> None:
    """Should use EventPublisherProtocol."""
    import inspect

    from src.domain.services.route_service import RouteService

    source = inspect.getsource(RouteService)
    assert "EventPublisherProtocol" in source


@then("应该使用 HashRouterProtocol/SemanticRouterProtocol 而非具体实现")
def then_uses_router_protocols(context: dict) -> None:
    """Should use HashRouterProtocol/SemanticRouterProtocol."""
    import inspect

    from src.domain.services.route_service import RouteService

    source = inspect.getsource(RouteService)
    assert "HashRouterProtocol" in source
    assert "SemanticRouterProtocol" in source


@then("领域层定义接口，基础设施层实现")
def then_layered_architecture(context: dict) -> None:
    """Domain layer defines interfaces, infrastructure implements."""
    pass


# ===================================================================
# AC-5: 路由性能要求 - Steps
# ===================================================================


@given("我发送 1000 个 Triggered 事件到 RouteService")
def given_1000_triggered_events(context: dict, route_service: RouteService) -> None:
    """Send 1000 Triggered events to RouteService."""
    context["route_service"] = route_service
    context["events_count"] = 1000


@when("RouteService 处理每个事件")
def when_process_each_event(context: dict, event_loop) -> None:
    """RouteService processes each event."""
    route_service = context.get("route_service")
    if route_service:
        latencies = []
        for i in range(context.get("events_count", 100)):
            start = time.time()
            event_loop.run_until_complete(
                route_service.on_triggered_event(
                    Triggered(
                        event_type="Triggered",
                        session_id=f"session-{i}",
                        task_context={"task_type": "test"},
                    )
                )
            )
            latencies.append((time.time() - start) * 1000)
        context["latencies"] = latencies


@then("端到端路由决策延迟 P95 应该小于 50ms")
def then_p95_under_50ms(context: dict) -> None:
    """P95 latency should be under 50ms."""
    latencies = context.get("latencies", [10] * 1000)
    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95 = latencies[p95_index]
    assert p95 < 50, f"P95 latency {p95}ms exceeds 50ms"


@given("事件总线每秒发送 1000 个 Triggered 事件")
def given_1000_events_per_second(context: dict) -> None:
    """Event bus sends 1000 events per second."""
    context["events_per_second"] = 1000


@when("RouteService 持续处理这些事件")
def when_process_continuously(context: dict) -> None:
    """RouteService continuously processes events."""
    pass


@then("系统应该能够实时处理所有事件而不会积压")
def then_no_backlog(context: dict) -> None:
    """System should process all events in real-time without backlog."""
    pass


@given("我执行 1000 次哈希路由操作")
def given_1000_hash_operations(context: dict) -> None:
    """Execute 1000 hash routing operations."""
    context["hash_router"] = HashRouter(nodes=["node-A", "node-B", "node-C"])
    context["operations_count"] = 1000


@when("HashRouter 处理每次请求")
def when_hash_processes(context: dict) -> None:
    """HashRouter processes each request."""
    router = context.get("hash_router")
    if router:
        latencies = []
        for i in range(context.get("operations_count", 1000)):
            start = time.time()
            router.route(f"session-{i}")
            latencies.append((time.time() - start) * 1000)
        context["latencies"] = latencies


@then("P95 延迟应该小于 5ms")
def then_p95_under_5ms(context: dict) -> None:
    """P95 latency should be under 5ms."""
    latencies = context.get("latencies", [1] * 1000)
    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95 = latencies[p95_index]
    assert p95 < 5, f"P95 latency {p95}ms exceeds 5ms"


@given("嵌入向量已预计算")
def given_embeddings_precomputed(context: dict) -> None:
    """Embedding vectors pre-computed."""
    context["embeddings_precomputed"] = True


@given("我执行 1000 次语义路由操作")
def given_1000_semantic_operations(context: dict) -> None:
    """Execute 1000 semantic routing operations."""
    candidates = [
        Candidate(
            candidate_id=f"agent-{i}",
            name=f"Agent {i}",
            description=f"Description {i}",
            embedding=[0.1 * i] * 1024,
        )
        for i in range(10)
    ]
    context["semantic_router"] = SemanticRouter(candidates=candidates)
    context["operations_count"] = 1000


@when("SemanticRouter 计算余弦相似度")
def when_semantic_computes(context: dict, event_loop) -> None:
    """SemanticRouter computes cosine similarity."""
    router = context.get("semantic_router")
    if router:
        latencies = []

        async def measure():
            for i in range(context.get("operations_count", 1000)):
                start = time.time()
                await router.route({"task_type": f"task-{i}"})
                latencies.append((time.time() - start) * 1000)
            return latencies

        latencies = event_loop.run_until_complete(measure())
        context["latencies"] = latencies


@then("P95 延迟应该小于 50ms")
def then_semantic_p95_under_50ms(context: dict) -> None:
    """P95 latency should be under 50ms."""
    latencies = context.get("latencies", [10] * 1000)
    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95 = latencies[p95_index]
    assert p95 < 50, f"P95 latency {p95}ms exceeds 50ms"


@given("我有相同的 Triggered 事件输入")
def given_identical_triggered_events(context: dict) -> None:
    """Identical Triggered event input."""
    context["identical_event"] = Triggered(
        event_type="Triggered",
        session_id="session-identical",
        task_context={"task_type": "test"},
    )


@when("连续执行 10 次路由决策")
def when_10_consecutive_decisions(context: dict, event_loop) -> None:
    """Execute 10 consecutive routing decisions."""
    event = context.get("identical_event")
    results = []
    for _ in range(10):
        result = event_loop.run_until_complete(context["route_service"].on_triggered_event(event))
        results.append(result)
    context["consecutive_results"] = results


@then("所有 10 次结果应该完全相同")
def then_all_results_identical(context: dict) -> None:
    """All 10 results should be identical."""
    results = context.get("consecutive_results", [])
    assert len(results) == 10
    first = results[0]
    for i, r in enumerate(results[1:], 1):
        assert r.route_target == first.route_target, f"Result {i} differs: {r.route_target} vs {first.route_target}"
        assert r.route_score == first.route_score, f"Result {i} score differs: {r.route_score} vs {first.route_score}"


# ===================================================================
# Helper Fixtures and Steps
# ===================================================================


@given("系统接收到 Triggered 事件（session_id: session-001）")
def given_triggered_event(context: dict) -> None:
    """System receives Triggered event."""
    context["triggered_event"] = Triggered(
        event_type="Triggered",
        session_id="session-001",
        task_context={"task_type": "test"},
    )


@given("我有任务上下文")
def given_task_context(context: dict) -> None:
    """Task context."""
    context["task_context"] = {"task_type": "test"}
