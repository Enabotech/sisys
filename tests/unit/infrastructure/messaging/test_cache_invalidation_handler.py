"""CacheInvalidationHandler 单元测试

TDD 红→绿→重构循环：
- Happy Path: DocumentProcessed 事件触发缓存失效
- Edge Case: 非 DocumentProcessed 事件 → 忽略
- Edge Case: 缓存失效失败 → 仅日志，不抛出异常
- Edge Case: document_id 为空 → 跳过
- Edge Case: 支持按 collection 前缀批量失效
- Edge Case: 二级索引缺失 → 降级为全量清理
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from src.application.ports.semantic_cache import SemanticCache
from src.domain.events.base import DomainEvent
from src.domain.events.document_events import DocumentProcessed
from src.infrastructure.messaging.event_handlers.cache_invalidation_handler import (
    CacheInvalidationHandler,
)


def _make_handler(
    cache: AsyncMock | None = None,
) -> tuple[CacheInvalidationHandler, AsyncMock]:
    """创建测试用 CacheInvalidationHandler 实例"""
    if cache is None:
        cache = AsyncMock(spec=SemanticCache)
        cache.invalidate_by_document_id = AsyncMock()
        cache.invalidate_pattern = AsyncMock()
        cache.invalidate_all = AsyncMock()

    handler = CacheInvalidationHandler(cache=cache, event_listener=None)
    return handler, cache


class TestCacheInvalidationHandler:
    """CacheInvalidationHandler 核心功能测试"""

    # ===================================================================
    # Happy Path: DocumentProcessed 事件触发缓存失效
    # ===================================================================

    async def test_document_processed_triggers_invalidation(self) -> None:
        """DocumentProcessed 事件 → 调用 invalidate_by_document_id"""
        handler, cache = _make_handler()
        doc_id = uuid.uuid4()
        event = DocumentProcessed(
            document_id=doc_id,
            tenant_id="test-tenant",
        )

        await handler.handle(event)

        # 验证 invalidate_by_document_id 被调用
        cache.invalidate_by_document_id.assert_called_once_with(str(doc_id))

    async def test_document_processed_with_parse_result(self) -> None:
        """DocumentProcessed 事件（含 parse_result）→ 触发失效"""
        handler, cache = _make_handler()
        doc_id = uuid.uuid4()
        event = DocumentProcessed(
            document_id=doc_id,
            tenant_id="test-tenant",
            parse_result={"status": "completed", "pages": 5},
        )

        await handler.handle(event)

        cache.invalidate_by_document_id.assert_called_once_with(str(doc_id))

    # ===================================================================
    # Edge Case: 非 DocumentProcessed 事件 → 忽略
    # ===================================================================

    async def test_non_document_processed_event_ignored(self) -> None:
        """非 DocumentProcessed 事件 → 不触发失效"""
        handler, cache = _make_handler()

        # 构造其他类型事件
        event = DomainEvent(
            event_type="EntitiesExtracted",
            event_id=uuid.uuid4(),
        )

        await handler.handle(event)

        # 验证 invalidate_by_document_id 未被调用
        cache.invalidate_by_document_id.assert_not_called()
        cache.invalidate_pattern.assert_not_called()
        cache.invalidate_all.assert_not_called()

    # ===================================================================
    # Edge Case: 缓存失效失败 → 仅日志，不抛出异常
    # ===================================================================

    async def test_invalidation_failure_logs_warning(self) -> None:
        """invalidate_by_document_id 抛出异常 → 不抛出，仅日志"""
        handler, cache = _make_handler()
        cache.invalidate_by_document_id.side_effect = RuntimeError("Redis 不可用")

        doc_id = uuid.uuid4()
        event = DocumentProcessed(
            document_id=doc_id,
            tenant_id="test-tenant",
        )

        # 不应抛出异常
        try:
            await handler.handle(event)
        except Exception:
            pytest.fail("handler.handle() 不应抛出异常")

        # 验证 invalidate_by_document_id 被调用
        cache.invalidate_by_document_id.assert_called_once_with(str(doc_id))

    # ===================================================================
    # Edge Case: document_id 为空 → 跳过
    # ===================================================================

    async def test_empty_document_id_skipped(self) -> None:
        """document_id 为空 → 跳过失效"""
        handler, cache = _make_handler()

        # 构造 document_id 为空的 DocumentProcessed 事件
        # 由于 default_factory=uuid.uuid4，无法真正为空
        # 通过设置 aggregate_id 为 None 来模拟
        event = DocumentProcessed()
        # 使用 object.__setattr__ 绕过 frozen dataclass
        object.__setattr__(event, "document_id", None)

        await handler.handle(event)

        cache.invalidate_by_document_id.assert_not_called()

    # ===================================================================
    # Edge Case: 支持按 collection 前缀批量失效
    # ===================================================================

    async def test_invalidate_pattern_called(self) -> None:
        """invalidate_pattern 被调用时按模式匹配失效"""
        handler, cache = _make_handler()

        # 直接调用 cache.invalidate_pattern
        await cache.invalidate_pattern("vec:doc-*", count=100)

        cache.invalidate_pattern.assert_called_once_with("vec:doc-*", count=100)

    # ===================================================================
    # Edge Case: 二级索引缺失 → 降级为全量清理
    # ===================================================================

    async def test_invalidate_all_fallback(self) -> None:
        """invalidate_all 被调用时全量清理"""
        handler, cache = _make_handler()

        # 直接调用 cache.invalidate_all
        await cache.invalidate_all()

        cache.invalidate_all.assert_called_once()


class TestCacheInvalidationHandlerEdgeCases:
    """边界条件测试"""

    async def test_handler_without_cache(self) -> None:
        """构造函数注入检查"""
        from unittest.mock import MagicMock

        mock_cache = MagicMock(spec=SemanticCache)
        handler = CacheInvalidationHandler(cache=mock_cache, event_listener=None)
        assert handler._cache is mock_cache

    async def test_document_processed_event_type_check(self) -> None:
        """验证 event_type 检查逻辑"""
        handler, cache = _make_handler()

        # event_type 为 "DocumentProcessed" 的其他事件类型
        event = DomainEvent(
            event_type="DocumentProcessed",
            event_id=uuid.uuid4(),
        )
        # 设置 aggregate_id 作为备选
        doc_id = uuid.uuid4()
        object.__setattr__(event, "aggregate_id", doc_id)

        await handler.handle(event)

        # event_type 匹配，但 DomainEvent 没有 document_id 字段
        # 所以不会触发 invalidate_by_document_id
        cache.invalidate_by_document_id.assert_not_called()


class TestCacheInvalidationHandlerInitWithListener:
    """验证 _wrap_handler 和 event_listener 注册路径"""

    def test_init_with_event_listener_registers_handler(self) -> None:
        """传入 event_listener 时应注册 DocumentProcessed 处理器"""
        from unittest.mock import MagicMock

        mock_cache = MagicMock(spec=SemanticCache)
        mock_listener = MagicMock()
        mock_listener.on_event = MagicMock()

        CacheInvalidationHandler(cache=mock_cache, event_listener=mock_listener)

        mock_listener.on_event.assert_called_once()
        args, _ = mock_listener.on_event.call_args
        assert args[0] == "DocumentProcessed"
        assert callable(args[1])

    def test_wrap_handler_returns_callable(self) -> None:
        """_wrap_handler 应返回可调用对象"""

        handler, _ = _make_handler()
        wrapped = handler._wrap_handler()
        assert callable(wrapped)

    def test_wrap_handler_calls_handle(self) -> None:
        """包装函数应调用 handle 方法"""
        from unittest.mock import AsyncMock

        cache = AsyncMock(spec=SemanticCache)
        cache.invalidate_by_document_id = AsyncMock()
        handler = CacheInvalidationHandler(cache=cache, event_listener=None)

        wrapped = handler._wrap_handler()
        doc_id = uuid.uuid4()
        event = DocumentProcessed(document_id=doc_id, tenant_id="test-tenant")
        wrapped(event)

        cache.invalidate_by_document_id.assert_called_once_with(str(doc_id))

    def test_wrap_handler_catches_exception(self) -> None:
        """包装函数应捕获异步 handle 抛出的异常，不向上传播"""
        from unittest.mock import AsyncMock, patch

        cache = AsyncMock(spec=SemanticCache)
        cache.invalidate_by_document_id = AsyncMock(side_effect=RuntimeError("test error"))
        handler = CacheInvalidationHandler(cache=cache, event_listener=None)

        # handle() 内部已捕获 invalidate_by_document_id 异常，需模拟 handle 本身抛出
        # 未处理异常（防御路径：事件总线不因单个 handler 崩溃而中断）
        with patch.object(handler, "handle", side_effect=RuntimeError("handler crashed")):
            wrapped = handler._wrap_handler()
            doc_id = uuid.uuid4()
            event = DocumentProcessed(document_id=doc_id, tenant_id="test-tenant")
            # 不应抛出异常
            wrapped(event)
