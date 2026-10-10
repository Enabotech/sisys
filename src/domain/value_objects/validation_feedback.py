"""Validation Feedback 值对象模块

定义 Story 4.7 反馈闭环的值对象与枚举：
- FixStrategy: 修复策略五值枚举（决策 #15 三分支 + R9-16 格④⑤可观测载体——二值枚举会把负样本命中虚标为 PURE_LLM）
- FeedbackOutcome: 闭环终态（ErrorCase.outcome 与 EvolutionLogEntry.final_status 共用）
- TriggerCode: 触发异常编码（失败模式第一维分类，AIOps failure history 基线字段）
- FixAttempt: 单次增强尝试记录（含跨尝试反馈通道的动作半边——R8-1）

设计依据：Story 4.7 AC-2/AC-3/AC-4（SDD 数据模型定稿）。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

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
    """修复策略五值枚举（决策 #15 三分支 + R9-16 格④⑤——技术债清偿 CR-R1-24
    将格④⑤从注释升格为可观测枚举值；PURE_LLM* 前缀统一可过滤「纯 LLM 修复」族）

    Attributes:
        CASE_GUIDED: 命中 RECOVERED 案例且 fix_summary 非空——注入修复配方
        NEGATIVE_CASE_GUIDED: 命中 MARKED_INFEASIBLE 案例且 category 匹配——注入负样本提示
        PURE_LLM: 无命中——纯 LLM 修复
        PURE_LLM_NO_RECIPE: 命中 RECOVERED 但 fix_summary 空（LLM_TRANSIENT 首例，
            R9-16 格④）——无可注入配方，不虚标 CASE_GUIDED
        PURE_LLM_COLLISION: 命中 MARKED_INFEASIBLE 但 category 不匹配（签名碰撞，
            R9-16 格⑤）——负样本提示抑制，不同根因不共享失败经验
    """

    CASE_GUIDED = "CASE_GUIDED"
    NEGATIVE_CASE_GUIDED = "NEGATIVE_CASE_GUIDED"
    PURE_LLM = "PURE_LLM"
    PURE_LLM_NO_RECIPE = "PURE_LLM_NO_RECIPE"
    PURE_LLM_COLLISION = "PURE_LLM_COLLISION"


class FeedbackOutcome(str, Enum):
    """反馈闭环终态枚举（EvolutionLogEntry.final_status / ErrorCase.outcome 最近一次）.

    ABORTED（技术债清偿 A 类——中止遥测，重开 R3-3「零观测」立法的中止半边）：
    仅 mid-attempt 非 LLM 中止路径写演进日志行（观测增强）；ErrorCase.outcome
    域收窄不含 ABORTED（中止不回填案例库），#17② LLM 瞬时直传维持零终态
    （重放不短路是刻意设计——R9-17）。
    """

    RECOVERED = "RECOVERED"
    MARKED_INFEASIBLE = "MARKED_INFEASIBLE"
    ABORTED = "ABORTED"


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
        fix_strategy: 修复策略五值
        stderr_excerpt: 该次失败 STDERR 摘录（截断 ≤2000；空串 = 无 STDERR 形态合法）
        suggested_fix_excerpt: 该次采纳的修复方案摘要（截断 ≤2000；空串 = fix-gen 未产出合法）
        violations_excerpt: 该次失败的 schema violations 摘要（mid-attempt 389 新违规
            反馈通道——CR-R1-22 清偿；条数截 ≤3、message 截 ≤200；空元组 = 无违规形态）
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
    violations_excerpt: tuple[dict[str, Any], ...] = ()

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
        # hex 字符集校验（R2 收紧：int(s,16) 宽容「0x」前缀/下划线分隔——fullmatch 与文案一致）
        if re.fullmatch(r"[0-9a-f]{64}", self.error_signature) is None:
            raise EntityValidationError(
                message="error_signature 必须为 hex 字符",
                context={"entity": "FixAttempt", "field": "error_signature"},
            )
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
        # violations 摘要截断（CR-R1-22：条数 ≤3 + 每条 message ≤200——防 prompt 膨胀，
        # 口径对齐事件路径 P0-H 的条数/尺寸门禁思想）
        object.__setattr__(
            self,
            "violations_excerpt",
            tuple(
                {**v, "message": str(v.get("message", ""))[:200]} if isinstance(v, dict) else v
                for v in self.violations_excerpt[:3]
            ),
        )
