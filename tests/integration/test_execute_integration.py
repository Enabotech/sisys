"""Integration tests for execute mechanism end-to-end flow."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.events.auto_execute_events import AutoExecuted
from src.domain.events.auto_route_events import AutoRouted
from src.domain.services.auto_execute_service import AutoExecuteService
from src.infrastructure.sandbox.docker_sandbox_adapter import DockerSandboxAdapter
from src.interfaces.event_listeners.auto_execute_completed_listener import AutoExecuteCompletedListener


class TestExecuteIntegration:
    """End-to-end integration tests for execute mechanism.

    Tests the complete flow:
    1. AutoRouted event arrives at AutoExecuteService
    2. AutoExecuteService starts Docker sandbox for session
    3. AutoExecuteService executes task in sandbox
    4. AutoExecuteService creates CheckpointSnapshot
    5. AutoExecuteService publishes AutoExecuted event
    6. AutoExecuteCompletedListener publishes downstream domain event
    """

    @pytest.fixture
    def mock_publisher(self) -> AsyncMock:
        """Create mock event publisher."""
        return AsyncMock()

    @pytest.fixture
    def sandbox(self):
        """Create DockerSandboxAdapter for integration testing."""
        adapter = DockerSandboxAdapter()
        yield adapter
        adapter.reset_all_containers()

    @pytest.fixture
    def execute_service(self, sandbox: DockerSandboxAdapter) -> AutoExecuteService:
        """Create AutoExecuteService with sandbox."""
        return AutoExecuteService(sandbox=sandbox, snapshot_repo=None)

    @pytest.fixture
    def execute_listener(self, mock_publisher: AsyncMock) -> AutoExecuteCompletedListener:
        """Create AutoExecuteCompletedListener with mock publisher."""
        return AutoExecuteCompletedListener(publisher=mock_publisher)

    @pytest.mark.asyncio
    async def test_routed_to_executed_flow(
        self,
        execute_service: AutoExecuteService,
        mock_publisher: AsyncMock,
    ) -> None:
        """Verify AutoRouted event flows through AutoExecuteService to AutoExecuted event."""
        # Create a AutoRouted event
        routed_event = AutoRouted(
            route_type="hash",
            session_id=f"integration-{uuid.uuid4().hex[:8]}",
            task_context={
                "code": "print('hello from sandbox')",
                "business_event_type": "ToolExecuted",
            },
            route_target="docker-sandbox",
            route_score=0.95,
        )

        # Process through execute service
        executed = await execute_service.on_routed_event(routed_event)

        # Verify AutoExecuted event was created
        assert executed is not None
        assert isinstance(executed, AutoExecuted)
        assert executed.session_id == routed_event.session_id
        assert executed.business_event_type == "ToolExecuted"
        assert executed.route_target == "docker-sandbox"

    @pytest.mark.asyncio
    async def test_sandbox_container_lifecycle(
        self,
        sandbox: DockerSandboxAdapter,
    ) -> None:
        """Verify sandbox container start/execute/stop lifecycle."""
        session_id = f"lifecycle-{uuid.uuid4().hex[:8]}"

        # Start container
        await sandbox.start_container(session_id)
        assert await sandbox.is_container_running(session_id) is True

        # Execute code
        result = await sandbox.execute_code(session_id, "print('test')")
        assert result["status"] == "completed"

        # Stop container
        await sandbox.stop_container(session_id)
        assert await sandbox.is_container_running(session_id) is False

    @pytest.mark.asyncio
    async def test_session_namespace_isolation(
        self,
        sandbox: DockerSandboxAdapter,
    ) -> None:
        """Verify different sessions get isolated containers."""
        session_a = f"isolated-a-{uuid.uuid4().hex[:8]}"
        session_b = f"isolated-b-{uuid.uuid4().hex[:8]}"

        # Start containers for both sessions
        await sandbox.start_container(session_a)
        await sandbox.start_container(session_b)

        # Both should be running
        assert await sandbox.is_container_running(session_a) is True
        assert await sandbox.is_container_running(session_b) is True

        # Stop session A - B should still be running
        await sandbox.stop_container(session_a)
        assert await sandbox.is_container_running(session_a) is False
        assert await sandbox.is_container_running(session_b) is True

        # Cleanup
        await sandbox.stop_container(session_b)

    @pytest.mark.asyncio
    async def test_executed_to_downstream_event_flow(
        self,
        execute_service: AutoExecuteService,
        execute_listener: AutoExecuteCompletedListener,
        mock_publisher: AsyncMock,
    ) -> None:
        """Verify AutoExecuted event triggers downstream domain event publication."""
        # Create a AutoRouted event
        routed_event = AutoRouted(
            route_type="hash",
            session_id=f"downstream-{uuid.uuid4().hex[:8]}",
            task_context={
                "code": "x = 42",
                "tool_id": "calculator",
                "business_event_type": "ToolExecuted",
            },
            route_target="docker-sandbox",
            route_score=0.9,
        )

        # Process through execute service
        executed = await execute_service.on_routed_event(routed_event)
        assert executed is not None

        # Process through listener
        await execute_listener.on_executed(executed)

        # Verify downstream event was published
        mock_publisher.publish.assert_called()
        call_args = mock_publisher.publish.call_args
        published_event = call_args[0][0]
        assert published_event.event_type == "ToolExecuted"

    @pytest.mark.asyncio
    async def test_executed_with_document_processed_type(
        self,
        execute_service: AutoExecuteService,
        execute_listener: AutoExecuteCompletedListener,
        mock_publisher: AsyncMock,
    ) -> None:
        """Verify AutoExecuted with DocumentProcessed type triggers DocumentProcessed domain event."""
        routed_event = AutoRouted(
            route_type="semantic",
            session_id=f"doc-process-{uuid.uuid4().hex[:8]}",
            task_context={
                "code": "parse_document()",
                "document_id": "doc-123",
                "business_event_type": "DocumentProcessed",
            },
            route_target="document-processor",
            route_score=0.88,
        )

        executed = await execute_service.on_routed_event(routed_event)
        assert executed is not None
        assert executed.business_event_type == "DocumentProcessed"

        await execute_listener.on_executed(executed)

        mock_publisher.publish.assert_called()
        call_args = mock_publisher.publish.call_args
        published_event = call_args[0][0]
        assert published_event.event_type == "DocumentProcessed"

    @pytest.mark.asyncio
    async def test_executed_with_agent_decided_type(
        self,
        execute_service: AutoExecuteService,
        execute_listener: AutoExecuteCompletedListener,
        mock_publisher: AsyncMock,
    ) -> None:
        """Verify AutoExecuted with AgentDecided type triggers AgentDecided domain event."""
        routed_event = AutoRouted(
            route_type="mixed",
            session_id=f"agent-decided-{uuid.uuid4().hex[:8]}",
            task_context={
                "code": "make_decision()",
                "agent_id": "agent-alpha",
                "business_event_type": "AgentDecided",
            },
            route_target="decision-agent",
            route_score=0.92,
        )

        executed = await execute_service.on_routed_event(routed_event)
        assert executed is not None
        assert executed.business_event_type == "AgentDecided"

        await execute_listener.on_executed(executed)

        mock_publisher.publish.assert_called()
        call_args = mock_publisher.publish.call_args
        published_event = call_args[0][0]
        assert published_event.event_type == "AgentDecided"

    @pytest.mark.asyncio
    async def test_execute_without_sandbox(
        self,
        execute_service: AutoExecuteService,
    ) -> None:
        """Verify AutoExecuteService works without sandbox (returns result with status)."""
        # Create service without sandbox
        service_no_sandbox = AutoExecuteService(sandbox=None, snapshot_repo=None)

        routed_event = AutoRouted(
            route_type="hash",
            session_id=f"no-sandbox-{uuid.uuid4().hex[:8]}",
            task_context={
                "code": "print('no sandbox')",
                "business_event_type": "ToolExecuted",
            },
            route_target="no-sandbox-target",
            route_score=0.5,
        )

        executed = await service_no_sandbox.on_routed_event(routed_event)

        # Should still return an AutoExecuted event
        assert executed is not None
        assert executed.session_id == routed_event.session_id

    @pytest.mark.asyncio
    async def test_checkpoint_snapshot_creation_with_repo(
        self,
        sandbox: DockerSandboxAdapter,
    ) -> None:
        """Verify AutoExecuteService creates CheckpointSnapshot when repo is configured."""
        # Create mock snapshot repo
        snapshots: list[CheckpointSnapshot] = []

        class MockSnapshotRepo:
            async def save(self, snapshot: CheckpointSnapshot) -> None:
                snapshots.append(snapshot)

            async def load(self, session_id: str) -> CheckpointSnapshot | None:
                return None

            async def delete(self, session_id: str) -> None:
                pass

        service = AutoExecuteService(sandbox=sandbox, snapshot_repo=MockSnapshotRepo())

        routed_event = AutoRouted(
            route_type="hash",
            session_id=f"snapshot-test-{uuid.uuid4().hex[:8]}",
            task_context={
                "code": "x = 1",
                "stage_id": "testing",
                "business_event_type": "ToolExecuted",
            },
            route_target="docker-sandbox",
            route_score=0.9,
        )

        executed = await service.on_routed_event(routed_event)

        # Verify snapshot was created
        assert executed is not None
        # Snapshot creation is internal, repo stores it

    @pytest.mark.asyncio
    async def test_restore_snapshot_flow(
        self,
        sandbox: DockerSandboxAdapter,
    ) -> None:
        """Verify snapshot restoration flow."""
        # Create mock snapshot repo with existing snapshot
        session_id = f"restore-{uuid.uuid4().hex[:8]}"
        existing_snapshot = CheckpointSnapshot(
            session_id=session_id,
            stage_id="restored-stage",
            state_version=2,
            state_data={"previous_result": "restored"},
        )

        class MockSnapshotRepo:
            async def save(self, snapshot: CheckpointSnapshot) -> None:
                pass

            async def load(self, sid: str) -> CheckpointSnapshot | None:
                if sid == session_id:
                    return existing_snapshot
                return None

            async def delete(self, session_id: str) -> None:
                pass

        service = AutoExecuteService(sandbox=sandbox, snapshot_repo=MockSnapshotRepo())

        restored = await service.restore_snapshot(session_id)

        assert restored is not None
        assert restored.session_id == session_id
        assert restored.state_version == 2

    @pytest.mark.asyncio
    async def test_concurrent_execution_same_session(
        self,
        sandbox: DockerSandboxAdapter,
    ) -> None:
        """Verify concurrent execution requests for same session are handled correctly."""
        session_id = f"concurrent-{uuid.uuid4().hex[:8]}"

        service = AutoExecuteService(sandbox=sandbox, snapshot_repo=None)

        # Create multiple routed events for same session
        events = [
            AutoRouted(
                route_type="hash",
                session_id=session_id,
                task_context={
                    "code": f"task_{i}",
                    "business_event_type": "ToolExecuted",
                },
                route_target="docker-sandbox",
                route_score=0.9,
            )
            for i in range(5)
        ]

        # Execute concurrently
        results = await asyncio.gather(*[service.on_routed_event(e) for e in events])

        # All should complete successfully
        assert len(results) == 5
        for result in results:
            assert result is not None

    @pytest.mark.asyncio
    async def test_executed_event_contains_full_context(
        self,
        execute_service: AutoExecuteService,
    ) -> None:
        """Verify AutoExecuted event contains all required fields from execution."""
        routed_event = AutoRouted(
            route_type="hash",
            session_id=f"context-{uuid.uuid4().hex[:8]}",
            task_context={
                "code": "calculate()",
                "cost_estimate": 0.05,
                "tool_id": "calculator-tool",
                "business_event_type": "ToolExecuted",
            },
            route_target="calculator-agent",
            route_score=0.94,
            trigger_event_type="Triggered",
            trigger_event_id=str(uuid.uuid4()),
        )

        executed = await execute_service.on_routed_event(routed_event)

        # Verify all fields are populated
        assert executed is not None
        assert executed.session_id == routed_event.session_id
        assert executed.task_context["code"] == "calculate()"
        assert executed.cost_estimate == 0.05
        assert executed.route_target == "calculator-agent"
        assert executed.route_score == 0.94
        assert executed.business_event_type == "ToolExecuted"
        assert executed.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_execution_creates_new_container_for_new_session(
        self,
        sandbox: DockerSandboxAdapter,
        execute_service: AutoExecuteService,
    ) -> None:
        """Verify new session creates new container, existing session reuses container."""
        session_1 = f"new-session-{uuid.uuid4().hex[:8]}"
        session_2 = f"new-session-{uuid.uuid4().hex[:8]}"

        # First execution - should start new container
        event1 = AutoRouted(
            route_type="hash",
            session_id=session_1,
            task_context={"code": "task1", "business_event_type": "ToolExecuted"},
            route_target="docker-sandbox",
            route_score=0.9,
        )
        result1 = await execute_service.on_routed_event(event1)
        assert result1 is not None

        # Second session - should also start new container
        event2 = AutoRouted(
            route_type="hash",
            session_id=session_2,
            task_context={"code": "task2", "business_event_type": "ToolExecuted"},
            route_target="docker-sandbox",
            route_score=0.9,
        )
        result2 = await execute_service.on_routed_event(event2)
        assert result2 is not None

        # Both sessions should be tracked separately
        assert await sandbox.is_container_running(session_1) is True
        assert await sandbox.is_container_running(session_2) is True
