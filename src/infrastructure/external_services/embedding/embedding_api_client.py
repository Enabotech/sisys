"""基础设施层 Embedding API 客户端

通过 HTTP 调用独立部署的 BGE-M3 嵌入服务，实现 EmbeddingServicePort 协议。
使用 httpx.AsyncClient 异步 HTTP 通信（I/O 密集型，与项目 56 端口 213 async 方法惯例一致）。

架构参考: architecture.md §4.3 嵌入模型配置
异常规范: sisys-uni-exception-design.md — 使用统一异常层次结构
依赖: httpx
"""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx

from src.domain.exceptions import (
    EmbeddingAPIError,
    EmbeddingResponseError,
    NetworkError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
)
from src.domain.ports.embedding_service import EmbeddingServicePort, SparseEmbedding
from src.infrastructure.config.embedding import EmbeddingConfig

logger = logging.getLogger(__name__)


class EmbeddingAPIClient(EmbeddingServicePort):
    """BGE-M3 嵌入 API 客户端

    通过 HTTP POST /v1/embeddings 调用独立 API 服务，实现 EmbeddingServicePort 协议。
    使用 httpx.AsyncClient 异步 HTTP 通信，调用方直接 await 无需 asyncio.to_thread 包装。

    异常策略：
    - 超时 → TimeoutError (EXCEPTION_302)
    - 网络故障 → NetworkError (EXCEPTION_102)
    - HTTP 传输层错误 → EmbeddingAPIError (EXCEPTION_306)
    - 响应格式/结构异常 → EmbeddingResponseError (EXCEPTION_307)
    - 客户端已关闭 → ServiceUnavailableError (EXCEPTION_303)
    """

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        """初始化 API 客户端

        Args:
            config: 嵌入模型配置，需设置 api_url 字段

        Raises:
            ValidationError: api_url 为空时
        """
        if config is None:
            config = EmbeddingConfig()
        if not config.api_url:
            raise ValidationError(message="EMBEDDING_API_URL 未配置，API 模式需要指定嵌入服务地址")
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=config.api_timeout,
        )
        self._closed = False

    async def __aenter__(self) -> EmbeddingAPIClient:
        """支持 async with 语句，确保资源正确释放"""
        return self

    async def __aexit__(self, *args: object) -> None:
        """退出 async with 块时自动关闭"""
        await self.close()

    def _check_closed(self) -> None:
        """检查客户端是否已关闭

        Raises:
            ServiceUnavailableError: 客户端已关闭时
        """
        if self._closed:
            raise ServiceUnavailableError("EmbeddingAPIClient 已关闭，无法执行嵌入操作")

    @property
    def dimension(self) -> int:
        """嵌入向量维度

        Returns:
            向量维度（bge-m3 固定为 1024）
        """
        return 1024

    async def embed_query(self, text: str) -> list[float]:
        """查询文本 Dense 嵌入

        对标 LangChain Embeddings.embed_query()。
        将单条查询文本编码为语义向量。

        Args:
            text: 查询文本

        Returns:
            经 L2 归一化的 1024 维浮点向量

        Raises:
            ValidationError: 文本为空时
        """
        if not text or not text.strip():
            raise ValidationError(message="文本不能为空")
        result = await self._encode([text], return_sparse=False)
        return cast(list[float], result["dense"][0])

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """文档批量 Dense 嵌入

        对标 LangChain Embeddings.embed_documents()。
        将文档文本批量编码为语义向量。

        Args:
            texts: 待编码文档文本列表（空列表返回空结果）

        Returns:
            浮点向量列表

        Raises:
            ValidationError: 列表中包含空文本时
        """
        if not texts:
            return []
        for i, t in enumerate(texts):
            if not t or not t.strip():
                raise ValidationError(message=f"文本列表第 {i} 项不能为空")
        result = await self._encode(texts, return_sparse=False)
        return cast(list[list[float]], result["dense"])

    async def embed_sparse(self, texts: list[str]) -> list[SparseEmbedding]:
        """文档 Sparse 嵌入（批量）

        将文档文本批量编码为稀疏词汇权重向量。

        Args:
            texts: 待编码文本列表（空列表返回空结果）

        Returns:
            SparseEmbedding 列表

        Raises:
            ValidationError: 列表中包含空文本时
        """
        if not texts:
            return []
        for i, t in enumerate(texts):
            if not t or not t.strip():
                raise ValidationError(message=f"文本列表第 {i} 项不能为空")
        result = await self._encode(texts, return_sparse=True)
        sparse_list = cast(list[dict[str, Any]], result.get("sparse", []))
        if not sparse_list:
            return [SparseEmbedding(indices=[], values=[]) for _ in texts]
        # 长度一致性校验：防止服务端返回的 sparse 列表长度与输入不匹配
        if len(sparse_list) != len(texts):
            raise EmbeddingResponseError(f"Sparse 结果数({len(sparse_list)})与输入数({len(texts)})不匹配")
        return [SparseEmbedding(indices=s["indices"], values=s["values"]) for s in sparse_list]

    async def _encode(self, texts: list[str], *, return_sparse: bool) -> dict[str, Any]:
        """统一请求 /v1/embeddings

        Args:
            texts: 文本列表
            return_sparse: 是否返回 Sparse 向量

        Returns:
            API 响应 dict（包含 dense 键，可选 sparse 键）

        Raises:
            TimeoutError: 请求超时时
            NetworkError: 网络故障时
            EmbeddingAPIError: HTTP 传输层错误时
            EmbeddingResponseError: 响应结构异常时
        """
        self._check_closed()
        try:
            resp = await self._client.post(
                "/v1/embeddings",
                json={"texts": texts, "return_sparse": return_sparse},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException as e:
            raise TimeoutError(f"嵌入 API 请求超时: {e}", cause=e) from e
        except httpx.TransportError as e:
            raise NetworkError(f"嵌入 API 网络错误: {e}", cause=e) from e
        except httpx.HTTPStatusError as e:
            raise EmbeddingAPIError(f"嵌入 API 返回 HTTP {e.response.status_code}", cause=e) from e
        except ValueError as e:
            raise EmbeddingResponseError(f"嵌入 API 响应格式异常: {e}", cause=e) from e

        # 响应结构校验：防止 API 返回异常格式导致 KeyError/IndexError 绕过异常包装
        if not isinstance(data, dict) or "dense" not in data:
            keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
            raise EmbeddingResponseError(f"嵌入 API 响应缺少 'dense' 字段: {keys}")
        if not isinstance(data["dense"], list):
            raise EmbeddingResponseError(f"嵌入 API 响应 'dense' 字段非列表: {type(data['dense']).__name__}")
        if len(data["dense"]) != len(texts):
            raise EmbeddingResponseError(f"嵌入 API 返回向量数({len(data['dense'])})与输入数({len(texts)})不匹配")

        return data

    async def close(self) -> None:
        """关闭 HTTP 客户端，释放连接池资源

        关闭后实例不可再使用，再次调用 embed_* 方法将抛出 ServiceUnavailableError。
        重复调用 close() 是安全的（幂等）。
        """
        if not self._closed:
            self._closed = True
            try:
                await self._client.aclose()
            except Exception:
                logger.debug("httpx.AsyncClient.aclose() 异常（可忽略）", exc_info=True)
