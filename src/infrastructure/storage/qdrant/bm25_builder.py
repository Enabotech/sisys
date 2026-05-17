"""基础设施层 BM25 稀疏向量构建模块

提供基于 TF-IDF 的稀疏向量构建功能，用于 BM25 稀疏检索

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import math
from collections import Counter

from src.infrastructure.storage.qdrant.models import SparseVector


class BM25Builder:
    """BM25 稀疏向量构建器

    MVP 使用简单 TF-IDF 计算，后续可替换为 Qdrant 原生 BM25

    Attributes:
        _stop_words: 英文停用词集合，用于过滤低价值词元
    """

    _stop_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "of",
        "to",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "and",
        "but",
        "or",
        "nor",
        "not",
        "so",
        "yet",
        "both",
        "either",
        "neither",
        "each",
        "every",
        "all",
        "any",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "only",
        "own",
        "same",
        "than",
        "too",
        "very",
        "just",
        "because",
        "if",
        "when",
        "where",
        "how",
        "what",
        "which",
        "who",
        "whom",
        "this",
        "that",
        "these",
        "those",
        "i",
        "me",
        "my",
        "myself",
        "we",
        "our",
        "ours",
        "you",
        "your",
        "he",
        "him",
        "his",
        "she",
        "her",
        "it",
        "its",
        "they",
        "them",
    }

    def build_sparse_vector(self, text: str) -> SparseVector:
        """从文本构建稀疏向量

        使用简单 TF-IDF 计算

        Args:
            text: 输入文本

        Returns:
            SparseVector 实例
        """
        if not text or not text.strip():
            return SparseVector(indices=[], values=[])

        tokens = self._tokenize(text)
        if not tokens:
            return SparseVector(indices=[], values=[])

        term_freq = Counter(tokens)
        total_terms = len(tokens)

        indices = []
        values = []

        for term, freq in sorted(term_freq.items()):
            tf = freq / total_terms
            idf = 1.0 + math.log(1 + total_terms / (1 + freq))
            weight = tf * idf

            indices.append(hash(term) % 1000000)
            values.append(round(weight, 6))

        return SparseVector(indices=indices, values=values)

    def _tokenize(self, text: str) -> list[str]:
        """分词并过滤停用词

        Args:
            text: 输入文本

        Returns:
            分词后的词元列表
        """
        tokens = text.lower().split()
        return [token.strip(".,!?;:\"'()[]{}") for token in tokens if token.lower() not in self._stop_words and len(token) > 1]
