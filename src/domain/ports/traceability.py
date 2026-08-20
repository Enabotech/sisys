"""领域层 溯源端口契约模块（TraceabilityPort）

定义高保真溯源（Bounding Box 级）的统一抽象端口契约。
支持从结论文本出发，检索相关文档切片，返回带 Bounding Box 坐标的引文列表。

设计决策：
- 输入为结论文本（claim），通过 LayeredRetrievalPort.search_top_down() 检索相关切片
- 引文置信度基于检索结果 score 归一化（0-1），无需额外余弦相似度计算
- 结果通过 TraceabilityResult TypedDict 独立返回，不污染 SearchResult 契约
- 领域层零外部依赖（仅使用 Python 标准库 + Protocol）
"""

from __future__ import annotations

import uuid
from typing import Protocol, TypedDict, runtime_checkable

from src.domain.value_objects.citation import Citation


class TraceabilityResult(TypedDict):
    """溯源结果 TypedDict

    与 SearchResult 风格一致，由领域层端口契约直接引用。

    Attributes:
        claim: 原始结论文本
        citations: 引文列表（按置信度降序）
        citation_count: 引文总数
        highest_confidence: 最高置信度
        has_bbox_support: 是否有 Bounding Box 坐标支持
    """

    claim: str
    citations: list[Citation]
    citation_count: int
    highest_confidence: float
    has_bbox_support: bool


@runtime_checkable
class TraceabilityPort(Protocol):
    """溯源端口契约

    定义高保真溯源的统一接口，支持从结论文本出发检索相关文档切片，
    返回带 Bounding Box 坐标的引文列表。
    """

    async def trace(
        self,
        claim: str,
        top_k: int = 10,
        min_confidence: float = 0.7,
    ) -> TraceabilityResult:
        """执行溯源，返回引文列表

        从结论文本出发，通过 LayeredRetrievalPort.search_top_down() 检索相关文档切片，
        计算引文置信度，构建溯源树结构。

        Args:
            claim: 结论文本
            top_k: 返回的引文数量上限
            min_confidence: 最小置信度阈值（低于此值的引文被过滤）

        Returns:
            TraceabilityResult 包含溯源结果

        Raises:
            TraceabilityError: LLM 评估调用失败时抛出
            ValidationError: 结论文本为空时抛出
        """
        ...

    async def get_citation_detail(
        self,
        citation_id: str,
    ) -> Citation:
        """获取单个引文的详细信息

        根据 citation_id 从当次溯源缓存中返回单个引文详情。
        MVP 阶段不持久化引文，数据来源为 trace() 执行时缓存的结果。

        Args:
            citation_id: 引文唯一标识

        Returns:
            Citation 实例

        Raises:
            TraceabilityNotFoundError: 未找到指定引文时抛出
        """
        ...

    async def get_citation_by_document(
        self,
        document_id: uuid.UUID,
    ) -> list[Citation]:
        """按文档 ID 获取所有引文

        从当次溯源缓存中按文档 ID 返回所有引文。
        MVP 阶段不持久化引文，结果为空时抛出 TraceabilityNotFoundError。

        Args:
            document_id: 文档 UUID

        Returns:
            引文列表

        Raises:
            TraceabilityNotFoundError: 未找到该文档的引文时抛出
        """
        ...


__all__ = [
    "TraceabilityPort",
    "TraceabilityResult",
]
