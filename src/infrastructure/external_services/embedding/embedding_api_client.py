"""基础设施层 Embedding API 客户端

通过 HTTP 调用独立部署的 BGE-M3 嵌入服务，实现 EmbeddingServicePort 协议。
使用 httpx.AsyncClient 异步 HTTP 通信（I/O 密集型，与项目 56 端口 213 async 方法惯例一致）。

故障恢复策略：
- 指数退避重试：对 500/502/503/504 等可恢复服务端错误，最多重试 3 次
  （首次 1s → 2s → 4s，含 0.1x 随机抖动避免惊群）
- 熔断器保护：连续 5 次失败断开 30 秒，防止对已宕服务无效重试

架构参考: architecture.md §4.3 嵌入模型配置
异常规范: sisys-uni-exception-design.md — 使用统一异常层次结构
依赖: httpx, tenacity
"""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

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
from src.infrastructure.external_services.embedding.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
)

logger = logging.getLogger(__name__)

# 可恢复的服务端 HTTP 状态码：这些错误可能因瞬时故障自行恢复
_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


def _is_retryable_http_error(exception: BaseException) -> bool:
    """判断异常是否可重试

    规则：
    - httpx.TimeoutException → 可重试（网络抖动）
    - httpx.TransportError → 可重试（临时连接故障）
    - HTTPStatusError 且状态码在 _RETRYABLE_STATUS_CODES 中 → 可重试
    - 其他 → 不可重试（直接抛出）
    """
    if isinstance(exception, httpx.TimeoutException):
        return True
    if isinstance(exception, httpx.TransportError):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in _RETRYABLE_STATUS_CODES
    return False


class EmbeddingAPIClient(EmbeddingServicePort):
    """BGE-M3 嵌入 API 客户端

    通过 HTTP POST /v1/embeddings 调用独立 API 服务，实现 EmbeddingServicePort 协议。
    使用 httpx.AsyncClient 异步 HTTP 通信，调用方直接 await 无需 asyncio.to_thread 包装。

    内置容错机制：
    - 指数退避重试（最多 3 次，针对 500/502/503/504）
    - 熔断器（5 次连续失败断开 30 秒）

    异常策略：
    - 超时 → TimeoutError (EXCEPTION_302)
    - 网络故障 → NetworkError (EXCEPTION_102)
    - 熔断器断开 → ServiceUnavailableError (EXCEPTION_303)
    - HTTP 传输层错误 → EmbeddingAPIError (EXCEPTION_306)
    - 响应格式/结构异常 → EmbeddingResponseError (EXCEPTION_307)
    - 客户端已关闭 → ServiceUnavailableError (EXCEPTION_303)
    """

    def __init__(
        self,
        config: EmbeddingConfig | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
    ) -> None:
        """初始化 API 客户端

        Args:
            config: 嵌入模型配置，需设置 api_url 字段
            circuit_breaker: 熔断器实例，默认使用故障阈值 5、恢复超时 30 秒
            retry_max_attempts: 最大重试次数（含首次，默认 3）
            retry_min_wait: 最小重试等待秒数（默认 1.0）
            retry_max_wait: 最大重试等待秒数（默认 4.0）

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
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            name="embedding-api",
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

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

        内置熔断器保护和指数退避重试：
        - 熔断器断开时快速失败（ServiceUnavailableError）
        - 500/502/503/504 最多重试 3 次（1s → 2s → 4s + 随机抖动）
        - 超时/网络故障也视为可重试

        Args:
            texts: 文本列表
            return_sparse: 是否返回 Sparse 向量

        Returns:
            API 响应 dict（包含 dense 键，可选 sparse 键）

        Raises:
            TimeoutError: 请求超时（重试耗尽后）
            NetworkError: 网络故障（重试耗尽后）
            EmbeddingAPIError: 服务端错误（重试耗尽后）
            EmbeddingResponseError: 响应结构异常
            ServiceUnavailableError: 熔断器断开或客户端已关闭
        """
        self._check_closed()

        # 第 1 步：检查熔断器状态（快速失败，不发起网络请求）
        try:
            self._circuit_breaker.before_call()
        except CircuitBreakerOpenError as e:
            raise ServiceUnavailableError(
                f"嵌入 API 熔断器已断开: {e}",
                cause=e,
            ) from e

        # 第 2 步：指数退避重试
        # 使用 tenacity.AsyncRetrying 而非 asyncio.gather + 手动循环，
        # 理由：
        # - 代码简洁，语义清晰
        # - 支持指数退避 + 随机抖动，避免惊群
        # - 支持条件重试（仅对可恢复错误重试）
        # - 与项目内已有依赖 tenacity 一致
        #
        # 设计要点：
        # - 重试层只让原始 httpx 异常传播（让 tenacity 的 retry_if_exception
        #   基于原始异常类型判断是否可重试），异常转换在重试耗尽后完成
        # - 响应格式错误（ValueError）不重试，直接向外抛出
        # - 重试耗尽后通知熔断器记录失败
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._retry_max_attempts),
                wait=wait_exponential(
                    multiplier=1,
                    min=self._retry_min_wait,
                    max=self._retry_max_wait,
                ),
                retry=retry_if_exception(_is_retryable_http_error),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    resp = await self._client.post(
                        "/v1/embeddings",
                        json={"texts": texts, "return_sparse": return_sparse},
                    )
                    resp.raise_for_status()
                    data = resp.json()
        except httpx.TimeoutException as e:
            self._circuit_breaker.on_failure()
            raise TimeoutError(f"嵌入 API 请求超时: {e}", cause=e) from e
        except httpx.TransportError as e:
            self._circuit_breaker.on_failure()
            raise NetworkError(f"嵌入 API 网络错误: {e}", cause=e) from e
        except httpx.HTTPStatusError as e:
            self._circuit_breaker.on_failure()
            raise EmbeddingAPIError(f"嵌入 API 返回 HTTP {e.response.status_code}", cause=e) from e
        except ValueError as e:
            # JSON 解析失败：不重试，不记熔断器（客户端问题）
            raise EmbeddingResponseError(f"嵌入 API 响应格式异常: {e}", cause=e) from e

        # 第 3 步：响应结构校验
        # data 在此处一定有值 —— 若 httpx/json 异常已在上面被捕获并转换
        if not isinstance(data, dict) or "dense" not in data:
            keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
            raise EmbeddingResponseError(f"嵌入 API 响应缺少 'dense' 字段: {keys}")
        if not isinstance(data["dense"], list):
            raise EmbeddingResponseError(f"嵌入 API 响应 'dense' 字段非列表: {type(data['dense']).__name__}")
        if len(data["dense"]) != len(texts):
            raise EmbeddingResponseError(f"嵌入 API 返回向量数({len(data['dense'])})与输入数({len(texts)})不匹配")

        # 成功 → 通知熔断器
        self._circuit_breaker.on_success()
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
