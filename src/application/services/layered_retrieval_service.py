"""Story 3.5 分层检索应用服务

编排 Dense 语义检索 + L3VectorPort 提供 L1-L4 分层检索能力。
支持自底向上（L4→L3 回溯）和自顶向下（L3→L4 展开）两种遍历策略。

降级策略：
- L4 检索失败 → 透明降级为普通 L3 检索，WARNING 日志
- L2/L1 当前为骨架实现（返回空列表），完整实现依赖 Story 3.6

依赖注入：
- DenseSemanticSearchService（外部构造，用于执行 Dense 语义检索）
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
from src.domain.ports.l3_vector import SearchResult

logger = logging.getLogger(__name__)

# 有效层级常量
VALID_LEVELS = frozenset({"L1", "L2", "L3", "L4"})


def _safe_truncate(text: str, max_len: int) -> str:
    """安全截断文本，处理多字节 UTF-8 字符

    Args:
        text: 输入文本
        max_len: 最大字符数

    Returns:
        截断后的文本
    """
    if not text:
        return ""
    # 按 Unicode 字符（而非字节）截断，避免多字节字符被从中截断
    chars = list(text)
    return "".join(chars[:max_len])


# 自顶向下展开时每个 Parent 最多展开的 Child 子块数
_DEFAULT_CHILD_EXPAND_COUNT = 3


class LayeredRetrievalService:
    """分层检索编排服务

    编排 DenseSemanticSearchService + L3VectorPort 实现 L1-L4 分层检索。
    支持自底向上（L4→L3 回溯）和自顶向下（L3→L4 展开）双向遍历。

    Attributes:
        _dense_search: Dense 语义检索服务
        _l3_vector: L3 向量存储端口
    """

    def __init__(
        self,
        dense_search: Any,
        l3_vector: Any,
    ) -> None:
        """初始化分层检索服务

        Args:
            dense_search: DenseSemanticSearchService 实例
            l3_vector: L3VectorPort 实例（用于按 payload 过滤回溯和按 ID 获取）
        """
        self._dense_search = dense_search
        self._l3_vector = l3_vector

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
        self._validate_inputs(query_text, collection, limit)
        self._validate_level(target_level)

        # L1/L2 骨架实现
        if target_level == "L1":
            logger.warning("L1 跨文档摘要检索尚未实现，返回空列表")
            return []
        if target_level == "L2":
            logger.warning("L2 文档摘要检索尚未实现，返回空列表")
            return []

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
        self._validate_inputs(query_text, collection, limit)
        self._validate_level(target_level)

        # L1/L2 骨架实现
        if target_level == "L1":
            logger.warning("L1 跨文档摘要检索尚未实现，返回空列表")
            return []
        if target_level == "L2":
            logger.warning("L2 文档摘要检索尚未实现，返回空列表")
            return []

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
            return [
                SearchResult(id=r["id"], score=r["score"], payload=r.get("payload") or {})
                for r in raw_results
                if "id" in r and "score" in r
            ]
        except Exception as e:
            logger.error("L3 直接检索失败: %s", e)
            raise LayeredRetrievalError(
                f"L3 直接检索失败: {e}",
                context={"collection": collection, "target_level": "L3"},
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
                SearchResult(id=r["id"], score=r["score"], payload=r.get("payload") or {})
                for r in raw_results
                if "id" in r and "score" in r
            ]
        except Exception as e:
            logger.error("L4 直接检索失败: %s", e)
            raise LayeredRetrievalError(
                f"L4 直接检索失败: {e}",
                context={"collection": collection, "target_level": "L4"},
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
        except Exception as e:
            # 降级：L4 检索失败 → 透明降级为 L3 检索
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
        merged_results: list[SearchResult] = []

        async def _fetch_parent(parent_id: str, info: dict[str, Any]) -> SearchResult | None:
            """获取单个父块内容

            Args:
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
                    "content": parent_payload.get("content", ""),
                    "document_id": parent_payload.get("document_id", ""),
                },
            )

        tasks = [asyncio.ensure_future(_fetch_parent(pid, inf)) for pid, inf in parent_info.items()]
        for task in tasks:
            result = await task
            if result is not None:
                merged_results.append(result)

        # 4. 按最高 Child 分数降序排列
        merged_results.sort(key=lambda r: r["score"], reverse=True)
        return merged_results[:limit]

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
        """
        # 1. 嵌入查询向量一次，L3 检索与后续 Child 展开复用
        try:
            query_vector = await self._dense_search._embedding.embed_query(query_text)
        except Exception as e:
            logger.error("L3 查询嵌入失败: %s", e)
            raise LayeredRetrievalError(
                f"L3 查询嵌入失败: {e}",
                context={"collection": collection, "target_level": "L4"},
            ) from e

        # 2. L3 层 Dense 检索（直接传向量，避免二次嵌入）
        parent_filter = self._merge_filter(filter_payload, {"index_level": "parent"})
        if tenant_id:
            parent_filter = self._merge_filter(parent_filter, {"tenant_id": tenant_id})
        try:
            l3_raw = await self._l3_vector.search(
                collection=collection,
                query_vector=query_vector,
                limit=min(limit, 5),  # 限制展开 Parent 数，避免 N+1 问题
                filter_payload=parent_filter,
            )
        except Exception as e:
            logger.error("L3 检索失败，无法展开 L4: %s", e)
            raise LayeredRetrievalError(
                f"L3 检索失败，无法展开 L4: {e}",
                context={"collection": collection, "target_level": "L4"},
            ) from e

        l3_results = [
            SearchResult(id=r["id"], score=r["score"], payload=r.get("payload") or {})
            for r in l3_raw
            if isinstance(r, dict) and "id" in r and "score" in r
        ]
        if not l3_results:
            return []

        # 3. 对每个命中 Parent，展开 Top-3 Child（复用 query_vector 传向量）
        expanded_results: list[SearchResult] = []
        for parent_result in l3_results:
            parent_id = parent_result.get("id")
            if parent_id is None:
                logger.warning("L3→L4 展开: Parent id 为 None，跳过")
                continue

            parent_payload = parent_result.get("payload", {})
            parent_content = parent_payload.get("content")
            if not isinstance(parent_content, str):
                parent_content = ""
            parent_content_preview = _safe_truncate(parent_content, 200)

            child_filter = self._merge_filter(
                filter_payload,
                {"index_level": "child", "parent_chunk_id": str(parent_id)},
            )
            if tenant_id:
                child_filter = self._merge_filter(child_filter, {"tenant_id": tenant_id})

            try:
                child_raw = await self._l3_vector.search(
                    collection=collection,
                    query_vector=query_vector,
                    limit=_DEFAULT_CHILD_EXPAND_COUNT,
                    filter_payload=child_filter,
                )
            except Exception:
                logger.warning("Parent %s 的 Child 展开失败，跳过", parent_id)
                continue

            child_results = [r for r in child_raw if isinstance(r, dict) and "id" in r and "score" in r]

            # 服务自身强制 Top-3 截断，不依赖后端 limit 行为
            for child in child_results[:_DEFAULT_CHILD_EXPAND_COUNT]:
                combined_score = parent_result["score"] * child["score"]
                child_payload = dict(child.get("payload", {}))
                child_payload["parent_chunk_id"] = str(parent_id)
                child_payload["parent_content"] = parent_content_preview
                child_payload["index_level"] = "child"

                expanded_results.append(
                    SearchResult(
                        id=child["id"],
                        score=combined_score,
                        payload=child_payload,
                    )
                )

        # 3. 按 Parent 分数 × Child 分数降序排列
        expanded_results.sort(key=lambda r: r["score"], reverse=True)
        return expanded_results[:limit]

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_inputs(query_text: str, collection: str, limit: int) -> None:
        """验证输入参数

        Args:
            query_text: 查询文本
            collection: Collection 名称
            limit: 返回结果数量限制

        Raises:
            ValidationError: 参数验证失败时
        """
        if not query_text or not query_text.strip():
            raise ValidationError(message="查询文本不能为空")
        if not collection or not collection.strip():
            raise ValidationError(message="Collection 名称不能为空")
        if limit < 1:
            raise ValidationError(message=f"limit 必须为正整数，当前值: {limit}")

    @staticmethod
    def _validate_level(level: str) -> None:
        """验证层级参数

        Args:
            level: 层级字符串

        Raises:
            LevelTransitionError: 层级非法时
        """
        if level not in VALID_LEVELS:
            raise LevelTransitionError(
                f"无效的层级: {level}，有效层级: L1/L2/L3/L4",
                context={"invalid_level": level, "valid_levels": sorted(VALID_LEVELS)},
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
        if base_filter:
            merged.update(base_filter)
        if extra_filter:
            merged.update(extra_filter)
        return merged if merged else None
