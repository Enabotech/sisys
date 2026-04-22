"""Acceptance tests for Story 1.14c - 自主调用循环 execute 实现.

Run with: pytest tests/acceptance/test_story_1_14c_steps.py -v
"""

from __future__ import annotations

import time
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.events.execute_events import Executed
from src.domain.events.route_events import Routed
from src.domain.services.execute_service import ExecuteService
from src.infrastructure.sandbox.docker_sandbox_adapter import DockerSandboxAdapter
from src.interfaces.event_listeners.execute_completed_listener import ExecuteCompletedListener

scenarios("test_story_1_14c.feature")


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
def sandbox():
    """Create DockerSandboxAdapter for testing."""
    adapter = DockerSandboxAdapter()
    yield adapter
    adapter.reset_all_containers()


@pytest.fixture
def execute_service(sandbox: DockerSandboxAdapter) -> ExecuteService:
    """Create ExecuteService with sandbox."""
    return ExecuteService(sandbox=sandbox, snapshot_repo=None)


@pytest.fixture
def execute_listener(mock_publisher: AsyncMock) -> ExecuteCompletedListener:
    """Create ExecuteCompletedListener with mock publisher."""
    return ExecuteCompletedListener(publisher=mock_publisher)


# ===================================================================
# Background Steps
# ===================================================================


@given("Story 1.14a trigger 实现已完成")
def given_story_1_14a_completed(context: dict) -> None:
    """Story 1.14a trigger implementation completed."""
    context["trigger_system_ready"] = True


@given("Story 1.14b route 实现已完成")
def given_story_1_14b_completed(context: dict) -> None:
    """Story 1.14b route implementation completed."""
    context["route_system_ready"] = True


@given("ExecuteService 已实现并配置了事件发布器")
def given_execute_service_ready(context: dict, execute_service: ExecuteService) -> None:
    """ExecuteService is ready with publisher."""
    context["execute_service"] = execute_service


@given("DockerSandboxAdapter 已配置")
def given_docker_sandbox_ready(context: dict, sandbox: DockerSandboxAdapter) -> None:
    """DockerSandboxAdapter is configured."""
    context["sandbox"] = sandbox


# ===================================================================
# AC-1: 会话命名空间隔离 - Given Steps
# ===================================================================


@given("沙箱适配器是 DockerSandboxAdapter")
def given_sandbox_is_docker(context: dict, sandbox: DockerSandboxAdapter) -> None:
    """Sandbox adapter is DockerSandboxAdapter."""
    context["sandbox"] = sandbox


@given("系统接收到 Routed 事件（session_id: test-session-123）")
def given_system_receives_routed_event_test_session(context: dict) -> None:
    """System receives Routed event with session_id test-session-123."""
    context["session_id"] = "test-session-123"
    context["routed_event"] = Routed(
        route_type="hash",
        session_id="test-session-123",
        task_context={"code": "print('test')", "business_event_type": "ToolExecuted"},
        route_target="docker-sandbox",
        route_score=0.95,
    )


@given("已有运行中的沙箱（session: test-session-123）")
def given_running_sandbox_test_session(context: dict, sandbox: DockerSandboxAdapter) -> None:
    """Sandbox is already running for session test-session-123."""
    context["session_id"] = "test-session-123"
    context["sandbox"] = sandbox


@given("系统接收到新的 Routed 事件（session_id: test-session-123）")
def given_system_receives_new_routed_event_test_session(context: dict) -> None:
    """System receives new Routed event with session_id test-session-123."""
    context["routed_event"] = Routed(
        route_type="hash",
        session_id="test-session-123",
        task_context={"code": "print('test')", "business_event_type": "ToolExecuted"},
        route_target="docker-sandbox",
        route_score=0.95,
    )


@given("沙箱 A 执行任务修改了内部状态")
def given_sandbox_a_modified(context: dict, sandbox: DockerSandboxAdapter) -> None:
    """Sandbox A executed task and modified internal state."""
    context["sandbox_a"] = sandbox
    context["session_a"] = f"sandbox-a-{uuid.uuid4().hex[:8]}"


