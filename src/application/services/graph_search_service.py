"""应用层 Graph 检索服务（第三路检索信号）

通过 L5GraphPort 执行图遍历检索，作为第三路信号参与三路 RRF 融合。

架构决策：
- 仅注入 L5GraphPort（领域端口），不使用 GraphRetriever（基础设施具象类）
- 检索流程：search_entities(query_text) → 对候选实体逐个 find_related() → 聚合去重 → SearchResult
- 异常时透明降级返回空列表（由编排层 HybridSearchService 处理）

依赖注入：
- L5GraphPort（领域层端口，Story 1.8 已合入）
"""

from __future__ import annotations

import logging
from typing import Any

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.l5_graph import L5GraphPort

logger = logging.getLogger(__name__)

# 实体类型权重映射
_TYPE_WEIGHTS: dict[str, float] = {
    "concept": 0.8,
    "person": 0.6,
    "organization": 0.7,
}

# 默认权重（未知实体类型）
_DEFAULT_TYPE_WEIGHT: float = 0.5


class GraphSearchService:
    """Graph 检索服务（第三路检索信号）

    通过 L5GraphPort 检索实体关联关系，输出兼容 SearchResult 的结果列表。
    search() 签名与 DenseSemanticSearchService/Bm25SparseSearchService 对齐。
    """

    def __init__(
        self,
        l5_graph: L5GraphPort,
    ) -> None:
        """初始化 Graph 检索服务

        Args:
            l5_graph: L5 图存储端口（领域层端口，非 GraphRetriever）
        """
        self._l5_graph = l5_graph

    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """执行 Graph 检索

        检索流程：
        1. L5GraphPort.search_entities(query_text, limit) → 候选实体列表
        2. 对每个候选实体调用 L5GraphPort.find_related(memory_id, max_depth=2)
        3. 聚合所有关联实体，按 memory_id 去重
        4. 转换为 SearchResult 格式

        Args:
            collection: Collection 名称（未使用，保留签名对齐）
            query_text: 查询文本
            limit: 候选实体数量限制
            tenant_id: 租户 ID（未使用，保留签名对齐）
            filter_payload: 过滤条件（未使用，保留签名对齐）

        Returns:
            SearchResult 格式的结果列表，按 score 降序排列
        """
        # 空查询直接返回空列表（与 Dense/Sparse 行为一致）
        if not query_text or not query_text.strip():
            return []

        # 步骤 1：通过 search_entities 解析查询文本中的实体
        try:
            candidates = await self._l5_graph.search_entities(query_text, limit=limit)
        except Exception as e:
            logger.warning("Graph 检索 search_entities 失败，透明降级: %s", e)
            return []

        if not candidates:
            return []

        # 步骤 2：对每个候选实体获取关联文档
        all_related: list[dict] = []
        seen_ids: set[str | int] = set()

        for entity in candidates:
            memory_id = entity.get("memory_id")
            if not memory_id:
                continue

            try:
                related = await self._l5_graph.find_related(memory_id, max_depth=2)
            except Exception as e:
                logger.warning("Graph 检索 find_related(%s) 失败，跳过该实体: %s", memory_id, e)
                continue

            for item in related:
                item_id = item.get("memory_id")
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    all_related.append(item)

        # 步骤 3：转换为 SearchResult
        results: list[SearchResult] = []
        for item in all_related:
            item_id = item.get("memory_id")
            if item_id is None:
                continue

            # 分数计算：type_weight * connection_count / (1 + hops)
            entity_type = item.get("type", "")
            type_weight = _TYPE_WEIGHTS.get(entity_type, _DEFAULT_TYPE_WEIGHT)
            connection_count = item.get("connection_count", 1)
            path = item.get("path", [])
            hops = len(path)
            score = type_weight * connection_count / (1 + hops)

            payload: dict[str, Any] = {
                "entity_type": entity_type,
                "properties": item.get("properties", {}),
                "hops": hops,
                "connection_count": connection_count,
            }

            results.append(SearchResult(id=item_id, score=score, payload=payload))

        # 按 score 降序排列
        results.sort(key=lambda r: r["score"], reverse=True)
        return results
