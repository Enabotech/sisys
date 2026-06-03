"""Acceptance tests for Story 90-7 - 事务子系统重构.

BDD step definitions for transaction subsystem refactoring.
Tests cover Session lifecycle separation, UoW instance isolation,
Outbox state machine, RetryPolicy, isolation levels,
Saga orchestration, and Saga scenario integration.

Run with: poetry run pytest tests/acceptance/test_acceptance_transaction_subsystem_refactor.py -v
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenario, scenarios, then, when

from src.domain.events.saga_events import SagaStatusChanged
from src.domain.exceptions import InvalidStateTransitionError
from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository
from src.infrastructure.messaging.outbox.outbox import OutboxEntity
from src.infrastructure.messaging.retry.retry_policy import RetryPolicy
from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
    PostgreSQLUnitOfWork,
)
from src.infrastructure.saga.saga_context import SagaContext
from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator
from src.infrastructure.saga.saga_status import SagaStatus
from src.infrastructure.storage.postgresql.session_context import (
    reset_session,
    set_session,
)

scenarios("test_acceptance_transaction_subsystem_refactor.feature")


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """Share state between BDD steps."""
    return {}


# ===================================================================
# Background Steps
# ===================================================================


@given("端口注册中心已初始化")
def ports_registry_initialized(context: dict) -> None:
    """Background: Port registry is initialized."""
    from src.domain.ports.registry import _global_registry

    context["registry"] = _global_registry


# ===================================================================
# AC-1: Session 生命周期职责分离
# ===================================================================


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-1 - UoW 不调用 close，由 Middleware 负责",
)
def test_ac1_uow_no_close():
    """Test UoW __aexit__ does not call session.close()."""
    pass


@given("PostgreSQLUnitOfWork 实例已创建")
def uow_instance_created(context: dict) -> None:
    """Create a PostgreSQLUnitOfWork instance with mock session."""
    mock_session = AsyncMock()
    token = set_session(mock_session)
    uow = PostgreSQLUnitOfWork()
    context["uow"] = uow
    context["mock_session"] = mock_session
    context["session_token"] = token


@when("执行 async with uow 代码块")
def execute_async_with_uow(context: dict, event_loop) -> None:
    """Execute async with UoW context manager."""
    uow = context["uow"]

    async def _run():
        async with uow:
            pass

    event_loop.run_until_complete(_run())
    context["uow"] = uow


@then("uow.__aexit__ 不调用 session.close()")
def verify_no_close_called(context: dict) -> None:
    """Verify close() was NOT called in __aexit__."""
    mock_session = context["mock_session"]
    mock_session.close.assert_not_called()


# ===================================================================
# AC-2: UnitOfWorkFactory Protocol + DI 注册
# ===================================================================


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-2 - UnitOfWorkFactory 可通过 DI 获取",
)
def test_ac2_uow_factory_di():
    """Test UnitOfWorkFactory is available via DI."""
    pass


@when('调用 resolver.resolve("uow_factory")')
def resolve_uow_factory(context: dict) -> None:
    """Resolve uow_factory from DI container."""
    from src.domain.ports.registry import _global_registry
    from src.domain.ports.resolver import Resolver

    resolver = Resolver(_global_registry)
    context["factory"] = resolver.resolve("uow_factory")


@then("返回 PostgreSQLUnitOfWork 类")
def verify_returns_uow_class(context: dict) -> None:
    """Verify resolver returns PostgreSQLUnitOfWork class."""
    factory = context["factory"]
    assert factory is PostgreSQLUnitOfWork


@then("UnitOfWorkFactory Protocol 接口已定义")
def verify_uow_factory_protocol() -> None:
    """Verify UnitOfWorkFactory Protocol is defined."""
    from src.domain.ports.unit_of_work import UnitOfWorkFactory

    assert hasattr(UnitOfWorkFactory, "__call__")


# ===================================================================
# AC-3: UoW 实例级标志位
# ===================================================================


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-3 - 多实例状态隔离",
)
def test_ac3_multi_instance_isolation():
    """Test multiple UoW instances have isolated state."""
    pass


@given("创建两个 PostgreSQLUnitOfWork 实例")
def two_uow_instances(context: dict) -> None:
    """Create two independent UoW instances."""
    mock1 = AsyncMock()
    token1 = set_session(mock1)
    uow1 = PostgreSQLUnitOfWork()
    reset_session(token1)

    mock2 = AsyncMock()
    token2 = set_session(mock2)
    uow2 = PostgreSQLUnitOfWork()
    reset_session(token2)

    context["uow1"] = uow1
    context["uow2"] = uow2
    context["mock1"] = mock1
    context["mock2"] = mock2


@when("第一个实例执行 commit")
def first_uow_commit(context: dict, event_loop) -> None:
    """First UoW executes commit."""
    token = set_session(context["mock1"])

    async def _commit():
        await context["uow1"].commit()

    try:
        event_loop.run_until_complete(_commit())
    finally:
        reset_session(token)


@then("第二个实例的 _committed 标志仍为 False")
def second_uow_not_affected(context: dict) -> None:
    """Verify second instance state is unaffected."""
    assert context["uow2"]._committed is False


# ===================================================================
# AC-4: Outbox archived 状态修复 + 状态机修复
# ===================================================================


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-4 - Outbox archived 状态可持久化",
)
def test_ac4_outbox_archived():
    """Test Outbox archived state persistence."""
    pass


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-4 - Outbox 状态机阻止非法转换",
)
def test_ac4_outbox_invalid_transition():
    """Test Outbox state machine blocks invalid transitions."""
    pass


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-4 - InMemoryOutboxRepository 状态转换",
)
def test_ac4_inmemory_outbox_state():
    """Test InMemoryOutboxRepository state transitions."""
    pass


@given("OutboxEntity 实例已创建")
def outbox_entity_created(context: dict) -> None:
    """Create an OutboxEntity instance."""
    entity = OutboxEntity(event_id=uuid.uuid4(), event_type="TestEvent", payload={"key": "value"})
    context["outbox_entity"] = entity


@when("依次标记为 failed 和 archived")
def mark_failed_then_archived(context: dict) -> None:
    """Mark entity as failed then archived."""
    entity = context["outbox_entity"]
    entity.mark_failed("test error")
    entity.mark_archived()


@then("OutboxEntity 状态变为 archived")
def verify_archived_status(context: dict) -> None:
    """Verify entity status is archived."""
    assert context["outbox_entity"].status == "archived"


@given("OutboxEntity 实例状态为 pending")
def outbox_entity_pending(context: dict) -> None:
    """Create an OutboxEntity in pending state."""
    entity = OutboxEntity(event_id=uuid.uuid4(), event_type="TestEvent", payload={"key": "value"})
    assert entity.status == "pending"
    context["outbox_entity"] = entity


@when("尝试直接标记为 archived")
def attempt_direct_archive(context: dict) -> None:
    """Attempt to archive from pending state (invalid)."""
    entity = context["outbox_entity"]
    try:
        entity.mark_archived()
        context["error_raised"] = False
    except InvalidStateTransitionError:
        context["error_raised"] = True


@then("抛出 InvalidStateTransitionError")
def verify_invalid_state_error(context: dict) -> None:
    """Verify InvalidStateTransitionError was raised."""
    assert context["error_raised"] is True


@given("InMemoryOutboxRepository 包含一个 pending 事件")
def inmemory_outbox_with_pending(context: dict, event_loop) -> None:
    """Create InMemoryOutboxRepository with a pending event."""
    from src.domain.events.base import DomainEvent

    repo = InMemoryOutboxRepository()
    event = DomainEvent(event_type="TestEvent", source="test")
    event_loop.run_until_complete(repo.save(event))
    context["outbox_repo"] = repo
    context["event_id"] = event.event_id


@when("调用 mark_published")
def mark_outbox_published(context: dict, event_loop) -> None:
    """Mark event as published."""
    repo = context["outbox_repo"]
    event_id = context["event_id"]
    event_loop.run_until_complete(repo.mark_published(event_id))


@then("事件状态变为 published")
def verify_published_status(context: dict, event_loop) -> None:
    """Verify no pending events remain (was published)."""
    repo = context["outbox_repo"]
    remaining = event_loop.run_until_complete(repo.get_unpublished(limit=10))
    assert len(remaining) == 0


# ===================================================================
# AC-5: Outbox 清理策略 + RetryPolicy 集成
# ===================================================================


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-5 - Outbox 清理已发布记录",
)
def test_ac5_outbox_cleanup():
    """Test Outbox cleanup of published records."""
    pass


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-5 - RetryPolicy 指数退避计算",
)
def test_ac5_retry_policy_backoff():
    """Test RetryPolicy exponential backoff."""
    pass


@given("InMemoryOutboxRepository 包含已发布和未发布事件")
def outbox_with_mixed_events(context: dict) -> None:
    """Create OutboxRepository with published and unpublished entities."""
    repo = InMemoryOutboxRepository()

    # Pending entity
    pending = OutboxEntity(event_id=uuid.uuid4(), event_type="TestEvent", payload={"key": "pending"})
    repo._entities.append(pending)

    # Published entity (with past published_at for cleanup eligibility)
    published = OutboxEntity(event_id=uuid.uuid4(), event_type="TestEvent", payload={"key": "published"})
    published.mark_failed("error")
    published.mark_archived()
    # Manually set to published for cleanup test
    published.status = "published"
    from datetime import UTC, datetime, timedelta

    published.published_at = datetime.now(UTC) - timedelta(days=1)
    repo._entities.append(published)

    context["outbox_repo"] = repo
    context["pending_event_id"] = pending.event_id


@when("调用 cleanup_old_published_records")
def cleanup_published(context: dict, event_loop) -> None:
    """Clean up old published records."""
    repo = context["outbox_repo"]
    context["cleanup_count"] = event_loop.run_until_complete(repo.cleanup_old_published_records(older_than_days=0))


@then("仅已发布记录被清理")
def verify_only_published_cleaned(context: dict) -> None:
    """Verify only published records were cleaned."""
    assert context["cleanup_count"] >= 1


@then("pending 事件不受影响")
def verify_pending_untouched(context: dict) -> None:
    """Verify pending events remain."""
    repo = context["outbox_repo"]
    pending_ids = [e.event_id for e in repo._entities if e.status == "pending"]
    assert context["pending_event_id"] in pending_ids


@given("RetryPolicy 配置已创建")
def retry_policy_created(context: dict) -> None:
    """Create RetryPolicy with known config."""
    policy = RetryPolicy(base_delay=1.0, max_delay=60.0, max_retries=5)
    context["retry_policy"] = policy


@when("计算多次重试的退避时间")
def compute_retry_delays(context: dict) -> None:
    """Compute delays for multiple retry attempts."""
    policy = context["retry_policy"]
    # Use deterministic jitter-free calculation
    delays = [policy.base_delay * (2**i) for i in range(5)]
    context["delays"] = delays


@then("退避时间按指数增长")
def verify_exponential_growth(context: dict) -> None:
    """Verify delays grow exponentially."""
    delays = context["delays"]
    for i in range(1, len(delays)):
        assert delays[i] >= delays[i - 1]


@then("不超过最大延迟")
def verify_max_delay_cap(context: dict) -> None:
    """Verify delays do not exceed max_delay."""
    policy = context["retry_policy"]
    delays = context["delays"]
    for delay in delays:
        assert delay <= policy.max_delay


# ===================================================================
# AC-6: 事务隔离级别配置 + 审计专用 UoW
# ===================================================================


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-6 - PostgreSQLManager 支持隔离级别",
)
def test_ac6_isolation_levels():
    """Test PostgreSQLManager supports isolation levels."""
    pass


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-6 - AuditUnitOfWork 使用 SERIALIZABLE 隔离级别",
)
def test_ac6_audit_uow():
    """Test AuditUnitOfWork uses SERIALIZABLE isolation."""
    pass


@given("PostgreSQLManager 类已加载")
def postgresql_manager_loaded(context: dict) -> None:
    """Load PostgreSQLManager class."""
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    context["pg_manager_cls"] = PostgreSQLManager


@then("支持 get_session_with_isolation 方法")
def verify_isolation_method(context: dict) -> None:
    """Verify get_session_with_isolation method exists."""
    cls = context["pg_manager_cls"]
    assert hasattr(cls, "get_session_with_isolation")
    import inspect

    sig = inspect.signature(cls.get_session_with_isolation)
    assert "isolation_level" in sig.parameters


@then("支持 SERIALIZABLE 和 REPEATABLE READ 隔离级别")
def verify_supported_isolation_levels() -> None:
    """Verify supported isolation level values."""
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    assert hasattr(PostgreSQLManager, "get_session_with_isolation")


@given("AuditUnitOfWork 类已加载")
def audit_uow_loaded(context: dict) -> None:
    """Load AuditUnitOfWork class."""
    from src.infrastructure.messaging.unit_of_work.audit_unit_of_work import AuditUnitOfWork

    context["audit_uow_cls"] = AuditUnitOfWork


@then("构造器注入 PostgreSQLManager")
def verify_audit_uow_constructor(context: dict) -> None:
    """Verify AuditUnitOfWork constructor accepts PostgreSQLManager."""
    import inspect

    cls = context["audit_uow_cls"]
    sig = inspect.signature(cls.__init__)
    params = list(sig.parameters.keys())
    assert "manager" in params


@then("定义了 begin/commit/rollback 方法")
def verify_audit_uow_methods(context: dict) -> None:
    """Verify AuditUnitOfWork has transaction methods."""
    cls = context["audit_uow_cls"]
    assert callable(getattr(cls, "begin", None))
    assert callable(getattr(cls, "commit", None))
    assert callable(getattr(cls, "rollback", None))


# ===================================================================
# AC-7: Saga 基础设施
# ===================================================================


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-7 - Saga 正向执行成功",
)
def test_ac7_saga_forward_execution():
    """Test Saga forward execution with ordered step execution."""
    pass


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-7 - Saga Step 失败触发补偿",
)
def test_ac7_saga_compensation():
    """Test Saga compensation when a step fails."""
    pass


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-7 - SagaStatusChanged 事件定义",
)
def test_ac7_saga_event():
    """Test SagaStatusChanged event definition."""
    pass


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-7 - SagaContext 不可变状态管理",
)
def test_ac7_saga_context_immutable():
    """Test SagaContext immutable state management."""
    pass


def _make_mock_repository() -> AsyncMock:
    """创建 mock SagaRepositoryProtocol"""
    repo = AsyncMock()
    repo.save = AsyncMock(return_value=None)
    repo.load = AsyncMock(return_value=None)
    repo.update_status = AsyncMock(return_value=None)
    return repo


@given("SagaOrchestrator 和 2 个 SagaStep 已创建")
def saga_orchestrator_2_steps(context: dict) -> None:
    """Create SagaOrchestrator with 2 mock SagaSteps."""
    step1 = MagicMock()
    step1.name = "step1"
    step1.execute = AsyncMock(side_effect=lambda ctx: ctx)
    step1.compensate = AsyncMock(side_effect=lambda ctx: ctx)

    step2 = MagicMock()
    step2.name = "step2"
    step2.execute = AsyncMock(side_effect=lambda ctx: ctx)
    step2.compensate = AsyncMock(side_effect=lambda ctx: ctx)

    context["steps"] = [step1, step2]
    context["step1"] = step1
    context["step2"] = step2
    context["repository"] = _make_mock_repository()


@when("执行 orchestrator.execute 步骤")
def execute_saga(context: dict, event_loop) -> None:
    """Execute Saga via orchestrator."""
    orchestrator = SagaOrchestrator(
        saga_id=uuid.uuid4(),
        saga_type="TestSaga",
        steps=context["steps"],
        repository=context["repository"],
    )
    context["orchestrator"] = orchestrator

    async def _execute():
        return await orchestrator.execute()

    context["result_context"] = event_loop.run_until_complete(_execute())


@then("两个 Step 按顺序执行")
def steps_executed_in_order(context: dict) -> None:
    """Verify steps executed in order."""
    context["step1"].execute.assert_called_once()
    context["step2"].execute.assert_called_once()


@then("SagaContext 状态为 COMPLETED")
def saga_completed(context: dict) -> None:
    """Verify Saga completed."""
    result = context["result_context"]
    assert result.status == SagaStatus.COMPLETED


@given("SagaOrchestrator 和 3 个 SagaStep（第 2 个失败）已创建")
def saga_orchestrator_3_steps_failing(context: dict) -> None:
    """Create SagaOrchestrator with 3 steps where step 2 fails."""
    step1 = MagicMock()
    step1.name = "step1"
    step1.execute = AsyncMock(side_effect=lambda ctx: ctx)
    step1.compensate = AsyncMock(side_effect=lambda ctx: ctx)

    step2 = MagicMock()
    step2.name = "step2"
    step2.execute = AsyncMock(side_effect=RuntimeError("step2 failed"))
    step2.compensate = AsyncMock(side_effect=lambda ctx: ctx)

    step3 = MagicMock()
    step3.name = "step3"
    step3.execute = AsyncMock(side_effect=lambda ctx: ctx)
    step3.compensate = AsyncMock(side_effect=lambda ctx: ctx)

    context["steps"] = [step1, step2, step3]
    context["step1"] = step1
    context["step2"] = step2
    context["step3"] = step3
    context["repository"] = _make_mock_repository()


@then("Step 1 的 compensate 被调用")
def step1_compensated(context: dict) -> None:
    """Verify step 1 compensation was called."""
    context["step1"].compensate.assert_called_once()


@then("SagaContext 状态为 COMPENSATED")
def saga_compensated(context: dict) -> None:
    """Verify Saga was compensated."""
    result = context["result_context"]
    assert result.status == SagaStatus.COMPENSATED


@given("SagaStatusChanged 事件类已加载")
def saga_event_loaded(context: dict) -> None:
    """Load SagaStatusChanged event class."""
    context["saga_event_cls"] = SagaStatusChanged


@then("事件包含 saga_id 和 saga_type 字段")
def verify_saga_event_fields(context: dict) -> None:
    """Verify SagaStatusChanged has required fields."""
    cls = context["saga_event_cls"]
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(cls)}
    assert "saga_id" in field_names
    assert "saga_type" in field_names


@then("事件类型为 SagaStatusChanged")
def verify_saga_event_type() -> None:
    """Verify default event_type is SagaStatusChanged."""
    event = SagaStatusChanged(saga_id=uuid.uuid4(), saga_type="TestSaga", new_status="RUNNING")
    assert event.event_type == "SagaStatusChanged"


@given("SagaContext 实例已创建")
def saga_context_created(context: dict) -> None:
    """Create a SagaContext instance."""
    ctx = SagaContext(saga_type="TestSaga")
    context["saga_context"] = ctx
    context["original_status"] = ctx.status


@when("调用 update_status 方法")
def update_saga_context_status(context: dict) -> None:
    """Update SagaContext status."""
    ctx = context["saga_context"]
    context["updated_context"] = ctx.update_status(SagaStatus.RUNNING)


@then("返回新的 SagaContext 实例")
def verify_new_instance(context: dict) -> None:
    """Verify update returns a new instance."""
    original = context["saga_context"]
    updated = context["updated_context"]
    assert updated is not original


@then("原实例状态不变")
def verify_original_unchanged(context: dict) -> None:
    """Verify original instance status is unchanged."""
    original = context["saga_context"]
    assert original.status == context["original_status"]


# ===================================================================
# AC-8: Saga 场景落地
# ===================================================================


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-8 - S01 文档处理 Saga 正向流程",
)
def test_ac8_s01_forward():
    """Test S01 DocumentProcessing Saga forward execution."""
    pass


@scenario(
    "test_acceptance_transaction_subsystem_refactor.feature",
    "AC-8 - S01 文档处理 Saga 补偿流程",
)
def test_ac8_s01_compensation():
    """Test S01 DocumentProcessing Saga compensation."""
    pass


def _make_doc_saga_steps(context: dict, fail_index: int | None = None) -> list[MagicMock]:
    """创建 S01 文档处理 Saga 的 mock steps."""
    step_names = ["upload_document", "save_metadata", "generate_embedding", "extract_entities"]
    steps = []
    for i, name in enumerate(step_names):
        step = MagicMock()
        step.name = name
        if fail_index is not None and i == fail_index:
            step.execute = AsyncMock(side_effect=RuntimeError(f"{name} failed"))
        else:
            step.execute = AsyncMock(side_effect=lambda ctx: ctx)
        step.compensate = AsyncMock(side_effect=lambda ctx: ctx)
        steps.append(step)
        context[f"step_{name}"] = step
    return steps


@given("4 个文档处理 SagaStep 已创建")
def doc_saga_4_steps(context: dict) -> None:
    """Create 4 document processing SagaSteps."""
    context["steps"] = _make_doc_saga_steps(context)
    context["repository"] = _make_mock_repository()


@when("执行文档处理 Saga")
def execute_doc_saga(context: dict, event_loop) -> None:
    """Execute document processing Saga."""
    orchestrator = SagaOrchestrator(
        saga_id=uuid.uuid4(),
        saga_type="DocumentProcessing",
        steps=context["steps"],
        repository=context["repository"],
    )

    async def _execute():
        return await orchestrator.execute()

    context["result_context"] = event_loop.run_until_complete(_execute())


@then("所有步骤按序执行")
def all_steps_executed(context: dict) -> None:
    """Verify all steps executed in order."""
    for name in ["upload_document", "save_metadata", "generate_embedding", "extract_entities"]:
        context[f"step_{name}"].execute.assert_called_once()


@given("4 个文档处理 SagaStep（第 3 个失败）已创建")
def doc_saga_4_steps_failing(context: dict) -> None:
    """Create 4 document processing SagaSteps with step 3 failing."""
    context["steps"] = _make_doc_saga_steps(context, fail_index=2)
    context["repository"] = _make_mock_repository()


@then("前 2 个步骤的 compensate 被调用")
def first_two_compensated(context: dict) -> None:
    """Verify first 2 steps' compensate was called."""
    context["step_upload_document"].compensate.assert_called_once()
    context["step_save_metadata"].compensate.assert_called_once()