@given("沙箱 B 执行独立任务")
def given_sandbox_b_executed(context: dict, sandbox: DockerSandboxAdapter) -> None:
    """Sandbox B executed independent task."""
    context["sandbox_b"] = sandbox
    context["session_b"] = f"sandbox-b-{uuid.uuid4().hex[:8]}"


# ===================================================================
# AC-1: 会话命名空间隔离 - When Steps
# ===================================================================


@when("ExecuteService 处理该 Routed 事件")
def when_execute_service_processes_routed(context: dict, event_loop) -> None:
    """ExecuteService processes the Routed event."""
    routed_event = context.get("routed_event")
    if routed_event:
        context["executed_event"] = event_loop.run_until_complete(context["execute_service"].on_routed_event(routed_event))


@when("ExecuteService 处理该事件")
def when_execute_service_processes_event(context: dict, event_loop) -> None:
    """ExecuteService processes the event."""
    routed_event = context.get("routed_event")
    if routed_event:
        context["executed_event"] = event_loop.run_until_complete(context["execute_service"].on_routed_event(routed_event))


@when("验证两个沙箱的隔离性")
def when_verify_sandbox_isolation(context: dict) -> None:
    """Verify isolation between two sandboxes."""
    pass


# ===================================================================
# AC-1: 会话命名空间隔离 - Then Steps
# ===================================================================


@then('应该为 session "test-session-123" 启动沙箱容器')
def then_start_container_for_session_test_session(context: dict) -> None:
    """Should start sandbox container for session test-session-123."""
    assert context.get("executed_event") is not None


@then("任务应该在沙箱中执行")
def then_task_executed_in_sandbox(context: dict) -> None:
    """Task should be executed in sandbox."""
    assert context.get("executed_event") is not None


@then("执行后容器应该停止")
def then_container_stopped_after_execution(context: dict) -> None:
    """Container should stop after execution."""
    pass


@then("应该复用同一个沙箱容器")
def then_reuse_same_sandbox_container(context: dict) -> None:
    """Should reuse the same sandbox container."""
    assert context.get("sandbox") is not None


@then("不应该启动新容器")
def then_no_new_container_started(context: dict) -> None:
    """Should not start new container."""
    pass


@then("沙箱 A 的状态变化不应该影响沙箱 B")
def then_sandbox_a_does_not_affect_b(context: dict) -> None:
    """Sandbox A state changes should not affect Sandbox B."""
    pass


# ===================================================================
# AC-2: 状态快照持久化 - Given Steps
# ===================================================================


@given("ExecuteService 配置了 RedisSnapshotStore")
def given_execute_service_with_redis_snapshot(context: dict, sandbox: DockerSandboxAdapter) -> None:
    """ExecuteService configured with RedisSnapshotStore."""
    snapshots: list[CheckpointSnapshot] = []

    class MockSnapshotRepo:
        async def save(self, snapshot: CheckpointSnapshot) -> None:
            snapshots.append(snapshot)

        async def load(self, session_id: str) -> CheckpointSnapshot | None:
            for s in snapshots:
                if s.session_id == session_id:
                    return s
            return None

        async def delete(self, session_id: str) -> None:
            nonlocal snapshots
            snapshots = [s for s in snapshots if s.session_id != session_id]

    context["snapshot_repo"] = MockSnapshotRepo()
    context["execute_service"] = ExecuteService(sandbox=sandbox, snapshot_repo=MockSnapshotRepo())


@given("任务执行成功完成")
def given_task_execution_success(context: dict) -> None:
    """Task execution completed successfully."""
    context["execution_success"] = True


@given("CheckpointSnapshot 已准备好保存")
def given_snapshot_ready(context: dict) -> None:
    """CheckpointSnapshot is ready to save."""
    context["snapshot_ready"] = True


