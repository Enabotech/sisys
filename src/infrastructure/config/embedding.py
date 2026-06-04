"""基础设施层嵌入模型配置

管理 BGE-M3 嵌入 API 的连接参数。
架构参考: architecture.md §4.3 嵌入模型配置
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class EmbeddingConfig:
    """嵌入 API 配置

    Attributes:
        api_url: 嵌入 API 服务地址
        api_timeout: API 请求超时秒数
    """

    api_url: str = ""
    api_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> EmbeddingConfig:
        """从环境变量构建配置

        Returns:
            嵌入 API 配置实例

        Raises:
            ValueError: EMBEDDING_API_URL 格式无效或 EMBEDDING_API_TIMEOUT 值非法时
        """
        api_url = os.getenv("EMBEDDING_API_URL", "").rstrip("/")
        if api_url:
            parsed = urlparse(api_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"EMBEDDING_API_URL 格式无效: {api_url!r}（需要完整 URL，如 http://host:port）")

        timeout_raw = os.getenv("EMBEDDING_API_TIMEOUT", "30.0")
        try:
            timeout = float(timeout_raw)
        except (ValueError, TypeError):
            raise ValueError(f"EMBEDDING_API_TIMEOUT 值非法: {timeout_raw!r}（需要数值）") from None
        if timeout <= 0:
            raise ValueError(f"EMBEDDING_API_TIMEOUT 必须为正数，当前值: {timeout}")
        return cls(
            api_url=api_url or "http://embedding-api:8000",
            api_timeout=timeout,
        )
