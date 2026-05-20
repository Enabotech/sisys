"""Story 1-18a 集成测试

端到端验证 OrchestrationService → PrefectEngine → EventPublisher 完整链路

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.events.publish_result import PublishResult
from src.domain.value_objects.flow_status import FlowStatus


class TestOrchestrationEndToEnd:
    """OrchestrationService → PrefectEngine → EventPublisher 端到端"""

    @pytest.mark.asyncio
    async def test_data_pipeline_full_chain(self) -> None:
        """data_pipeline 完整链路：OrchestrationService → PrefectEngine.submit_flow"""
        from src.application.services.orchestration_service import (
            OrchestrationService,
            WorkflowTask,
        )
        from src.infrastructure.config.prefect import PrefectConfig
        from src.infrastructure.workflow.prefect_engine import PrefectEngine

        # Setup mock EventPublisher
        event_publisher = AsyncMock()
        event_publisher.publish = AsyncMock(return_value=PublishResult(event_id="test", redis_success=True))

        # Setup real PrefectEngine with mock SDK
        config = PrefectConfig()
        engine = PrefectEngine(config, event_publisher)

        mock_deployment = MagicMock()
        mock_deployment.id = uuid.uuid4()
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid.uuid4()

        with patch("src.infrastructure.workflow.prefect_engine.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.read_deployment_by_name = AsyncMock(return_value=mock_deployment)
            mock_client.create_flow_run_from_deployment = AsyncMock(return_value=mock_flow_run)
            mock_client.read_flow_run = AsyncMock()
            mock_flow_run_state = MagicMock()
            from prefect.states import StateType

            mock_flow_run_state.type = StateType.RUNNING
            mock_flow_run.state = mock_flow_run_state
            mock_flow_run.run_count = 0
            mock_client.read_flow_run.return_value = mock_flow_run

            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=False)

            # OrchestrationService 使用真实 PrefectEngine + mock AgentEngine
            mock_agent_engine = AsyncMock()
            service = OrchestrationService(engine, mock_agent_engine)
            task = WorkflowTask(
                flow_name="DocumentProcessing/default",
                parameters={
                    "document_id": str(uuid.uuid4()),
                    "file_path": "/test.pdf",
                },
                task_type="data_pipeline",
            )

            result = await service.execute(task)

        assert isinstance(result.flow_run_id, str)
        assert isinstance(result.status, FlowStatus)
        assert result.status == FlowStatus.RUNNING


class TestPrefectEngineStatusMapping:
    """PrefectEngine 状态映射集成验证"""

    @pytest.mark.asyncio
    async def test_all_state_types_mapped(self) -> None:
        """验证所有 Prefect StateType 都有映射"""
        from prefect.states import StateType

        from src.infrastructure.config.prefect import PrefectConfig
        from src.infrastructure.workflow.prefect_engine import PrefectEngine

        config = PrefectConfig()
        engine = PrefectEngine(config, AsyncMock())

        for state_type in StateType:
            state = MagicMock()
            state.type = state_type
            result = engine._map_state_type(state, 0)
            assert isinstance(result, FlowStatus), f"StateType.{state_type.name} 未映射到 FlowStatus"


class TestEventRegistrationChain:
    """事件注册链路验证"""

    def test_rag_indexed_registered_in_domain_registry(self) -> None:
        """RAGIndexed 应注册到 DomainEvent._registry"""
        from src.domain.events.base import DomainEvent
        from src.domain.events.workflow_events import RAGIndexed

        assert "RAGIndexed" in DomainEvent._registry
        assert DomainEvent._registry["RAGIndexed"] is RAGIndexed

    def test_report_generated_registered_in_domain_registry(self) -> None:
        """ReportGenerated 应注册到 DomainEvent._registry"""
        from src.domain.events.base import DomainEvent
        from src.domain.events.workflow_events import ReportGenerated

        assert "ReportGenerated" in DomainEvent._registry
        assert DomainEvent._registry["ReportGenerated"] is ReportGenerated

    def test_workflow_events_exported_from_events_init(self) -> None:
        """工作流事件应从 events __init__.py 导出"""
        import src.domain.events as events

        assert hasattr(events, "RAGIndexed")
        assert hasattr(events, "ReportGenerated")

    def test_workflow_engine_registered_in_composition_root(self) -> None:
        """WorkflowEnginePort 应在 composition_root 中注册"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("workflow_engine")
        assert spec is not None

    def test_orchestration_service_registered_in_composition_root(self) -> None:
        """OrchestrationService 应在 composition_root 中注册"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("orchestration_service")
        assert spec is not None
