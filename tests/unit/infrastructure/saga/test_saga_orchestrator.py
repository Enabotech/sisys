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
from src.infrastructure.saga.saga_status import SagaStatus


class _TestEvent(DomainEvent):
    """Test event for saga testing."""

    event_type: str = field(default="TestSagaEvent", init=False)


class TestSagaOrchestrator:
    """验证 SagaOrchestrator 正向执行和补偿流程"""

    @pytest.mark.asyncio
    async def test_orchestrator_forward_execution(self) -> None:
        """SagaOrchestrator 应正确执行正向流程"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        # 创建 mock steps
        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"
        step1.execute.return_value = {"step1_result": "data1"}
        step1.compensate.return_value = None

        step2 = mock.AsyncMock(spec=SagaStep)
        step2.name = "step2"
        step2.execute.return_value = {"step2_result": "data2"}
        step2.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1, step2],
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.COMPLETED
        assert result.current_step_index == 2
        step1.execute.assert_awaited_once()
        step2.execute.assert_awaited_once()
        step1.compensate.assert_not_awaited()
        step2.compensate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_orchestrator_compensation_on_step_failure(self) -> None:
        """中间步骤失败时应触发补偿"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"
        step1.execute.return_value = {"step1_result": "data1"}
        step1.compensate.return_value = None

        step2 = mock.AsyncMock(spec=SagaStep)
        step2.name = "step2"
        step2.execute.side_effect = RuntimeError("step2 failed")
        step2.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1, step2],
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.COMPENSATED
        step1.execute.assert_awaited_once()
        step2.execute.assert_awaited_once()
        step1.compensate.assert_awaited_once()
        step2.compensate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_orchestrator_compensation_failure_marks_failed(self) -> None:
        """补偿失败时应标记为 FAILED"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"
        step1.execute.return_value = {"step1_result": "data1"}
        step1.compensate.side_effect = RuntimeError("compensate failed")

        step2 = mock.AsyncMock(spec=SagaStep)
        step2.name = "step2"
        step2.execute.side_effect = RuntimeError("step2 failed")
        step2.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1, step2],
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.FAILED
        assert result.errors is not None
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_orchestrator_context_preserves_step_data(self) -> None:
        """SagaContext 应保存各步骤输出"""
        from src.domain.ports.saga import SagaStep
        from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator

        step1 = mock.AsyncMock(spec=SagaStep)
        step1.name = "step1"
        step1.execute.return_value = {"key1": "value1"}
        step1.compensate.return_value = None

        step2 = mock.AsyncMock(spec=SagaStep)
        step2.name = "step2"
        step2.execute.return_value = {"key2": "value2"}
        step2.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="test_saga",
            steps=[step1, step2],
        )

        result = await orchestrator.execute()

        assert "step1" in result.steps_data
        assert result.steps_data["step1"]["output"]["key1"] == "value1"
        assert "step2" in result.steps_data
        assert result.steps_data["step2"]["output"]["key2"] == "value2"
