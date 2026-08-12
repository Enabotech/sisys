"""领域层 重排序端口模块（RerankerPort）

定义重排序（Rerank）端口契约，用于对 RRF 融合后的 Top-K 候选结果进行精排。

设计决策：
- 独立评分任务，使用专用重排序 API（如 litellm.rerank()），不复用 LLMClientPort
- 端口统一返回 `SearchResult`，不引入 RerankResult 值对象
- `original_score` 等附加信息存入 payload["original_score"]
- 领域层零外部依赖（仅使用 Python 标准库 + SearchResult）

top_k 语义：
- `top_k` 是截断参数——对全部输入结果重排序，仅返回分数最高的前 top_k 个
- `top_k >= len(results)` 时返回全部（结果数量不变）
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l3_vector import SearchResult


@runtime_checkable
class RerankerPort(Protocol):
    """重排序端口契约

    对 Top-K 候选结果执行重排序（精排），返回按重排序分数降序排列的结果。

    实现：
    - LiteLLMRerankerClient（基础设施层，调用 litellm.rerank() 专用端点）
    """

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 20,
    ) -> list[SearchResult]:
        """对候选结果执行重排序

        Args:
            query: 原始查询文本
            results: 待重排序的候选结果列表（通常为 RRF 融合结果）
            top_k: 截断参数——仅返回分数最高的前 top_k 个；
                   top_k >= len(results) 时返回全部（结果数量不变）

        Returns:
            按重排序分数降序排列的结果列表，长度不超过 top_k
        """
        ...
