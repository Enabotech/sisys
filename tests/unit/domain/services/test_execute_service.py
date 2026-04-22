"""Tests for ExecuteService domain service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.events.execute_events import Executed
from src.domain.events.route_events import Routed
from src.domain.services.execute_service import ExecuteService


class TestExecuteService:
    """TDD tests for ExecuteService domain service."""

    def test_service_initialization(self) -> None:
        """RED: ExecuteService should initialize with optional dependencies."""
        service = ExecuteService()

        assert service._sandbox is None
        assert service._snapshot_repo is None

    def test_service_with_sandbox_and_repo(self) -> None:
        """RED: ExecuteService should accept sandbox and repo dependencies."""
        mock_sandbox = MagicMock()
        mock_repo = MagicMock()

        service = ExecuteService(sandbox=mock_sandbox, snapshot_repo=mock_repo)

        assert service._sandbox is mock_sandbox
        assert service._snapshot_repo is mock_repo

    @pytest.mark.asyncio
    async def test_on_routed_event_returns_executed_event(self) -> None:
        """RED: on_routed_event should return Executed event on success."""
        service = ExecuteService()

        routed_event = Routed(
            session_id="test-session",
            task_context={"task": "test", "code": "print('hello')"},
            route_target="tool-1",
            route_score=0.9,
            route_type="semantic",
        )

        result = await service.on_routed_event(routed_event)

        assert result is not None
        assert isinstance(result, Executed)
        assert result.session_id == "test-session"

    @pytest.mark.asyncio
    async def test_on_routed_event_without_session_id_returns_none(self) -> None:
        """RED: on_routed_event should return None if session_id is missing."""
        service = ExecuteService()

        routed_event = Routed(session_id="", task_context={})

        result = await service.on_routed_event(routed_event)

        assert result is None

    @pytest.mark.asyncio
    async def test_on_routed_event_publishes_executed_event(self) -> None:
        """RED: on_routed_event should populate all fields correctly."""
        service = ExecuteService()

        routed_event = Routed(
            session_id="test-session-123",
            task_context={
                "task": "analysis",
                "code": "x = 1 + 1",
                "business_event_type": "ToolExecuted",
            },
            route_target="ceo-agent",
            route_score=0.95,
            route_type="hash",
        )

        result = await service.on_routed_event(routed_event)

        assert result is not None
        assert result.session_id == "test-session-123"
        assert result.task_context["task"] == "analysis"
        assert result.business_event_type == "ToolExecuted"
        assert result.route_target == "ceo-agent"
        assert result.route_score == 0.95

    @pytest.mark.asyncio
    async def test_create_snapshot_returns_snapshot(self) -> None:
        """RED: create_snapshot should create and return CheckpointSnapshot."""
        mock_repo = AsyncMock()
        mock_repo.load = AsyncMock(return_value=None)
        mock_repo.save = AsyncMock()
        service = ExecuteService(snapshot_repo=mock_repo)

        result = await service.create_snapshot(
            session_id="test-session",
            state={"key": "value"},
            stage_id="planning",
        )

        assert result is not None
        assert result.session_id == "test-session"
        assert result.stage_id == "planning"
        mock_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_snapshot_increments_version(self) -> None:
        """RED: create_snapshot should increment version if existing snapshot."""
        existing_snapshot = MagicMock()
        existing_snapshot.state_version = 3

        mock_repo = AsyncMock()
        mock_repo.load = AsyncMock(return_value=existing_snapshot)
        mock_repo.save = AsyncMock()
        service = ExecuteService(snapshot_repo=mock_repo)

        result = await service.create_snapshot(
            session_id="test-session",
            state={"new_key": "new_value"},
        )

        assert result is not None
        assert result.state_version == 4

    @pytest.mark.asyncio
    async def test_on_routed_event_handles_exception(self) -> None:
        """Coverage: on_routed_event exception handler (lines 163-179)."""
        mock_sandbox = AsyncMock()
        mock_sandbox.start_container = AsyncMock()
        mock_sandbox.execute_code = AsyncMock(side_effect=Exception("execution failed"))
        service = ExecuteService(sandbox=mock_sandbox)

        routed_event = Routed(
            session_id="error-session",
            task_context={"code": "print('test')", "business_event_type": "ToolExecuted"},
            route_target="test-agent",
            route_score=0.9,
            route_type="hash",
        )

        # Should return Executed event with failure status, not raise
        result = await service.on_routed_event(routed_event)

        assert result is not None
        assert result.session_id == "error-session"
        assert result.execution_result["status"] == "failed"
        assert "execution failed" in result.execution_result["error"]

    @pytest.mark.asyncio
    async def test_restore_snapshot_returns_none_when_no_repo(self) -> None:
        """Coverage: restore_snapshot when no repo configured (lines 226-227)."""
        service = ExecuteService(snapshot_repo=None)

        result = await service.restore_snapshot("any-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_restore_snapshot_returns_none_when_not_found(self) -> None:
        """Coverage: restore_snapshot when no snapshot exists (lines 232-233)."""
        mock_repo = AsyncMock()
        mock_repo.load = AsyncMock(return_value=None)
        service = ExecuteService(snapshot_repo=mock_repo)

        result = await service.restore_snapshot("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_on_routed_event_returns_executed_when_sandbox_fails(self) -> None:
        """Coverage: on_routed_event returns Executed even if sandbox.execute_code fails."""
        mock_sandbox = AsyncMock()
        mock_sandbox.start_container = AsyncMock()
        mock_sandbox.execute_code = AsyncMock(side_effect=Exception("execution failed"))
        service = ExecuteService(sandbox=mock_sandbox)

        routed_event = Routed(
            session_id="exec-fail-session",
            task_context={"code": "raise_error()", "business_event_type": "ToolExecuted"},
            route_target="test-agent",
            route_score=0.8,
            route_type="hash",
        )

        result = await service.on_routed_event(routed_event)

        assert result is not None
        assert result.session_id == "exec-fail-session"
        assert result.execution_result["status"] == "failed"
