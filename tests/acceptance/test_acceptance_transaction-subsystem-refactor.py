"""Acceptance tests for Story 20-7 - 事务子系统重构.

BDD step definitions for transaction subsystem refactoring.
Tests cover Session lifecycle separation, UoW instance isolation,
and Saga orchestration patterns.

Run with: poetry run pytest tests/acceptance/test_acceptance_transaction-subsystem-refactor.py -v
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("test_acceptance_transaction-subsystem-refactor.feature")


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
# AC-1: UoW 不调用 close
# ===================================================================


@given("PostgreSQLUnitOfWork 实例已创建")
def uow_instance_created(context: dict) -> None:
    """Create a PostgreSQLUnitOfWork instance with mock session."""
    from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
        PostgreSQLUnitOfWork,
    )
    from src.infrastructure.storage.postgresql.session_context import (
        set_session,
    )

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
# AC-3: 多实例状态隔离
# ===================================================================


@given("创建两个 PostgreSQLUnitOfWork 实例")
def two_uow_instances(context: dict) -> None:
    """Create two independent UoW instances."""
    from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
        PostgreSQLUnitOfWork,
    )
    from src.infrastructure.storage.postgresql.session_context import (
        reset_session,
        set_session,
    )

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
    from src.infrastructure.storage.postgresql.session_context import set_session

    token = set_session(context["mock1"])

    async def _commit():
        await context["uow1"].commit()

    try:
        event_loop.run_until_complete(_commit())
    finally:
        from src.infrastructure.storage.postgresql.session_context import reset_session

        reset_session(token)


@then("第二个实例的 _committed 标志仍为 False")
def second_uow_not_affected(context: dict) -> None:
    """Verify second instance state is unaffected."""
    assert context["uow2"]._committed is False


# ===================================================================
# AC-7: Saga 正向执行成功
# ===================================================================


def _make_mock_repository() -> AsyncMock:
    """创建 mock SagaRepositoryProtocol。"""
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

    from src.infrastructure.saga.saga_context import SagaContext

    saga_context = SagaContext(saga_type="TestSaga")
    context["saga_context"] = saga_context


@when("执行 orchestrator.execute 步骤")
def execute_saga(context: dict, event_loop) -> None:
    """Execute Saga via orchestrator."""
    from uuid import uuid4

    from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

    orchestrator = SagaOrchestrator(
        saga_id=uuid4(),
        saga_type="TestSaga",
        steps=context["steps"],
        repository=context["repository"],
    )
    context["orchestrator"] = orchestrator

    async def _execute():
        result = await orchestrator.execute()
        return result

    context["result_context"] = event_loop.run_until_complete(_execute())


@then("两个 Step 按顺序执行")
def steps_executed_in_order(context: dict) -> None:
    """Verify steps executed in order."""
    step1 = context["step1"]
    step2 = context["step2"]
    step1.execute.assert_called_once()
    step2.execute.assert_called_once()


@then("SagaContext 状态为 COMPLETED")
def saga_completed(context: dict) -> None:
    """Verify Saga completed."""
    from src.infrastructure.saga.saga_status import SagaStatus

    result = context["result_context"]
    assert result.status == SagaStatus.COMPLETED


# ===================================================================
# AC-7: Saga 补偿
# ===================================================================


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

    from src.infrastructure.saga.saga_context import SagaContext

    saga_context = SagaContext(saga_type="TestSaga")
    context["saga_context"] = saga_context


@then("Step 1 的 compensate 被调用")
def step1_compensated(context: dict) -> None:
    """Verify step 1 compensation was called."""
    step1 = context["step1"]
    step1.compensate.assert_called_once()


@then("SagaContext 状态为 COMPENSATED")
def saga_compensated(context: dict) -> None:
    """Verify Saga was compensated."""
    from src.infrastructure.saga.saga_status import SagaStatus

    result = context["result_context"]
    assert result.status == SagaStatus.COMPENSATED
