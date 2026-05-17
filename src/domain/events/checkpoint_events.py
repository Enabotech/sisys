"""领域层 检查点事件模块

定义规划检查点相关的领域事件

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent
from .enums import RecoveryMode


@dataclass(frozen=True)
class CheckpointReached(DomainEvent):
    """规划检查点达成时触发的事件

    Attributes:
        checkpoint_id: 检查点唯一标识符
        event_type: 事件类型，固定为"CheckpointReached"
        phase_identifier: 阶段标识符
        user_feedback_request: 是否需要用户反馈
    """

    checkpoint_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="CheckpointReached", init=False)
    phase_identifier: str = ""
    user_feedback_request: bool = False

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.checkpoint_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Checkpoint")


@dataclass(frozen=True)
class CheckpointRecovered(DomainEvent):
    """检查点从先前状态恢复时触发的事件

    Attributes:
        checkpoint_id: 检查点唯一标识符
        event_type: 事件类型，固定为"CheckpointRecovered"
        recovery_mode: 恢复模式（Replay/OVERRIDE）
        modification_content: 修改内容字典
        affected_checkpoints: 受影响的检查点列表
        consistency_risk_level: 一致性风险级别
        execution_delay_ms: 执行延迟（毫秒）
        cost: 成本
    """

    checkpoint_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="CheckpointRecovered", init=False)
    recovery_mode: RecoveryMode = RecoveryMode.REPLAY
    modification_content: dict[str, Any] = field(default_factory=dict)
    affected_checkpoints: list[str] = field(default_factory=list)
    consistency_risk_level: str = "low"
    execution_delay_ms: float = 0.0
    cost: float = 0.0

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.checkpoint_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Checkpoint")
