"""litellm 类型存根

基于 litellm v1.28+ 公开 API 提供类型定义。
覆盖 LiteLLMRerankerClient 使用的 rerank() 方法，以及 LitellmLLMClient 使用的 acompletion()。
来源:
  - src/infrastructure/external_services/reranker/litellm_reranker_client.py
  - src/infrastructure/external_services/llm/litellm_llm_client.py
"""

from typing import Any, Dict, List, Optional

class ModelResponse:
    """LLM 调用响应"""

    choices: List[Dict[str, Any]]

    def get(self, key: str, default: Any = None) -> Any: ...

class RerankResponse:
    """重排序响应"""

    results: List[Dict[str, Any]]

    def get(self, key: str, default: Any = None) -> Any: ...

async def acompletion(
    model: str,
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    response_format: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    timeout: Optional[int] = None,
    **kwargs: Any,
) -> ModelResponse:
    """调用 LLM 完成 API

    Args:
        model: 模型名称
        messages: 消息列表
        temperature: 温度参数
        max_tokens: 最大 token 数
        response_format: 响应格式（用于结构化输出）
        api_key: API 密钥
        api_base: API 端点地址
        timeout: 超时时间（秒）

    Returns:
        ModelResponse 包含 choices 列表
    """
    ...

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
