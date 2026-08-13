"""基础设施层缓存失效事件处理器模块

监听 DocumentProcessed 事件，触发语义缓存失效。
通过 SemanticCache.invalidate_by_document_id() 端口方法封装二级索引逻辑。

设计要点：
- 订阅 DocumentProcessed 事件，当文档解析/索引完成后触发缓存清理
- 采用二级索引精确失效策略，不直接操作 redis_client
- 失效失败仅记录日志，不抛出异常（不影响主流程）
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.ports.semantic_cache import SemanticCache
    from src.domain.events.base import DomainEvent

logger = logging.getLogger(__name__)


class CacheInvalidationHandler:
    """缓存失效事件处理器

    监听 DocumentProcessed 事件，触发语义缓存失效。
    通过 SemanticCache.invalidate_by_document_id() 端口方法封装二级索引逻辑。

    Attributes:
        _cache: 语义缓存端口实例
    """

    def __init__(self, cache: SemanticCache) -> None:
        """初始化缓存失效处理器

        Args:
            cache: 语义缓存端口实例（用于执行缓存失效操作）
        """
        self._cache = cache

    async def handle(self, event: DomainEvent) -> None:
        """处理 DocumentProcessed 事件，触发缓存失效

        调用 SemanticCache.invalidate_by_document_id() 端口方法，
        通过二级索引精确失效受影响的缓存条目。
        失效失败仅记录 WARNING 日志，不抛出异常。

        Args:
            event: 领域事件实例
        """
        # 仅处理 DocumentProcessed 事件
        if event.event_type != "DocumentProcessed":
            return

        # 提取 document_id
        doc_id = getattr(event, "document_id", None)
        if doc_id is None:
            logger.warning("DocumentProcessed 事件缺少 document_id 字段，跳过缓存失效")
            return

        doc_id_str = str(doc_id)

        try:
            await self._cache.invalidate_by_document_id(doc_id_str)
            logger.debug("缓存失效成功: document_id=%s", doc_id_str)
        except Exception:
            logger.warning("缓存失效失败（不影响主流程）: document_id=%s", doc_id_str, exc_info=True)
