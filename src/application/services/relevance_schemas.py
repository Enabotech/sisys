"""应用层 检索相关性评估 Pydantic Schema 模块

定义 LLM-as-a-Judge 多维评估的结构化 Schema：
- RelevanceEvaluation: LLM 评估结果（相关性/完整性/时效性三维评分 + 综合评分 + 阻断标记）
- RuleBasedEvaluation: 规则预检结果（空结果/低分快速过滤）

设计决策：
- 定义在应用层（src/application/），允许依赖 Pydantic
- 领域层零外部依赖约束不适用于此
- 使用 Pydantic V2 BaseModel + Field + @computed_field + @model_validator
- overall_score 由服务端 @computed_field 计算，不依赖 LLM 输出一致性
- should_block 以 overall_score < 0.6 为准，阻断准确率 100% 可验证
"""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field, model_validator

# 阻断阈值：综合评分 < 0.6 时标注"数据不足"并阻断
BLOCK_THRESHOLD = 0.6
# 阻断理由文案
BLOCK_REASON_TEXT = "数据不足"


class RelevanceEvaluation(BaseModel):
    """LLM-as-a-Judge 多维评估结果

    包含相关性/完整性/时效性三维评分、判断理由和综合评分。
    overall_score 与 should_block 由 @computed_field 服务端计算，
    不依赖 LLM 输出的一致性。

    Attributes:
        context_relevance: 上下文相关性评分（0-1）
        context_relevance_reason: 相关性判断理由
        completeness: 完整性评分（0-1）
        completeness_reason: 完整性判断理由
        timeliness: 时效性评分（0-1）
        timeliness_reason: 时效性判断理由
        overall_score: 综合评分（@computed_field，(context_relevance + completeness + timeliness) / 3.0）
        should_block: 是否阻断生成（@computed_field，overall_score < 0.6）
        block_reason: 阻断理由（should_block=True 时必须为非空，默认"数据不足"）
    """

    context_relevance: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="上下文相关性评分，1.0=完全匹配查询意图，0.0=完全不相关",
    )
    context_relevance_reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="相关性判断理由",
    )
    completeness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="完整性评分，1.0=全部信息覆盖，0.0=无必要信息",
    )
    completeness_reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="完整性判断理由",
    )
    timeliness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="时效性评分，1.0=最新信息，0.0=完全过时",
    )
    timeliness_reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="时效性判断理由",
    )
    block_reason: str | None = Field(
        default=None,
        max_length=200,
        description="阻断理由（should_block=True 时必须为非空，默认'数据不足'；should_block=False 时必须为 None）",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overall_score(self) -> float:
        """综合评分：三维评分的算术平均

        服务端独立计算，不依赖 LLM 输出的一致性；
        阻断守卫以此值为准，阻断准确率 100% 可验证。
        """
        return (self.context_relevance + self.completeness + self.timeliness) / 3.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def should_block(self) -> bool:
        """是否阻断生成：综合评分 < 0.6"""
        return self.overall_score < BLOCK_THRESHOLD

    @model_validator(mode="after")
    def _validate_block_reason(self) -> "RelevanceEvaluation":
        """跨字段条件必填验证

        - should_block=True 时 block_reason 必须为非空（自动填充"数据不足"）
        - should_block=False 时 block_reason 必须为 None
        """
        if self.should_block:
            if not self.block_reason:
                self.block_reason = BLOCK_REASON_TEXT
        else:
            self.block_reason = None
        return self


class RuleBasedEvaluation(BaseModel):
    """规则预检结果

    快速过滤明显不足的检索结果（纯计算，无外部调用，P95 < 100ms）。

    Attributes:
        has_valid_results: 检索结果是否有效（非空列表且至少一个有效 score）
        min_score: 检索结果最低分（has_valid_results=False 时归一化为 0.0）
        max_score: 检索结果最高分（has_valid_results=False 时归一化为 0.0）
        avg_score: 检索结果平均分（has_valid_results=False 时归一化为 0.0）
        result_count: 检索结果数量（has_valid_results=False 时为 0）
        quick_block: 快速阻断标记（结果为空或平均分 < 0.3 时阻断）
    """

    has_valid_results: bool = Field(..., description="检索结果是否有效（非空列表）")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="检索结果最低分")
    max_score: float = Field(default=0.0, ge=0.0, le=1.0, description="检索结果最高分")
    avg_score: float = Field(default=0.0, ge=0.0, le=1.0, description="检索结果平均分")
    result_count: int = Field(default=0, ge=0, description="检索结果数量")
    quick_block: bool = Field(default=False, description="快速阻断标记")

    @model_validator(mode="after")
    def _normalize_empty(self) -> "RuleBasedEvaluation":
        """空结果归一化

        实现顺序：先判空再取 min/max/avg，空列表不进入统计计算，
        避免 min([])/max([]) 抛 ValueError。
        """
        if not self.has_valid_results:
            self.min_score = 0.0
            self.max_score = 0.0
            self.avg_score = 0.0
            self.result_count = 0
            self.quick_block = True
        return self


__all__ = [
    "RelevanceEvaluation",
    "RuleBasedEvaluation",
    "BLOCK_THRESHOLD",
    "BLOCK_REASON_TEXT",
]