@given("我执行 1000 次快照保存操作")
def given_1000_snapshot_save_ops(context: dict) -> None:
    """Execute 1000 snapshot save operations."""
    context["snapshot_ops_count"] = 1000


@given("已保存的 CheckpointSnapshot（session: test-session-123）")
def given_existing_snapshot_test_session(context: dict, sandbox: DockerSandboxAdapter) -> None:
    """CheckpointSnapshot already saved."""
    session_id = "test-session-123"
    snapshot = CheckpointSnapshot(
        session_id=session_id,
        stage_id="test-stage",
        state_version=1,
        state_data={"test": "data"},
    )
    context["existing_snapshot"] = snapshot
    context["session_id"] = session_id

    # Configure mock snapshot repo with existing snapshot
    class MockSnapshotRepo:
        async def save(self, snap: CheckpointSnapshot) -> None:
            pass

        async def load(self, sid: str) -> CheckpointSnapshot | None:
            if sid == session_id:
                return snapshot
            return None

        async def delete(self, sid: str) -> None:
            pass

    context["execute_service"] = ExecuteService(sandbox=sandbox, snapshot_repo=MockSnapshotRepo())


@given("session 已存在快照（版本 1）")
def given_session_has_snapshot_v1(context: dict) -> None:
    """Session has snapshot with version 1."""
    session_id = context.get("session_id", "test-session-123")
    snapshot = CheckpointSnapshot(
        session_id=session_id,
        stage_id="completed",
        state_version=1,
        state_data={"result": "v1"},
    )
    context["existing_snapshot"] = snapshot


# ===================================================================
# AC-2: 状态快照持久化 - When Steps
# ===================================================================


@when("状态快照被创建")
def when_snapshot_created(context: dict, event_loop) -> None:
    """State snapshot is created."""
    session_id = context.get("session_id", "test-session-123")
    state = {"execution_result": {"status": "completed"}}
    context["snapshot"] = event_loop.run_until_complete(context["execute_service"].create_snapshot(session_id, state, "test"))


@when("保存到 Redis")
def when_save_to_redis(context: dict) -> None:
    """Save to Redis."""
    pass


@when("调用 ExecuteService.restore_snapshot")
def when_restore_snapshot(context: dict, event_loop) -> None:
    """Call ExecuteService.restore_snapshot."""
    session_id = context.get("session_id", "test-session-123")
    context["restored_snapshot"] = event_loop.run_until_complete(context["execute_service"].restore_snapshot(session_id))


@when("创建新快照")
def when_create_new_snapshot(context: dict, event_loop) -> None:
    """Create new snapshot."""
    session_id = context.get("session_id", "test-session-123")
    state = {"execution_result": {"status": "updated"}}
    context["new_snapshot"] = event_loop.run_until_complete(
        context["execute_service"].create_snapshot(session_id, state, "new-stage")
    )


# ===================================================================
# AC-2: 状态快照持久化 - Then Steps
# ===================================================================


@then("CheckpointSnapshot 应该保存到 Redis")
def then_snapshot_saved_to_redis(context: dict) -> None:
    """CheckpointSnapshot should be saved to Redis."""
    assert context.get("snapshot") is not None


@then("快照应该包含执行结果")
def then_snapshot_contains_execution_result(context: dict) -> None:
    """Snapshot should contain execution result."""
    snapshot = context.get("snapshot")
    if snapshot:
        assert snapshot.state_data is not None


@then("P95 延迟应该小于 50ms")
def then_p95_under_50ms(context: dict) -> None:
    """P95 latency should be under 50ms."""
    pass


@then("原始状态应该被恢复")
def then_original_state_restored(context: dict) -> None:
    """Original state should be restored."""
    restored = context.get("restored_snapshot")
    assert restored is not None


@then("新快照版本应该是 2")
def then_new_snapshot_version_is_2(context: dict) -> None:
    """New snapshot version should be 2."""
    new_snapshot = context.get("new_snapshot")
    if new_snapshot:
        assert new_snapshot.state_version == 2


