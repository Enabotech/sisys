"""OrchestrationService 单元测试

验证路由逻辑、WorkflowEnginePort/AgentEnginePort 委托、WorkflowResult 创建
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast
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


@pytest.fixture
def mock_agent_engine() -> AsyncMock:
    """Mock AgentEnginePort"""
    engine = AsyncMock()
    engine.submit_graph = AsyncMock(return_value=str(uuid.uuid4()))
    engine.get_graph_status = AsyncMock(return_value=FlowStatus.COMPLETED)
    return engine


class TestOrchestrationServiceProtocolCompliance:
    """OrchestrationService 应满足应用层服务约束"""

    def test_only_depends_on_engine_ports(self) -> None:
        """OrchestrationService 仅依赖端口层"""
        import ast

        from src.application.services.orchestration_service import (
            OrchestrationService,
        )

        source = ast.unparse(ast.parse(open(OrchestrationService.__module__.replace(".", "/") + ".py").read()))
        assert "infrastructure" not in source, "OrchestrationService 不应导入 infrastructure 层"


class TestOrchestrationServiceExecute:
    """OrchestrationService.execute() 路由测试"""

    async def test_execute_data_pipeline_routes_to_workflow_engine(
        self, mock_workflow_engine: AsyncMock, mock_agent_engine: AsyncMock
    ) -> None:
        """data_pipeline 类型应委托给 WorkflowEnginePort"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        service = OrchestrationService(mock_workflow_engine, mock_agent_engine)
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

    async def test_execute_returns_workflow_result(self, mock_workflow_engine: AsyncMock, mock_agent_engine: AsyncMock) -> None:
        """execute 应返回 WorkflowResult"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowResult,
            WorkflowTask,
        )

        service = OrchestrationService(mock_workflow_engine, mock_agent_engine)
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

    async def test_execute_data_pipeline_returns_submitted_status(
        self, mock_workflow_engine: AsyncMock, mock_agent_engine: AsyncMock
    ) -> None:
        """data_pipeline 返回的 status 应来自 engine"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        mock_workflow_engine.get_flow_status = AsyncMock(return_value=FlowStatus.RUNNING)

        service = OrchestrationService(mock_workflow_engine, mock_agent_engine)
        task = WorkflowTask(
            flow_name="DocumentProcessing/default",
            parameters={"document_id": str(uuid.uuid4())},
            task_type="data_pipeline",
        )

        result = await service.execute(task)
        assert result.status == FlowStatus.RUNNING

    async def test_execute_agent_reasoning_routes_to_agent_engine(
        self, mock_workflow_engine: AsyncMock, mock_agent_engine: AsyncMock
    ) -> None:
        """agent_reasoning 类型应委托给 AgentEnginePort"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        service = OrchestrationService(mock_workflow_engine, mock_agent_engine)
        task = WorkflowTask(
            flow_name="BasicAgent",
            parameters={"task_description": "分析市场趋势", "agent_role": "analyst", "graph_name": "BasicAgent"},
            task_type="agent_reasoning",
        )

        result = await service.execute(task)

        mock_agent_engine.submit_graph.assert_called_once_with(
            "BasicAgent",
            {"task_description": "分析市场趋势", "agent_role": "analyst", "graph_name": "BasicAgent"},
        )
        assert isinstance(result.status, FlowStatus)


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
            cast(Any, task).flow_name = "changed"

    def test_workflow_result_is_frozen(self) -> None:
        """WorkflowResult 应为 frozen dataclass"""
        from src.application.services.orchestration_service import WorkflowResult

        result = WorkflowResult(
            flow_run_id=str(uuid.uuid4()),
            status=FlowStatus.PENDING,
            submitted_at=datetime.now(),
        )
        with pytest.raises(AttributeError):
            cast(Any, result).flow_run_id = "changed"


class TestOrchestrationServiceValidation:
    """参数验证测试"""

    async def test_execute_rejects_empty_flow_name(self, mock_workflow_engine: AsyncMock, mock_agent_engine: AsyncMock) -> None:
        """空 flow_name 应抛出 ValueError"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        service = OrchestrationService(mock_workflow_engine, mock_agent_engine)
        task = WorkflowTask(flow_name="", parameters={}, task_type="data_pipeline")

        with pytest.raises(ValueError, match="flow_name 不能为空"):
            await service.execute(task)

    async def test_execute_rejects_empty_parameters_for_data_pipeline(
        self, mock_workflow_engine: AsyncMock, mock_agent_engine: AsyncMock
    ) -> None:
        """data_pipeline 空参数应抛出 ValueError"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        service = OrchestrationService(mock_workflow_engine, mock_agent_engine)
        task = WorkflowTask(flow_name="test/default", parameters={}, task_type="data_pipeline")

        with pytest.raises(ValueError, match="parameters"):
            await service.execute(task)

    async def test_execute_rejects_missing_graph_name_for_agent_reasoning(
        self, mock_workflow_engine: AsyncMock, mock_agent_engine: AsyncMock
    ) -> None:
        """agent_reasoning 缺少 graph_name 应抛出 ValueError"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        service = OrchestrationService(mock_workflow_engine, mock_agent_engine)
        task = WorkflowTask(
            flow_name="test",
            parameters={"task_description": "test"},
            task_type="agent_reasoning",
        )

        with pytest.raises(ValueError, match="graph_name"):
            await service.execute(task)
