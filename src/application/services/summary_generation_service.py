"""应用层 摘要生成应用服务

编排 LLMClientPort + LayeredRetrievalPort + EmbeddingServicePort + L3VectorPort
实现契约化结构化摘要的生成、存储和检索。

设计决策：
- 注入 LLMClientPort 驱动结构化输出（调用 structured_generate）
- 注入 LayeredRetrievalPort 获取检索上下文和填充 L1/L2 骨架
- 注入 EmbeddingServicePort 和 L3VectorPort 用于摘要向量持久化
- 跨文档模式（cross_document=True）聚合 L2 摘要生成 L1 摘要
- 注入可选的 RelevanceEvaluationService 作为检索质量守卫（Story 3.7）
  - 评估失败降级为跳过评估直接生成摘要（WARNING 日志）
  - 规则预检/评估阻断 → 必然阻断，不降级
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
    RelevanceEvaluationBlockedError,
    RelevanceEvaluationError,
    SummaryGenerationError,
    SummaryPerspectiveNotSupportedError,
    ValidationError,
)
from src.domain.exceptions.llm_exceptions import LLMAPIError, LLMConfigError, LLMResponseError
from src.domain.ports.archive_repository import ArchiveQuery
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
        _relevance_evaluation: 检索相关性评估服务（可选守卫）
    """

    def __init__(
        self,
        llm_client: Any,
        layered_retrieval: Any,
        embedding_service: Any,
        l3_vector: Any,
        relevance_evaluation_service: Any | None = None,
        archive_repo: Any | None = None,
    ) -> None:
        """初始化摘要生成服务

        Args:
            llm_client: LLMClientPort 实例
            layered_retrieval: LayeredRetrievalPort 实例
            embedding_service: EmbeddingServicePort 实例
            l3_vector: L3VectorPort 实例
            relevance_evaluation_service: 检索相关性评估服务（可选，None 时跳过评估）
            archive_repo: ArchiveRepositoryPort 实例（可选，用于陈旧数据兜底判断）
        """
        self._llm_client = llm_client
        self._layered_retrieval = layered_retrieval
        self._embedding_service = embedding_service
        self._l3_vector = l3_vector
        self._relevance_evaluation = relevance_evaluation_service
        self._archive_repo = archive_repo

    async def generate_summary(
        self,
        query_text: str,
        search_results: list[SearchResult],
        perspective: str,
        config: LLMConfig | None = None,
        tenant_id: str | None = None,
        cross_document: bool = False,
        limit: int = 10,
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
            limit: 跨文档模式下 L2 检索结果数量限制（默认 10）

        Returns:
            对应视角 Schema 的 Pydantic 实例

        Raises:
            ValidationError: 查询文本为空时
            SummaryPerspectiveNotSupportedError: 不支持的视角类型
            SummaryGenerationError: 摘要生成整体失败
            LLMConfigError: LLM 配置错误时透传
        """
        # 验证查询文本
        if not query_text or not query_text.strip():
            raise ValidationError(message="查询文本不能为空")

        # 验证视角类型
        if perspective not in PERSPECTIVE_SCHEMA_MAP:
            raise SummaryPerspectiveNotSupportedError(perspective=perspective)

        # 获取 Schema 和 Prompt 模板
        schema_cls = PERSPECTIVE_SCHEMA_MAP[perspective]
        prompt_map = PERSPECTIVE_PROMPT_MAP.get(perspective)

        # 陈旧提示兜底预取（Story 3.12）：payload 无 is_stale 标记时通过 archive_repo 批量判断
        l2_results: list[SearchResult] = []
        if cross_document:
            try:
                l2_results = await self._layered_retrieval.search_top_down(
                    query_text=query_text,
                    target_level="L2",
                    collection="documents",
                    limit=limit,
                    tenant_id=tenant_id,
                    filter_payload=None,
                )
                await self._prefetch_staleness(l2_results)
                search_context = self._build_cross_document_context(l2_results)
            except Exception as e:
                logger.warning("L2 摘要检索失败，回退到单文档结果: %s", e)
                await self._prefetch_staleness(search_results)
                search_context = self._build_search_context(search_results)
                l2_results = list(search_results)  # 回退到单文档结果
        else:
            # 单文档模式：使用传入的检索结果
            await self._prefetch_staleness(search_results)
            search_context = self._build_search_context(search_results)

        # 构建检索质量评估守卫（Story 3.7）
        evaluation_results: list[SearchResult] = l2_results if cross_document else search_results
        await self._run_relevance_guard(
            query_text=query_text,
            search_results=evaluation_results,
        )

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

        # 计算单文档模式的 document_id（唯一时用于幂等点 ID；跨文档模式或文档不唯一时为 None）
        document_id: str | None = None
        if not cross_document:
            doc_ids = {
                str(r.get("payload", {}).get("document_id", ""))
                for r in search_results
                if isinstance(r, dict) and r.get("payload", {}).get("document_id")
            }
            if len(doc_ids) == 1:
                document_id = next(iter(doc_ids))

        # 计算来源文档 ID（单文档模式从检索结果 payload 提取；跨文档模式从 L2 摘要 payload 提取）
        source_document_ids: list[str] = []
        if cross_document:
            for r in l2_results:
                payload = r.get("payload", {}) if isinstance(r, dict) else {}
                if isinstance(payload, dict):
                    source_document_ids.extend(payload.get("source_document_ids", []))
            source_document_ids = list(dict.fromkeys(str(sid) for sid in source_document_ids if sid))
        else:
            source_document_ids = list(
                dict.fromkeys(
                    str(r.get("payload", {}).get("document_id", ""))
                    for r in search_results
                    if isinstance(r, dict) and r.get("payload", {}).get("document_id")
                )
            )

        # 存储摘要结果
        await self._store_summary(
            summary=result,
            perspective=perspective,
            query_text=query_text,
            cross_document=cross_document,
            source_document_ids=source_document_ids,
            tenant_id=tenant_id,
            document_id=document_id,
        )

        return result

    async def _store_summary(
        self,
        summary: Any,
        perspective: str,
        query_text: str,
        cross_document: bool = False,
        source_document_ids: list[str] | None = None,
        tenant_id: str | None = None,
        document_id: str | None = None,
    ) -> None:
        """存储摘要结果到 Qdrant

        Args:
            summary: 摘要 Schema 实例
            perspective: 视角类型
            query_text: 查询文本
            cross_document: 是否跨文档摘要
            source_document_ids: 来源文档 ID 列表
            tenant_id: 租户 ID（多租户隔离）
            document_id: 文档 ID（单文档模式幂等点 ID 用）
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
            logger.error("摘要向量生成失败，跳过存储: %s", e)
            return

        # 构建 payload
        key_points = getattr(summary, "key_points", [])[:10]
        confidence_score = getattr(summary, "confidence_score", 0.0)

        # 幂等点 ID：单文档模式用 document_id + perspective 实现 upsert 更新
        if document_id:
            point_id = f"summary-{document_id}-{perspective}"
        else:
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
                "tenant_id": tenant_id,
            },
        }

        try:
            await self._l3_vector.upsert_points(collection=collection, points=[point])
            logger.info("摘要已存储至 %s: %s", collection, point_id)
        except Exception as e:
            logger.error("摘要存储至 %s 失败: %s", collection, e)

    def _build_search_context(self, search_results: list[SearchResult]) -> str:
        """构建检索上下文文本

        当检索结果中包含陈旧数据（payload.is_stale=True）时，
        在内容前附加 [数据陈旧: 原因=..., 标记时间=...] 前缀。
        无 is_stale 标记的兜底判断由 generate_summary() 前的 _prefetch_staleness() 完成。

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
            if isinstance(payload, dict):
                # 优先使用 content（L3/L4 块级内容），降级到 summary_text（L2 摘要内容）
                content = payload.get("content") or payload.get("summary_text") or ""
                stale_flag = self._resolve_stale_flag(payload)
                if stale_flag:
                    stale_reason = payload.get("stale_reason", "未知")
                    stale_since = payload.get("stale_since", "")
                    content = f"[数据陈旧: 原因={stale_reason}, 标记时间={stale_since}] {content}"
            else:
                content = ""
            context_parts.append(f"[{i}] {content}")

        return "\n\n".join(context_parts)

    def _build_cross_document_context(self, l2_results: list[SearchResult]) -> str:
        """构建跨文档摘要上下文

        跨文档模式（L1）同样支持陈旧提示：检查 l2_results 的 payload["is_stale"]，
        前缀格式与正文模式一致（[数据陈旧: ...]）。

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
            perspective_label = payload.get("perspective", "") if isinstance(payload, dict) else ""
            confidence = payload.get("confidence_score", "") if isinstance(payload, dict) else ""
            stale_flag = self._resolve_stale_flag(payload)
            if stale_flag:
                stale_reason = payload.get("stale_reason", "未知")
                stale_since = payload.get("stale_since", "")
                summary_text = f"[数据陈旧: 原因={stale_reason}, 标记时间={stale_since}] {summary_text}"
            context_parts.append(f"[文档摘要 {i}] (视角:{perspective_label}, 置信度:{confidence}) {summary_text}")

        return "\n\n".join(context_parts)

    def _resolve_stale_flag(self, payload: dict[str, Any]) -> bool:
        """判断 payload 对应的检索结果是否陈旧

        payload 中有 is_stale 标记时直接使用。
        无标记时的兜底判断由 generate_summary() 中的 _prefetch_staleness() 完成。

        Args:
            payload: 检索结果 payload

        Returns:
            陈旧返回 True，否则返回 False
        """
        return payload.get("is_stale") is True

    async def _prefetch_staleness(self, results: list[SearchResult]) -> None:
        """通过 archive_repo 兜底预取陈旧标记

        收集所有无 is_stale 标记的结果，批量查询 L2 判断陈旧性，
        将陈旧结果回写到 payload 的 is_stale/stale_reason/stale_since 字段。
        archive_repo 未注入时跳过（已知限制，记录 WARNING）。

        Args:
            results: 检索结果列表
        """
        if self._archive_repo is None:
            return
        missing_ids: list[str] = []
        for r in results:
            payload = r.get("payload", {}) if isinstance(r, dict) else {}
            if isinstance(payload, dict) and payload.get("is_stale") is None:
                aid = payload.get("archive_id")
                if aid:
                    missing_ids.append(str(aid))
        if not missing_ids:
            return
        try:
            from uuid import UUID

            # 过滤非法 archive_id，与 StalenessWeightService 的 _is_valid_uuid 策略一致
            uuids: list[UUID] = []
            for aid in missing_ids:
                try:
                    uuids.append(UUID(aid))
                except (ValueError, AttributeError):
                    logger.warning("跳过非法 archive_id: %s", aid)
            if not uuids:
                return
            query = ArchiveQuery(archive_ids=uuids, limit=1000)
            archives = await self._archive_repo.find(query)
            stale_map: dict[str, bool] = {}
            for a in archives:
                stale_map[str(a.archive_id)] = a.is_stale()
            for r in results:
                payload = r.get("payload", {}) if isinstance(r, dict) else {}
                if isinstance(payload, dict) and payload.get("is_stale") is None:
                    aid = payload.get("archive_id")
                    if aid and stale_map.get(str(aid)):
                        payload["is_stale"] = True
                        payload.setdefault("stale_reason", "expired")
                        payload.setdefault("stale_since", "")
        except Exception as e:
            logger.warning("陈旧数据兜底查询失败，跳过陈旧提示: %s", e)

    async def _run_relevance_guard(
        self,
        query_text: str,
        search_results: list[SearchResult],
    ) -> None:
        """执行检索质量评估守卫（Story 3.7）

        在摘要生成前对检索结果进行质量评估。
        若评估失败或服务未注册，降级为跳过评估（WARNING 日志）。
        若规则预检/评估阻断，抛出 RelevanceEvaluationBlockedError。

        Args:
            query_text: 查询文本
            search_results: 检索结果

        Raises:
            RelevanceEvaluationBlockedError: 检索结果不足被阻断
        """
        if self._relevance_evaluation is None:
            # 可选依赖未注入时跳过评估
            logger.warning("相关性评估服务未注册，跳过评估")
            return

        try:
            # 先执行规则预检
            rule_result = await self._relevance_evaluation.quick_rule_check(
                query_text=query_text,
                search_results=search_results,
            )

            if rule_result["quick_block"]:
                # 规则预检阻断 → 必然阻断，不降级
                raise RelevanceEvaluationBlockedError(
                    query_text=query_text,
                    overall_score=0.0,
                    block_reason="数据不足（规则预检阻断）",
                )

            # 执行 LLM 多维评估
            evaluation_result = await self._relevance_evaluation.evaluate(
                query_text=query_text,
                search_results=search_results,
            )

            if evaluation_result.should_block:
                # 评估阻断 → 必然阻断，不降级
                raise RelevanceEvaluationBlockedError(
                    query_text=query_text,
                    overall_score=evaluation_result.overall_score,
                    block_reason=evaluation_result.block_reason or "数据不足",
                )

        except RelevanceEvaluationBlockedError:
            # 阻断异常向上透传（不降级）
            raise
        except RelevanceEvaluationError as e:
            # LLM 评估调用失败 → 降级跳过评估（WARNING 日志）
            logger.warning("LLM 评估调用失败，跳过评估: %s", e)
        except Exception as e:
            # 其他异常 → 降级跳过评估（WARNING 日志）
            logger.warning("相关性评估异常，跳过评估: %s", e)


__all__ = [
    "SummaryGenerationService",
]
