"""应用层红蓝辩论 LLM 结构化输出 Schema 模块

Story 4.5 — 定义红/蓝视角分析与风险全景视图合成的 Pydantic 结构化 Schema
（LLM structured_generate 的 response_schema 契约）。

设计决策：
- 定义在应用层（src/application/），允许依赖 Pydantic（领域零依赖红线）
- RiskViewSchema **不含** overlap_rate/warnings 字段——由服务端注入
  （不信任 LLM 输出分化度，relevance_schemas computed_field 服务端裁决先例）
- to_domain() 承担 list→tuple 转换职责（VO 字段全 tuple，Schema 全 list）
  并以 perspective 参数区分红/蓝（同一 Schema 双视角复用）
- Pydantic 校验 + 领域 VO 双重不变量（VO __post_init__ 兜底）
- NonEmptyStr 条目级非空校验（R1-F02 根因修复）：strip_whitespace + min_length=1
  对齐 VO 的 strip 判空语义，使空串/纯空白条目在 LLM 解析层即拒（客户端
  ValidationError 触发 tenacity 重试自纠）；选型依据——pydantic v2 的
  Field(strip_whitespace=True) 是 deprecated no-op 且会泄漏脏键进发给 LLM 的
  JSON Schema，Annotated+StringConstraints 是唯一正确机制（model_json_schema
  输出干净携带 minLength，约束解码正确受益）
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from src.domain.value_objects.debate import (
    ConsensusArea,
    DebatePerspective,
    DisagreementArea,
    PerspectiveAnalysis,
    RiskView,
)

# 条目级非空字符串约束（strip 后非空）——R1-F02 根因修复的单一事实源
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ConsensusAreaSchema(BaseModel):
    """共识区域条目 Schema（合成输出嵌套结构）"""

    area: NonEmptyStr = Field(..., description="共识主题")
    description: NonEmptyStr = Field(..., description="共识内容")
    confidence: float = Field(..., ge=0.0, le=1.0, description="共识置信度（0-1）")

    def to_domain_value(self) -> ConsensusArea:
        """转换为 ConsensusArea 领域值对象"""
        return ConsensusArea(area=self.area, description=self.description, confidence=self.confidence)


class DisagreementAreaSchema(BaseModel):
    """分歧区域条目 Schema（合成输出嵌套结构）"""

    area: NonEmptyStr = Field(..., description="分歧主题")
    red_position: NonEmptyStr = Field(..., description="红方（激进派）立场")
    blue_position: NonEmptyStr = Field(..., description="蓝方（保守派）立场")
    risk_note: NonEmptyStr = Field(..., description="分歧带来的决策风险提示")

    def to_domain_value(self) -> DisagreementArea:
        """转换为 DisagreementArea 领域值对象"""
        return DisagreementArea(
            area=self.area,
            red_position=self.red_position,
            blue_position=self.blue_position,
            risk_note=self.risk_note,
        )


class PerspectiveAnalysisSchema(BaseModel):
    """单视角分析 Schema（红/蓝双视角共用，perspective 由调用方指定）

    LLM 结构化输出契约：stance + arguments（1~8 条）+ risks + recommendations + confidence。
    """

    stance: NonEmptyStr = Field(..., description="一句话立场")
    arguments: list[NonEmptyStr] = Field(
        ...,
        min_length=1,
        max_length=8,
        description="核心论点（1~8 条，每条非空）",
    )
    risks: list[NonEmptyStr] = Field(
        default_factory=list,
        description="该视角识别的主要风险（允许空）",
    )
    recommendations: list[NonEmptyStr] = Field(
        default_factory=list,
        description="该视角建议（允许空）",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度（0-1）")

    def to_domain(self, perspective: DebatePerspective) -> PerspectiveAnalysis:
        """转换为领域 PerspectiveAnalysis 值对象（list→tuple 转换职责）

        Args:
            perspective: 辩论视角（红=激进派 / 蓝=保守派，由调用方指定）

        Returns:
            PerspectiveAnalysis 领域值对象（Pydantic 校验 + VO 不变量双重保障）
        """
        return PerspectiveAnalysis(
            perspective=perspective,
            stance=self.stance,
            arguments=tuple(self.arguments),
            risks=tuple(self.risks),
            recommendations=tuple(self.recommendations),
            confidence=self.confidence,
        )


class RiskViewSchema(BaseModel):
    """风险全景视图 Schema（合成阶段输出）

    注意：**不含** overlap_rate 与 warnings——两项由服务端计算注入
    （不信任 LLM 输出分化度），见 to_domain 参数。
    """

    consensus_areas: list[ConsensusAreaSchema] = Field(
        ...,
        min_length=1,
        description="共识区域（至少 1 条）",
    )
    disagreement_areas: list[DisagreementAreaSchema] = Field(
        ...,
        min_length=1,
        description="分歧区域（至少 1 条）",
    )
    overall_risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        ...,
        description="整体风险等级",
    )

    def to_domain(
        self,
        overlap_rate: float,
        warnings: tuple[str, ...] = (),
    ) -> RiskView:
        """转换为领域 RiskView 值对象（服务端注入分化度量）

        Args:
            overlap_rate: 红蓝重叠率（服务端经 DebateEvaluator.evaluate_overlap 计算）
            warnings: 质量警告（如重叠率 ≥ 0.80 分化偏弱，服务端裁决）

        Returns:
            RiskView 领域值对象
        """
        return RiskView(
            consensus_areas=tuple(area.to_domain_value() for area in self.consensus_areas),
            disagreement_areas=tuple(area.to_domain_value() for area in self.disagreement_areas),
            overall_risk_level=self.overall_risk_level,
            overlap_rate=overlap_rate,
            warnings=warnings,
        )


__all__ = [
    "ConsensusAreaSchema",
    "DisagreementAreaSchema",
    "PerspectiveAnalysisSchema",
    "RiskViewSchema",
]
