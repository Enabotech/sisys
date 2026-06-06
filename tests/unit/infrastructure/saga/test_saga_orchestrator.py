"""SagaOrchestrator 单元测试

验证 AC-7: Saga 基础设施
对应 Task 7 的 TDD 测试
"""

from __future__ import annotations

from dataclasses import field
from unittest import mock
from uuid import uuid4

import pytest

from src.domain.events.base import DomainEvent
from src.domain.exceptions import ValidationError
from src.infrastructure.saga.saga_status import SagaStatus


class _TestEvent(DomainEvent):
    """Test event for saga testing."""

    event_type: str = field(default="TestSagaEvent", init=False)


def _make_mock_repository() -> mock.AsyncMock:
    """创建 mock SagaRepositoryProtocol"""
    repo = mock.AsyncMock()
    repo.save = mock.AsyncMock(return_value=None)
    repo.load = mock.AsyncMock(return_value=None)
    repo.update_status = mock.AsyncMock(return_value=None)
    return repo


class TestSagaOrchestrator:
    """验证 SagaOrchestrator 正向执行和补偿流程"""

    async def test_orchestrator_forward_execution(self) -> None:
        """SagaOrchestrator 应正确执行正向流程"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        repo = _make_mock_repository()

        # 创建 mock steps — execute 返回 SagaContext
        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"
        step1.execute.side_effect = lambda ctx: ctx
        step1.compensate.return_value = None

        step2 = mock.AsyncMock(spec=SagaStep)
        step2.name = "step2"
        step2.execute.side_effect = lambda ctx: ctx
        step2.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1, step2],
            repository=repo,
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.COMPLETED
        assert result.current_step_index == 2
        step1.execute.assert_awaited_once()
        step2.execute.assert_awaited_once()
        step1.compensate.assert_not_awaited()
        step2.compensate.assert_not_awaited()

    async def test_orchestrator_compensation_on_step_failure(self) -> None:
        """中间步骤失败时应触发补偿"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        repo = _make_mock_repository()

        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"
        step1.execute.side_effect = lambda ctx: ctx
        step1.compensate.return_value = None

        step2 = mock.AsyncMock(spec=SagaStep)
        step2.name = "step2"
        step2.execute.side_effect = RuntimeError("step2 failed")
        step2.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1, step2],
            repository=repo,
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.COMPENSATED
        step1.execute.assert_awaited_once()
        step2.execute.assert_awaited_once()
        step1.compensate.assert_awaited_once()
        step2.compensate.assert_not_awaited()

    async def test_orchestrator_compensation_failure_marks_failed(self) -> None:
        """补偿失败时应标记为 FAILED"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        repo = _make_mock_repository()

        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"
        step1.execute.side_effect = lambda ctx: ctx
        step1.compensate.side_effect = RuntimeError("compensate failed")

        step2 = mock.AsyncMock(spec=SagaStep)
        step2.name = "step2"
        step2.execute.side_effect = RuntimeError("step2 failed")
        step2.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1, step2],
            repository=repo,
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.FAILED
        assert result.errors is not None
        assert len(result.errors) > 0

    async def test_orchestrator_context_preserves_step_data(self) -> None:
        """SagaContext 应保存各步骤输出"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        repo = _make_mock_repository()

        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"
        step1.execute.side_effect = lambda ctx: ctx
        step1.compensate.return_value = None

        step2 = mock.AsyncMock(spec=SagaStep)
        step2.name = "step2"
        step2.execute.side_effect = lambda ctx: ctx
        step2.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1, step2],
            repository=repo,
        )

        result = await orchestrator.execute()

        assert "step1" in result.steps_data
        assert "step2" in result.steps_data

    async def test_orchestrator_empty_steps_raises(self) -> None:
        """空步骤列表应抛出 ValidationError"""
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        repo = _make_mock_repository()

        with pytest.raises(ValidationError, match="steps 不能为空列表"):
            SagaOrchestrator(
                saga_id=uuid4(),
                saga_type="test_saga",
                steps=[],
                repository=repo,
            )

    async def test_orchestrator_properties(self) -> None:
        """context 和 steps 属性应返回正确的值"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        repo = _make_mock_repository()
        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1],
            repository=repo,
        )

        # context 属性应返回 SagaContext 实例
        assert orchestrator.context is not None
        assert orchestrator.context.status == SagaStatus.PENDING

        # steps 属性应返回步骤列表
        assert len(orchestrator.steps) == 1
        assert orchestrator.steps[0] is step1

    async def test_orchestrator_first_step_failure_goes_failed(self) -> None:
        """第一步失败时没有可补偿步骤，直接标记为 FAILED"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        repo = _make_mock_repository()

        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"
        step1.execute.side_effect = RuntimeError("step1 failed")
        step1.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1],
            repository=repo,
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.FAILED
        step1.compensate.assert_not_awaited()

    async def test_orchestrator_saves_after_each_step(self) -> None:
        """每步执行后应调用 repository.save"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        repo = _make_mock_repository()

        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"
        step1.execute.side_effect = lambda ctx: ctx
        step1.compensate.return_value = None

        step2 = mock.AsyncMock(spec=SagaStep)
        step2.name = "step2"
        step2.execute.side_effect = lambda ctx: ctx
        step2.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1, step2],
            repository=repo,
        )

        await orchestrator.execute()

        # save 调用次数：初始 RUNNING + 每步执行后 + 最终 COMPLETED
        assert repo.save.await_count == 4
