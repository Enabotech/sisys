"""领域层检查点实体模块

定义检查点领域实体，包含阶段标识和恢复能力
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from src.domain.exceptions import EntityStateTransitionError, EntityValidationError


@dataclass
class CorrectionRecord:
    """检查点纠正记录

    Story 6-3 复用激活注记：五字段族对齐 or.md L305 修正日志要素 5/7 MVP
    子集（correction_type=修正类型/previous_value·new_value=修正前后值/
    applied_by=修正人/applied_at=修正时间）。correction_id 仅本 docstring
    提及、类中无此字段（R1-F5 定谳的差异注记——MVP 修正定位经前后值与
    调用上下文承载）；「置信度变化/影响因子」等 6-6 审批面要素届时再扩展。
    序列化投影：经 dataclasses.asdict 等价形态入快照 state_data.
    correction_history 键（applied_at 取 isoformat() 字符串化——R8-F5）。

    Attributes:
        correction_id: Unique identifier for this correction.
            （注：仅文档语义说明，类字段区不存在 correction_id 字段。）
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

    Story 6-3 聚合激活注记（OD-12 附则 a 驱动点钦定）：创建面④步内仅当
    completed=True 时构造本聚合并调 complete()（checksum 计算前——R2A-5）；
    修正面经快照 state_data.correction_history 键投影承载（不重建聚合实例
    ——R6-8）；恢复面只读不驱动 recover()（恢复执行引擎归 6-6——R2A-4 防
    「已 completed 拒绝 recover → 243」陷阱）。序列化取舍：聚合不整体序列化
    进 state_data——仅 status 经映射进 completed 键、correction_records 经
    五字段投影进 correction_history 键。phase_identifier 复用 stage 值域
    （STAGE_VALUE_DOMAIN 同源——与 CheckpointReached.phase_identifier 同口径）。

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
            EntityValidationError: 任何不变量违反时抛出
        """
        if not isinstance(self.checkpoint_id, uuid.UUID):
            raise EntityValidationError(
                message="checkpoint_id must be a valid UUID",
                context={"entity": "Checkpoint", "field": "checkpoint_id"},
            )
        if not self.phase_identifier or not self.phase_identifier.strip():
            raise EntityValidationError(
                message="phase_identifier must not be empty",
                context={"entity": "Checkpoint", "field": "phase_identifier"},
            )
        if not isinstance(self.status, CheckpointStatus):
            raise EntityValidationError(
                message="status must be a valid CheckpointStatus",
                context={"entity": "Checkpoint", "field": "status", "expected_type": "CheckpointStatus"},
            )
        return True

    def complete(self) -> None:
        """标记检查点为已完成

        有效转换: PENDING -> COMPLETED, IN_PROGRESS -> COMPLETED, RECOVERED -> COMPLETED

        Raises:
            EntityStateTransitionError: 检查点已完成时抛出
        """
        # P1-01 Fix: Add state guard
        if self.status == CheckpointStatus.COMPLETED:
            raise EntityStateTransitionError(
                from_status=self.status.value,
                to_status="completed",
                message="Checkpoint is already completed",
            )
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
            EntityStateTransitionError: 检查点已完成时抛出
        """
        # P1-02 Fix: Add state guard
        if self.status == CheckpointStatus.COMPLETED:
            raise EntityStateTransitionError(
                from_status=self.status.value,
                to_status="recovered",
                message="Cannot recover a completed checkpoint",
            )
        self.recovery_mode = mode
        self.status = CheckpointStatus.RECOVERED
        self.updated_at = datetime.now(UTC)