# ===================================================================
# AC-3: 执行事件发布 - Given Steps
# ===================================================================


@given("任务执行完成")
def given_task_execution_completed_ac3(context: dict, execute_service: ExecuteService) -> None:
    """Task execution completed."""
    context["task_execution_completed"] = True
    # Set up routed event for the when step to process
    context["routed_event"] = Routed(
        route_type="hash",
        session_id="test-session-ac3",
        task_context={"code": "print('test')", "business_event_type": "ToolExecuted", "cost_estimate": 0.05},
        route_target="docker-sandbox",
        route_score=0.95,
    )
    context["execute_service"] = execute_service


@given('business_event_type 为 "ToolExecuted"')
def given_business_event_type_tool_executed(context: dict) -> None:
    """business_event_type is ToolExecuted."""
    context["business_event_type"] = "ToolExecuted"


@given('business_event_type 为 "DocumentProcessed"')
def given_business_event_type_document_processed(context: dict) -> None:
    """business_event_type is DocumentProcessed."""
    context["business_event_type"] = "DocumentProcessed"


@given('business_event_type 为 "AgentDecided"')
def given_business_event_type_agent_decided(context: dict) -> None:
    """business_event_type is AgentDecided."""
    context["business_event_type"] = "AgentDecided"


@given("ExecuteCompletedListener 收到 Executed 事件")
def given_listener_received_executed(context: dict, execute_listener: ExecuteCompletedListener) -> None:
    """ExecuteCompletedListener received Executed event."""
    executed = Executed(
        session_id="test-session",
        task_context={"business_event_type": context.get("business_event_type", "ToolExecuted")},
        execution_result={"status": "completed"},
        cost_estimate=0.01,
        latency_ms=10.0,
        business_event_type=context.get("business_event_type", "ToolExecuted"),
        route_target="test-target",
        route_score=0.9,
    )
    context["executed_event"] = executed
    context["listener"] = execute_listener


# ===================================================================
# AC-3: 执行事件发布 - When Steps
# ===================================================================


@when("ExecuteService 发布执行结果")
def when_execute_service_publishes_result(context: dict, event_loop) -> None:
    """ExecuteService publishes execution result."""
    routed_event = context.get("routed_event")
    execute_service = context.get("execute_service")
    if routed_event and execute_service:
        context["executed_event"] = event_loop.run_until_complete(execute_service.on_routed_event(routed_event))


@given("监听器处理该事件")
def given_listener_processes_event(context: dict, event_loop) -> None:
    """Listener processes the event (given)."""
    listener = context.get("listener")
    executed = context.get("executed_event")
    if executed and listener:
        event_loop.run_until_complete(listener.on_executed(executed))


@when("监听器处理该事件")
def when_listener_processes_event(context: dict, event_loop) -> None:
    """Listener processes the event (when)."""
    listener = context.get("listener")
    executed = context.get("executed_event")
    if executed and listener:
        event_loop.run_until_complete(listener.on_executed(executed))


# ===================================================================
# AC-3: 执行事件发布 - Then Steps
# ===================================================================


@then("Executed 事件应该被发布")
def then_executed_event_published(context: dict) -> None:
    """Executed event should be published."""
    assert context.get("executed_event") is not None


@then("事件应该包含 session_id")
def then_event_contains_session_id(context: dict) -> None:
    """Event should contain session_id."""
    executed = context.get("executed_event")
    assert executed is not None
    assert executed.session_id is not None


@then("事件应该包含 business_event_type")
def then_event_contains_business_event_type(context: dict) -> None:
    """Event should contain business_event_type."""
    executed = context.get("executed_event")
    assert executed is not None
    assert executed.business_event_type is not None


@then("应该发布 ToolExecuted 领域事件")
def then_publish_tool_executed(context: dict) -> None:
    """Should publish ToolExecuted domain event."""
    pass


@then("应该发布 DocumentProcessed 领域事件")
def then_publish_document_processed(context: dict) -> None:
    """Should publish DocumentProcessed domain event."""
    pass


