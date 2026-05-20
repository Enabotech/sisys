"""PrefectEngine 单元测试

验证 submit_flow/get_flow_status、状态映射、WorkflowEnginePort 一致性
使用 mock Prefect SDK，不启动真实 server
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.value_objects.flow_status import FlowStatus
from src.infrastructure.config.prefect import PrefectConfig
from src.infrastructure.workflow.prefect_engine import PrefectEngine


@pytest.fixture
def mock_event_publisher() -> AsyncMock:
    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    return publisher


@pytest.fixture
def engine(mock_event_publisher: AsyncMock) -> PrefectEngine:
    config = PrefectConfig()
    return PrefectEngine(config, mock_event_publisher)


class TestPrefectEngineProtocolCompliance:
    """PrefectEngine 满足 WorkflowEnginePort Protocol"""

    def test_is_workflow_engine_port(self, engine: PrefectEngine) -> None:
        from src.domain.ports.workflow_engine import WorkflowEnginePort

        assert isinstance(engine, WorkflowEnginePort)


class TestPrefectEngineSubmitFlow:
    """submit_flow 测试"""

    @pytest.mark.asyncio
    async def test_submit_flow_returns_string_id(self, engine: PrefectEngine) -> None:
        mock_deployment = MagicMock()
        mock_deployment.id = uuid.uuid4()
        mock_flow_run = MagicMock()
        mock_flow_run.id = uuid.uuid4()

        mock_client = AsyncMock()
        mock_client.read_deployment_by_name = AsyncMock(return_value=mock_deployment)
        mock_client.create_flow_run_from_deployment = AsyncMock(return_value=mock_flow_run)

        with patch("src.infrastructure.workflow.prefect_engine.get_client") as mock_get_client:
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await engine.submit_flow(
                "DocumentProcessing/default",
                {"document_id": str(uuid.uuid4()), "file_path": "/test.pdf"},
            )

        assert isinstance(result, str)
        assert len(result) > 0
        mock_client.read_deployment_by_name.assert_called_once_with("DocumentProcessing/default")
        mock_client.create_flow_run_from_deployment.assert_called_once()


class TestPrefectEngineGetFlowStatus:
    """get_flow_status 状态映射测试"""

    @pytest.mark.asyncio
    async def test_running_maps_to_running(self, engine: PrefectEngine) -> None:
        from prefect.states import StateType

        mock_flow_run = MagicMock()
        mock_flow_run.state = MagicMock()
        mock_flow_run.state.type = StateType.RUNNING

        mock_client = AsyncMock()
        mock_client.read_flow_run = AsyncMock(return_value=mock_flow_run)

        with patch("src.infrastructure.workflow.prefect_engine.get_client") as mock_get_client:
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=False)

            status = await engine.get_flow_status(str(uuid.uuid4()))

        assert status == FlowStatus.RUNNING

    @pytest.mark.asyncio
    async def test_completed_maps_to_completed(self, engine: PrefectEngine) -> None:
        from prefect.states import StateType

        mock_flow_run = MagicMock()
        mock_flow_run.state = MagicMock()
        mock_flow_run.state.type = StateType.COMPLETED

        mock_client = AsyncMock()
        mock_client.read_flow_run = AsyncMock(return_value=mock_flow_run)

        with patch("src.infrastructure.workflow.prefect_engine.get_client") as mock_get_client:
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=False)

            status = await engine.get_flow_status(str(uuid.uuid4()))

        assert status == FlowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_failed_maps_to_failed(self, engine: PrefectEngine) -> None:
        from prefect.states import StateType

        mock_flow_run = MagicMock()
        mock_flow_run.state = MagicMock()
        mock_flow_run.state.type = StateType.FAILED
        mock_flow_run.run_count = 3

        mock_client = AsyncMock()
        mock_client.read_flow_run = AsyncMock(return_value=mock_flow_run)

        with patch("src.infrastructure.workflow.prefect_engine.get_client") as mock_get_client:
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=False)

            status = await engine.get_flow_status(str(uuid.uuid4()))

        assert status == FlowStatus.FAILED

    @pytest.mark.asyncio
    async def test_scheduled_maps_to_pending(self, engine: PrefectEngine) -> None:
        from prefect.states import StateType

        mock_flow_run = MagicMock()
        mock_flow_run.state = MagicMock()
        mock_flow_run.state.type = StateType.SCHEDULED

        mock_client = AsyncMock()
        mock_client.read_flow_run = AsyncMock(return_value=mock_flow_run)

        with patch("src.infrastructure.workflow.prefect_engine.get_client") as mock_get_client:
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=False)

            status = await engine.get_flow_status(str(uuid.uuid4()))

        assert status == FlowStatus.PENDING


class TestPrefectEngineInputValidation:
    """输入验证测试"""

    @pytest.mark.asyncio
    async def test_submit_flow_rejects_empty_flow_name(self, engine: PrefectEngine) -> None:
        """空 flow_name 应抛出 ValueError"""
        with pytest.raises(ValueError, match="flow_name 格式无效"):
            await engine.submit_flow("", {})

    @pytest.mark.asyncio
    async def test_submit_flow_rejects_flow_name_without_slash(self, engine: PrefectEngine) -> None:
        """无斜杠的 flow_name 应抛出 ValueError"""
        with pytest.raises(ValueError, match="flow_name 格式无效"):
            await engine.submit_flow("NoSlashHere", {})

    @pytest.mark.asyncio
    async def test_get_flow_status_rejects_invalid_uuid(self, engine: PrefectEngine) -> None:
        """无效 UUID 格式应抛出 ValueError"""
        with pytest.raises(ValueError, match="flow_run_id 格式无效"):
            await engine.get_flow_status("not-a-uuid")

    @pytest.mark.asyncio
    async def test_get_flow_status_rejects_empty_string(self, engine: PrefectEngine) -> None:
        """空字符串应抛出 ValueError"""
        with pytest.raises(ValueError, match="flow_run_id 格式无效"):
            await engine.get_flow_status("")
