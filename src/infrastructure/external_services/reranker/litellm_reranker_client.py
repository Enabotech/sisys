"""基础设施层重排序客户端（LiteLLM Reranker）

实现 RerankerPort 接口，使用 litellm.rerank() 专用端点进行重排序。
不经过 LLMClientPort（专用重排序 API 与文本生成 API 本质不同）。

设计决策：
- 使用 litellm.rerank() 专用端点（如 BAAI/bge-reranker-v2-m3）
- 不经过 LLMClientPort（仅含 generate()/structured_generate()，无法返回数值分数）
- 降级策略：调用失败时返回原始 results（不阻断主流程），WARNING 日志
- 分数契约：score = 归一化重排序分数，payload["original_score"] = 原 RRF 分数
"""

from __future__ import annotations

import logging
from typing import Any

from src.domain.exceptions import RerankError
from src.domain.ports.l3_vector import SearchResult
from src.infrastructure.external_services.reranker.config import RerankerConfig

logger = logging.getLogger(__name__)

# 尝试导入 litellm（可选依赖）
_litellm: Any
_litellm_available = False

try:
    import litellm

    _litellm = litellm
    _litellm_available = True
except ImportError:
    _litellm = None


class LiteLLMRerankerClient:
    """LiteLLM 重排序客户端

    实现 RerankerPort 接口，调用 litellm.rerank() 专用端点进行重排序。

    Attributes:
        config: 重排序配置（必需，非可选）
    """

    def __init__(
        self,
        config: RerankerConfig,
    ) -> None:
        """初始化重排序客户端

        Args:
            config: 重排序配置（必需，非可选）
        """
        self._config = config

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 20,
    ) -> list[SearchResult]:
        """对候选结果执行重排序

        Args:
            query: 原始查询文本
            results: 待重排序的候选结果列表
            top_k: 截断参数——仅返回分数最高的前 top_k 个；
                   顶部调用方传入（如 HybridSearchService 计算 min(limit*2, 20)），
                   config.top_k 作为配置默认值参考

        Returns:
            按重排序分数降序排列的结果列表，长度不超过 top_k
        """
        if not results:
            return []

        # 降级：重排序失败时返回原始结果
        try:
            return await self._do_rerank(query, results, top_k)
        except Exception as e:
            logger.warning("重排序 API 调用失败，降级返回原始结果: %s", e)
            # 确保原始分数保留
            for r in results:
                r["payload"]["original_score"] = r["score"]
            return results[:top_k]

    async def _do_rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """执行实际重排序 API 调用

        Args:
            query: 查询文本
            results: 候选结果列表
            top_k: 截断数量

        Returns:
            重排序后的结果列表
        """
        if not _litellm_available:
            logger.warning("litellm 未安装，降级返回原始结果")
            for r in results:
                r["payload"]["original_score"] = r["score"]
            return results[:top_k]

        # 准备文档列表
        documents = [r.get("payload", {}).get("title", "") or str(r.get("id", "")) for r in results]

        # 调用 litellm.rerank() 专用端点
        response = await _litellm.rerank(
            model=self._config.model,
            query=query,
            documents=documents,
            top_k=top_k,
            api_key=self._config.api_key or None,
            api_base=self._config.base_url or None,
            timeout=self._config.timeout,
        )

        # 处理响应——支持对象属性访问和 dict 两种响应格式
        reranked: list[SearchResult] = []
        raw_results: list[Any] = []
        if hasattr(response, "results"):
            raw_results = list(response.results) if response.results else []
        elif isinstance(response, dict):
            raw_results = response.get("results", [])
        else:
            logger.warning("重排序响应格式异常: %s", type(response).__name__)
            raise RerankError(
                "Unexpected response type",
                context={"response_type": type(response).__name__},
            )

        for item in raw_results:
            if isinstance(item, dict):
                index = item.get("index")
                rerank_score = item.get("relevance_score")
            else:
                index = getattr(item, "index", None)
                rerank_score = getattr(item, "relevance_score", None)

            if index is None or rerank_score is None:
                logger.warning("重排序响应项缺少 index 或 relevance_score: %s", item)
                continue

            if not isinstance(index, int) or index < 0 or index >= len(results):
                logger.warning("重排序响应 index 越界: index=%d, results_len=%d", index, len(results))
                continue

            original = results[index]
            original_score = original["score"]

            payload: dict[str, Any] = dict(original.get("payload", {}))
            payload["original_score"] = original_score
            payload["rerank_score"] = rerank_score

            reranked.append(
                SearchResult(
                    id=original["id"],
                    score=rerank_score,
                    payload=payload,
                )
            )

        # 按重排序分数降序排列
        reranked.sort(key=lambda r: r["score"], reverse=True)
        return reranked
