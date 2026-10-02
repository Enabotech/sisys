"""领域层红蓝辩论值对象模块

Story 4.5 — 红蓝辩论机制基础（单 Agent 多视角 MVP）的输入/输出不可变结构：
辩论视角枚举、争议议题、单视角分析、共识/分歧区域、风险全景视图、
质量评估结果与辩论结果聚合。

设计依据：
- FR-ST-05（红蓝辩论机制基础）/ FR-SP-10（温度阶梯，服务层实现，本模块不涉及）
- architecture.md §7（SYS AGENT 裁决与辩论机制）/ §7.3（终止条件算法输入）
- 领域零依赖：仅标准库（dataclasses/enum/uuid/datetime）+ 领域异常

不变量清单（违反抛 EntityValidationError EXCEPTION_242，context 携带
entity/field/value/constraint）：
1. DebateTopic.title 非空且 ≤ 200 字符；background ≤ 8000 字符
2. PerspectiveAnalysis.stance 非空；arguments 1~8 条且每条非空；
   confidence ∈ [0.0, 1.0]；perspective 枚举合法
3. ConsensusArea/DisagreementArea.area 非空；描述类字段非空；
   ConsensusArea.confidence ∈ [0.0, 1.0]
4. RiskView.consensus_areas ≥ 1 且 disagreement_areas ≥ 1；
   overall_risk_level ∈ {"LOW","MEDIUM","HIGH"}；overlap_rate ∈ [0.0, 1.0]
5. DebateQuality.overlap_rate ∈ [0.0, 1.0]；DebateResult.duration_ms ≥ 0

演进预留（V1 多轮辩论 Story 10.6 零破坏升级）：
- DebateQuality.gain_rate/repetition_rate 字段预留（MVP 单轮恒 None）
- 全部集合字段 tuple 化，状态机与迁移计数见 DebateSession 聚合根
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from src.domain.exceptions import EntityValidationError

# 风险等级合法值（Literal 语义用 frozenset 校验）
VALID_RISK_LEVELS: frozenset[str] = frozenset({"LOW", "MEDIUM", "HIGH"})

# 议题字段长度上限
TITLE_MAX_LENGTH = 200
BACKGROUND_MAX_LENGTH = 8000

# 视角论点条数边界
ARGUMENTS_MIN_COUNT = 1
ARGUMENTS_MAX_COUNT = 8


class DebatePerspective(str, Enum):
    """辩论视角枚举：红=激进派（发散），蓝=保守派（收敛）

    单 Agent 多视角 MVP 中，视角由应用层差异化 system prompt + 温度阶梯承载
    （红 T=0.8 发散 / 蓝 T=0.5 收敛）；本枚举作为视角身份的领域锚点。
    """

    RED_AGGRESSIVE = "red_aggressive"
    BLUE_CONSERVATIVE = "blue_conservative"


def _validate_non_empty(
    entity: str,
    field_name: str,
    value: str,
    *,
    allow_empty: bool = False,
) -> None:
    """校验字符串字段非空（私有助手，各 VO __post_init__ 复用）

    Args:
        entity: 实体名（context 用）
        field_name: 字段名
        value: 待校验值
        allow_empty: 是否允许空串（默认不允许）

    Raises:
        EntityValidationError: 值为空串且不允许时
    """
    if not allow_empty and not value.strip():
        raise EntityValidationError(
            message=f"{entity}.{field_name} 不能为空",
            context={
                "entity": entity,
                "field": field_name,
                "value": value,
                "constraint": "non-empty",
            },
        )


def _validate_confidence(entity: str, field_name: str, value: float) -> None:
    """校验置信度 ∈ [0.0, 1.0]（私有助手）

    Raises:
        EntityValidationError: 超出 [0.0, 1.0] 范围时
    """
    if not 0.0 <= value <= 1.0:
        raise EntityValidationError(
            message=f"{entity}.{field_name} 必须在 [0.0, 1.0] 范围内",
            context={
                "entity": entity,
                "field": field_name,
                "value": value,
                "constraint": "[0.0, 1.0]",
            },
        )


def _validate_non_empty_strings(
    entity: str,
    field_name: str,
    values: tuple[str, ...],
) -> None:
    """校验字符串元组每条非空（私有助手）

    Raises:
        EntityValidationError: 任一条为空串时
    """
    for item in values:
        if not item.strip():
            raise EntityValidationError(
                message=f"{entity}.{field_name} 的每个条目不能为空",
                context={
                    "entity": entity,
                    "field": field_name,
                    "value": item,
                    "constraint": "each-non-empty",
                },
            )


@dataclass(frozen=True)
class DebateTopic:
    """争议议题值对象（辩论输入）

    高不确定性争议议题的载体；background 供双视角引用（独立生成阶段
    双方均可见议题与背景，但互相不可见对方输出——独立立场方法论）。

    Attributes:
        tenant_id: 租户 ID
        title: 议题标题，非空且 ≤ 200 字符
        background: 议题背景与证据上下文，≤ 8000 字符，可为空
        debate_id: 辩论会话标识（与 DebateSession 聚合根共用）
        created_at: 创建时间（UTC）
    """

    tenant_id: uuid.UUID
    title: str
    background: str = ""
    debate_id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """构造时校验不变量（组 1）"""
        if not isinstance(self.tenant_id, uuid.UUID):
            raise EntityValidationError(
                message="DebateTopic.tenant_id must be a valid UUID",
                context={"entity": "DebateTopic", "field": "tenant_id", "value": self.tenant_id},
            )
        _validate_non_empty("DebateTopic", "title", self.title)
        if len(self.title) > TITLE_MAX_LENGTH:
            raise EntityValidationError(
                message=f"DebateTopic.title 长度 {len(self.title)} 超过上限 {TITLE_MAX_LENGTH}",
                context={
                    "entity": "DebateTopic",
                    "field": "title",
                    "value": len(self.title),
                    "constraint": f"≤ {TITLE_MAX_LENGTH}",
                },
            )
        if len(self.background) > BACKGROUND_MAX_LENGTH:
            raise EntityValidationError(
                message=f"DebateTopic.background 长度 {len(self.background)} 超过上限 {BACKGROUND_MAX_LENGTH}",
                context={
                    "entity": "DebateTopic",
                    "field": "background",
                    "value": len(self.background),
                    "constraint": f"≤ {BACKGROUND_MAX_LENGTH}",
                },
            )


@dataclass(frozen=True)
class PerspectiveAnalysis:
    """单视角分析值对象（红/蓝一方输出）

    Attributes:
        perspective: 辩论视角（红=激进派 / 蓝=保守派）
        stance: 一句话立场，非空
        arguments: 核心论点 1~8 条，每条非空
        risks: 该视角识别的主要风险（允许空 tuple，每条非空）
        recommendations: 该视角建议（允许空 tuple，每条非空）
        confidence: 置信度 ∈ [0.0, 1.0]
    """

    perspective: DebatePerspective
    stance: str
    arguments: tuple[str, ...]
    risks: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    confidence: float = 0.5

    def __post_init__(self) -> None:
        """构造时校验不变量（组 2）"""
        if not isinstance(self.perspective, DebatePerspective):
            raise EntityValidationError(
                message="PerspectiveAnalysis.perspective 必须是 DebatePerspective 枚举成员",
                context={
                    "entity": "PerspectiveAnalysis",
                    "field": "perspective",
                    "value": str(self.perspective),
                    "constraint": "DebatePerspective enum",
                },
            )
        _validate_non_empty("PerspectiveAnalysis", "stance", self.stance)
        argument_count = len(self.arguments)
        if not ARGUMENTS_MIN_COUNT <= argument_count <= ARGUMENTS_MAX_COUNT:
            raise EntityValidationError(
                message=(
                    f"PerspectiveAnalysis.arguments 条数 {argument_count} 超出 [{ARGUMENTS_MIN_COUNT}, {ARGUMENTS_MAX_COUNT}]"
                ),
                context={
                    "entity": "PerspectiveAnalysis",
                    "field": "arguments",
                    "value": argument_count,
                    "constraint": f"{ARGUMENTS_MIN_COUNT}~{ARGUMENTS_MAX_COUNT} 条",
                },
            )
        _validate_non_empty_strings("PerspectiveAnalysis", "arguments", self.arguments)
        _validate_non_empty_strings("PerspectiveAnalysis", "risks", self.risks)
        _validate_non_empty_strings("PerspectiveAnalysis", "recommendations", self.recommendations)
        _validate_confidence("PerspectiveAnalysis", "confidence", self.confidence)


@dataclass(frozen=True)
class ConsensusArea:
    """共识区域条目：双视角共同认可的判断

    Attributes:
        area: 共识主题，非空
        description: 共识内容，非空
        confidence: 置信度 ∈ [0.0, 1.0]
    """

    area: str
    description: str
    confidence: float = 0.5

    def __post_init__(self) -> None:
        """构造时校验不变量（组 3）"""
        _validate_non_empty("ConsensusArea", "area", self.area)
        _validate_non_empty("ConsensusArea", "description", self.description)
        _validate_confidence("ConsensusArea", "confidence", self.confidence)


@dataclass(frozen=True)
class DisagreementArea:
    """分歧区域条目：双视角立场对立点

    无 confidence 字段系有意设计——对立立场不存在单一置信度
    （红蓝各自置信度见 PerspectiveAnalysis.confidence）。

    Attributes:
        area: 分歧主题，非空
        red_position: 红方立场，非空
        blue_position: 蓝方立场，非空
        risk_note: 分歧带来的决策风险提示，非空
    """

    area: str
    red_position: str
    blue_position: str
    risk_note: str

    def __post_init__(self) -> None:
        """构造时校验不变量（组 3）"""
        _validate_non_empty("DisagreementArea", "area", self.area)
        _validate_non_empty("DisagreementArea", "red_position", self.red_position)
        _validate_non_empty("DisagreementArea", "blue_position", self.blue_position)
        _validate_non_empty("DisagreementArea", "risk_note", self.risk_note)


@dataclass(frozen=True)
class RiskView:
    """风险全景视图（辩论核心输出）

    合成阶段对比红蓝论点输出的共识/分歧全景；overlap_rate 与 warnings
    由应用层服务端注入（不信任 LLM 输出分化度，relevance_schemas computed_field
    服务端裁决先例）。

    Attributes:
        consensus_areas: 共识区域，≥ 1 条
        disagreement_areas: 分歧区域，≥ 1 条
        overall_risk_level: 整体风险等级（LOW/MEDIUM/HIGH）
        overlap_rate: 红蓝重叠率 ∈ [0.0, 1.0]
        warnings: 质量警告（如重叠率 ≥ 0.80 分化偏弱），允许空
    """

    consensus_areas: tuple[ConsensusArea, ...]
    disagreement_areas: tuple[DisagreementArea, ...]
    overall_risk_level: str
    overlap_rate: float
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """构造时校验不变量（组 4）"""
        if len(self.consensus_areas) < 1:
            raise EntityValidationError(
                message="RiskView.consensus_areas 至少 1 条（风险全景必须包含共识区域）",
                context={
                    "entity": "RiskView",
                    "field": "consensus_areas",
                    "value": len(self.consensus_areas),
                    "constraint": "≥ 1",
                },
            )
        if len(self.disagreement_areas) < 1:
            raise EntityValidationError(
                message="RiskView.disagreement_areas 至少 1 条（风险全景必须包含分歧区域）",
                context={
                    "entity": "RiskView",
                    "field": "disagreement_areas",
                    "value": len(self.disagreement_areas),
                    "constraint": "≥ 1",
                },
            )
        if self.overall_risk_level not in VALID_RISK_LEVELS:
            raise EntityValidationError(
                message=f"RiskView.overall_risk_level 非法值 {self.overall_risk_level!r}",
                context={
                    "entity": "RiskView",
                    "field": "overall_risk_level",
                    "value": self.overall_risk_level,
                    "constraint": "LOW|MEDIUM|HIGH",
                },
            )
        if not 0.0 <= self.overlap_rate <= 1.0:
            raise EntityValidationError(
                message="RiskView.overlap_rate 必须在 [0.0, 1.0] 范围内",
                context={
                    "entity": "RiskView",
                    "field": "overlap_rate",
                    "value": self.overlap_rate,
                    "constraint": "[0.0, 1.0]",
                },
            )
        _validate_non_empty_strings("RiskView", "warnings", self.warnings)


@dataclass(frozen=True)
class DebateQuality:
    """辩论质量评估结果（V1 多轮字段预留）

    MVP 单轮辩论仅 overlap_rate 有值；gain_rate（增益率）与
    repetition_rate（重复率）为 V1 多轮辩论终止条件预留（architecture.md §7.3）。

    Attributes:
        overlap_rate: 红蓝重叠率 ∈ [0.0, 1.0]（MVP 必填）
        gain_rate: 增益率（多轮概念，MVP 单轮恒 None）
        repetition_rate: 重复率（多轮概念，MVP 单轮恒 None）
    """

    overlap_rate: float
    gain_rate: float | None = None
    repetition_rate: float | None = None

    def __post_init__(self) -> None:
        """构造时校验不变量（组 5）"""
        if not 0.0 <= self.overlap_rate <= 1.0:
            raise EntityValidationError(
                message="DebateQuality.overlap_rate 必须在 [0.0, 1.0] 范围内",
                context={
                    "entity": "DebateQuality",
                    "field": "overlap_rate",
                    "value": self.overlap_rate,
                    "constraint": "[0.0, 1.0]",
                },
            )


@dataclass(frozen=True)
class DebateResult:
    """辩论结果值对象（服务返回聚合）

    Attributes:
        debate_id: 辩论会话 ID
        topic_title: 议题标题
        red_analysis: 红方（激进派）视角分析
        blue_analysis: 蓝方（保守派）视角分析
        risk_view: 风险全景视图（辩论核心输出）
        quality: 辩论质量评估
        duration_ms: 辩论耗时（毫秒），≥ 0
    """

    debate_id: uuid.UUID
    topic_title: str
    red_analysis: PerspectiveAnalysis
    blue_analysis: PerspectiveAnalysis
    risk_view: RiskView
    quality: DebateQuality
    duration_ms: int

    def __post_init__(self) -> None:
        """构造时校验不变量（组 5）"""
        if not isinstance(self.debate_id, uuid.UUID):
            raise EntityValidationError(
                message="DebateResult.debate_id must be a valid UUID",
                context={"entity": "DebateResult", "field": "debate_id", "value": self.debate_id},
            )
        _validate_non_empty("DebateResult", "topic_title", self.topic_title)
        if self.duration_ms < 0:
            raise EntityValidationError(
                message=f"DebateResult.duration_ms 不能为负（{self.duration_ms}）",
                context={
                    "entity": "DebateResult",
                    "field": "duration_ms",
                    "value": self.duration_ms,
                    "constraint": "≥ 0",
                },
            )


__all__ = [
    "ARGUMENTS_MAX_COUNT",
    "ARGUMENTS_MIN_COUNT",
    "BACKGROUND_MAX_LENGTH",
    "ConsensusArea",
    "DebatePerspective",
    "DebateQuality",
    "DebateResult",
    "DebateTopic",
    "DisagreementArea",
    "PerspectiveAnalysis",
    "RiskView",
    "TITLE_MAX_LENGTH",
    "VALID_RISK_LEVELS",
]
