"""领域层自动执行服务模块

AutoExecuteService 是在隔离会话命名空间中执行任务的领域服务
监听 AutoRouted 事件，在沙盒环境（Docker/gVisor）中执行任务，
创建状态快照用于恢复，并发布 AutoExecuted 事件给下游监听者

架构：领域层（无外部依赖），通过端口/协议实现沙盒执行和快照存储

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.events.auto_execute_events import AutoExecuted
from src.domain.events.auto_route_events import AutoRouted
from src.domain.ports.sandbox_executor import SandboxExecutor
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol

logger = logging.getLogger(__name__)


class AutoExecuteService:
    """执行 AutoRouted 事件中任务的领域服务

    职责：
    - 监听 AutoRouted 事件（来自 Story 1.14b 路由机制）
    - 在隔离沙盒（Docker/gVisor）中执行任务
    - 创建状态快照用于恢复
    - 发布 AutoExecuted 事件给下游监听者

    架构：领域层，通过端口/协议接入基础设施适配器
    """

    def __init__(
        self,
        sandbox: SandboxExecutor | None = None,
        snapshot_repo: SnapshotRepositoryProtocol | None = None,
    ):
        """初始化 AutoExecuteService

        Args:
            sandbox: 沙盒执行器端口。传入 None 用于独立测试
            snapshot_repo: 快照仓储端口。传入 None 用于独立测试
        """
        self._sandbox = sandbox
        self._snapshot_repo = snapshot_repo

    async def on_routed_event(self, event: AutoRouted) -> AutoExecuted | None:
        """处理 AutoRouted 事件：执行任务并发布 AutoExecuted 事件

        Args:
            event: 来自 Story 1.14b 的 AutoRouted 事件

        Returns:
            执行成功时返回 AutoExecuted 事件，否则返回 None
        """
        logger.debug("Processing AutoRouted event: session_id=%s", event.session_id)

        session_id = event.session_id
        task_context = event.task_context
        route_target = event.route_target
        route_score = event.route_score
        route_type = event.route_type
        trigger_event_type = event.trigger_event_type
        trigger_event_id = event.trigger_event_id

        if not session_id:
            logger.warning("AutoRouted event missing session_id, skipping execution")
            return None

        # Start sandbox if not already running
        if self._sandbox:
            await self._sandbox.start_container(session_id)

        # Execute the task
        execution_result: dict[str, Any] = {"status": "completed"}
        start_time = time.monotonic()

        try:
            if self._sandbox and task_context.get("code"):
                code = task_context["code"]
                execution_result = await self._sandbox.execute_code(session_id, code)
            else:
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
                route_type=route_type,
                trigger_event_type=trigger_event_type,
                trigger_event_id=trigger_event_id,
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

            executed = AutoExecuted(
                session_id=session_id,
                task_context=task_context,
                execution_result=execution_result,
                cost_estimate=task_context.get("cost_estimate", 0.0),
                latency_ms=latency_ms,
                business_event_type=task_context.get("business_event_type", "ToolExecuted"),
                route_target=route_target,
                route_score=route_score,
                route_type=route_type,
                trigger_event_type=trigger_event_type,
                trigger_event_id=trigger_event_id,
            )
            return executed

    async def create_snapshot(
        self,
        session_id: str,
        state: dict[str, Any],
        stage_id: str = "intermediate",
    ) -> CheckpointSnapshot | None:
        """为会话创建检查点快照

        Args:
            session_id: 会话标识符
            state: 需要快照的状态数据
            stage_id: 当前执行阶段

        Returns:
            创建的 CheckpointSnapshot，若未配置仓储则返回 None
        """
        if not self._snapshot_repo:
            logger.warning("No snapshot repository configured, skipping snapshot")
            return None

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
        """恢复会话的最新快照

        Args:
            session_id: 会话标识符

        Returns:
            恢复的 CheckpointSnapshot，若快照不存在则返回 None
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
