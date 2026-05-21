"""基础设施层语义路由模块

基于 bge-m3 向量嵌入实现语义相似度路由，将任务上下文与候选目标进行最佳匹配

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class EmbeddingModelProtocol(Protocol):
    """嵌入模型协议，由基础设施层实现"""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """生成文本的嵌入向量

        Args:
            texts: 待嵌入的文本字符串列表

        Returns:
            嵌入向量列表，每个向量为浮点数列表
        """
        ...


@dataclass
class Candidate:
    """路由候选项数据类，表示一个 Agent 或工具

    Attributes:
        candidate_id: 候选项唯一标识
        name: 候选项名称
        description: 候选项描述
        embedding: 预计算的嵌入向量
    """

    candidate_id: str
    name: str
    description: str
    embedding: list[float]


class SemanticRouter:
    """语义路由器，基于 bge-m3 嵌入向量通过余弦相似度匹配任务与候选目标

    Attributes:
        DEFAULT_EMBEDDING_DIM: 默认嵌入维度（bge-m3 为 1024）
        MAX_CACHE_SIZE: 最大缓存条目数
    """

    # bge-m3 默认嵌入维度
    DEFAULT_EMBEDDING_DIM: int = 1024

    # 最大缓存条目数，防止内存溢出
    MAX_CACHE_SIZE: int = 10000

    def __init__(
        self,
        candidates: Sequence[Candidate] | None = None,
        embedding_model: EmbeddingModelProtocol | None = None,
        cache_ttl_seconds: int = 86400,  # 24 小时，用于缓存大小限制而非过期
    ):
        """初始化语义路由器

        Args:
            candidates: 初始候选项列表（Agent/工具），None 表示创建空路由器
            embedding_model: 嵌入模型端口，用于计算任务嵌入（可选）
            cache_ttl_seconds: 内存缓存 TTL（默认 24 小时，用于大小限制）
        """
        self._candidates = {c.candidate_id: c for c in candidates} if candidates else {}
        self._embedding_model = embedding_model
        self._cache_ttl = cache_ttl_seconds
        self._embedding_cache: OrderedDict[str, list[float]] = OrderedDict()  # LRU 缓存

    def add_candidate(self, candidate: Candidate) -> None:
        """添加路由候选项

        Args:
            candidate: 待添加的候选项（Agent 或工具）
        """
        self._candidates[candidate.candidate_id] = candidate

    def remove_candidate(self, candidate_id: str) -> None:
        """移除路由候选项

        Args:
            candidate_id: 待移除的候选项 ID
        """
        self._candidates.pop(candidate_id, None)

    async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
        """基于语义相似度将任务路由到最佳匹配候选项

        Args:
            task_context: 任务上下文字典，至少包含 'task_type' 或 'description' 字段

        Returns:
            元组 (candidate_id, similarity_score)，无候选项时返回 ("", 0.0)
        """
        if not self._candidates:
            return "", 0.0

        # 从上下文中提取任务描述
        task_description = self._extract_task_description(task_context)
        if not task_description:
            return "", 0.0

        # 获取任务嵌入向量
        task_embedding = await self._get_task_embedding(task_description)

        # 计算与所有候选项的相似度
        best_candidate_id = ""
        best_score = 0.0

        for candidate_id, candidate in self._candidates.items():
            score = self._cosine_similarity(task_embedding, candidate.embedding)
            if score > best_score:
                best_score = score
                best_candidate_id = candidate_id

        # 如果所有相似度为 0（无嵌入模型或无匹配），返回第一个候选项
        if not best_candidate_id and self._candidates:
            first_candidate_id = next(iter(self._candidates))
            return first_candidate_id, 0.0

        return best_candidate_id, best_score

    def _extract_task_description(self, task_context: dict[str, Any]) -> str:
        """从任务上下文中提取描述字符串

        Args:
            task_context: 任务上下文字典

        Returns:
            描述字符串，未找到时返回空字符串
        """
        # 按优先级顺序查找描述字段
        for key in ("description", "task_description", "task_type", "name", "prompt"):
            if key in task_context and task_context[key]:
                value = task_context[key]
                if isinstance(value, str):
                    return value
                if isinstance(value, list | dict):
                    # 复杂类型转为字符串
                    return str(value)
        return ""

    async def _get_task_embedding(self, text: str) -> list[float]:
        """获取任务文本的嵌入向量，支持 LRU 缓存

        Args:
            text: 待嵌入的任务文本

        Returns:
            嵌入向量
        """
        # 优先检查内存缓存（命中时移至末尾，标记为最近使用）
        if text in self._embedding_cache:
            self._embedding_cache.move_to_end(text)
            return self._embedding_cache[text]

        # 计算嵌入向量
        if self._embedding_model is None:
            # 无嵌入模型，返回零向量（相似度将为 0）
            embedding = [0.0] * self.DEFAULT_EMBEDDING_DIM
        else:
            embeddings = await self._embedding_model.embed([text])
            embedding = embeddings[0] if embeddings else [0.0] * self.DEFAULT_EMBEDDING_DIM

        # LRU 淘汰：超限时移除最旧条目后添加新条目
        if len(self._embedding_cache) >= self.MAX_CACHE_SIZE:
            self._embedding_cache.popitem(last=False)
        self._embedding_cache[text] = embedding

        return embedding

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Similarity score between -1 and 1 (0 if vectors have zero magnitude)
        """
        if not a or not b:
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = math.sqrt(sum(x * x for x, _ in zip(a, b)))
        magnitude_b = math.sqrt(sum(y * y for _, y in zip(a, b)))

        if magnitude_a == 0.0 or magnitude_b == 0.0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    @property
    def candidate_count(self) -> int:
        """Return the number of candidates."""
        return len(self._candidates)
