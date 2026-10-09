"""演进日志聚合根模块（Story 4.7 AC-4）

定义 EvolutionLogEntry 聚合根——反馈闭环的终态记录（AIOps failure history 基线）：
- 按 execution_id 幂等 upsert（同 execution 重复写入不产生重复行）
- trigger_code 记录失败模式第一维分类（EXCEPTION_389 / EXCEPTION_382）
- fix_attempts 携带各次 attempt_execution_id 回链（增强期间事件溯源）
- duration_sec 口径（R8-21）：从 recover() 进入到终态返回的墙钟时间
  （含 fix-gen 与重执行时长；不含基础重试阶段耗时）

设计依据：Story 4.7 AC-4（SDD 数据模型定稿 + migration 017 表设计）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.validation_feedback import FeedbackOutcome, FixAttempt, TriggerCode

__all__ = ["EvolutionLogEntry"]


def _require_uuid(value: object, field_name: str) -> uuid.UUID:
    """校验并归一为 UUID 实例.

    Args:
        value: 待校验值（接受 UUID 或可解析字符串）
        field_name: 字段名（异常 context 用）

    Returns:
        归一后的 UUID 实例

    Raises:
        EntityValidationError: 值非有效 UUID
    """
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            raise EntityValidationError(
                message=f"{field_name} 必须为有效 UUID",
                context={"entity": "EvolutionLogEntry", "field": field_name},
            ) from exc
    raise EntityValidationError(
        message=f"{field_name} 必须为有效 UUID",
        context={"entity": "EvolutionLogEntry", "field": field_name},
    )


@dataclass
class EvolutionLogEntry:
    """演进日志聚合根（execution_id 幂等——闭环终态唯一记录）

    Attributes:
        tenant_id: 租户 ID
        tool_id: 工具 ID（按工具查询反馈历史的过滤键）
        execution_id: 触发执行的 execution id（幂等键——与 382/389 context、
            两领域事件 id 全链同源，决策 #16）
        trigger_code: 触发异常编码（EXCEPTION_389 / EXCEPTION_382——失败模式第一维分类）
        error_signature: 归一化错误签名（64 hex）
        enhanced_retry_count: 增强尝试总数（1-3，总尝试语义非 3+1）
        fix_attempts: 各次尝试记录元组（含 attempt_execution_id 回链）
        duration_sec: 闭环墙钟时长（秒）
        final_status: 终态（RECOVERED / MARKED_INFEASIBLE）
        tool_version: 工具版本快照
        created_at: 创建时间
        log_id: 主键
    """

    tenant_id: uuid.UUID
    tool_id: uuid.UUID
    execution_id: uuid.UUID
    trigger_code: TriggerCode
    error_signature: str
    enhanced_retry_count: int
    fix_attempts: tuple[FixAttempt, ...]
    duration_sec: float
    final_status: FeedbackOutcome
    log_id: uuid.UUID | None = None
    tool_version: str = ""
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        """构造时归一主键/时间戳并校验全部不变量.

        Raises:
            EntityValidationError: 任一不变量不满足
        """
        self.log_id = _require_uuid(self.log_id if self.log_id is not None else uuid.uuid4(), "log_id")
        self.tenant_id = _require_uuid(self.tenant_id, "tenant_id")
        self.tool_id = _require_uuid(self.tool_id, "tool_id")
        self.execution_id = _require_uuid(self.execution_id, "execution_id")
        created = self.created_at if self.created_at is not None else datetime.now(UTC)
        if created.tzinfo is None or created.utcoffset() is None:
            raise EntityValidationError(
                message="created_at 必须为 timezone-aware datetime",
                context={"entity": "EvolutionLogEntry", "field": "created_at"},
            )
        self.created_at = created
        self.fix_attempts = tuple(self.fix_attempts)
        self.validate()

    def validate(self) -> bool:
        """校验聚合不变量.

        Returns:
            校验通过返回 True

        Raises:
            EntityValidationError: 签名非 64 hex / 尝试数越界 [1,3] /
                trigger_code 或 final_status 枚举域违反 / 计数与 attempts 不守恒
        """
        if not isinstance(self.error_signature, str) or len(self.error_signature) != 64:
            raise EntityValidationError(
                message="error_signature 必须为 64 hex 完整 sha256 hexdigest",
                context={"entity": "EvolutionLogEntry", "field": "error_signature"},
            )
        if not isinstance(self.enhanced_retry_count, int) or not 1 <= self.enhanced_retry_count <= 3:
            raise EntityValidationError(
                message="enhanced_retry_count 必须在 [1, 3]（总尝试语义）",
                context={"entity": "EvolutionLogEntry", "field": "enhanced_retry_count"},
            )
        if not isinstance(self.trigger_code, TriggerCode):
            raise EntityValidationError(
                message="trigger_code 必须为 TriggerCode 枚举成员（EXCEPTION_389/EXCEPTION_382）",
                context={"entity": "EvolutionLogEntry", "field": "trigger_code"},
            )
        if not isinstance(self.final_status, FeedbackOutcome):
            raise EntityValidationError(
                message="final_status 必须为 FeedbackOutcome 枚举成员（终态二值）",
                context={"entity": "EvolutionLogEntry", "field": "final_status"},
            )
        if not isinstance(self.duration_sec, (int, float)) or self.duration_sec < 0:
            raise EntityValidationError(
                message="duration_sec 必须 ≥ 0（闭环墙钟时长）",
                context={"entity": "EvolutionLogEntry", "field": "duration_sec"},
            )
        if len(self.fix_attempts) != self.enhanced_retry_count:
            raise EntityValidationError(
                message="fix_attempts 条数必须等于 enhanced_retry_count（每次尝试一条记录）",
                context={"entity": "EvolutionLogEntry", "field": "fix_attempts"},
            )
        return True
