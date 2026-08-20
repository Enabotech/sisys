"""应用层 溯源应用服务

编排 LayeredRetrievalPort 实现高保真溯源（Bounding Box 级）。
从结论文本出发，检索相关文档切片，计算引文置信度，构建溯源树结构。

设计决策：
- 注入 LayeredRetrievalPort.search_top_down() 检索相关切片（L3→L4 展开）
- 引文置信度基于检索结果 score 归一化（0-1），无需额外余弦相似度计算
- 结果通过 TraceabilityResult TypedDict 独立返回，不污染 SearchResult 契约
- get_citation_detail / get_citation_by_document 从当次溯源缓存返回（MVP 不持久化）
- Bounding Box 坐标从检索结果 payload 中提取（若存在）
- LLM 评估调用失败抛出 TraceabilityError（外部异常，可降级）
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from src.domain.exceptions import TraceabilityError, TraceabilityNotFoundError
from src.domain.exceptions.llm_exceptions import LLMAPIError, LLMResponseError
from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.traceability import TraceabilityResult
from src.domain.value_objects.citation import Citation
from src.domain.value_objects.parsed_document import BoundingBox

logger = logging.getLogger(__name__)


class TraceabilityService:
    """溯源服务

    编排 LayeredRetrievalPort 实现高保真溯源（Bounding Box 级）。

    Attributes:
        _retrieval_port: 分层检索端口
        _citation_cache: 当次溯源结果缓存（MVP 阶段，不持久化）
        _cache_claim: 当次缓存对应的结论文本
    """

    def __init__(
        self,
        retrieval_port: Any,
    ) -> None:
        """初始化溯源服务

        Args:
            retrieval_port: LayeredRetrievalPort 实例
        """
        self._retrieval_port = retrieval_port
        self._citation_cache: dict[str, Citation] = {}
        self._citations_by_document: dict[uuid.UUID, list[Citation]] = {}
        self._cache_claim: str = ""

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
            TraceabilityResult TypedDict
        """
        # 1. 检索相关文档切片
        search_results: list[SearchResult] = []
        try:
            search_results = await self._retrieval_port.search_top_down(
                query_text=claim,
                target_level="L4",
                collection="documents",
                limit=top_k,
            )
        except (LLMAPIError, LLMResponseError) as e:
            raise TraceabilityError(
                claim=claim,
                citation_count=0,
                message=f"溯源检索调用失败: {e}",
                cause=e,
            ) from e
        except Exception as e:
            raise TraceabilityError(
                claim=claim,
                citation_count=0,
                message=f"溯源检索调用失败: {e}",
                cause=e,
            ) from e

        # 2. 将检索结果转换为 Citation 对象
        citations: list[Citation] = []
        has_bbox_support = False
        for result in search_results:
            payload = result.get("payload", {}) if isinstance(result, dict) else {}
            if not isinstance(payload, dict):
                continue

            # 提取 Bounding Box（从 payload 中）
            bbox: BoundingBox | None = None
            bbox_data = payload.get("bbox")
            if bbox_data is not None and isinstance(bbox_data, dict):
                try:
                    bbox = BoundingBox(
                        x=float(bbox_data.get("x", 0)),
                        y=float(bbox_data.get("y", 0)),
                        width=float(bbox_data.get("width", 0)),
                        height=float(bbox_data.get("height", 0)),
                        page=int(bbox_data.get("page", 1)),
                    )
                    has_bbox_support = True
                except (TypeError, ValueError, KeyError):
                    logger.debug("BoundingBox 构造失败，忽略 bbox 字段")

            # 提取文档 ID
            doc_id_str = payload.get("document_id", "")
            try:
                document_id = uuid.UUID(doc_id_str) if doc_id_str else uuid.uuid4()
            except ValueError:
                document_id = uuid.uuid4()

            # 提取文本和页码
            text = payload.get("content", "")
            page_start = payload.get("page_start", 1)
            chunk_id = payload.get("chunk_id", str(result.get("id", "")))

            # 置信度 = 检索结果 score 归一化（0-1）
            score = result.get("score", 0.0) if isinstance(result, dict) else 0.0
            confidence = max(0.0, min(1.0, float(score)))

            # 过滤置信度 < min_confidence
            if confidence < min_confidence:
                continue

            # 构造 citation_id（由 chunk_id 生成）
            citation_id = f"{chunk_id}-cit"

            citation = Citation(
                citation_id=citation_id,
                document_id=document_id,
                chunk_id=str(chunk_id),
                text=text,
                start_offset=0,
                end_offset=len(text),
                page_number=page_start if isinstance(page_start, int) else 1,
                bbox=bbox,
                confidence=confidence,
            )
            citations.append(citation)

        # 3. 按置信度降序排序
        citations.sort(key=lambda c: c.confidence, reverse=True)

        # TODO: [P1-5] LLM-as-a-Judge 评估 — MVP 裁剪
        # 当前引文置信度仅基于检索 score 归一化，未调用 LLM 进行多维评估。
        # 后续迭代需通过 traceability_prompts.build_traceability_prompt() 构建评估 Prompt，
        # 调用 LLM 端口对引文进行 relevance / completeness / accuracy 三维评分，
        # 并将 LLM 评估结果合并到 Citation.confidence 中。

        # 4. 缓存本次结果
        self._citation_cache = {c.citation_id: c for c in citations}
        self._citations_by_document = {}
        for c in citations:
            self._citations_by_document.setdefault(c.document_id, []).append(c)
        self._cache_claim = claim

        # 5. 返回 TraceabilityResult
        return {
            "claim": claim,
            "citations": citations,
            "citation_count": len(citations),
            "highest_confidence": citations[0].confidence if citations else 0.0,
            "has_bbox_support": has_bbox_support,
        }

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
        citation = self._citation_cache.get(citation_id)
        if citation is None:
            raise TraceabilityNotFoundError(
                claim=self._cache_claim,
                min_confidence=0.7,
                message=f"未找到引文: {citation_id}",
            )
        return citation

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
        citations = self._citations_by_document.get(document_id, [])
        if not citations:
            raise TraceabilityNotFoundError(
                claim=self._cache_claim,
                min_confidence=0.7,
                message=f"未找到文档 {document_id} 的引文",
            )
        return citations


__all__ = [
    "TraceabilityService",
]
