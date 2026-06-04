"""基础设施层 Embedding API 客户端

通过 HTTP 调用独立部署的 BGE-M3 嵌入服务，实现 EmbeddingServicePort 协议。

架构参考: architecture.md §4.3 嵌入模型配置
依赖: httpx
"""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx

from src.domain.ports.embedding_service import EmbeddingServicePort
from src.infrastructure.config.embedding import EmbeddingConfig

logger = logging.getLogger(__name__)


class EmbeddingServiceError(RuntimeError):
    """嵌入服务调用异常

    包装 HTTP 客户端层异常（连接、超时、非预期响应），
    避免原始 httpx 异常泄露到应用层。
    """


class EmbeddingAPIClient(EmbeddingServicePort):
    """BGE-M3 嵌入 API 客户端

    通过 HTTP POST /v1/embeddings 调用独立 API 服务，实现 EmbeddingServicePort 协议。
    方法签名使用同步 def，内部使用 httpx.Client（同步），
    调用方通过 asyncio.to_thread 包装以避免阻塞事件循环。
    """

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        """初始化 API 客户端

        Args:
            config: 嵌入模型配置，需设置 api_url 字段

        Raises:
            ValueError: api_url 为空时
        """
        if config is None:
            config = EmbeddingConfig()
        if not config.api_url:
            raise ValueError("EMBEDDING_API_URL 未配置，API 模式需要指定嵌入服务地址")
        self._config = config
        self._client = httpx.Client(
            base_url=config.api_url,
            timeout=config.api_timeout,
        )

    @property
    def dimension(self) -> int:
        """嵌入向量维度

        Returns:
            向量维度（bge-m3 固定为 1024）
        """
        return 1024

    def encode_text(self, text: str) -> list[float]:
        """单文本 Dense 编码

        Args:
            text: 待编码文本

        Returns:
            经 L2 归一化的 1024 维浮点向量

        Raises:
            ValueError: 文本为空时
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        result = self._encode([text], return_sparse=False)
        return cast(list[float], result["dense"][0])

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        """批量文本 Dense 编码

        Args:
            texts: 待编码文本列表（空列表返回空结果）

        Returns:
            浮点向量列表

        Raises:
            ValueError: 列表中包含空文本时
        """
        if not texts:
            return []
        for i, t in enumerate(texts):
            if not t or not t.strip():
                raise ValueError(f"文本列表第 {i} 项不能为空")
        result = self._encode(texts, return_sparse=False)
        return cast(list[list[float]], result["dense"])

    def encode_sparse(self, text: str) -> dict[str, list[Any]]:
        """单文本 Sparse 编码

        Args:
            text: 待编码文本

        Returns:
            {"indices": list[int], "values": list[float]}

        Raises:
            ValueError: 文本为空时
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        result = self._encode([text], return_sparse=True)
        sparse_list = cast(list[dict[str, Any]], result.get("sparse", []))
        if not sparse_list:
            return {"indices": [], "values": []}
        return sparse_list[0]

    def _encode(self, texts: list[str], *, return_sparse: bool) -> dict[str, Any]:
        """统一请求 /v1/embeddings

        Args:
            texts: 文本列表
            return_sparse: 是否返回 Sparse 向量

        Returns:
            API 响应 dict

        Raises:
            EmbeddingServiceError: 网络错误、超时或非预期响应时
        """
        try:
            resp = self._client.post(
                "/v1/embeddings",
                json={"texts": texts, "return_sparse": return_sparse},
            )
            resp.raise_for_status()
            return cast(dict[str, Any], resp.json())
        except httpx.TimeoutException as e:
            raise EmbeddingServiceError(f"嵌入 API 请求超时: {e}") from e
        except httpx.NetworkError as e:
            raise EmbeddingServiceError(f"嵌入 API 网络错误: {e}") from e
        except httpx.HTTPStatusError:
            raise
        except (ValueError, KeyError) as e:
            raise EmbeddingServiceError(f"嵌入 API 响应格式异常: {e}") from e

    def close(self) -> None:
        """关闭 HTTP 客户端"""
        self._client.close()
