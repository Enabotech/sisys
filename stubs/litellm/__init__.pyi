"""litellm 类型存根

基于 litellm v1.28+ 公开 API 提供类型定义。
覆盖 LiteLLMRerankerClient 使用的 rerank() 方法。
来源: src/infrastructure/external_services/reranker/litellm_reranker_client.py
"""

from typing import Any, Dict, List, Optional

class RerankResponse:
    """重排序响应"""

    results: List[Dict[str, Any]]

    def get(self, key: str, default: Any = None) -> Any: ...

async def rerank(
    model: str,
    query: str,
    documents: List[str],
    top_k: int = 20,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    timeout: int = 10,
    **kwargs: Any,
) -> RerankResponse:
    """调用重排序 API 对查询和文档进行评分

    Args:
        model: 重排序模型名称（如 BAAI/bge-reranker-v2-m3）
        query: 查询文本
        documents: 待排序文档列表
        top_k: 返回前 K 个最相关文档
        api_key: API 密钥
        api_base: API 端点地址
        timeout: 超时时间（秒）

    Returns:
        RerankResponse 包含 results 列表，每个结果含 index 和 relevance_score
    """
    ...
