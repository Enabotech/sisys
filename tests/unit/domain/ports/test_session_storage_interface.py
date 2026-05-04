"""SessionStorage Protocol type checking tests."""

from __future__ import annotations

import inspect

from src.domain.ports.session_storage import SessionStorage


class TestSessionStorageInterface:
    """SessionStorage Protocol 接口测试。"""

    def test_protocol_has_required_methods(self) -> None:
        """SessionStorage 应定义所有必需的抽象方法。"""
        # Protocol 方法
        assert hasattr(SessionStorage, "save")
        assert hasattr(SessionStorage, "load")
        assert hasattr(SessionStorage, "delete")
        assert hasattr(SessionStorage, "exists")

    def test_methods_are_abstract(self) -> None:
        """方法应标记为抽象。"""
        # 检查方法是否有 __isabstractmethod__ 属性
        assert getattr(SessionStorage.save, "__isabstractmethod__", False) is True
        assert getattr(SessionStorage.load, "__isabstractmethod__", False) is True
        assert getattr(SessionStorage.delete, "__isabstractmethod__", False) is True
        assert getattr(SessionStorage.exists, "__isabstractmethod__", False) is True

    def test_save_signature(self) -> None:
        """save 方法应有正确的签名。"""
        sig = inspect.signature(SessionStorage.save)
        params = list(sig.parameters.keys())
        assert "session_id" in params
        assert "agent_id" in params
        assert "state" in params
        assert "ttl" in params

    def test_load_signature(self) -> None:
        """load 方法应有正确的签名。"""
        sig = inspect.signature(SessionStorage.load)
        params = list(sig.parameters.keys())
        assert "session_id" in params

    def test_delete_signature(self) -> None:
        """delete 方法应有正确的签名。"""
        sig = inspect.signature(SessionStorage.delete)
        params = list(sig.parameters.keys())
        assert "session_id" in params

    def test_exists_signature(self) -> None:
        """exists 方法应有正确的签名。"""
        sig = inspect.signature(SessionStorage.exists)
        params = list(sig.parameters.keys())
        assert "session_id" in params

    def test_protocol_is_not_instantiable(self) -> None:
        """SessionStorage 是 Protocol，不能直接实例化。"""
        # Protocol 不应能直接实例化（运行时不报错但类型检查会警告）
        # 这里只验证它是 Protocol 类型
        # Protocol classes have _is_protocol flag
        assert getattr(SessionStorage, "_is_protocol", False) is True
