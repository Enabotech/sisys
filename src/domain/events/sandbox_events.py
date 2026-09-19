"""领域层沙箱事件模块

定义沙箱执行相关的领域事件。
Story 4.4 — Docker 沙箱执行：
- SandboxSessionStarted: 沙箱会话启动事件（双通道 reliable）
- SandboxSessionTerminated: 沙箱会话终止事件（双通道 reliable）
- SandboxExecutionFailed: 沙箱执行失败事件（双通道 reliable）

事件聚合根设计：
- aggregate_type = "SandboxSession"（字符串 session_id 通过 metadata.session_id 关联）
- aggregate_id = UUID（与 session_id 字符串分离，符合 DomainEvent 基类约定）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class SandboxSessionStarted(DomainEvent):
    """沙箱会话启动事件

    Attributes:
        session_id: 业务会话标识符（字符串，匹配 ^[A-Za-z0-9_-]{1,64}$）
        container_id: Docker 容器 ID
        image_digest: 实际启动的镜像 digest
        resource_limits: 容器资源限制字典（来自 ContainerSpec.to_dict()）
        event_type: 事件类型，固定为"SandboxSessionStarted"
    """

    session_id: str = ""
    container_id: str = ""
    image_digest: str = ""
    resource_limits: dict[str, Any] = field(default_factory=dict)
    event_type: str = field(default="SandboxSessionStarted", init=False)

    def __post_init__(self) -> None:
        """设置 aggregate_id 和 aggregate_type,session_id 通过 metadata 透传"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", uuid.uuid4())
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "SandboxSession")
        if "session_id" not in self.metadata and self.session_id:
            object.__setattr__(
                self,
                "metadata",
                {**self.metadata, "session_id": self.session_id},
            )


@dataclass(frozen=True)
class SandboxSessionTerminated(DomainEvent):
    """沙箱会话终止事件

    Attributes:
        session_id: 业务会话标识符
        container_id: Docker 容器 ID
        termination_reason: 终止原因（如 idle_timeout / explicit_stop / orphan_cleanup）
        duration_sec: 会话持续时长（秒）
        event_type: 事件类型，固定为"SandboxSessionTerminated"
    """

    session_id: str = ""
    container_id: str = ""
    termination_reason: str = ""
    duration_sec: float = 0.0
    event_type: str = field(default="SandboxSessionTerminated", init=False)

    def __post_init__(self) -> None:
        """设置 aggregate_id 和 aggregate_type,session_id 通过 metadata 透传"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", uuid.uuid4())
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "SandboxSession")
        if "session_id" not in self.metadata and self.session_id:
            object.__setattr__(
                self,
                "metadata",
                {**self.metadata, "session_id": self.session_id},
            )


@dataclass(frozen=True)
class SandboxExecutionFailed(DomainEvent):
    """沙箱执行失败事件

    Attributes:
        session_id: 业务会话标识符
        execution_id: 执行实例 ID（用于关联 Validation Feedback 闭环）
        error_code: 异常编码（如 EXCEPTION_315-319）
        error_message: 异常消息
        stderr: 标准错误输出（用于 Story 4.7 Validation Feedback）
        event_type: 事件类型，固定为"SandboxExecutionFailed"
    """

    session_id: str = ""
    execution_id: str = ""
    error_code: str = ""
    error_message: str = ""
    stderr: str = ""
    event_type: str = field(default="SandboxExecutionFailed", init=False)

    def __post_init__(self) -> None:
        """设置 aggregate_id 和 aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", uuid.uuid4())
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "SandboxSession")
        if "session_id" not in self.metadata and self.session_id:
            object.__setattr__(
                self,
                "metadata",
                {**self.metadata, "session_id": self.session_id},
            )


__all__ = [
    "SandboxSessionStarted",
    "SandboxSessionTerminated",
    "SandboxExecutionFailed",
]
