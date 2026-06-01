"""基础设施层嵌入服务包

提供 BGE-M3 嵌入模型的基础设施层实现
"""

from src.infrastructure.external_services.embedding.bge3_embedding_service import (
    BGE3EmbeddingService,
)

__all__ = ["BGE3EmbeddingService"]
