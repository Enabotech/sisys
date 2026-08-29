"""event_exceptions 单元测试。

验证 EventPublishError 和 VersionError 的构造、编码、上下文传递和继承链。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import ConflictError
from src.domain.exceptions.event_exceptions import EventPublishError, VersionError
from src.domain.exceptions.system_exceptions import MessageBusError


class TestEventPublishError:
    """EventPublishError 测试套件。"""

    def test_default_message(self) -> None:
        """无 message 时使用默认模板。"""
        exc = EventPublishError(event_type="DocumentProcessed")
        assert "DocumentProcessed" in str(exc)
        assert exc.code == "EXCEPTION_107"

    def test_custom_message(self) -> None:
        """自定义 message 覆盖默认。"""
        exc = EventPublishError(event_type="TestEvent", message="custom msg")
        assert str(exc) == "custom msg"

    def test_context_includes_event_type(self) -> None:
        """上下文应包含 event_type。"""
        exc = EventPublishError(event_type="TestEvent", context={"extra": 1})
        assert exc.context["event_type"] == "TestEvent"
        assert exc.context["extra"] == 1

    def test_cause_is_stored_in_context(self) -> None:
        """cause 异常应被保存到上下文中。"""
        cause = ValueError("boom")
        exc = EventPublishError(event_type="X", context={"root_cause": cause})
        assert exc.context["root_cause"] is cause

    def test_inherits_message_bus_error(self) -> None:
        """应继承 MessageBusError。"""
        assert issubclass(EventPublishError, MessageBusError)


class TestVersionError:
    """VersionError 测试套件。"""

    def test_code_and_message(self) -> None:
        """版本冲突异常应有固定编码。"""
        exc = VersionError()
        assert exc.code == "EXCEPTION_251"

    def test_inherits_conflict_error(self) -> None:
        """应继承 ConflictError。"""
        assert issubclass(VersionError, ConflictError)
