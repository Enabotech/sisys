"""领域层任务级证据包值对象（Story 5-3 — 单 Agent 标准工作流）

TaskEvidencePackage——单 Agent 工作流终态的可验证结果载体（证据打包阶段产
物），六类字段齐备（输入摘要哈希/任务分解图/工具调用轨迹/中间产物快照/置信
度评分及依据/引用源列表），成功与失败终态均产包（AC-3——失败包携带失败原
因与跨重试轮全部已执行轨迹）。

出处：
- or.md §四.11.[1]（L343 结构化证据包标准——六类字段）。
- epics_v1.0.md L1562-1564（AC-3 证据打包）。
- 结构模板：工具级 EvidencePackage VO（src/domain/value_objects/tool_execution.py）
  与 _build_evidence 组装先例（tool_execution_engine.py L511-533）。

口径钉死：
- input_hash = sha256(task_description).hexdigest()（64 位十六进制——
  业务侧构造唯一口径，VO 侧守卫格式合法性）。
- status 依最终 verification_passed（通过=completed、否则 failed +
  failure_reason=末次验证失败摘要——R1-F17 判定规则）。

不可变纪律：全部集合字段为 tuple 形态（artifacts_snapshot 为元组对
tuple[tuple[str, str], ...]——frozen VO 禁可变 dict/list 字段，data_sources
tuple 同款纪律）。

校验语义：__post_init__ 为 VO 构造器守卫——校验失败抛 EntityValidationError
(242)（服务端 package 阶段不捕获本包的构造异常——证据包字段全部由服务侧
确定性组装，无 LLM 自由文本直入）。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.exceptions import EntityValidationError

#: 合法终态集合（判定规则：package 依最终 verification_passed）
_VALID_STATUSES: tuple[str, ...] = ("completed", "failed")


@dataclass(frozen=True)
class TaskEvidencePackage:
    """任务级证据包值对象（九字段，frozen 不可变）

    Attributes:
        input_hash: 任务输入摘要哈希（sha256(task_description).hexdigest()——64 位 hex）
        task_breakdown: 任务分解图（规划阶段产物步骤序列）
        tool_trace: 工具调用轨迹（含版本后缀；跨重试轮聚合——失败终态含全部已执行轨迹）
        artifacts_snapshot: 关键中间产物快照（元组对 (名称, 内容快照)——不可变纪律）
        confidence: 置信度评分（0.0-1.0——来源于验证阶段产物）
        confidence_rationale: 置信度依据（验证阶段 rationale 同源）
        citations: 引用源切片 ID 列表（工具级证据 citations 语义聚合）
        status: 终态标记（"completed"/"failed"——依最终 verification_passed）
        failure_reason: 失败原因（失败终态时非空——末次验证失败摘要；成功终态为空串）
    """

    input_hash: str
    task_breakdown: tuple[str, ...]
    tool_trace: tuple[str, ...]
    artifacts_snapshot: tuple[tuple[str, str], ...]
    confidence: float
    confidence_rationale: str
    citations: tuple[str, ...]
    status: str
    failure_reason: str = ""

    def __post_init__(self) -> None:
        """自校验：口径/范围/枚举/元组形态/失败终态守卫（242）。

        校验顺序契约：先类型守卫再值域判（truthy 标量越过判空的防线）；
        失败终态守卫（status=="failed" 时 failure_reason 非空）是 AC-3
        「失败终态含失败原因」的 VO 层兜底。
        """
        # input_hash：类型 + 64 位十六进制格式
        if not isinstance(self.input_hash, str):
            raise EntityValidationError(
                message=f"input_hash 必须为 str 类型（实际 {type(self.input_hash).__name__}）",
                context={"entity_type": "TaskEvidencePackage", "field": "input_hash"},
            )
        if len(self.input_hash) != 64 or any(c not in "0123456789abcdef" for c in self.input_hash):
            raise EntityValidationError(
                message="input_hash 必须为 sha256 十六进制摘要（64 位 hex）",
                context={"entity_type": "TaskEvidencePackage", "field": "input_hash"},
            )
        # 三 tuple 字段：形态 + 元素级类型
        for field_name in ("task_breakdown", "tool_trace", "citations"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple):
                raise EntityValidationError(
                    message=f"{field_name} 必须为 tuple 类型（实际 {type(value).__name__}）——frozen VO 禁可变序列字段",
                    context={"entity_type": "TaskEvidencePackage", "field": field_name},
                )
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    raise EntityValidationError(
                        message=f"{field_name} 元素必须为非空 str",
                        context={"entity_type": "TaskEvidencePackage", "field": field_name},
                    )
        # artifacts_snapshot：元组对形态（(名称, 内容) 二元组、两元素均 str）
        if not isinstance(self.artifacts_snapshot, tuple):
            raise EntityValidationError(
                message=f"artifacts_snapshot 必须为 tuple 类型（实际 {type(self.artifacts_snapshot).__name__}）"
                "——frozen VO 禁可变 dict 字段（元组对形态纪律）",
                context={"entity_type": "TaskEvidencePackage", "field": "artifacts_snapshot"},
            )
        for pair in self.artifacts_snapshot:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise EntityValidationError(
                    message="artifacts_snapshot 元素必须为二元组 (名称, 内容快照)",
                    context={"entity_type": "TaskEvidencePackage", "field": "artifacts_snapshot"},
                )
            if not isinstance(pair[0], str) or not isinstance(pair[1], str):
                raise EntityValidationError(
                    message="artifacts_snapshot 元组对两元素均须为 str",
                    context={"entity_type": "TaskEvidencePackage", "field": "artifacts_snapshot"},
                )
        # confidence：类型 + 范围
        if not isinstance(self.confidence, float):
            raise EntityValidationError(
                message=f"confidence 必须为 float 类型（实际 {type(self.confidence).__name__}）",
                context={"entity_type": "TaskEvidencePackage", "field": "confidence"},
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise EntityValidationError(
                message=f"confidence 必须在 [0.0, 1.0] 范围（实际 {self.confidence}）",
                context={"entity_type": "TaskEvidencePackage", "field": "confidence"},
            )
        # confidence_rationale：非空
        if not isinstance(self.confidence_rationale, str) or not self.confidence_rationale.strip():
            raise EntityValidationError(
                message="confidence_rationale 必须为非空 str（置信度评分及依据六类字段之一）",
                context={"entity_type": "TaskEvidencePackage", "field": "confidence_rationale"},
            )
        # status：二值枚举 + 失败终态守卫
        if self.status not in _VALID_STATUSES:
            raise EntityValidationError(
                message=f"status 必须为 {'/'.join(_VALID_STATUSES)} 之一（实际 {self.status!r}）",
                context={"entity_type": "TaskEvidencePackage", "field": "status"},
            )
        if not isinstance(self.failure_reason, str):
            raise EntityValidationError(
                message=f"failure_reason 必须为 str 类型（实际 {type(self.failure_reason).__name__}）",
                context={"entity_type": "TaskEvidencePackage", "field": "failure_reason"},
            )
        if self.status == "failed" and not self.failure_reason.strip():
            raise EntityValidationError(
                message="失败终态 failure_reason 必须非空（末次验证失败摘要——AC-3）",
                context={"entity_type": "TaskEvidencePackage", "field": "failure_reason"},
            )


__all__ = ["TaskEvidencePackage"]
