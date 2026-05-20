"""OrchestrationService 单元测试

验证路由逻辑、WorkflowEnginePort 委托、WorkflowResult 创建

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.domain.value_objects.flow_status import FlowStatus


@pytest.fixture
def mock_workflow_engine() -> AsyncMock:
    """Mock WorkflowEnginePort"""
    engine = AsyncMock()
    engine.submit_flow = AsyncMock(return_value=str(uuid.uuid4()))
    engine.get_flow_status = AsyncMock(return_value=FlowStatus.PENDING)
    return engine


class TestOrchestrationServiceProtocolCompliance:
    """OrchestrationService 应满足应用层服务约束"""

    def test_only_depends_on_workflow_engine_port(self) -> None:
        """OrchestrationService 仅依赖 WorkflowEnginePort 端口"""
        import ast

        from src.application.services.orchestration_service import (
            OrchestrationService,
        )

        source = ast.unparse(ast.parse(open(OrchestrationService.__module__.replace(".", "/") + ".py").read()))
        assert "infrastructure" not in source, "OrchestrationService 不应导入 infrastructure 层"


class TestOrchestrationServiceExecute:
    """OrchestrationService.execute() 路由测试"""

    @pytest.mark.asyncio
    async def test_execute_data_pipeline_routes_to_workflow_engine(self, mock_workflow_engine: AsyncMock) -> None:
        """data_pipeline 类型应委托给 WorkflowEnginePort"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        service = OrchestrationService(mock_workflow_engine)
        task = WorkflowTask(
            flow_name="DocumentProcessing/default",
            parameters={"document_id": str(uuid.uuid4()), "file_path": "/test.pdf"},
            task_type="data_pipeline",
        )

        await service.execute(task)

        mock_workflow_engine.submit_flow.assert_called_once_with(
            "DocumentProcessing/default",
            {"document_id": task.parameters["document_id"], "file_path": "/test.pdf"},
        )

    @pytest.mark.asyncio
    async def test_execute_returns_workflow_result(self, mock_workflow_engine: AsyncMock) -> None:
        """execute 应返回 WorkflowResult"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowResult,
            WorkflowTask,
        )

        service = OrchestrationService(mock_workflow_engine)
        task = WorkflowTask(
            flow_name="DocumentProcessing/default",
            parameters={"document_id": str(uuid.uuid4())},
            task_type="data_pipeline",
        )

        result = await service.execute(task)

        assert isinstance(result, WorkflowResult)
        assert isinstance(result.flow_run_id, str)
        assert isinstance(result.status, FlowStatus)
        assert isinstance(result.submitted_at, datetime)

    @pytest.mark.asyncio
    async def test_execute_data_pipeline_returns_submitted_status(self, mock_workflow_engine: AsyncMock) -> None:
        """data_pipeline 返回的 status 应来自 engine"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        mock_workflow_engine.get_flow_status = AsyncMock(return_value=FlowStatus.RUNNING)

        service = OrchestrationService(mock_workflow_engine)
        task = WorkflowTask(
            flow_name="DocumentProcessing/default",
            parameters={},
            task_type="data_pipeline",
        )

        result = await service.execute(task)
        assert result.status == FlowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_execute_agent_reasoning_raises_not_implemented(self, mock_workflow_engine: AsyncMock) -> None:
        """agent_reasoning 类型在 MVP 阶段应抛出 NotImplementedError"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        service = OrchestrationService(mock_workflow_engine)
        task = WorkflowTask(
            flow_name="AgentReasoning",
            parameters={},
            task_type="agent_reasoning",
        )

        with pytest.raises(NotImplementedError):
            await service.execute(task)


class TestWorkflowTaskValueObject:
    """WorkflowTask 值对象测试"""

    def test_workflow_task_is_frozen(self) -> None:
        """WorkflowTask 应为 frozen dataclass"""
        from src.application.services.orchestration_service import WorkflowTask

        task = WorkflowTask(
            flow_name="test",
            parameters={},
            task_type="data_pipeline",
        )
        with pytest.raises(AttributeError):
            task.flow_name = "changed"  # type: ignore[misc]

    def test_workflow_result_is_frozen(self) -> None:
        """WorkflowResult 应为 frozen dataclass"""
        from src.application.services.orchestration_service import WorkflowResult

        result = WorkflowResult(
            flow_run_id=str(uuid.uuid4()),
            status=FlowStatus.PENDING,
            submitted_at=datetime.now(),
        )
        with pytest.raises(AttributeError):
            result.flow_run_id = "changed"  # type: ignore[misc]
