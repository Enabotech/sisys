"""Story 3.5 分层检索应用服务

编排 Dense 语义检索 + L3VectorPort 提供 L1-L4 分层检索能力。
支持自底向上（L4→L3 回溯）和自顶向下（L3→L4 展开）两种遍历策略。

降级策略：
- L4 检索失败 → 透明降级为普通 L3 检索，WARNING 日志
- L2/L1 当前为骨架实现（返回空列表），完整实现依赖 Story 3.6

依赖注入：
- DenseSemanticSearchService（外部构造，用于执行 Dense 语义检索）
- EmbeddingServicePort（用于查询向量嵌入，自顶向下展开时复用）
- L3VectorPort（用于按 ID 回溯和按 payload 过滤检索）
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.domain.exceptions import ValidationError
from src.domain.exceptions.layered_retrieval_exceptions import (
    LayeredRetrievalError,
    LevelTransitionError,
)
from src.domain.exceptions.system_exceptions import SystemException
from src.domain.ports.embedding_service import EmbeddingServicePort
from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.layered_retrieval import LAYERED_RETRIEVAL_LEVELS

logger = logging.getLogger(__name__)


def _safe_truncate(text: str, max_len: int) -> str:
    """安全截断文本，处理多字节 UTF-8 字符

    Args:
        text: 输入文本
        max_len: 最大字符数

    Returns:
        截断后的文本
    """
    if max_len < 1:
        return ""
    if not text:
        return ""
    # 按 Unicode 字符（而非字节）截断，避免多字节字符被从中截断
    chars = list(text)
    return "".join(chars[:max_len])


# 分层检索编排常量
# 自顶向下展开时每个 Parent 最多展开的 Child 子块数
_DEFAULT_CHILD_EXPAND_COUNT = 3
# 自顶向下展开时最多展开的 Parent 数（限制 N+1 查询开销）
_MAX_EXPAND_PARENTS = 5
# 检索结果 limit 上限（防止向量数据库 OOM 或内存压力）
_MAX_LIMIT = 200


class LayeredRetrievalService:
    """分层检索编排服务

    编排 DenseSemanticSearchService + EmbeddingServicePort + L3VectorPort 实现 L1-L4 分层检索。
    支持自底向上（L4→L3 回溯）和自顶向下（L3→L4 展开）双向遍历。

    Attributes:
        _dense_search: Dense 语义检索服务
        _embedding_service: 嵌入服务端口（自顶向下展开时复用查询向量）
        _l3_vector: L3 向量存储端口
    """

    def __init__(
        self,
        dense_search: Any,
        l3_vector: Any,
        embedding_service: EmbeddingServicePort,
    ) -> None:
        """初始化分层检索服务

        Args:
            dense_search: DenseSemanticSearchService 实例
            l3_vector: L3VectorPort 实例（用于按 payload 过滤回溯和按 ID 获取）
            embedding_service: EmbeddingServicePort 实例（用于查询向量嵌入）
        """
        self._dense_search = dense_search
        self._l3_vector = l3_vector
        self._embedding_service = embedding_service

    async def search_top_down(
        self,
        query_text: str,
        target_level: str = "L4",
        collection: str = "documents",
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """自顶向下遍历检索

        从高层级向低层级展开。根据 target_level 决定执行哪个层级检索：
        - L1：跨文档摘要（骨架，返回空列表）
        - L2：文档摘要（骨架，返回空列表）
        - L3：文档切片层检索（常规 Dense 检索）
        - L4：L3→L4 展开（命中 Parent 的 Top-3 Child 展开）

        Args:
            query_text: 查询文本
            target_level: 检索目标粒度层级（"L1"/"L2"/"L3"/"L4"）
            collection: Collection 名称
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            按相关性降序排列的检索结果列表

        Raises:
            ValidationError: 参数验证失败时
            LevelTransitionError: 层级遍历路径非法时
        """
        self._validate_inputs(query_text, collection, limit, tenant_id)
        self._validate_level(target_level)

        # L1/L2 摘要检索
        if target_level == "L1":
            return await self._search_l1_summaries(
                query_text=query_text,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
            )
        if target_level == "L2":
            return await self._search_l2_summaries(
                query_text=query_text,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
            )

        # L3 直接检索
        if target_level == "L3":
            return await self._search_l3_direct(
                query_text=query_text,
                collection=collection,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
            )

        # L3→L4 展开（自顶向下）
        if target_level == "L4":
            return await self._search_top_down_l3_to_l4(
                query_text=query_text,
                collection=collection,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
            )

        return []

    async def search_bottom_up(
        self,
        query_text: str,
        target_level: str = "L4",
        collection: str = "documents",
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """自底向上遍历检索

        从低层级向高层级回溯。根据 target_level 决定执行哪个层级检索：
        - L4：L4 层直接检索（Child 块检索）
        - L3：L4→L3 回溯（命中 Child → 回溯 Parent）
        - L2/L1：骨架（返回空列表）

        Args:
            query_text: 查询文本
            target_level: 检索目标粒度层级（"L1"/"L2"/"L3"/"L4"）
            collection: Collection 名称
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            按相关性降序排列的检索结果列表

        Raises:
            ValidationError: 参数验证失败时
            LevelTransitionError: 层级遍历路径非法时
        """
        self._validate_inputs(query_text, collection, limit, tenant_id)
        self._validate_level(target_level)

        # L1/L2 摘要检索
        if target_level == "L1":
            return await self._search_l1_summaries(
                query_text=query_text,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
            )
        if target_level == "L2":
            return await self._search_l2_summaries(
                query_text=query_text,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
            )

        # L4 直接检索
        if target_level == "L4":
            return await self._search_l4_direct(
                query_text=query_text,
                collection=collection,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
            )

        # L4→L3 回溯（自底向上）
        if target_level == "L3":
            return await self._search_bottom_up_l4_to_l3(
                query_text=query_text,
                collection=collection,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
            )

        return []

    # ------------------------------------------------------------------
    # 内部实现方法
    # ------------------------------------------------------------------

    async def _search_l3_direct(
        self,
        query_text: str,
        collection: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """L3 层直接检索

        在 L3 层（Parent 块）执行 Dense 语义检索。

        Args:
            query_text: 查询文本
            collection: Collection 名称
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            L3 层检索结果列表

        Raises:
            LayeredRetrievalError: 下游检索失败时包装为领域异常传播
        """
        parent_filter = self._merge_filter(filter_payload, {"index_level": "parent"})
        try:
            raw_results = await self._dense_search.search(
                collection=collection,
                query_text=query_text,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=parent_filter,
            )
            if not raw_results:
                return []
            # 归一化 payload：确保 index_level 层级标记存在，供调用方区分结果层级
            return [
                SearchResult(
                    id=r["id"],
                    score=r["score"],
                    payload=self._normalize_payload(r.get("payload", {}), "parent"),
                )
                for r in raw_results
                if "id" in r and "score" in r
            ]
        except Exception as e:
            # 依赖异常统一为领域契约：包装为 LayeredRetrievalError 向上传播
            logger.error("L3 直接检索失败: %s", e)
            raise LayeredRetrievalError(
                f"L3 直接检索失败: {e}",
                context={"collection": collection, "target_level": "L3", "tenant_id": tenant_id},
            ) from e

    async def _search_l4_direct(
        self,
        query_text: str,
        collection: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """L4 层直接检索

        在 L4 层（Child 块）执行 Dense 语义检索。

        Args:
            query_text: 查询文本
            collection: Collection 名称
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            L4 层检索结果列表

        Raises:
            LayeredRetrievalError: 下游检索失败时包装为领域异常传播
        """
        child_filter = self._merge_filter(filter_payload, {"index_level": "child"})
        try:
            raw_results = await self._dense_search.search(
                collection=collection,
                query_text=query_text,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=child_filter,
            )
            if not raw_results:
                return []
            return [
                SearchResult(id=r["id"], score=r["score"], payload=r.get("payload", {}))
                for r in raw_results
                if "id" in r and "score" in r
            ]
        except Exception as e:
            # 依赖异常统一为领域契约：包装为 LayeredRetrievalError 向上传播
            logger.error("L4 直接检索失败: %s", e)
            raise LayeredRetrievalError(
                f"L4 直接检索失败: {e}",
                context={"collection": collection, "target_level": "L4", "tenant_id": tenant_id},
            ) from e

    async def _search_bottom_up_l4_to_l3(
        self,
        query_text: str,
        collection: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """L4→L3 自底向上回溯

        1. 在 L4 层（Child 块）执行 Dense 语义检索
        2. 对命中结果的 parent_chunk_id 去重
        3. 通过 L3VectorPort.get_point() 按 ID 获取父块内容
        4. 返回去重合并后的 L3 层结果

        Args:
            query_text: 查询文本
            collection: Collection 名称
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            去重合并后的 L3 层结果列表
        """
        # 1. L4 层 Dense 检索
        child_filter = self._merge_filter(filter_payload, {"index_level": "child"})
        try:
            l4_results = await self._dense_search.search(
                collection=collection,
                query_text=query_text,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=child_filter,
            )
        except SystemException:
            # 基础设施故障：必须传播，不能降级掩盖
            raise
        except Exception as e:
            # 业务级异常（如检索超时、无结果）：透明降级为 L3 检索
            logger.warning("L4 检索失败，降级为 L3 直接检索: %s", e)
            return await self._search_l3_direct(
                query_text=query_text,
                collection=collection,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
            )

        if not l4_results:
            return []

        # 2. 按 parent_chunk_id 去重
        parent_info: dict[str, dict[str, Any]] = {}
        for r in l4_results:
            payload = r.get("payload", {})
            parent_id = payload.get("parent_chunk_id")
            if not parent_id:
                continue
            if parent_id not in parent_info:
                parent_info[parent_id] = {
                    "max_child_score": r["score"],
                    "child_count": 0,
                    "parent_chunk_id": parent_id,
                }
            else:
                if r["score"] > parent_info[parent_id]["max_child_score"]:
                    parent_info[parent_id]["max_child_score"] = r["score"]
            parent_info[parent_id]["child_count"] += 1

        if not parent_info:
            return []

        # 3. 通过 get_point() 回溯获取父块内容（并发获取，避免 N+1 串行查询）
        # 使用 gather(return_exceptions=True)：单个父块获取失败不影响其余结果
        # 过滤异常，保留有效的 SearchResult（TypedDict 不支持 isinstance，故按异常类型过滤）
        fetch_results = await asyncio.gather(
            *[self._fetch_parent(collection, pid, inf) for pid, inf in parent_info.items()],
            return_exceptions=True,
        )
        merged_results: list[SearchResult] = [r for r in fetch_results if not isinstance(r, BaseException) and r is not None]

        # 4. 按最高 Child 分数降序排列（分数相同时按 id 确保确定性）
        merged_results.sort(key=lambda r: (-r["score"], r["id"]))
        return merged_results[:limit]

    async def _fetch_parent(
        self,
        collection: str,
        parent_id: str,
        info: dict[str, Any],
    ) -> SearchResult | None:
        """获取单个父块内容（并发任务）

        Args:
            collection: Collection 名称
            parent_id: 父块 ID
            info: 父块去重信息

        Returns:
            合并后的 SearchResult，或 None（获取失败时）
        """
        try:
            parent_point = await self._l3_vector.get_point(collection, parent_id)
        except Exception:
            logger.warning("L4→L3 回溯: 获取父块 %s 失败，跳过", parent_id)
            return None
        if parent_point is None:
            return None

        parent_payload = parent_point.get("payload", {})
        return SearchResult(
            id=parent_id,
            score=info["max_child_score"],
            payload={
                "parent_chunk_id": parent_id,
                "child_count": info["child_count"],
                "index_level": "parent",
                "content": _safe_truncate(parent_payload.get("content", ""), 200),
                "document_id": parent_payload.get("document_id", ""),
            },
        )

    async def _search_top_down_l3_to_l4(
        self,
        query_text: str,
        collection: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """L3→L4 自顶向下展开

        1. 在 L3 层（Parent 块）执行 Dense 语义检索
        2. 对命中 Parent 展开 Top-3 Child 子块
        3. 每个 Child 结果携带 parent_content 摘要和 parent_chunk_id

        Args:
            query_text: 查询文本
            collection: Collection 名称
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            展开后的 L4 层结果列表

        Raises:
            LayeredRetrievalError: 查询嵌入或 L3 检索失败时包装为领域异常传播
        """
        # 1. 嵌入查询向量一次，L3 检索与后续 Child 展开复用
        try:
            query_vector = await self._embedding_service.embed_query(query_text)
        except Exception as e:
            logger.error("L3 查询嵌入失败: %s", e)
            raise LayeredRetrievalError(
                f"L3 查询嵌入失败: {e}",
                context={"collection": collection, "target_level": "L4", "tenant_id": tenant_id},
            ) from e

        # 2. L3 层 Dense 检索（直接传向量，避免二次嵌入）
        parent_filter = self._merge_filter_with_tenant(filter_payload, {"index_level": "parent"}, tenant_id)
        try:
            l3_raw = await self._l3_vector.search(
                collection=collection,
                query_vector=query_vector,
                limit=min(limit, _MAX_EXPAND_PARENTS),  # 限制展开 Parent 数，避免 N+1 问题
                filter_payload=parent_filter,
            )
        except Exception as e:
            logger.error("L3 检索失败，无法展开 L4: %s", e)
            raise LayeredRetrievalError(
                f"L3 检索失败，无法展开 L4: {e}",
                context={"collection": collection, "target_level": "L4", "tenant_id": tenant_id},
            ) from e

        l3_results = [
            SearchResult(id=r["id"], score=r["score"], payload=r.get("payload", {}))
            for r in l3_raw
            if isinstance(r, dict) and "id" in r and "score" in r
        ]
        if not l3_results:
            return []

        # 3. 对每个命中 Parent，展开 Top-3 Child（复用 query_vector 传向量）
        # 并发展开：避免串行 N+1 查询，gather 并发执行所有 Parent 的 Child 展开
        expanded_results: list[SearchResult] = []

        async def _expand_child(parent_result: SearchResult) -> list[SearchResult]:
            """展开单个 Parent 的 Child 子块

            Args:
                parent_result: Parent 检索结果

            Returns:
                展开后的 Child 结果列表
            """
            parent_id = parent_result.get("id")
            if parent_id is None:
                logger.warning("L3→L4 展开: Parent id 为 None，跳过")
                return []

            parent_payload = parent_result.get("payload", {})
            parent_content = parent_payload.get("content")
            if not isinstance(parent_content, str):
                parent_content = ""
            parent_content_preview = _safe_truncate(parent_content, 200)

            child_filter = self._merge_filter_with_tenant(
                filter_payload,
                {"index_level": "child", "parent_chunk_id": str(parent_id)},
                tenant_id,
            )

            try:
                child_raw = await self._l3_vector.search(
                    collection=collection,
                    query_vector=query_vector,
                    limit=_DEFAULT_CHILD_EXPAND_COUNT,
                    filter_payload=child_filter,
                )
            except Exception:
                logger.warning("Parent %s 的 Child 展开失败，跳过", parent_id)
                return []

            child_results = [r for r in child_raw if isinstance(r, dict) and "id" in r and "score" in r]
            child_results.sort(key=lambda r: r["score"], reverse=True)  # 显式排序，不依赖后端顺序

            # 服务自身强制 Top-3 截断，不依赖后端 limit 行为
            children: list[SearchResult] = []
            for child in child_results[:_DEFAULT_CHILD_EXPAND_COUNT]:
                combined_score = parent_result["score"] * child["score"]
                child_payload = dict(child.get("payload", {}))
                child_payload["parent_chunk_id"] = str(parent_id)
                child_payload["parent_content"] = parent_content_preview
                child_payload["index_level"] = "child"
                children.append(SearchResult(id=child["id"], score=combined_score, payload=child_payload))
            return children

        child_batches = await asyncio.gather(
            *[_expand_child(p) for p in l3_results],
            return_exceptions=True,
        )
        for batch in child_batches:
            if isinstance(batch, list):
                expanded_results.extend(batch)

        # 3. 按 Parent 分数 × Child 分数降序排列（分数相同时按 id 确保确定性）
        expanded_results.sort(key=lambda r: (-r["score"], r["id"]))
        return expanded_results[:limit]

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    async def _search_l2_summaries(
        self,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """L2 文档摘要检索

        在 document_summaries collection 中执行 Dense 语义检索。
        L2 硬编码 collection 名为 "document_summaries"，与顶层 collection 参数解耦。

        降级策略：摘要 collection 不存在时降级为骨架（返回空列表，WARNING 日志）；
        Qdrant 查询异常时捕获 Exception 降级返回空列表 + WARNING 日志。

        Args:
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            摘要检索结果列表（list[SearchResult]）
        """
        return await self._search_summaries(
            collection="document_summaries",
            query_text=query_text,
            limit=limit,
            tenant_id=tenant_id,
            filter_payload=filter_payload,
            log_message="L2 文档摘要检索执行成功",
        )

    async def _search_l1_summaries(
        self,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """L1 跨文档摘要检索

        在 cross_document_summaries collection 中执行 Dense 语义检索。
        L1 硬编码 collection 名为 "cross_document_summaries"，与顶层 collection 参数解耦。

        降级策略：摘要 collection 不存在时降级为骨架（返回空列表，WARNING 日志）；
        Qdrant 查询异常时捕获 Exception 降级返回空列表 + WARNING 日志。

        Args:
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件

        Returns:
            跨文档摘要检索结果列表（list[SearchResult]）
        """
        return await self._search_summaries(
            collection="cross_document_summaries",
            query_text=query_text,
            limit=limit,
            tenant_id=tenant_id,
            filter_payload=filter_payload,
            log_message="L1 跨文档摘要检索执行成功",
        )

    async def _search_summaries(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
        log_message: str = "",
    ) -> list[SearchResult]:
        """摘要 collection 通用检索

        在指定摘要 collection 中执行 Dense 语义检索。
        不传递 index_level 过滤条件（摘要 collection 中的所有点均为摘要，无需额外过滤）。
        复用 self._dense_search.search() 端到端 Dense 检索模式。

        降级策略（独立 try/except，与 L3/L4 的 raise LayeredRetrievalError 不同）：
        - 摘要 collection 不存在时降级为骨架（返回空列表，WARNING 日志）
        - Qdrant 查询异常时捕获 Exception 降级返回空列表 + WARNING 日志

        Args:
            collection: 摘要 collection 名称（"document_summaries"/"cross_document_summaries"）
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID
            filter_payload: Payload 过滤条件
            log_message: 成功日志消息

        Returns:
            摘要检索结果列表（list[SearchResult]）
        """
        # 摘要 collection 不存在时降级为骨架（返回空列表）
        try:
            if not await self._l3_vector.collection_exists(collection):
                logger.warning("摘要 collection %s 不存在，降级返回空列表", collection)
                return []
        except Exception as e:
            logger.warning("检查摘要 collection %s 失败，降级返回空列表: %s", collection, e)
            return []

        try:
            raw_results = await self._dense_search.search(
                collection=collection,
                query_text=query_text,
                limit=limit,
                tenant_id=tenant_id,
                filter_payload=filter_payload,
            )
        except Exception as e:
            # 摘要不可用时静默降级保证检索可用性（与 L3/L4 的 raise 不同）
            logger.warning("摘要检索失败，降级返回空列表: %s", e)
            return []

        if not raw_results:
            return []
        if log_message:
            logger.info(log_message)
        return [
            SearchResult(id=r["id"], score=r["score"], payload=r.get("payload", {}))
            for r in raw_results
            if "id" in r and "score" in r
        ]

    @staticmethod
    def _validate_inputs(query_text: str, collection: str, limit: int, tenant_id: str | None = None) -> None:
        """验证输入参数

        Args:
            query_text: 查询文本
            collection: Collection 名称
            limit: 返回结果数量限制
            tenant_id: 租户 ID（可选，仅空白时拒绝）

        Raises:
            ValidationError: 参数验证失败时
        """
        if not query_text or not query_text.strip():
            raise ValidationError(message="查询文本不能为空")
        if not collection or not collection.strip():
            raise ValidationError(message="Collection 名称不能为空")
        if limit < 1:
            raise ValidationError(message=f"limit 必须为正整数，当前值: {limit}")
        if limit > _MAX_LIMIT:
            raise ValidationError(message=f"limit 不能超过 {_MAX_LIMIT}，当前值: {limit}")
        # tenant_id 空白校验：防止纯空白字符串绕过校验直接注入 Qdrant filter
        if tenant_id is not None and not tenant_id.strip():
            raise ValidationError(message="tenant_id 不能为空或仅含空白字符")

    @staticmethod
    def _validate_level(level: str) -> None:
        """验证层级参数

        Args:
            level: 层级字符串

        Raises:
            LevelTransitionError: 层级非法时
        """
        if level not in LAYERED_RETRIEVAL_LEVELS:
            raise LevelTransitionError(
                f"无效的层级: {level}，有效层级: L1/L2/L3/L4",
                context={"invalid_level": level, "valid_levels": sorted(LAYERED_RETRIEVAL_LEVELS)},
            )

    @staticmethod
    def _merge_filter(
        base_filter: dict | None,
        extra_filter: dict | None,
    ) -> dict | None:
        """合并过滤条件

        Args:
            base_filter: 基础过滤条件
            extra_filter: 额外过滤条件

        Returns:
            合并后的过滤条件
        """
        if base_filter is None and extra_filter is None:
            return None
        merged: dict[str, Any] = {}
        if base_filter is not None:
            merged.update(base_filter)
        if extra_filter is not None:
            merged.update(extra_filter)
        return merged if merged else None

    @staticmethod
    def _normalize_payload(
        payload: dict[str, Any],
        index_level: str,
    ) -> dict[str, Any]:
        """归一化检索结果 payload，确保层级元数据完整

        Args:
            payload: 原始 payload
            index_level: 目标层级（"parent"/"child"）

        Returns:
            确保包含 index_level 字段的 payload
        """
        normalized = dict(payload)
        normalized.setdefault("index_level", index_level)
        return normalized

    @classmethod
    def _merge_filter_with_tenant(
        cls,
        base_filter: dict | None,
        extra_filter: dict | None,
        tenant_id: str | None,
    ) -> dict | None:
        """合并过滤条件并注入租户 ID

        供直接调用 L3VectorPort.search() 的路径使用（该端口无独立 tenant_id 参数，
        租户隔离依赖 filter_payload 注入，此处统一封装避免各路径重复实现）。

        Args:
            base_filter: 基础过滤条件
            extra_filter: 额外过滤条件
            tenant_id: 租户 ID（None 时不注入）

        Returns:
            合并后的过滤条件（含 tenant_id 条件）
        """
        merged = cls._merge_filter(base_filter, extra_filter)
        if tenant_id is None:
            return merged
        return cls._merge_filter(merged or {}, {"tenant_id": tenant_id.strip()})
