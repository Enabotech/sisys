"""应用层档案事件处理器单元测试

验证 ArchiveValidityHandler 的注册模式和处理逻辑。
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.application.event_handlers.archive_handlers import ArchiveValidityHandler
from src.domain.entities.strategic_archive import ArchiveType
from src.domain.events.archive_events import FactBecameStale, ValidityPeriodSet
from src.domain.events.base import DomainEvent


def _make_listener() -> MagicMock:
    """创建 Mock 事件监听器（EventListener 端口）"""
    return MagicMock()


class TestArchiveValidityHandler:
    """ArchiveValidityHandler 事件处理器测试"""

    def test_register_handlers_subscribes_events(self) -> None:
        """register_handlers 注册 ValidityPeriodSet 和 FactBecameStale"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        handler.register_handlers()
        # on_event 触发两次：ValidityPeriodSet + FactBecameStale
        assert listener.on_event.call_count == 2
        event_types = [call.args[0] for call in listener.on_event.call_args_list]
        assert "ValidityPeriodSet" in event_types
        assert "FactBecameStale" in event_types

    def test_handle_validity_period_set_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """ValidityPeriodSet 事件处理记录日志"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        handler.register_handlers()
        # 直接调用处理逻辑
        event = ValidityPeriodSet(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            archive_type=ArchiveType.ASSUMPTION,
            valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            valid_until=datetime(2027, 12, 31, tzinfo=UTC),
        )
        with caplog.at_level(logging.INFO, logger="src.application.event_handlers.archive_handlers"):
            handler._handle_validity_period_set(event)
        assert "Validity period set for archive" in caplog.text

    def test_wrapped_callback_handles_validity_event(self) -> None:
        """包装回调正确处理 ValidityPeriodSet"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        handler.register_handlers()
        # 找到 ValidityPeriodSet 回调
        validity_cb = None
        for call in listener.on_event.call_args_list:
            if call.args[0] == "ValidityPeriodSet":
                validity_cb = call.args[1]
                break
        assert validity_cb is not None
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        # 应正常执行不抛异常
        validity_cb(event)

    def test_wrapped_callback_handles_fact_stale(self) -> None:
        """包装回调正确处理 FactBecameStale"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        handler.register_handlers()
        stale_cb = None
        for call in listener.on_event.call_args_list:
            if call.args[0] == "FactBecameStale":
                stale_cb = call.args[1]
                break
        assert stale_cb is not None
        event = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="expired")
        # 应正常执行不抛异常
        stale_cb(event)

    def test_wrapped_callback_swallows_unknown_event(self) -> None:
        """未知事件类型被安全忽略"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        handler.register_handlers()
        validity_cb = None
        for call in listener.on_event.call_args_list:
            if call.args[0] == "ValidityPeriodSet":
                validity_cb = call.args[1]
                break
        # 传入一个非预期类型的事件基类
        unknown = DomainEvent(event_type="UnknownEvent")
        assert validity_cb is not None
        validity_cb(unknown)  # 不应抛出

    def test_handle_fact_became_stale_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """FactBecameStale 事件处理记录日志"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        event = FactBecameStale(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            archive_type=ArchiveType.ASSUMPTION,
            valid_until=None,
            stale_reason="archived_too_long",
        )
        with caplog.at_level(logging.INFO, logger="src.application.event_handlers.archive_handlers"):
            handler._handle_fact_became_stale(event)
        assert "Fact became stale for archive" in caplog.text
        assert "archived_too_long" in caplog.text
