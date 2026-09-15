"""领域层沙箱事件模块

定义沙箱会话生命周期与执行结果事件，继承 DomainEvent 基类，
使用基类 12 字段契约（event_id / event_type / timestamp / source /
schema_version / aggregate_id / aggregate_type / version / payload /
correlation_id / causation_id / metadata），业务字段（session_id /
container_id 等）保留为事件自有字段或合并入 payload。

设计依据：Story 4.4 硬约束
- 继承 DomainEvent 基类（src/domain/events/base.py:42-69）
- 业务主键 session_id（字符串）通过 metadata 字典传递，与基类 aggregate_id（UUID）分离
- 子类通过 event_type: str = field(default="Xxx", init=False) 标注具体类型（参考 ToolExecuted 模式）

通道映射：
- SandboxSessionStarted / SandboxSessionTerminated / SandboxExecutionFailed
  → realtime (Redis pub/sub) + reliable (RabbitMQ + Outbox) 双通道投递
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from src.domain.events.base import DomainEvent

__all__ = [
    "SandboxSessionStarted",
    "SandboxSessionTerminated",
    "SandboxExecutionFailed",
]


@dataclass(frozen=True)
class SandboxSessionStarted(DomainEvent):
    """沙箱会话启动事件

    Attributes:
        session_id: 业务标识符（字符串，匹配 ^[A-Za-z0-9_-]{1,64}$）
        container_id: Docker container ID
        image_digest: 实际启动的镜像 digest（含 sha256 前缀）
        resource_limits: 来自 ContainerSpec.to_dict()
        event_type: 事件类型，固定为 "SandboxSessionStarted"
    """

    session_id: str = ""
    container_id: str = ""
    image_digest: str = ""
    resource_limits: dict[str, Any] = field(default_factory=dict)
    event_type: str = field(default="SandboxSessionStarted", init=False)

    def __post_init__(self) -> None:
        """设置 aggregate_id / aggregate_type / metadata 关联 session_id"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", uuid.uuid4())
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "SandboxSession")
        if self.session_id and "session_id" not in self.metadata:
            object.__setattr__(self, "metadata", {**self.metadata, "session_id": self.session_id})


@dataclass(frozen=True)
class SandboxSessionTerminated(DomainEvent):
    """沙箱会话终止事件

    Attributes:
        session_id: 业务标识符
        container_id: Docker container ID
        reason: 终止原因（idle_timeout / manual / error）
        event_type: 事件类型，固定为 "SandboxSessionTerminated"
    """

    session_id: str = ""
    container_id: str = ""
    reason: str = ""
    event_type: str = field(default="SandboxSessionTerminated", init=False)

    def __post_init__(self) -> None:
        """设置 aggregate_id / aggregate_type / metadata 关联 session_id"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", uuid.uuid4())
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "SandboxSession")
        if self.session_id and "session_id" not in self.metadata:
            object.__setattr__(self, "metadata", {**self.metadata, "session_id": self.session_id})


@dataclass(frozen=True)
class SandboxExecutionFailed(DomainEvent):
    """沙箱代码执行失败事件

    Attributes:
        session_id: 业务标识符
        container_id: Docker container ID
        stderr: 标准错误输出
        exit_code: 容器内进程退出码
        error_code: 对应领域异常 code（如 EXCEPTION_316 / EXCEPTION_317）
        event_type: 事件类型，固定为 "SandboxExecutionFailed"
    """

    session_id: str = ""
    container_id: str = ""
    stderr: str = ""
    exit_code: int | None = None
    error_code: str = ""
    event_type: str = field(default="SandboxExecutionFailed", init=False)

    def __post_init__(self) -> None:
        """设置 aggregate_id / aggregate_type / metadata 关联 session_id"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", uuid.uuid4())
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "SandboxExecution")
        if self.session_id and "session_id" not in self.metadata:
            object.__setattr__(self, "metadata", {**self.metadata, "session_id": self.session_id})
