"""PublicBlackboard Protocol type checking tests."""

from __future__ import annotations

import inspect

from src.application.ports.public_blackboard import PublicBlackboard


class TestPublicBlackboardInterface:
    """PublicBlackboard Protocol 接口测试。"""

    def test_protocol_has_required_methods(self) -> None:
        """PublicBlackboard 应定义所有必需的抽象方法。"""
        assert hasattr(PublicBlackboard, "post")
        assert hasattr(PublicBlackboard, "get")
        assert hasattr(PublicBlackboard, "get_by_agent")
        assert hasattr(PublicBlackboard, "get_latest")

    def test_post_signature(self) -> None:
        """post 方法应有正确的签名。"""
        sig = inspect.signature(PublicBlackboard.post)
        params = list(sig.parameters.keys())
        assert "conversation_id" in params
        assert "agent_id" in params
        assert "content" in params
        assert "confidence" in params
        assert "citations" in params

    def test_get_signature(self) -> None:
        """get 方法应有正确的签名。"""
        sig = inspect.signature(PublicBlackboard.get)
        params = list(sig.parameters.keys())
        assert "conversation_id" in params

    def test_get_by_agent_signature(self) -> None:
        """get_by_agent 方法应有正确的签名。"""
        sig = inspect.signature(PublicBlackboard.get_by_agent)
        params = list(sig.parameters.keys())
        assert "conversation_id" in params
        assert "agent_id" in params

    def test_get_latest_signature(self) -> None:
        """get_latest 方法应有正确的签名。"""
        sig = inspect.signature(PublicBlackboard.get_latest)
        params = list(sig.parameters.keys())
        assert "conversation_id" in params

    def test_protocol_is_protocol(self) -> None:
        """PublicBlackboard 应是 Protocol 类型。"""
        # Protocol classes have _is_protocol flag
        assert getattr(PublicBlackboard, "_is_protocol", False) is True
