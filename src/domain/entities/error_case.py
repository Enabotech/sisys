"""错误案例库聚合根模块（Story 4.7 AC-5）

定义 ErrorCase 聚合根——同根因失败的历史经验资产：
- 自然键 (tenant_id, tool_id, error_signature) 唯一，精确查表至多 1 行
- 分类计数（recovered_count/infeasible_count）防不可行写回冲掉修复配方（R1-10）
- occurrence_count 守恒 = recovered + infeasible（R3-2 定谳）
- fix_summary 仅 RECOVERED 且非 LLM_TRANSIENT 路径覆写（决策 #17①），
  V1 语义为「最近一次成功修复」（R8-20 措辞诚实化——非「最佳」，无成功率比较机制）

设计依据：Story 4.7 AC-5（SDD 数据模型定稿 + migration 017 表设计）。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.validation_feedback import FeedbackOutcome

__all__ = ["ErrorCase"]

# 摘录字段统一截断上限（与 migration 列宽 VARCHAR(2000) 同口径）
_EXCERPT_MAX_LENGTH = 2000


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
                context={"entity": "ErrorCase", "field": field_name},
            ) from exc
    raise EntityValidationError(
        message=f"{field_name} 必须为有效 UUID",
        context={"entity": "ErrorCase", "field": field_name},
    )


def _require_aware(value: datetime, field_name: str) -> datetime:
    """校验 datetime 为 timezone-aware.

    Args:
        value: 待校验时间戳
        field_name: 字段名（异常 context 用）

    Returns:
        原时间戳

    Raises:
        EntityValidationError: naive datetime
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise EntityValidationError(
            message=f"{field_name} 必须为 timezone-aware datetime",
            context={"entity": "ErrorCase", "field": field_name},
        )
    return value


@dataclass
class ErrorCase:
    """错误案例聚合根（自然键唯一——同签名失败的历史经验）

    Attributes:
        case_id: 主键
        tenant_id: 租户 ID（自然键成员）
        tool_id: 工具 ID（自然键成员）
        error_signature: 归一化错误签名（64 hex 完整 sha256——与提取器/列宽同一口径）
        error_category: 错误分类（首写定格——389-Schema=SCHEMA_VIOLATION /
            389-LLM 瞬时=LLM_TRANSIENT / 382-EXECUTION=沙箱 error_code，R3-9）
        stderr_excerpt: STDERR 摘录（截断 ≤2000）
        fix_summary: 修复配方摘要（≤2000；仅 RECOVERED 且非 LLM_TRANSIENT 覆写——决策 #17①）
        outcome: 最近一次终态（RECOVERED / MARKED_INFEASIBLE）
        recovered_count: 恢复成功计数
        infeasible_count: 不可行标记计数
        occurrence_count: 观测总计数（= recovered + infeasible，含重放递增——R9-18）
        last_seen_at: 最近观测时间
        created_at: 创建时间
    """

    tenant_id: uuid.UUID
    tool_id: uuid.UUID
    error_signature: str
    error_category: str
    outcome: FeedbackOutcome
    last_seen_at: datetime
    case_id: uuid.UUID | None = None
    stderr_excerpt: str = ""
    fix_summary: str = ""
    recovered_count: int = 0
    infeasible_count: int = 0
    occurrence_count: int = 0
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        """构造时归一主键/时间戳并校验全部不变量.

        Raises:
            EntityValidationError: 任一不变量不满足
        """
        self.case_id = _require_uuid(self.case_id if self.case_id is not None else uuid.uuid4(), "case_id")
        self.tenant_id = _require_uuid(self.tenant_id, "tenant_id")
        self.tool_id = _require_uuid(self.tool_id, "tool_id")
        self.last_seen_at = _require_aware(self.last_seen_at, "last_seen_at")
        self.created_at = _require_aware(
            self.created_at if self.created_at is not None else datetime.now(UTC),
            "created_at",
        )
        self.stderr_excerpt = (self.stderr_excerpt or "")[:_EXCERPT_MAX_LENGTH]
        self.fix_summary = (self.fix_summary or "")[:_EXCERPT_MAX_LENGTH]
        self.validate()

    def validate(self) -> bool:
        """校验聚合不变量.

        Returns:
            校验通过返回 True

        Raises:
            EntityValidationError: 签名非 64 hex / 分类计数为负 /
                occurrence 守恒破坏 / outcome 枚举域违反 / 分类为空
        """
        if not isinstance(self.error_signature, str) or len(self.error_signature) != 64:
            raise EntityValidationError(
                message="error_signature 必须为 64 hex 完整 sha256 hexdigest",
                context={"entity": "ErrorCase", "field": "error_signature"},
            )
        # hex 字符集校验（R2 收紧：int(s,16) 宽容「0x」前缀/下划线分隔——
        # sha256 hexdigest 恒为 64 位小写 hex，fullmatch 与错误文案口径一致）
        if re.fullmatch(r"[0-9a-f]{64}", self.error_signature) is None:
            raise EntityValidationError(
                message="error_signature 必须为 hex 字符",
                context={"entity": "ErrorCase", "field": "error_signature"},
            )
        if not isinstance(self.error_category, str) or not self.error_category.strip():
            raise EntityValidationError(
                message="error_category 不能为空（首写定格——category 二次过滤前提）",
                context={"entity": "ErrorCase", "field": "error_category"},
            )
        if not isinstance(self.outcome, FeedbackOutcome) or self.outcome == FeedbackOutcome.ABORTED:
            raise EntityValidationError(
                message="outcome 必须为 FeedbackOutcome 枚举成员且 ∈ {RECOVERED, MARKED_INFEASIBLE}"
                "（ABORTED 为演进日志中止态——中止不回填案例库，技术债清偿 A 类域收窄）",
                context={"entity": "ErrorCase", "field": "outcome"},
            )
        if self.recovered_count < 0 or self.infeasible_count < 0:
            raise EntityValidationError(
                message="分类计数必须 ≥ 0",
                context={"entity": "ErrorCase", "field": "recovered_count/infeasible_count"},
            )
        if self.occurrence_count != self.recovered_count + self.infeasible_count:
            raise EntityValidationError(
                message="occurrence_count 必须等于 recovered_count 与 infeasible_count 合计（守恒不变量）",
                context={"entity": "ErrorCase", "field": "occurrence_count"},
            )
        if self.occurrence_count < 1:
            raise EntityValidationError(
                message="occurrence_count 必须 ≥ 1（案例行存在即至少一次观测）",
                context={"entity": "ErrorCase", "field": "occurrence_count"},
            )
        return True

    @property
    def natural_key(self) -> tuple[uuid.UUID, uuid.UUID, str]:
        """自然键三元组（UNIQUE 约束列——精确查表的全部语义）."""
        return (self.tenant_id, self.tool_id, self.error_signature)
