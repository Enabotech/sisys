"""领域层压缩质量评估器模块

检索-压缩循环的质量守卫（对齐架构设计 §17.1.5.1 CompressionQualityEvaluator）。
评估压缩后上下文的信息熵 + 关键实体覆盖率 + 冗余度。
评分 < 0.7 触发二次生成。

评分维度：
1. 信息熵（40%）：压缩后信息密度，基于字符分布多样性
2. 关键实体覆盖率（40%）：Top-20 关键实体保留比例
3. 冗余度（20%）：重复内容比例，基于 n-gram 重复检测

设计决策：
- 纯计算，无外部调用（P95 < 50ms）
- 领域层零外部依赖
- 使用简单启发式算法评估，不依赖 LLM
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from src.domain.ports.l3_vector import SearchResult

# 评分权重常量
_ENTROPY_WEIGHT: float = 0.40
_COVERAGE_WEIGHT: float = 0.40
_REDUNDANCY_WEIGHT: float = 0.20

# 质量门禁阈值
QUALITY_THRESHOLD: float = 0.70

# n-gram 分析参数
_NGRAM_SIZE: int = 3
_NGRAM_REPEAT_THRESHOLD: float = 0.15


class CompressionQualityEvaluator:
    """压缩质量评估器

    评估压缩后上下文的信息保留质量。
    评分维度：信息熵（40%）+ 关键实体覆盖率（40%）+ 冗余度（20%）。
    评分 < 0.7 表示质量不足，需触发二次生成。
    """

    async def evaluate(
        self,
        compressed_context: str,
        original_docs: list[SearchResult],
        key_entities: list[dict[str, Any]],
    ) -> float:
        """评估压缩质量

        Args:
            compressed_context: 压缩后的上下文文本
            original_docs: 原始检索文档列表（用于扩展评估）
            key_entities: 关键实体列表（Top-20）

        Returns:
            综合质量评分（0-1，<0.7 触发二次生成）
        """
        if not compressed_context or not compressed_context.strip():
            return 0.0

        # 1. 信息熵评分
        entropy_score = self._calculate_entropy(compressed_context)

        # 2. 关键实体覆盖率
        coverage_score = self._calculate_coverage(compressed_context, key_entities)

        # 3. 冗余度评分
        redundancy_score = self._calculate_redundancy(compressed_context)

        # 4. 综合评分
        total_score = (
            _ENTROPY_WEIGHT * entropy_score + _COVERAGE_WEIGHT * coverage_score + _REDUNDANCY_WEIGHT * redundancy_score
        )

        return min(max(total_score, 0.0), 1.0)

    @staticmethod
    def _calculate_entropy(text: str) -> float:
        """计算信息熵评分

        基于字符分布多样性计算信息熵。
        高分表示信息密度高，低分表示重复性高。

        Args:
            text: 输入文本

        Returns:
            信息熵评分（0-1，归一化）
        """
        if not text:
            return 0.0

        # 统计字符频率
        char_count = len(text)
        freq = Counter(text)

        # 计算 Shannon 熵
        entropy = 0.0
        for count in freq.values():
            p = count / char_count
            if p > 0:
                entropy -= p * math.log2(p)

        # 归一化：最大熵 = log2(字符种类数)
        max_entropy = math.log2(max(len(freq), 2))
        normalized = entropy / max_entropy if max_entropy > 0 else 0.0

        # 归一化到 [0, 1]，中文文本通常在 0.5-0.9 之间
        return min(max(normalized, 0.0), 1.0)

    @staticmethod
    def _calculate_coverage(text: str, key_entities: list[dict[str, Any]]) -> float:
        """计算关键实体覆盖率

        统计 Top-20 关键实体在压缩文本中出现的比例。

        Args:
            text: 压缩后的上下文文本
            key_entities: 关键实体列表

        Returns:
            实体覆盖率评分（0-1）
        """
        if not key_entities:
            return 1.0  # 无实体时满分

        entity_names = [e.get("name", "") for e in key_entities if e.get("name")]
        if not entity_names:
            return 1.0

        covered = 0
        for name in entity_names:
            if name in text:
                covered += 1

        return covered / len(entity_names)

    @staticmethod
    def _calculate_redundancy(text: str) -> float:
        """计算冗余度评分

        基于 n-gram 重复检测。高分表示低冗余。

        Args:
            text: 输入文本

        Returns:
            冗余度评分（0-1，高分=低冗余）
        """
        if len(text) < _NGRAM_SIZE:
            return 1.0  # 短文本默认低冗余

        # 提取 n-gram
        ngrams: list[str] = []
        for i in range(len(text) - _NGRAM_SIZE + 1):
            ngrams.append(text[i : i + _NGRAM_SIZE])

        # 统计重复比例
        total = len(ngrams)
        if total == 0:
            return 1.0

        freq = Counter(ngrams)
        unique_count = len(freq)

        # 重复率 = 1 - (唯一 n-gram 数 / 总 n-gram 数)
        repeat_ratio = 1.0 - (unique_count / total)

        # 边界情况：文本长度等于 n-gram 大小时仅生成 1 个 n-gram，
        # 无法检测重复。此时回退到字符级重复检测（全字符唯一则低冗余，
        # 否则视为高冗余）。
        if len(ngrams) == 1:
            char_freq = Counter(text)
            if len(char_freq) == len(text):
                return 1.0
            return 0.0

        # 评分 = 1 - 重复率（归一化），重复率超过阈值时线性降分
        if repeat_ratio <= _NGRAM_REPEAT_THRESHOLD:
            return 1.0
        return max(1.0 - (repeat_ratio - _NGRAM_REPEAT_THRESHOLD) * 2, 0.0)


__all__ = [
    "CompressionQualityEvaluator",
    "QUALITY_THRESHOLD",
]
