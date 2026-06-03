"""基础设施层嵌入模型配置

管理 BGE-M3 嵌入 API 的连接参数。
架构参考: architecture.md §4.3 嵌入模型配置
"""

from __future__ import annotations

import os
from dataclasses import dataclass


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
        """
        return cls(
            api_url=os.getenv("EMBEDDING_API_URL", "http://embedding-api:8000"),
            api_timeout=float(os.getenv("EMBEDDING_API_TIMEOUT", "30.0")),
        )
