"""领域层 Embedding 嵌入服务异常模块

嵌入服务专属异常，用于区分 Embedding API 传输层错误、响应格式错误和模型错误。
对标业界最佳实践（Google domain+reason、Stripe type+code 二级编码），
为 Embedding 子系统分配独立异常编码，提升监控可观测性和故障定位效率。

异常编码范围：EXCEPTION_306 ~ EXCEPTION_319（预留）
- 306: API 传输层错误（HTTP 4xx/5xx）
- 307: 响应格式错误（JSON 解析、结构校验、数量不匹配）
- 308: 模型错误（未加载、推理失败、输出键缺失）
"""

from __future__ import annotations

from src.domain.exceptions.external_exceptions import ExternalException, ThirdPartyError


class EmbeddingAPIError(ThirdPartyError):
    """嵌入 API 传输层错误

    嵌入服务 HTTP 调用返回非预期状态码（4xx/5xx）。
    继承 ThirdPartyError，HTTP 映射自动回退至 502 Bad Gateway。

    Attributes:
        code: EXCEPTION_306
        message: 嵌入 API 传输层错误描述
    """

    code = "EXCEPTION_306"
    message = "Embedding API error"


class EmbeddingResponseError(ThirdPartyError):
    """嵌入 API 响应格式错误

    嵌入服务返回的响应结构不符合预期，包括：
    - JSON 解析失败
    - 缺少 'dense' 字段
    - 'dense' 字段非列表
    - 向量数量与输入文本数量不匹配
    - Sparse 结果数量与输入不匹配

    继承 ThirdPartyError，HTTP 映射自动回退至 502 Bad Gateway。

    Attributes:
        code: EXCEPTION_307
        message: 嵌入 API 响应格式错误描述
    """

    code = "EXCEPTION_307"
    message = "Embedding response format error"


class EmbeddingModelError(ExternalException):
    """嵌入模型错误

    BGE-M3 模型运行时故障，包括：
    - 模型未加载（503）
    - 模型推理失败（500）
    - 模型输出缺少必要键（dense_vecs / lexical_weights）

    注意：此异常用于服务端（embedding_api_server）的内部错误分类，
    服务端对外仍使用 HTTPException。客户端侧通过 HTTP 状态码间接感知。

    Attributes:
        code: EXCEPTION_308
        message: 嵌入模型错误描述
    """

    code = "EXCEPTION_308"
    message = "Embedding model error"


__all__ = [
    "EmbeddingAPIError",
    "EmbeddingResponseError",
    "EmbeddingModelError",
]
