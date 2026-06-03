"""基础设施层嵌入服务包

提供 BGE-M3 嵌入模型的基础设施层实现（统一 API Client）
"""

from src.infrastructure.external_services.embedding.embedding_api_client import (
    EmbeddingAPIClient,
)

__all__ = ["EmbeddingAPIClient"]
