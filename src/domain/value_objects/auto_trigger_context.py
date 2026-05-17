"""领域层自动触发上下文值对象模块

从领域事件或心跳事件中提取的上下文信息，用于传递给下游自动路由/
自动执行阶段。遵循六边形架构：值对象，仅包含业务逻辑，无外部依赖

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class AutoTriggerContext:
    """从自动触发事件中提取的上下文值对象（不可变）

    由 AutoTriggerService 使用，将 session_id、agent_id 和任务上下文传递给
    自动路由阶段

    Attributes:
        session_id: 会话标识符
        trigger_type: 触发类型（"domain_event" 或 "heartbeat"）
        agent_id: 代理标识符（可选）
        task_context: 任务上下文字典
        timestamp: 触发时间戳（UTC）
        source_event_type: 源事件类型
        source_event_id: 源事件标识符（可选）
    """

    session_id: str
    trigger_type: str  # "domain_event" | "heartbeat"
    agent_id: str | None = None
    task_context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_event_type: str = ""
    source_event_id: str | None = None

    def __post_init__(self) -> None:
        """校验必需字段并应用默认值"""
        if not self.session_id:
            # Use default session when none provided
            object.__setattr__(self, "session_id", "default")

    @classmethod
    def from_domain_event(
        cls,
        event_type: str,
        payload: dict[str, Any],
        event_id: str | None = None,
    ) -> AutoTriggerContext:
        """从领域事件载荷中提取自动触发上下文

        Args:
            event_type: 领域事件类型（如 "DocumentProcessed"）
            payload: 事件载荷字典
            event_id: 事件标识符（可选）

        Returns:
            提取字段后的 AutoTriggerContext 实例
        """
        # Extract session_id from various possible locations
        session_id = (
            payload.get("session_id")
            or payload.get("payload", {}).get("session_id")
            or payload.get("aggregate_id")
            or "default"
        )
        # Extract agent_id
        agent_id = payload.get("agent_id") or payload.get("payload", {}).get("agent_id")
        # Extract task context
        task_context = {
            k: v
            for k, v in payload.items()
            if k
            in (
                "task_type",
                "priority",
                "tool_name",
                "checkpoint_id",
                "correction_type",
                "routing_decision",
                "isolation_level",
                "document_id",
                "strategy_id",
                "agent_id",
                "session_id",
                "error_message",
                "retry_count",
            )
            and k not in ("aggregate_id", "event_id", "event_type")
        }

        return cls(
            session_id=session_id,
            trigger_type="domain_event",
            agent_id=agent_id,
            task_context=task_context,
            source_event_type=event_type,
            source_event_id=event_id,
        )

    @classmethod
    def from_heartbeat(
        cls,
        heartbeat_id: str,
        wake_reason: str = "",
        todo_items: tuple[str, ...] | None = None,
        cost_budget: float = 0.0,
    ) -> AutoTriggerContext:
        """从心跳事件中提取自动触发上下文

        Args:
            heartbeat_id: 心跳唯一标识符
            wake_reason: 唤醒原因（scheduled/user_request/system_recovery）
            todo_items: 待办任务列表
            cost_budget: 成本预算上限

        Returns:
            从心跳派生的 AutoTriggerContext 实例
        """
        return cls(
            session_id="heartbeat-scheduler",
            trigger_type="heartbeat",
            agent_id=None,
            task_context={
                "heartbeat_id": heartbeat_id,
                "wake_reason": wake_reason,
                "todo_items": list(todo_items) if todo_items else [],
                "cost_budget": cost_budget,
            },
            source_event_type="HeartbeatTriggered",
            source_event_id=heartbeat_id,
        )
