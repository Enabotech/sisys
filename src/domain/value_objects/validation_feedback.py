"""Validation Feedback 值对象模块

定义 Story 4.7 反馈闭环的值对象与枚举：
- FixStrategy: 修复策略三分支（决策 #15——二值枚举会把负样本命中虚标为 PURE_LLM）
- FeedbackOutcome: 闭环终态（ErrorCase.outcome 与 EvolutionLogEntry.final_status 共用）
- TriggerCode: 触发异常编码（失败模式第一维分类，AIOps failure history 基线字段）
- FixAttempt: 单次增强尝试记录（含跨尝试反馈通道的动作半边——R8-1）

设计依据：Story 4.7 AC-2/AC-3/AC-4（SDD 数据模型定稿）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from src.domain.exceptions import EntityValidationError

__all__ = [
    "FeedbackOutcome",
    "FixAttempt",
    "FixStrategy",
    "TriggerCode",
]

# 摘录字段统一截断上限（stderr/suggested_fix 同口径，防 DoS 与存储溢出）
_EXCERPT_MAX_LENGTH = 2000


class FixStrategy(str, Enum):
    """修复策略三分支枚举（决策 #15）

    Attributes:
        CASE_GUIDED: 命中 RECOVERED 案例且 fix_summary 非空——注入修复配方
        NEGATIVE_CASE_GUIDED: 命中 MARKED_INFEASIBLE 案例且 category 匹配——注入负样本提示
        PURE_LLM: 无命中（或命中但无可注入配方/碰撞抑制——R9-16 格④⑤注记）——纯 LLM 修复
    """

    CASE_GUIDED = "CASE_GUIDED"
    NEGATIVE_CASE_GUIDED = "NEGATIVE_CASE_GUIDED"
    PURE_LLM = "PURE_LLM"


class FeedbackOutcome(str, Enum):
    """反馈闭环终态枚举（ErrorCase.outcome 最近一次 / EvolutionLogEntry.final_status）"""

    RECOVERED = "RECOVERED"
    MARKED_INFEASIBLE = "MARKED_INFEASIBLE"


class TriggerCode(str, Enum):
    """触发异常编码枚举（失败模式第一维分类）

    Attributes:
        EXCEPTION_389: OUTPUT 校验基础重试耗尽（Schema 违规 / LLM 瞬时两子路径）
        EXCEPTION_382: 执行失败（stage=EXECUTION 且 cause ∈ ExecutionError 族）
    """

    EXCEPTION_389 = "EXCEPTION_389"
    EXCEPTION_382 = "EXCEPTION_382"


def _truncate(value: str, limit: int = _EXCERPT_MAX_LENGTH) -> str:
    """截断字符串至指定长度.

    Args:
        value: 原始字符串
        limit: 上限（默认 2000——摘录字段统一口径）

    Returns:
        截断后的字符串（len(value) <= limit 恒成立）
    """
    return value[:limit] if len(value) > limit else value


@dataclass(frozen=True)
class FixAttempt:
    """单次增强尝试记录值对象（frozen）

    跨尝试反馈通道（Reflexion 动作+结果成对——R8-1）：
    attempt k 的修复 prompt 携带 attempt 1..k-1 的 stderr_excerpt（结果半边）
    与 suggested_fix_excerpt（动作半边——「禁止重复失败方案」指令的指涉对象）。

    Attributes:
        attempt_no: 尝试序号（1-based）
        attempt_execution_id: 该次重执行的 execution id（入口注入或引擎兜底新铸——决策 #16；
            空串 = 未发生重执行的合法形态（llm_generation_failed 形态），R2-9 禁立 UUID 不变量）
        error_signature: 该次失败的归一化签名
        fix_strategy: 修复策略三分支
        stderr_excerpt: 该次失败 STDERR 摘录（截断 ≤2000；空串 = 无 STDERR 形态合法）
        suggested_fix_excerpt: 该次采纳的修复方案摘要（截断 ≤2000；空串 = fix-gen 未产出合法）
        succeeded: 该次尝试是否成功
        detail: 失败类型描述（retry_failed / llm_generation_failed / 成功形态描述）
    """

    attempt_no: int
    error_signature: str
    fix_strategy: FixStrategy
    succeeded: bool
    detail: str = ""
    attempt_execution_id: str = ""
    stderr_excerpt: str = ""
    suggested_fix_excerpt: str = ""

    def __post_init__(self) -> None:
        """构造时校验不变量并截断摘录字段.

        Raises:
            EntityValidationError: attempt_no 非 1-based / 签名非 64 hex /
                attempt_execution_id 非空且非合法 UUID / 枚举域违反
        """
        if not isinstance(self.attempt_no, int) or self.attempt_no < 1:
            raise EntityValidationError(
                message="attempt_no 必须为 1-based 正整数",
                context={"entity": "FixAttempt", "field": "attempt_no"},
            )
        if not isinstance(self.error_signature, str) or len(self.error_signature) != 64:
            raise EntityValidationError(
                message="error_signature 必须为 64 hex 完整 sha256 hexdigest",
                context={"entity": "FixAttempt", "field": "error_signature"},
            )
        try:
            int(self.error_signature, 16)
        except ValueError as exc:
            raise EntityValidationError(
                message="error_signature 必须为 hex 字符",
                context={"entity": "FixAttempt", "field": "error_signature"},
            ) from exc
        if self.attempt_execution_id:
            try:
                uuid.UUID(self.attempt_execution_id)
            except (ValueError, AttributeError) as exc:
                raise EntityValidationError(
                    message="attempt_execution_id 非空时必须为合法 UUID 字符串",
                    context={"entity": "FixAttempt", "field": "attempt_execution_id"},
                ) from exc
        if not isinstance(self.fix_strategy, FixStrategy):
            raise EntityValidationError(
                message="fix_strategy 必须为 FixStrategy 枚举成员",
                context={"entity": "FixAttempt", "field": "fix_strategy"},
            )
        # frozen 实例的截断经 object.__setattr__（__post_init__ 内合法通道）
        object.__setattr__(self, "stderr_excerpt", _truncate(self.stderr_excerpt))
        object.__setattr__(self, "suggested_fix_excerpt", _truncate(self.suggested_fix_excerpt))
