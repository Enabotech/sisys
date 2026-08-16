"""应用层 摘要生成应用服务

编排 LLMClientPort + LayeredRetrievalPort + EmbeddingServicePort + L3VectorPort
实现契约化结构化摘要的生成、存储和检索。

设计决策：
- 注入 LLMClientPort 驱动结构化输出（调用 structured_generate）
- 注入 LayeredRetrievalPort 获取检索上下文和填充 L1/L2 骨架
- 注入 EmbeddingServicePort 和 L3VectorPort 用于摘要向量持久化
- 跨文档模式（cross_document=True）聚合 L2 摘要生成 L1 摘要
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.application.services.summary_prompts import PERSPECTIVE_PROMPT_MAP
from src.application.services.summary_schemas import (
    PERSPECTIVE_SCHEMA_MAP,
)
from src.domain.exceptions import (
    SummaryGenerationError,
    SummaryPerspectiveNotSupportedError,
)
from src.domain.exceptions.llm_exceptions import LLMAPIError, LLMConfigError, LLMResponseError
from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.llm_client import LLMConfig

logger = logging.getLogger(__name__)

# 摘要存储常量
DEFAULT_EMBEDDING_DIMENSION = 1024  # bge-m3 向量维度


class SummaryGenerationService:
    """契约化摘要生成服务

    编排 LLMClientPort + LayeredRetrievalPort + EmbeddingServicePort + L3VectorPort
    实现多视角结构化摘要的生成、存储和检索。

    Attributes:
        _llm_client: LLM 客户端端口
        _layered_retrieval: 分层检索端口
        _embedding_service: 嵌入服务端口
        _l3_vector: L3 向量存储端口
    """

    def __init__(
        self,
        llm_client: Any,
        layered_retrieval: Any,
        embedding_service: Any,
        l3_vector: Any,
    ) -> None:
        """初始化摘要生成服务

        Args:
            llm_client: LLMClientPort 实例
            layered_retrieval: LayeredRetrievalPort 实例
            embedding_service: EmbeddingServicePort 实例
            l3_vector: L3VectorPort 实例
        """
        self._llm_client = llm_client
        self._layered_retrieval = layered_retrieval
        self._embedding_service = embedding_service
        self._l3_vector = l3_vector

    async def generate_summary(
        self,
        query_text: str,
        search_results: list[SearchResult],
        perspective: str,
        config: LLMConfig | None = None,
        tenant_id: str | None = None,
        cross_document: bool = False,
    ) -> Any:
        """生成契约化结构化摘要

        根据视角类型，将检索结果转化为符合预定义 JSON Schema 的结构化摘要。
        支持单文档摘要（L2）和跨文档摘要（L1）两种模式。

        Args:
            query_text: 原始查询文本
            search_results: 分层检索结果（L3/L4 内容）
            perspective: 视角类型（"financial"/"market"/"technical"）
            config: 可选 LLM 调用配置（LLMConfig 值对象）
            tenant_id: 可选租户 ID
            cross_document: 跨文档摘要模式

        Returns:
            对应视角 Schema 的 Pydantic 实例

        Raises:
            SummaryPerspectiveNotSupportedError: 不支持的视角类型
            SummaryGenerationError: 摘要生成整体失败
        """
        # 验证视角类型
        if perspective not in PERSPECTIVE_SCHEMA_MAP:
            raise SummaryPerspectiveNotSupportedError(perspective=perspective)

        # 获取 Schema 和 Prompt 模板
        schema_cls = PERSPECTIVE_SCHEMA_MAP[perspective]
        prompt_map = PERSPECTIVE_PROMPT_MAP.get(perspective)

        # 构建检索上下文
        if cross_document:
            # 跨文档模式：从 L2 检索获取摘要上下文
            try:
                l2_results = await self._layered_retrieval.search_top_down(
                    query_text=query_text,
                    target_level="L2",
                    collection="documents",
                    limit=10,
                    tenant_id=tenant_id,
                    filter_payload=None,
                )
                search_context = self._build_cross_document_context(l2_results)
            except Exception as e:
                logger.warning("L2 摘要检索失败: %s", e)
                search_context = self._build_search_context(search_results)
        else:
            # 单文档模式：使用传入的检索结果
            search_context = self._build_search_context(search_results)

        # 构建 Prompt
        system_prompt = prompt_map["system_prompt"] if prompt_map else ""
        user_prompt = (
            prompt_map["user_prompt_template"].format(
                query_text=query_text,
                search_context=search_context,
            )
            if prompt_map
            else f"查询：{query_text}\n上下文：{search_context}"
        )

        # 调用 LLM 生成结构化输出
        try:
            result = await self._llm_client.structured_generate(
                prompt=user_prompt,
                response_schema=schema_cls,
                config=config,
                system_prompt=system_prompt,
            )
        except LLMConfigError:
            # 配置错误透传不包装
            raise
        except (LLMAPIError, LLMResponseError) as e:
            # LLM 调用失败包装为 SummaryGenerationError
            raise SummaryGenerationError(
                perspective=perspective,
                query_text=query_text,
                message=f"LLM 调用失败: {e}",
                cause=e,
            ) from e
        except Exception as e:
            # 其他异常包装为 SummaryGenerationError
            raise SummaryGenerationError(
                perspective=perspective,
                query_text=query_text,
                message=f"摘要生成失败: {e}",
                cause=e,
            ) from e

        # 存储摘要结果
        await self._store_summary(
            summary=result,
            perspective=perspective,
            query_text=query_text,
            cross_document=cross_document,
            source_document_ids=[str(r.get("id", "")) for r in search_results if isinstance(r, dict)],
        )

        return result

    async def _store_summary(
        self,
        summary: Any,
        perspective: str,
        query_text: str,
        cross_document: bool = False,
        source_document_ids: list[str] | None = None,
    ) -> None:
        """存储摘要结果到 Qdrant

        Args:
            summary: 摘要 Schema 实例
            perspective: 视角类型
            query_text: 查询文本
            cross_document: 是否跨文档摘要
            source_document_ids: 来源文档 ID 列表
        """
        collection = "cross_document_summaries" if cross_document else "document_summaries"
        index_level = "L1" if cross_document else "L2"

        # 懒创建 collection
        try:
            exists = await self._l3_vector.collection_exists(collection)
            if not exists:
                await self._l3_vector.create_collection(
                    collection=collection,
                    vector_size=DEFAULT_EMBEDDING_DIMENSION,
                )
        except Exception as e:
            logger.warning("创建 collection %s 失败: %s", collection, e)

        # 生成摘要向量
        try:
            summary_text = getattr(summary, "summary_text", query_text)
            vectors = await self._embedding_service.embed_documents([summary_text])
            vector = vectors[0] if vectors else [0.0] * DEFAULT_EMBEDDING_DIMENSION
        except Exception as e:
            logger.warning("摘要向量生成失败: %s", e)
            vector = [0.0] * DEFAULT_EMBEDDING_DIMENSION

        # 构建 payload
        key_points = getattr(summary, "key_points", [])
        confidence_score = getattr(summary, "confidence_score", 0.0)

        point_id = f"summary-{perspective}-{uuid.uuid4()}"
        point = {
            "id": point_id,
            "vector": vector,
            "payload": {
                "perspective": perspective,
                "summary_text": summary_text,
                "key_points": key_points,
                "confidence_score": confidence_score,
                "source_document_ids": source_document_ids or [],
                "index_level": index_level,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        try:
            await self._l3_vector.upsert_points(collection=collection, points=[point])
            logger.info("摘要已存储至 %s: %s", collection, point_id)
        except Exception as e:
            logger.warning("摘要存储失败: %s", e)

    def _build_search_context(self, search_results: list[SearchResult]) -> str:
        """构建检索上下文文本

        Args:
            search_results: 检索结果列表

        Returns:
            格式化的上下文文本
        """
        if not search_results:
            return "无相关检索结果。"

        context_parts = []
        for i, result in enumerate(search_results, 1):
            payload = result.get("payload", {}) if isinstance(result, dict) else {}
            content = payload.get("content", "") if isinstance(payload, dict) else ""
            context_parts.append(f"[{i}] {content}")

        return "\n\n".join(context_parts)

    def _build_cross_document_context(self, l2_results: list[SearchResult]) -> str:
        """构建跨文档摘要上下文

        Args:
            l2_results: L2 摘要检索结果

        Returns:
            格式化的上下文文本
        """
        if not l2_results:
            return "无相关文档摘要。"

        context_parts = []
        for i, result in enumerate(l2_results, 1):
            payload = result.get("payload", {}) if isinstance(result, dict) else {}
            summary_text = payload.get("summary_text", "") if isinstance(payload, dict) else ""
            context_parts.append(f"[文档摘要 {i}] {summary_text}")

        return "\n\n".join(context_parts)


__all__ = [
    "SummaryGenerationService",
]
