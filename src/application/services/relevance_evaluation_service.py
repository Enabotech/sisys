"""应用层 检索相关性评估应用服务

编排 LLMClientPort 实现 LLM-as-a-Judge 多维评估。
包含规则预检（快速过滤）和 LLM 深度评估（多维评分）两层守卫。

设计决策：
- 注入 LLMClientPort 驱动结构化输出（调用 structured_generate）
- quick_rule_check() 为纯计算，无外部调用，P95 < 100ms
- evaluate() 先执行规则预检，再调用 LLM 深度评估
- evaluate() 永远不抛 RelevanceEvaluationBlockedError，阻断信息通过
  should_block/block_reason 字段传递
- LLM 调用失败抛出 RelevanceEvaluationError（包装原始 LLM 异常）
- LLMConfigError 透传不包装
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Any

from src.application.services.relevance_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.application.services.relevance_schemas import RelevanceEvaluation
from src.domain.exceptions import RelevanceEvaluationError
from src.domain.exceptions.llm_exceptions import LLMAPIError, LLMConfigError, LLMResponseError
from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.llm_client import LLMConfig

logger = logging.getLogger(__name__)

# 规则预检阻断阈值：平均分 < 0.3 时快速阻断
QUICK_BLOCK_AVG_THRESHOLD = 0.3


class RelevanceEvaluationService:
    """检索相关性评估服务

    编排 LLMClientPort 实现 LLM-as-a-Judge 多维评估。
    包含规则预检和 LLM 深度评估两层守卫。

    Attributes:
        _llm_client: LLM 客户端端口
    """

    def __init__(
        self,
        llm_client: Any,
    ) -> None:
        """初始化相关性评估服务

        Args:
            llm_client: LLMClientPort 实例
        """
        self._llm_client = llm_client

    async def evaluate(
        self,
        query_text: str,
        search_results: list[SearchResult],
        config: LLMConfig | None = None,
    ) -> RelevanceEvaluation:
        """执行 LLM-as-a-Judge 多维评估

        先执行规则预检快速过滤，再调用 LLM 进行深度评估。
        永远不抛 RelevanceEvaluationBlockedError，阻断信息通过返回结果的
        should_block/block_reason 字段传递。

        Args:
            query_text: 原始查询文本
            search_results: 分层检索结果（L3/L4 内容）
            config: 可选 LLM 调用配置（LLMConfig 值对象）

        Returns:
            RelevanceEvaluation 实例，包含三维评分、综合评分和阻断状态

        Raises:
            RelevanceEvaluationError: LLM 评估调用失败时抛出
            LLMConfigError: LLM 配置错误时透传（不包装）
        """
        # 第一步：规则预检
        rule_result = await self.quick_rule_check(
            query_text=query_text,
            search_results=search_results,
        )

        if rule_result["quick_block"]:
            # 快速阻断：直接返回阻断结果
            reason = "检索结果为空或质量不足"
            if not rule_result["has_valid_results"]:
                reason = "数据不足（检索结果为空）"
            elif rule_result["avg_score"] < QUICK_BLOCK_AVG_THRESHOLD:
                reason = f"数据不足（检索结果平均分 {rule_result['avg_score']:.2f} < 0.3）"

            return RelevanceEvaluation(
                context_relevance=0.0,
                context_relevance_reason="规则预检阻断，未执行 LLM 评估",
                completeness=0.0,
                completeness_reason="规则预检阻断，未执行 LLM 评估",
                timeliness=0.0,
                timeliness_reason="规则预检阻断，未执行 LLM 评估",
                block_reason=reason,
            )

        # 第二步：构建检索上下文（含时效性标记和引用值）
        search_context = self._build_search_context_with_timeliness(search_results)

        # 第三步：计算时效性引用值（服务端备用，AC-8 要求）
        # 当 LLM 未输出时效性评估所需信息时，此值可直接作为 timeliness 兜底
        timeliness_ref = self._evaluate_timeliness(search_results)
        # 将时效性引用值作为补充信息注入上下文
        search_context += f"\n\n[时效性参考值: {timeliness_ref:.2f}]"

        # 第四步：构建 Prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            query_text=query_text,
            search_context=search_context,
        )

        # 第四步：调用 LLM 进行多维评估
        try:
            result = await self._llm_client.structured_generate(
                prompt=user_prompt,
                response_schema=RelevanceEvaluation,
                config=config,
                system_prompt=SYSTEM_PROMPT,
            )
            if not isinstance(result, RelevanceEvaluation):
                # LLM 返回非 Schema 实例时包装为 RelevanceEvaluationError
                raise RelevanceEvaluationError(
                    query_text=query_text,
                    result_count=len(search_results),
                    message="LLM 评估返回结果不是 RelevanceEvaluation 实例",
                )
        except LLMConfigError:
            # 配置错误透传不包装
            raise
        except (LLMAPIError, LLMResponseError) as e:
            # LLM 调用失败包装为 RelevanceEvaluationError
            raise RelevanceEvaluationError(
                query_text=query_text,
                result_count=len(search_results),
                message=f"LLM 评估调用失败: {e}",
                cause=e,
            ) from e
        except asyncio.CancelledError:
            # 协程取消透传不包装，避免干扰协程取消机制
            raise
        except Exception as e:
            # 其他异常包装为 RelevanceEvaluationError
            raise RelevanceEvaluationError(
                query_text=query_text,
                result_count=len(search_results),
                message=f"LLM 评估调用失败: {e}",
                cause=e,
            ) from e

        return result

    async def quick_rule_check(
        self,
        query_text: str,
        search_results: list[SearchResult],
    ) -> dict[str, Any]:
        """规则预检：快速过滤明显不足的检索结果

        纯计算，无外部调用，P95 < 100ms。

        Args:
            query_text: 原始查询文本
            search_results: 分层检索结果

        Returns:
            RuleBasedResult 的 dict 表示，包含预检结果
        """
        del query_text  # 规则预检不依赖查询文本

        # 空结果快速阻断
        if not search_results:
            return {
                "has_valid_results": False,
                "min_score": 0.0,
                "max_score": 0.0,
                "avg_score": 0.0,
                "result_count": 0,
                "quick_block": True,
            }

        # 防御性计算：过滤 NaN/负值/缺失 score
        valid_scores: list[float] = []
        for result in search_results:
            score = result.get("score", 0.0) if isinstance(result, dict) else 0.0
            if not isinstance(score, (int, float)):
                score = 0.0
            if not math.isfinite(score):
                score = 0.0
            if score < 0.0:
                score = 0.0
            valid_scores.append(score)

        if not valid_scores:
            return {
                "has_valid_results": False,
                "min_score": 0.0,
                "max_score": 0.0,
                "avg_score": 0.0,
                "result_count": 0,
                "quick_block": True,
            }

        min_score = min(valid_scores)
        max_score = max(valid_scores)
        avg_score = sum(valid_scores) / len(valid_scores)
        has_valid_results = True
        result_count = len(search_results)
        quick_block = avg_score < QUICK_BLOCK_AVG_THRESHOLD

        return {
            "has_valid_results": has_valid_results,
            "min_score": min_score,
            "max_score": max_score,
            "avg_score": avg_score,
            "result_count": result_count,
            "quick_block": quick_block,
        }

    def _evaluate_timeliness(self, search_results: list[SearchResult]) -> float:
        """评估检索结果的时效性评分

        从 SearchResult.payload 中提取时效性字段（按优先级）：
        1. valid_until — 若存在且 valid_until < now，时效性评分 0.0（完全过期）
        2. updated_at — 若存在，计算距今天数，>365天 0.3，>180天 0.6，>30天 0.8，否则 1.0
        3. created_at — 若存在且 updated_at 不存在，同上逻辑
        4. 以上字段均不存在 — 默认 1.0（不惩罚）

        综合时效性评分 = 所有检索结果时效性评分的平均值。

        Args:
            search_results: 检索结果列表

        Returns:
            时效性评分（0-1）
        """
        if not search_results:
            return 1.0

        now = datetime.now(timezone.utc)
        scores: list[float] = []

        for result in search_results:
            payload = result.get("payload", {}) if isinstance(result, dict) else {}
            if not isinstance(payload, dict):
                scores.append(1.0)
                continue

            score = self._calculate_timeliness_for_payload(payload, now)
            scores.append(score)

        if not scores:
            return 1.0

        return sum(scores) / len(scores)

    def _calculate_timeliness_for_payload(self, payload: dict[str, Any], now: datetime) -> float:
        """计算单个 payload 的时效性评分

        Args:
            payload: 检索结果的 payload 字典
            now: 当前时间

        Returns:
            时效性评分（0-1）
        """
        # 1. 检查 valid_until（完全过期判定）
        valid_until = self._parse_timestamp(payload.get("valid_until"))
        if valid_until is not None and valid_until < now:
            return 0.0

        # 2. 检查 updated_at
        ts = self._parse_timestamp(payload.get("updated_at"))
        if ts is None:
            # 3. 降级到 created_at
            ts = self._parse_timestamp(payload.get("created_at"))

        if ts is None:
            # 4. 字段均不存在 — 默认 1.0（不惩罚）
            return 1.0

        days_diff = (now - ts).days
        if days_diff > 365:
            return 0.3
        elif days_diff > 180:
            return 0.6
        elif days_diff > 30:
            return 0.8
        else:
            return 1.0

    def _parse_timestamp(self, value: Any) -> datetime | None:
        """解析时间戳字符串为 datetime 对象

        无时区信息的 naive datetime 统一视为 UTC（与 now 的 timezone.utc 对齐），
        避免 naive/aware 混合比较抛 TypeError。

        Args:
            value: 时间戳值（str 或 datetime）

        Returns:
            aware datetime 对象（UTC），解析失败返回 None
        """
        if value is None:
            return None
        ts: datetime | None = None
        if isinstance(value, datetime):
            ts = value
        elif isinstance(value, str):
            try:
                # 尝试 ISO 格式解析
                ts = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                try:
                    # 尝试去除时区信息的 ISO 格式
                    ts = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
                except (ValueError, TypeError):
                    pass
        if ts is None:
            return None
        if ts.tzinfo is None:
            # naive datetime 统一视为 UTC
            return ts.replace(tzinfo=timezone.utc)
        return ts

    def _build_search_context_with_timeliness(self, search_results: list[SearchResult]) -> str:
        """构建含时效性标记的检索上下文

        在标准检索上下文基础上，为每个检索结果条目附加时效性标记。
        时效性字段信息嵌入在 {search_context} 中，不需要新增独立占位符。

        Args:
            search_results: 检索结果列表

        Returns:
            格式化的上下文文本（含时效性标记）
        """
        if not search_results:
            return "无相关检索结果。"

        context_parts = []
        for i, result in enumerate(search_results, 1):
            payload = result.get("payload", {}) if isinstance(result, dict) else {}
            content = ""
            timeliness_marker = ""

            if isinstance(payload, dict):
                content = payload.get("content") or payload.get("summary_text") or ""

                # 提取时效性字段构造标记
                ts_parts = []
                for key in ("updated_at", "created_at", "valid_until"):
                    val = payload.get(key)
                    if val:
                        ts_parts.append(f"{key}={val}")
                if ts_parts:
                    timeliness_marker = f" [时效性: {'; '.join(ts_parts)}]"

            context_parts.append(f"[{i}]{timeliness_marker} {content}")

        return "\n\n".join(context_parts)


__all__ = [
    "RelevanceEvaluationService",
    "QUICK_BLOCK_AVG_THRESHOLD",
]