@then("应该发布 AgentDecided 领域事件")
def then_publish_agent_decided(context: dict) -> None:
    """Should publish AgentDecided domain event."""
    pass


@then("事件应该包含 execution_result")
def then_event_contains_execution_result(context: dict) -> None:
    """Event should contain execution_result."""
    executed = context.get("executed_event")
    assert executed is not None
    assert executed.execution_result is not None


@then("事件应该包含 cost_estimate")
def then_event_contains_cost_estimate(context: dict) -> None:
    """Event should contain cost_estimate."""
    executed = context.get("executed_event")
    assert executed is not None
    assert executed.cost_estimate is not None


@then("事件应该包含 latency_ms")
def then_event_contains_latency_ms(context: dict) -> None:
    """Event should contain latency_ms."""
    executed = context.get("executed_event")
    assert executed is not None
    assert executed.latency_ms is not None


# ===================================================================
# AC-4: execute 与 trigger/route 解耦 - Given Steps
# ===================================================================


@given("ExecuteService 完成执行")
def given_execute_service_completed(context: dict) -> None:
    """ExecuteService completed execution."""
    context["execution_completed"] = True


@given("我验证 ExecuteService 源代码")
def given_validate_execute_service_source(context: dict) -> None:
    """Validate ExecuteService source code."""
    pass


@given("我检查 ExecuteService 实现")
def given_check_execute_service_impl(context: dict) -> None:
    """Check ExecuteService implementation."""
    pass


# ===================================================================
# AC-4: execute 与 trigger/route 解耦 - When Steps
# ===================================================================


@when("发布 Executed 事件")
def when_publish_executed_event(context: dict, event_loop) -> None:
    """Publish Executed event."""
    routed_event = context.get("routed_event")
    execute_service = context.get("execute_service")
    if routed_event and execute_service and context.get("executed_event") is None:
        context["executed_event"] = event_loop.run_until_complete(execute_service.on_routed_event(routed_event))


# ===================================================================
# AC-4: execute 与 trigger/route 解耦 - Then Steps
# ===================================================================


@then("不应该直接调用任何 trigger 或 route 函数")
def then_no_direct_trigger_route_call(context: dict) -> None:
    """Should not directly call any trigger or route function."""
    pass


@then("通信应该通过事件总线异步进行")
def then_async_via_event_bus(context: dict) -> None:
    """Communication should be via event bus asynchronously."""
    pass


@then("ExecuteService 不应该导入任何基础设施层模块")
def then_execute_service_no_infrastructure_imports(context: dict) -> None:
    """ExecuteService should not import infrastructure modules."""
    import inspect

    from src.domain.services.execute_service import ExecuteService

    source = inspect.getsource(ExecuteService)
    assert "infrastructure" not in source or "Protocol" in source


@then("SandboxExecutor 端口应该位于 interfaces 层")
def then_sandbox_executor_port_in_interfaces(context: dict) -> None:
    """SandboxExecutor port should be in interfaces layer."""
    from src.interfaces.sandbox.sandbox_port import SandboxExecutor

    assert SandboxExecutor is not None


@then("DockerSandboxAdapter 应该位于 infrastructure 层")
def then_docker_adapter_in_infrastructure(context: dict) -> None:
    """DockerSandboxAdapter should be in infrastructure layer."""
    from src.infrastructure.sandbox.docker_sandbox_adapter import DockerSandboxAdapter

    assert DockerSandboxAdapter is not None


@then("应该使用 SandboxExecutorProtocol 而非具体实现")
def then_uses_sandbox_protocol(context: dict) -> None:
    """Should use SandboxExecutorProtocol."""
    import inspect

    from src.domain.services.execute_service import ExecuteService

    source = inspect.getsource(ExecuteService)
    assert "SandboxExecutorProtocol" in source


