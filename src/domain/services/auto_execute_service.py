"""AutoExecuteService — domain service that executes tasks in isolated session namespaces.

Responsibilities:
- Listen to AutoRouted events from Story 1.14b
- Execute tasks in sandboxed environment (Docker/gVisor)
- Create state snapshots for recovery
- Publish AutoExecuted events to downstream listeners

Architecture: Domain layer (no external dependencies), uses port/protocol for
sandbox execution and snapshot storage.
"""

from __future__ import annotations

import logging
from typing import Any

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.events.auto_execute_events import AutoExecuted
from src.domain.events.base import DomainEvent
from src.domain.ports.sandbox_executor_protocol import SandboxExecutorProtocol
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol

logger = logging.getLogger(__name__)


class AutoExecuteService:
    """Domain service that executes tasks from AutoRouted events.

    Responsibilities:
    - Listen to AutoRouted events (from Story 1.14b route mechanism)
    - Execute tasks in isolated sandbox (Docker/gVisor)
    - Create state snapshots for recovery
    - Publish AutoExecuted events to downstream listeners

    Architecture: Domain layer, uses port/protocol for infrastructure adapters.
    """

    def __init__(
        self,
        sandbox: SandboxExecutorProtocol | None = None,
        snapshot_repo: SnapshotRepositoryProtocol | None = None,
    ):
        """Initialize AutoExecuteService.

        Args:
            sandbox: Sandbox executor port. None for standalone testing.
            snapshot_repo: Snapshot repository port. None for standalone testing.
        """
        self._sandbox = sandbox
        self._snapshot_repo = snapshot_repo

    async def on_routed_event(self, event: DomainEvent) -> AutoExecuted | None:
        """Handle a AutoRouted event: execute task and publish AutoExecuted event.

        Args:
            event: AutoRouted event from Story 1.14b

        Returns:
            AutoExecuted event if execution was successful, None otherwise
        """
        logger.debug("Processing AutoRouted event: session_id=%s", getattr(event, "session_id", "unknown"))

        # Extract fields from AutoRouted event
        session_id = getattr(event, "session_id", "")
        task_context = getattr(event, "task_context", {})
        route_target = getattr(event, "route_target", "")
        route_score = getattr(event, "route_score", 0.0)
        route_type = getattr(event, "route_type", "")

        if not session_id:
            logger.warning("AutoRouted event missing session_id, skipping execution")
            return None

        # Start sandbox if not already running
        if self._sandbox:
            await self._sandbox.start_container(session_id)

        # Execute the task
        execution_result: dict[str, Any] = {"status": "completed"}
        import time

        start_time = time.monotonic()

        try:
            if self._sandbox and task_context.get("code"):
                # Execute code in sandbox
                code = task_context["code"]
                execution_result = await self._sandbox.execute_code(session_id, code)
            else:
                # No code to execute, just mark as completed
                execution_result = {"status": "completed", "message": "No code to execute"}

            latency_ms = (time.monotonic() - start_time) * 1000

            # Create snapshot after execution
            if self._snapshot_repo:
                snapshot = CheckpointSnapshot(
                    session_id=session_id,
                    stage_id=task_context.get("stage_id", "completed"),
                    state_version=1,
                    state_data={
                        "last_execution_result": execution_result,
                        "route_target": route_target,
                        "route_score": route_score,
                        "route_type": route_type,
                    },
                )
                await self._snapshot_repo.save(snapshot)

            # Determine business event type from task context
            business_event_type = task_context.get("business_event_type", "ToolExecuted")

            executed = AutoExecuted(
                session_id=session_id,
                task_context=task_context,
                execution_result=execution_result,
                cost_estimate=task_context.get("cost_estimate", 0.0),
                latency_ms=latency_ms,
                business_event_type=business_event_type,
                route_target=route_target,
                route_score=route_score,
            )

            logger.info(
                "Executed task: session_id=%s business_event_type=%s latency_ms=%.2f",
                session_id,
                business_event_type,
                latency_ms,
            )
            return executed

        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.error("Execution failed: session_id=%s error=%s", session_id, e)
            execution_result = {"status": "failed", "error": str(e)}

            # Still publish AutoExecuted event with failure status
            executed = AutoExecuted(
                session_id=session_id,
                task_context=task_context,
                execution_result=execution_result,
                cost_estimate=task_context.get("cost_estimate", 0.0),
                latency_ms=latency_ms,
                business_event_type=task_context.get("business_event_type", "ToolExecuted"),
                route_target=route_target,
                route_score=route_score,
            )
            return executed

    async def create_snapshot(
        self,
        session_id: str,
        state: dict[str, Any],
        stage_id: str = "intermediate",
    ) -> CheckpointSnapshot | None:
        """Create a checkpoint snapshot for the session.

        Args:
            session_id: Session identifier
            state: State data to snapshot
            stage_id: Current execution stage

        Returns:
            Created CheckpointSnapshot or None if no repository configured
        """
        if not self._snapshot_repo:
            logger.warning("No snapshot repository configured, skipping snapshot")
            return None

        # Load existing snapshot to get version
        existing = await self._snapshot_repo.load(session_id)
        version = existing.state_version + 1 if existing else 1

        snapshot = CheckpointSnapshot(
            session_id=session_id,
            stage_id=stage_id,
            state_version=version,
            state_data=state,
        )

        await self._snapshot_repo.save(snapshot)
        logger.debug("Created snapshot: session_id=%s version=%d", session_id, version)
        return snapshot

    async def restore_snapshot(self, session_id: str) -> CheckpointSnapshot | None:
        """Restore the latest snapshot for a session.

        Args:
            session_id: Session identifier

        Returns:
            Restored CheckpointSnapshot or None if no snapshot exists
        """
        if not self._snapshot_repo:
            logger.warning("No snapshot repository configured, cannot restore")
            return None

        snapshot = await self._snapshot_repo.load(session_id)
        if snapshot:
            logger.info("Restored snapshot: session_id=%s version=%d", session_id, snapshot.state_version)
        else:
            logger.warning("No snapshot found for session_id=%s", session_id)
        return snapshot
