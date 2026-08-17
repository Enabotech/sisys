"""领域层 检索相关性评估端口契约模块（RelevanceEvaluationPort）

定义 LLM-as-a-Judge 多维评估的抽象端口契约。
支持规则预检（快速过滤）和 LLM 深度评估（多维评分）两层守卫。

设计决策：
- 输入使用 SearchResult（与现有检索服务签名对齐，同域内类型引用）
- config 使用 LLMConfig 值对象（同域内类型引用，提供精确类型约束）
- 返回结果为 TypedDict（与 SearchResult 风格一致，领域层零外部依赖）
- evaluate() 永远不抛 RelevanceEvaluationBlockedError，阻断信息通过
  should_block/block_reason 字段传递；该异常由调用方检查时应抛出
- quick_rule_check() 为纯计算，无外部调用，P95 < 100ms
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.llm_client import LLMConfig


class RelevanceEvaluationResult(TypedDict):
    """LLM-as-a-Judge 多维评估结果 TypedDict

    与 SearchResult 风格一致，由领域层端口契约直接引用。

    Attributes:
        context_relevance: 上下文相关性评分（0-1）
        context_relevance_reason: 相关性判断理由
        completeness: 完整性评分（0-1）
        completeness_reason: 完整性判断理由
        timeliness: 时效性评分（0-1）
        timeliness_reason: 时效性判断理由
        overall_score: 综合评分（0-1，(context_relevance + completeness + timeliness) / 3.0）
        should_block: 是否阻断生成（overall_score < 0.6 时为 True）
        block_reason: 阻断理由（should_block=True 时必填，否则为 None）
    """

    context_relevance: float
    context_relevance_reason: str
    completeness: float
    completeness_reason: str
    timeliness: float
    timeliness_reason: str
    overall_score: float
    should_block: bool
    block_reason: str | None


class RuleBasedResult(TypedDict):
    """规则预检结果 TypedDict

    Attributes:
        has_valid_results: 检索结果是否有效（非空列表）
        min_score: 检索结果最低分（空结果时为 0.0）
        max_score: 检索结果最高分（空结果时为 0.0）
        avg_score: 检索结果平均分（空结果时为 0.0）
        result_count: 检索结果数量（空结果时为 0）
        quick_block: 快速阻断标记（结果为空或平均分 < 0.3 时阻断）
    """

    has_valid_results: bool
    min_score: float
    max_score: float
    avg_score: float
    result_count: int
    quick_block: bool


@runtime_checkable
class RelevanceEvaluationPort(Protocol):
    """检索相关性评估端口契约

    定义 LLM-as-a-Judge 多维评估的统一接口，包含规则预检和 LLM 深度评估两层守卫。
    """

    async def evaluate(
        self,
        query_text: str,
        search_results: list[SearchResult],
        config: LLMConfig | None = None,
    ) -> Any:
        """执行 LLM-as-a-Judge 多维评估

        先执行规则预检快速过滤，再调用 LLM 进行深度评估。
        永远不抛 RelevanceEvaluationBlockedError，阻断信息通过返回结果的
        should_block/block_reason 字段传递。

        Args:
            query_text: 原始查询文本
            search_results: 分层检索结果（L3/L4 内容）
            config: 可选 LLM 调用配置（LLMConfig 值对象）

        Returns:
            -- 返回类型说明 --
            返回对象具有 Pydantic @computed_field 行为（RelevanceEvaluation 实例），
            调用方按属性访问（result.overall_score / result.should_block）。
            evaluate() 返回的实际对象包含 overall_score/should_block 等
            @computed_field 计算字段，这是应用层 QoS 增强，端口契约无法精确表达。
            与 SummaryGenerationPort 一致使用 Any。

        Raises:
            RelevanceEvaluationError: LLM 评估调用失败时抛出
            LLMConfigError: LLM 配置错误时透传（不包装）
        """
        ...

    async def quick_rule_check(
        self,
        query_text: str,
        search_results: list[SearchResult],
    ) -> RuleBasedResult:
        """规则预检：快速过滤明显不足的检索结果

        纯计算，无外部调用，P95 < 100ms。
        空结果 → quick_block=True；平均分 < 0.3 → quick_block=True。

        Args:
            query_text: 原始查询文本
            search_results: 分层检索结果

        Returns:
            RuleBasedResult 包含预检结果
        """
        ...


__all__ = [
    "RelevanceEvaluationPort",
    "RelevanceEvaluationResult",
    "RuleBasedResult",
]
