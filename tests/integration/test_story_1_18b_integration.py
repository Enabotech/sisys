"""Story 1-18b 集成测试

端到端验证 OrchestrationService → LangGraphEngine → EventPublisher 完整链路

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from src.domain.events.publish_result import PublishResult
from src.domain.value_objects.flow_status import FlowStatus


class TestAgentReasoningFullChain:
    """OrchestrationService → LangGraphEngine 端到端"""

    @pytest.mark.asyncio
    async def test_agent_reasoning_full_chain(self) -> None:
        """agent_reasoning 完整链路：OrchestrationService → LangGraphEngine.submit_graph"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )
        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
        from src.infrastructure.config.langgraph import LangGraphConfig

        event_publisher = AsyncMock()
        event_publisher.publish = AsyncMock(return_value=PublishResult(event_id="test", redis_success=True))
        config = LangGraphConfig()
        agent_engine = LangGraphEngine(config, event_publisher)

        mock_workflow_engine = AsyncMock()
        mock_workflow_engine.submit_flow = AsyncMock(return_value=str(uuid.uuid4()))
        mock_workflow_engine.get_flow_status = AsyncMock(return_value=FlowStatus.PENDING)

        service = OrchestrationService(mock_workflow_engine, agent_engine)
        task = WorkflowTask(
            flow_name="BasicAgent",
            parameters={"task_description": "分析市场趋势", "agent_role": "analyst", "graph_name": "BasicAgent"},
            task_type="agent_reasoning",
        )

        result = await service.execute(task)

        assert isinstance(result.flow_run_id, str)
        assert result.status == FlowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_agent_reasoning_get_status(self) -> None:
        """agent_reasoning 提交后应能查询状态"""
        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
        from src.infrastructure.config.langgraph import LangGraphConfig

        event_publisher = AsyncMock()
        event_publisher.publish = AsyncMock(return_value=PublishResult(event_id="test", redis_success=True))
        config = LangGraphConfig()
        engine = LangGraphEngine(config, event_publisher)

        run_id = await engine.submit_graph(
            "BasicAgent",
            {"task_description": "测试状态查询", "agent_role": "analyst"},
        )

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.COMPLETED


class TestDualEngineRouting:
    """双引擎路由验证"""

    @pytest.mark.asyncio
    async def test_data_pipeline_routes_to_prefect(self) -> None:
        """data_pipeline 应路由到 WorkflowEnginePort"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        mock_workflow_engine = AsyncMock()
        mock_workflow_engine.submit_flow = AsyncMock(return_value=str(uuid.uuid4()))
        mock_workflow_engine.get_flow_status = AsyncMock(return_value=FlowStatus.RUNNING)

        mock_agent_engine = AsyncMock()

        service = OrchestrationService(mock_workflow_engine, mock_agent_engine)
        task = WorkflowTask(
            flow_name="DocumentProcessing/default",
            parameters={"document_id": str(uuid.uuid4())},
            task_type="data_pipeline",
        )

        await service.execute(task)

        mock_workflow_engine.submit_flow.assert_called_once()
        mock_agent_engine.submit_graph.assert_not_called()

    @pytest.mark.asyncio
    async def test_agent_reasoning_routes_to_langgraph(self) -> None:
        """agent_reasoning 应路由到 AgentEnginePort"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )

        mock_workflow_engine = AsyncMock()
        mock_agent_engine = AsyncMock()
        mock_agent_engine.submit_graph = AsyncMock(return_value=str(uuid.uuid4()))
        mock_agent_engine.get_graph_status = AsyncMock(return_value=FlowStatus.COMPLETED)

        service = OrchestrationService(mock_workflow_engine, mock_agent_engine)
        task = WorkflowTask(
            flow_name="BasicAgent",
            parameters={"task_description": "测试", "graph_name": "BasicAgent"},
            task_type="agent_reasoning",
        )

        await service.execute(task)

        mock_agent_engine.submit_graph.assert_called_once()
        mock_workflow_engine.submit_flow.assert_not_called()