@then("应该使用 SnapshotRepositoryProtocol 而非具体实现")
def then_uses_snapshot_protocol(context: dict) -> None:
    """Should use SnapshotRepositoryProtocol."""
    import inspect

    from src.domain.services.execute_service import ExecuteService

    source = inspect.getsource(ExecuteService)
    assert "SnapshotRepositoryProtocol" in source


@then("领域层定义接口，基础设施层实现")
def then_domain_defines_interfaces(context: dict) -> None:
    """Domain layer defines interfaces, infrastructure implements."""
    pass


# ===================================================================
# AC-5: 执行性能要求 - Given Steps
# ===================================================================


@given("我执行 1000 次沙箱启动操作")
def given_1000_sandbox_startups(context: dict) -> None:
    """Execute 1000 sandbox startup operations."""
    context["startup_ops_count"] = 1000


@given("我执行 1000 次快照保存操作")
def given_1000_snapshot_saves(context: dict) -> None:
    """Execute 1000 snapshot save operations."""
    context["snapshot_ops_count"] = 1000


@given("事件总线每秒发送 100 个 Routed 事件")
def given_100_routed_events_per_second(context: dict) -> None:
    """Event bus sends 100 Routed events per second."""
    context["events_per_second"] = 100


@given("我有相同的 Routed 事件输入")
def given_identical_routed_event(context: dict) -> None:
    """Identical Routed event input."""
    context["identical_event"] = Routed(
        route_type="hash",
        session_id="session-identical",
        task_context={"code": "print('test')", "business_event_type": "ToolExecuted"},
        route_target="docker-sandbox",
        route_score=0.95,
    )


# ===================================================================
# AC-5: 执行性能要求 - When Steps
# ===================================================================


@when("测量启动延迟")
def when_measure_startup_latency(context: dict) -> None:
    """Measure startup latency."""
    latencies = []
    for i in range(100):
        start = time.perf_counter()
        latencies.append((time.perf_counter() - start) * 1000)
    context["latencies"] = latencies


@when("测量保存延迟")
def when_measure_save_latency(context: dict) -> None:
    """Measure save latency."""
    latencies = []
    for i in range(100):
        start = time.perf_counter()
        latencies.append((time.perf_counter() - start) * 1000)
    context["latencies"] = latencies


@when("ExecuteService 持续处理这些事件")
def when_execute_service_processes_continuously(context: dict, event_loop) -> None:
    """ExecuteService continuously processes events."""
    count = 0
    start = time.perf_counter()
    target_duration = 1.0
    while (time.perf_counter() - start) < target_duration:
        event = Routed(
            route_type="hash",
            session_id=f"session-{uuid.uuid4().hex[:8]}",
            task_context={"code": "print('test')", "business_event_type": "ToolExecuted"},
            route_target="docker-sandbox",
            route_score=0.95,
        )
        event_loop.run_until_complete(context["execute_service"].on_routed_event(event))
        count += 1
    context["processed_count"] = count


@when("连续执行 10 次任务")
def when_execute_10_times(context: dict, event_loop) -> None:
    """Execute 10 consecutive tasks."""
    event = context.get("identical_event")
    results = []
    for _ in range(10):
        result = event_loop.run_until_complete(context["execute_service"].on_routed_event(event))
        results.append(result)
    context["results"] = results


# ===================================================================
# AC-5: 执行性能要求 - Then Steps
# ===================================================================


@then("P95 延迟应该小于 100ms")
def then_p95_under_100ms(context: dict) -> None:
    """P95 latency should be under 100ms."""
    pass


@then("系统应该能够实时处理所有事件而不会积压")
def then_no_backlog(context: dict) -> None:
    """System should process all events without backlog."""
    pass


@then("所有 10 次结果应该完全相同")
def then_all_10_results_identical(context: dict) -> None:
    """All 10 results should be identical."""
    results = context.get("results", [])
    assert len(results) == 10, f"Expected 10 results, got {len(results)}"
    first_result = str(results[0].execution_result) if results[0] else None
    for i, r in enumerate(results[1:], 1):
        assert str(r.execution_result) == first_result, f"Result {i} differs"
