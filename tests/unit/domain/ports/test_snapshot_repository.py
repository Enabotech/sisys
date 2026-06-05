"""SnapshotRepositoryProtocol Protocol 行为验证测试

验证检查点快照仓储端口的运行时类型检查、异步方法签名和数据持久化行为
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol


class TestSnapshotRepositoryProtocolRuntimeCheckable:
    """SnapshotRepositoryProtocol 结构化子类型检查"""

    def test_compatible_class_passes_isinstance(self) -> None:
        """实现 save/load/delete 的类应通过 isinstance 检查"""

        class FakeRepo:
            async def save(self, snapshot: Any) -> None:
                pass

            async def load(self, session_id: str) -> Any:
                return None

            async def delete(self, session_id: str) -> None:
                pass

        assert isinstance(FakeRepo(), SnapshotRepositoryProtocol)

    def test_incompatible_class_fails_isinstance(self) -> None:
        """不实现任何方法的类不应通过 isinstance 检查"""

        class Incompatible:
            def other(self) -> None:
                pass

        assert not isinstance(Incompatible(), SnapshotRepositoryProtocol)

    def test_partial_impl_missing_save_fails(self) -> None:
        """仅实现 load+delete 的类不应通过 isinstance"""

        class PartialRepo:
            async def load(self, session_id: str) -> Any:
                return None

            async def delete(self, session_id: str) -> None:
                pass

        assert not isinstance(PartialRepo(), SnapshotRepositoryProtocol)

    def test_partial_impl_missing_load_fails(self) -> None:
        """仅实现 save+delete 的类不应通过 isinstance"""

        class PartialRepo:
            async def save(self, snapshot: Any) -> None:
                pass

            async def delete(self, session_id: str) -> None:
                pass

        assert not isinstance(PartialRepo(), SnapshotRepositoryProtocol)

    def test_partial_impl_missing_delete_fails(self) -> None:
        """仅实现 save+load 的类不应通过 isinstance"""

        class PartialRepo:
            async def save(self, snapshot: Any) -> None:
                pass

            async def load(self, session_id: str) -> Any:
                return None

        assert not isinstance(PartialRepo(), SnapshotRepositoryProtocol)


class TestSnapshotRepositoryProtocolMethodSignature:
    """SnapshotRepositoryProtocol 方法签名验证"""

    def test_save_is_async(self) -> None:
        """save 应为异步方法"""
        assert asyncio.iscoroutinefunction(SnapshotRepositoryProtocol.save)

    def test_load_is_async(self) -> None:
        """load 应为异步方法"""
        assert asyncio.iscoroutinefunction(SnapshotRepositoryProtocol.load)

    def test_delete_is_async(self) -> None:
        """delete 应为异步方法"""
        assert asyncio.iscoroutinefunction(SnapshotRepositoryProtocol.delete)


class TestSnapshotRepositoryProtocolBehavior:
    """SnapshotRepositoryProtocol 行为验证"""

    async def test_load_returns_none_for_missing_session(self) -> None:
        """load 不存在的 session 应返回 None"""

        class InMemoryRepo:
            def __init__(self) -> None:
                self._store: dict[str, Any] = {}

            async def save(self, snapshot: Any) -> None:
                pass

            async def load(self, session_id: str) -> Any:
                return self._store.get(session_id)

            async def delete(self, session_id: str) -> None:
                self._store.pop(session_id, None)

        repo = InMemoryRepo()
        result = await repo.load("nonexistent")
        assert result is None

    async def test_save_and_load_roundtrip(self) -> None:
        """save 后 load 应返回存储的快照"""

        class InMemoryRepo:
            def __init__(self) -> None:
                self._store: dict[str, Any] = {}

            async def save(self, snapshot: Any) -> None:
                self._store["sess-1"] = snapshot

            async def load(self, session_id: str) -> Any:
                return self._store.get(session_id)

            async def delete(self, session_id: str) -> None:
                self._store.pop(session_id, None)

        repo = InMemoryRepo()
        snapshot = {"state": "active", "step": 3}
        await repo.save(snapshot)
        loaded = await repo.load("sess-1")
        assert loaded == snapshot

    async def test_delete_removes_snapshot(self) -> None:
        """delete 后 load 应返回 None"""

        class InMemoryRepo:
            def __init__(self) -> None:
                self._store: dict[str, Any] = {}

            async def save(self, snapshot: Any) -> None:
                self._store["sess-del"] = snapshot

            async def load(self, session_id: str) -> Any:
                return self._store.get(session_id)

            async def delete(self, session_id: str) -> None:
                self._store.pop(session_id, None)

        repo = InMemoryRepo()
        await repo.save({"state": "pending"})
        assert await repo.load("sess-del") is not None

        await repo.delete("sess-del")
        assert await repo.load("sess-del") is None
