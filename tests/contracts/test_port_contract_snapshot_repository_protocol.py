"""SnapshotRepositoryProtocol 端口契约测试

验证 SnapshotRepositoryProtocol 的结构化子类型合规性。
"""

from __future__ import annotations

import inspect

from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol


class TestSnapshotRepositoryProtocolContract:
    """测试 SnapshotRepositoryProtocol 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        """验证 Protocol 使用 @runtime_checkable 装饰器"""
        assert hasattr(SnapshotRepositoryProtocol, "_is_runtime_protocol")
        assert SnapshotRepositoryProtocol._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_save_method_exists(self) -> None:
        """验证 save 方法存在且为异步"""
        assert hasattr(SnapshotRepositoryProtocol, "save")
        method = getattr(SnapshotRepositoryProtocol, "save")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_load_method_exists(self) -> None:
        """验证 load 方法存在且为异步"""
        assert hasattr(SnapshotRepositoryProtocol, "load")
        method = getattr(SnapshotRepositoryProtocol, "load")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_delete_method_exists(self) -> None:
        """验证 delete 方法存在且为异步"""
        assert hasattr(SnapshotRepositoryProtocol, "delete")
        method = getattr(SnapshotRepositoryProtocol, "delete")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_compliant_implementation(self) -> None:
        """验证合规实现可通过 isinstance 检查"""

        class MockRepo:
            async def save(self, snapshot) -> None:
                pass

            async def load(self, session_id: str):
                return None

            async def delete(self, session_id: str) -> None:
                pass

        repo = MockRepo()
        assert isinstance(repo, SnapshotRepositoryProtocol)

    def test_noncompliant_implementation_fails(self) -> None:
        """验证不合规实现无法通过 isinstance 检查"""

        class BadRepo:
            pass

        assert not isinstance(BadRepo(), SnapshotRepositoryProtocol)


__all__ = ["TestSnapshotRepositoryProtocolContract"]
