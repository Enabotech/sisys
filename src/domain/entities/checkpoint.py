"""领域层检查点实体模块

定义检查点领域实体，包含阶段标识和恢复能力

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


@dataclass
class CorrectionRecord:
    """检查点纠正记录

    Attributes:
        correction_id: Unique identifier for this correction.
        correction_type: Type of correction (e.g., L0, L1, L2, L3).
        previous_value: The value before correction.
        new_value: The value after correction.
        applied_by: User or system that applied the correction.
        applied_at: Timestamp when correction was applied.
    """

    correction_type: str
    previous_value: str = ""
    new_value: str = ""
    applied_by: str = ""
    applied_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class RecoveryMode(str, Enum):
    """检查点恢复模式枚举"""

    REPLAY = "replay"
    OVERRIDE = "override"


class CheckpointStatus(str, Enum):
    """检查点完成状态枚举"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    RECOVERED = "recovered"


@dataclass
class Checkpoint:
    """检查点实体，包含阶段标识和恢复能力

    不变量约束:
    - checkpoint_id 必须为有效 UUID
    - phase_identifier 不能为空
    - status 必须为有效 CheckpointStatus
    """

    checkpoint_id: uuid.UUID
    phase_identifier: str
    status: CheckpointStatus = CheckpointStatus.PENDING
    recovery_mode: RecoveryMode | None = None
    summary: str = ""
    correction_records: list[CorrectionRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate(self) -> bool:
        """验证不变量约束

        Returns:
            所有不变量满足时返回 True

        Raises:
            ValueError: 任何不变量违反时抛出
        """
        if not isinstance(self.checkpoint_id, uuid.UUID):
            raise ValueError("checkpoint_id must be a valid UUID")
        if not self.phase_identifier or not self.phase_identifier.strip():
            raise ValueError("phase_identifier must not be empty")
        if not isinstance(self.status, CheckpointStatus):
            raise ValueError("status must be a valid CheckpointStatus")
        return True

    def complete(self) -> None:
        """标记检查点为已完成

        有效转换: PENDING -> COMPLETED, IN_PROGRESS -> COMPLETED, RECOVERED -> COMPLETED

        Raises:
            ValueError: 检查点已完成时抛出
        """
        # P1-01 Fix: Add state guard
        if self.status == CheckpointStatus.COMPLETED:
            raise ValueError("Checkpoint is already completed")
        self.status = CheckpointStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        self.updated_at = self.completed_at

    def recover(self, mode: RecoveryMode) -> None:
        """从检查点恢复，使用指定模式

        有效转换: PENDING -> RECOVERED, IN_PROGRESS -> RECOVERED, RECOVERED -> RECOVERED
        不能恢复已完成的检查点

        Args:
            mode: 恢复模式（REPLAY 或 OVERRIDE）

        Raises:
            ValueError: 检查点已完成时抛出
        """
        # P1-02 Fix: Add state guard
        if self.status == CheckpointStatus.COMPLETED:
            raise ValueError("Cannot recover a completed checkpoint")
        self.recovery_mode = mode
        self.status = CheckpointStatus.RECOVERED
        self.updated_at = datetime.now(UTC)
