"""领域层 审计事件模块

定义审计日志相关的领域事件，满足等保2.0合规要求

AC-1 标准字段 (FR-SC-02):
    log_id: 审计日志条目的UUID标识符
    timestamp: 操作发生时间（UTC）
    actor: 执行操作的用户ID或系统组件
    action_type: 执行的操作类型
    target_resource: 被操作的资源
    old_value: 操作前状态（JSON）
    new_value: 操作后状态（JSON）

扩展字段 (FR-SC-04 多维搜索):
    correction_level: 纠正级别（L0-L3），用于追踪相关事件

参考: Story 1.10 SDD规范定义

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from src.domain.events.base import DomainEvent


class AuditActionType(str, Enum):
    """系统操作的审计动作类型

    包含认证、授权、文档、Agent、检查点、纠正和系统等各类操作
    """

    # Authentication events - 认证事件
    AUTHENTICATION_LOGIN = "authentication:login"
    AUTHENTICATION_LOGOUT = "authentication:logout"
    AUTHENTICATION_FAILED = "authentication:failed"
    AUTHENTICATION_LOCKED = "authentication:locked"

    # Authorization events - 授权事件
    AUTHORIZATION_GRANT = "authorization:grant"
    AUTHORIZATION_REVOKE = "authorization:revoke"
    AUTHORIZATION_ACCESS = "authorization:access"

    # Document events - 文档事件
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_DOWNLOAD = "document:download"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_PROCESS = "document:process"

    # Agent events - Agent事件
    AGENT_DECIDE = "agent:decide"
    AGENT_EXECUTE = "agent:execute"
    AGENT_ROUTE = "agent:route"

    # Checkpoint events - 检查点事件
    CHECKPOINT_CREATE = "checkpoint:create"
    CHECKPOINT_RESTORE = "checkpoint:restore"
    CHECKPOINT_REPLAY = "checkpoint:replay"

    # Correction events - 纠正事件
    CORRECTION_APPROVE = "correction:approve"
    CORRECTION_REJECT = "correction:reject"
    CORRECTION_APPLY = "correction:apply"

    # System events - 系统事件
    SYSTEM_CONFIG_CHANGE = "system:config_change"
    SYSTEM_INIT = "system:init"
    SYSTEM_SHUTDOWN = "system:shutdown"


@dataclass(frozen=True)
class AuditEvent(DomainEvent):
    """审计日志条目的领域事件

    继承DomainEvent并添加审计特定字段，满足FR-SC-02要求

    Attributes:
        event_id: 唯一事件标识符（继承自DomainEvent）
        event_type: 事件类型，固定为"AuditEvent"（继承自DomainEvent）
        timestamp: 审计操作发生时间（继承自DomainEvent）
        source: 产生此事件的系统组件
        aggregate_id: 被审计实体的ID
        aggregate_type: 被审计实体的类型
        log_id: 审计日志条目的UUID标识符
        actor: 用户ID或系统组件
        action_type: 执行的操作类型
        target_resource: 被操作的资源
        old_value: 操作前状态（JSON）
        new_value: 操作后状态（JSON）
        correction_level: 纠正级别（L0-L3，可选）
    """

    event_type: str = field(default="AuditEvent", init=False)
    source: str = "audit"
    log_id: UUID = field(default_factory=uuid4)
    actor: str = ""
    action_type: str = ""
    target_resource: str = ""
    old_value: dict[str, Any] = field(default_factory=dict)
    new_value: dict[str, Any] = field(default_factory=dict)
    correction_level: int | None = None

    def __post_init__(self) -> None:
        """初始化后验证必填字段"""
        if not self.actor:
            raise ValueError("actor is required for AuditEvent")
        if not self.action_type:
            raise ValueError("action_type is required for AuditEvent")
        if self.correction_level is not None and not (0 <= self.correction_level <= 3):
            raise ValueError("correction_level must be 0-3 or None")

    def to_audit_dict(self) -> dict[str, Any]:
        """序列化为审计专用字典格式

        Returns:
            包含FR-SC-02字段的字典：log_id、timestamp、actor、
            action_type、target_resource、old_value、new_value
        """
        return {
            "log_id": str(self.log_id),
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "action_type": self.action_type,
            "target_resource": self.target_resource,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "correction_level": self.correction_level,
        }
