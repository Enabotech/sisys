"""SISYS 领域层智能体实体模块。

定义智能体领域实体，包含身份画像、职责边界和状态机转换逻辑。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class AgentRole(str, Enum):
    """智能体角色枚举。"""

    CEO = "ceo"
    CFO = "cfo"
    CMO = "cmo"
    CTO = "cto"
    COO = "coo"
    CHO = "cho"
    AUD = "aud"
    SYS = "sys"


class AgentStatus(str, Enum):
    """智能体执行状态枚举。"""

    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Agent:
    """智能体实体，包含身份画像和职责边界。

    不变量约束:
    - agent_id 必须为有效 UUID
    - role 必须为有效 AgentRole
    - name 不能为空

    Attributes:
        agent_id: 智能体唯一标识符。
        role: 智能体角色。
        name: 智能体名称。
        description: 智能体描述。
        status: 当前执行状态。
        failure_reason: 失败原因。
        domain_knowledge: 领域知识列表。
        responsibilities: 职责列表。
        created_at: 创建时间。
        updated_at: 最后更新时间。
    """

    agent_id: uuid.UUID
    role: AgentRole
    name: str
    description: str = ""
    status: AgentStatus = AgentStatus.IDLE
    failure_reason: str = ""
    domain_knowledge: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate(self) -> bool:
        """验证不变量约束。

        Returns:
            所有不变量满足时返回 True。

        Raises:
            ValueError: 任何不变量违反时抛出。
        """
        if not isinstance(self.agent_id, uuid.UUID):
            raise ValueError("agent_id must be a valid UUID")
        if not isinstance(self.role, AgentRole):
            raise ValueError("role must be a valid AgentRole")
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        return True

    # P1-05 Fix: Add state transition methods
    def start(self) -> None:
        """将智能体从 IDLE 转换为 RUNNING。

        Raises:
            ValueError: 智能体不处于 IDLE 状态时抛出。
        """
        if self.status != AgentStatus.IDLE:
            raise ValueError(f"Can only start from IDLE, current: {self.status.value}")
        self.status = AgentStatus.RUNNING
        self.updated_at = datetime.now(UTC)

    def complete(self) -> None:
        """将智能体从 RUNNING 转换为 COMPLETED。

        Raises:
            ValueError: 智能体不处于 RUNNING 状态时抛出。
        """
        if self.status != AgentStatus.RUNNING:
            raise ValueError(f"Can only complete from RUNNING, current: {self.status.value}")
        self.status = AgentStatus.COMPLETED
        self.updated_at = datetime.now(UTC)

    def fail(self, reason: str = "") -> None:
        """将智能体转换为 FAILED 状态。

        Args:
            reason: 可选的失败原因，用于诊断。

        Raises:
            ValueError: 智能体已处于 FAILED 状态时抛出。
        """
        # P1-03 Fix: Reject re-failing an already failed agent
        if self.status == AgentStatus.FAILED:
            raise ValueError(f"Agent is already failed (reason: {self.failure_reason!r})")
        self.failure_reason = reason
        self.status = AgentStatus.FAILED
        self.updated_at = datetime.now(UTC)

    def restart(self) -> None:
        """将失败或已完成的智能体重置为 IDLE。

        Raises:
            ValueError: 智能体不处于 FAILED 或 COMPLETED 状态时抛出。
        """
        if self.status not in (AgentStatus.FAILED, AgentStatus.COMPLETED):
            raise ValueError(f"Can only restart from FAILED or COMPLETED, current: {self.status.value}")
        self.failure_reason = ""
        self.status = AgentStatus.IDLE
        self.updated_at = datetime.now(UTC)

    def wait(self) -> None:
        """将智能体转换为 WAITING 状态。"""
        if self.status not in (AgentStatus.RUNNING, AgentStatus.WAITING):
            raise ValueError(f"Can only wait from RUNNING or WAITING, current: {self.status.value}")
        self.status = AgentStatus.WAITING
        self.updated_at = datetime.now(UTC)
