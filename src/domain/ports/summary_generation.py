"""领域层 摘要生成端口契约模块（SummaryGenerationPort）

定义契约化结构化摘要生成的统一抽象端口契约。
支持多视角（财务/市场/技术）和跨文档摘要模式。

设计决策：
- 输入使用 SearchResult（与现有检索服务签名对齐，同域内类型引用）
- perspective 为视角类型字符串（"financial"/"market"/"technical"）
- cross_document 参数区分单文档摘要（L2）和跨文档摘要（L1）
- config 使用 LLMConfig 值对象（同域内类型引用，提供精确类型约束）
- 返回类型为 Any（领域层不依赖 pydantic）
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.llm_client import LLMConfig


@runtime_checkable
class SummaryGenerationPort(Protocol):
    """摘要生成端口契约

    定义契约化摘要生成的统一接口，支持多视角结构化输出。
    输入检索结果列表，输出符合预定义 JSON Schema 的结构化摘要。
    """

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
            tenant_id: 可选租户 ID（多租户隔离）
            cross_document: 跨文档摘要模式（False 生成单文档 L2 摘要，
                           True 聚合 L2 摘要生成跨文档 L1 摘要）
            limit: 跨文档模式下 L2 检索结果数量限制（默认 10）

        Returns:
            对应视角 Schema 的 Pydantic 实例

        Raises:
            ValidationError: 查询文本为空时
            SummaryPerspectiveNotSupportedError: 不支持的视角类型
            SummaryGenerationError: 摘要生成整体失败
            LLMConfigError: LLM 配置错误时透传
        """
        ...


__all__ = [
    "SummaryGenerationPort",
]
